/* Native browser UI; exported decisions also run under Node in CI. */
(function (root) {
  "use strict";
  const state = {snapshot: null, selected: null, worker: null, fresh: false, at: 0};
  function controls(s, now = Date.now()) {
    const usable = s.fresh && s.snapshot && now - s.at < 6000 && s.snapshot.mode !== "cancelled";
    return {pause: Boolean(usable && s.snapshot.mode === "running"), resume: Boolean(usable && s.snapshot.mode === "paused"), cancel: Boolean(usable)};
  }
  function count(value) { return Number.isFinite(value) && value >= 0 ? String(value) : "unknown"; }
  function seconds(value) { return Number.isFinite(value) && value >= 0 ? `${Number(value.toFixed(1))} s` : "unknown"; }
  function fields(value, labels, format = count) {
    return Object.entries(labels).map(([key, label]) => `${label}: ${format(value?.[key])}`).join(" · ");
  }
  function select(s, snapshot) {
    s.snapshot = snapshot;
    if (!snapshot.issues.some(i => i.issue === s.selected)) s.selected = snapshot.issues[0]?.issue ?? null;
    const issue = snapshot.issues.find(i => i.issue === s.selected);
    if (!issue?.workers.some(w => w.worker === s.worker)) s.worker = null;
    return issue;
  }
  function text(doc, tag, value) {
    const el = doc.createElement(tag);
    el.textContent = value == null ? "unknown" : String(value);
    return el;
  }
  if (typeof module !== "undefined") module.exports = {controls, select, text};
  if (!root.document) return;
  const doc = root.document;
  const byId = id => doc.getElementById(id);
  let csrf = null;
  function updateControls() {
    if (state.fresh && Date.now() - state.at >= 6000) {
      state.fresh = false;
      byId("connection").textContent = "Disconnected or delayed · last observation is stale · return to main conversation";
    }
    const allowed = controls(state);
    for (const id of ["pause", "resume", "cancel"]) byId(id).disabled = !allowed[id];
  }
  function paragraph(parent, value) { parent.append(text(doc, "p", value)); }
  function render(snapshot) {
    const issue = select(state, snapshot);
    byId("context").textContent = `${snapshot.repository} · Queue ${snapshot.queue.slice(0, 8)} · ${snapshot.mode}`;
    byId("queue-id").textContent = `Complete queue ID: ${snapshot.queue}`;
    byId("capacity").textContent = `Clone-wide capacity used — ${fields(snapshot.clone_wide_used, {issues: "Issues", workers: "Workers", backlog: "PR backlog"})}. Selected queue limits — ${fields(snapshot.limits, {issues: "Issues", workers: "Workers", backlog: "PR backlog", attempts: "Attempts"})} · Time budget: ${seconds(snapshot.limits?.seconds)}. Quota: ${snapshot.quota?.state ?? "unknown"} · Retry at: ${snapshot.quota?.retry_at == null ? "unknown" : new Date(snapshot.quota.retry_at * 1000).toISOString()}`;
    byId("dependencies").textContent = `Dependency source: ${snapshot.dependencies.status} · observed ${snapshot.dependencies.at ?? "unknown"}`;
    byId("control-history").textContent = `Recorded controls: ${snapshot.controls.map(c => `${c.event} ${c.at ?? "unknown"}`).join("; ") || "none"}`;
    const rows = byId("issues"); rows.replaceChildren();
    for (const item of snapshot.issues) {
      const row = doc.createElement("tr"), cell = doc.createElement("td");
      const button = text(doc, "button", `#${item.issue}`);
      button.addEventListener("click", () => {state.selected = item.issue; state.worker = null; render(snapshot);});
      cell.append(button); row.append(cell, text(doc, "td", item.activity), text(doc, "td", item.readiness)); rows.append(row);
    }
    const detail = byId("detail"); detail.replaceChildren();
    if (issue) {
      paragraph(detail, `Issue #${issue.issue} · attempt ${issue.attempt ?? "unknown"} · ${issue.activity}`);
      paragraph(detail, `Dependency/capacity wait: ${snapshot.dependencies.issues?.[String(issue.issue)] ?? "unknown"}`);
      const reasons = snapshot.dependencies.reasons?.[String(issue.issue)] ?? [];
      for (const reason of reasons) paragraph(detail, `Recorded dependency reason: ${reason}`);
      paragraph(detail, `Recorded timing — Elapsed: ${seconds(issue.timing?.elapsed)} · ${fields(issue.timing?.phases, {implement: "Implementation", review: "Review", worker_setup: "Worker setup", human_review_wait: "Human review wait", coordinator: "Coordinator"}, seconds)}`);
      paragraph(detail, `Review worker rounds: ${issue.review_rounds ?? "unknown"} · Rework: ${issue.rework ?? "unknown"}`);
      for (const kind of ["phase", "plan", "question", "decision", "check", "review", "readiness"]) {
        const entries = issue.evidence.filter(e => e.kind === kind);
        if (!entries.length) paragraph(detail, `${kind}: unknown — no recorded evidence`);
        for (const e of entries) {
          const p = text(doc, "p", `${kind}: ${e.state} · ${e.summary} · ${e.source} · revision freshness ${e.freshness} · ${e.at ?? "unknown"}${e.round ? ` · round ${e.round}` : ""}`);
          p.className = "evidence"; detail.append(p);
          // Server already validates links; repeat selected-repository boundary in DOM.
          if (e.reference && safeLink(e.reference, snapshot.repository)) {
            const a = text(doc, "a", "Evidence reference"); a.href = e.reference; a.rel = "noreferrer"; detail.append(a);
          }
        }
      }
      if (issue.pr && safeLink(issue.pr, snapshot.repository)) {const a = text(doc, "a", "Recorded PR"); a.href = issue.pr; detail.append(a);}
      else paragraph(detail, "PR: unknown — no recorded link");
      for (const worker of issue.workers) {
        const b = text(doc, "button", `${worker.role} · ${worker.status} · ${worker.worker}`);
        b.addEventListener("click", () => {state.worker = worker.worker; render(snapshot);}); detail.append(b);
      }
    }
    const panel = byId("worker"); panel.replaceChildren();
    const worker = issue?.workers.find(w => w.worker === state.worker);
    if (worker) {
      paragraph(panel, `Recorded worker outcome: ${worker.status}. Completion alone establishes no accepted review, checks or PR readiness.`);
      const table = doc.createElement("table");
      const head = doc.createElement("tr"); for (const title of ["Setting", "Requested", "Observed"]) head.append(text(doc, "th", title)); table.append(head);
      for (const key of ["provider", "model", "effort"]) {const row = doc.createElement("tr"); for (const v of [key, worker.requested[key], worker.observed[key]]) row.append(text(doc, "td", v)); table.append(row);} panel.append(table);
      paragraph(panel, `Verification source: ${worker.source ?? "unknown"} · Session: ${worker.session ?? "unknown"}`);
      paragraph(panel, `Timing — ${fields(worker.timing, {setup: "Setup", running: "Running"}, seconds)}`);
      const usageLabels = {totalTokens: "Total tokens", inputTokens: "Input tokens", cachedInputTokens: "Cached input tokens", cacheWriteInputTokens: "Cache write input tokens", outputTokens: "Output tokens", reasoningOutputTokens: "Reasoning output tokens"};
      const available = Object.fromEntries(Object.entries(usageLabels).filter(([key]) => worker.tokens?.[key] != null));
      paragraph(panel, `Usage — ${Object.keys(available).length ? fields(worker.tokens, available) : "unknown"}`);
      for (const m of worker.milestones) paragraph(panel, `${m.event} · ${m.at ?? "unknown"}`);
    } else paragraph(panel, "Select a worker. Missing outcomes and receipts remain unknown.");
    updateControls();
  }
  function safeLink(value, repo) {
    try {const u = new URL(value); return u.origin === "https://github.com" && u.pathname.startsWith(`/${repo}/`) && !u.username && !u.password;} catch {return false;}
  }
  async function request(path, body) {
    const response = await fetch(path, {method: body ? "POST" : "GET", cache: "no-store", signal: AbortSignal.timeout(4500), headers: body ? {"Content-Type": "application/json", "X-Ballast-CSRF": csrf ?? ""} : {}, body: body ? JSON.stringify(body) : undefined});
    if (!response.ok) throw new Error("Unavailable"); return response.json();
  }
  async function poll() {
    try {const snapshot = await request("/api/snapshot"); state.fresh = true; state.at = Date.now(); render(snapshot); byId("connection").textContent = `Connected · observed ${snapshot.at} · coordinator liveness unknown`;}
    catch {state.fresh = false; byId("connection").textContent = "Disconnected or context unavailable · last observation is stale · return to main conversation"; updateControls();}
    setTimeout(poll, 2000);
  }
  for (const [id, action] of [["pause", "paused"], ["resume", "running"], ["cancel", "cancelled"]]) {
    byId(id).addEventListener("click", async () => {
      if (!controls(state)[id]) return;
      if (id === "cancel" && !root.confirm("Request cancellation? Active workers may remain unknown; this does not release ownership.")) return;
      state.fresh = false; byId("connection").textContent = "Control requested · last observation is stale · awaiting new snapshot"; updateControls();
      try {await request("/api/control", {action});} catch {byId("connection").textContent = "Control outcome unknown. Observe before acting again; no automatic replay.";}
    });
  }
  const capability = root.location.hash.slice(1);
  root.history.replaceState(null, "", "/");
  // Store only the CSRF token; the session credential stays HttpOnly. Reloads observe.
  csrf = root.sessionStorage.getItem("ballast-csrf");
  (async () => {
    if (capability) {try {const session = await request("/api/session", {capability}); csrf = session.csrf; root.sessionStorage.setItem("ballast-csrf", csrf);} catch {byId("connection").textContent = "Authorization failed. Reopen the capability URL from the main conversation."; return;}}
    poll();
  })();
  setInterval(updateControls, 1000);
})(globalThis);
