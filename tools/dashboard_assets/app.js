/* Native browser UI; exported decisions also run under Node in CI. */
(function (root) {
  "use strict";
  const state = {snapshot: null, selected: null, worker: null, fresh: false, at: 0};
  const kinds = ["phase", "plan", "question", "decision", "check", "review", "readiness"];
  const activityLabels = {active: "Running", pr_wait: "PR wait", merged: "Merged", stopped: "Stopped", unclaimed: "Unclaimed", unknown: "Unknown"};
  const modeLabels = {running: "Running", paused: "Paused", cancelled: "Cancelled", quota_paused: "Quota paused"};
  function controls(s, now = Date.now()) {
    const usable = s.fresh && s.snapshot && now - s.at < 6000 && s.snapshot.mode !== "cancelled";
    return {pause: Boolean(usable && s.snapshot.mode === "running"), resume: Boolean(usable && s.snapshot.mode === "paused"), cancel: Boolean(usable)};
  }
  function count(value) { return Number.isFinite(value) && value >= 0 ? String(value) : "unknown"; }
  function seconds(value) { return Number.isFinite(value) && value >= 0 ? `${Number(value.toFixed(1))} s` : "unknown"; }
  function select(s, snapshot) {
    s.snapshot = snapshot;
    if (!snapshot.issues.some(i => i.issue === s.selected)) s.selected = snapshot.issues[0]?.issue ?? null;
    const issue = snapshot.issues.find(i => i.issue === s.selected);
    if (!issue?.workers.some(w => w.worker === s.worker)) s.worker = null;
    return issue;
  }
  function text(doc, tag, value) {const el = doc.createElement(tag); el.textContent = value == null ? "unknown" : String(value); return el;}
  function relative(value, now = Date.now()) {
    const ms = typeof value === "number" ? value * 1000 : Date.parse(value);
    if (!Number.isFinite(ms)) return "unknown";
    if (ms > now) {
      const diff = Math.ceil((ms - now) / 1000);
      return diff < 3600 ? `in ${Math.ceil(diff / 60)} min` : diff < 86400 ? `in ${Math.ceil(diff / 3600)} h` : `in ${Math.ceil(diff / 86400)} d`;
    }
    const diff = Math.floor((now - ms) / 1000);
    return diff < 60 ? "just now" : diff < 3600 ? `${Math.floor(diff / 60)} min ago` : diff < 86400 ? `${Math.floor(diff / 3600)} h ago` : `${Math.floor(diff / 86400)} d ago`;
  }
  function absent(evidence) {return kinds.filter(kind => !evidence.some(e => e.kind === kind));}
  function attention(issue, dependencies) {
    const records = [], answered = new Set(), latest = new Set();
    for (const e of [...(issue.evidence ?? [])].reverse()) {
      if (e.kind === "question") {
        if (e.state === "pending" && (!e.reference || !answered.has(e.reference))) records.push(e);
        if (e.state === "answered" && e.reference) answered.add(e.reference);
      } else if (["phase", "plan", "review", "readiness"].includes(e.kind)) {
        if (!latest.has(e.kind) && e.state === "blocked") records.push(e);
        latest.add(e.kind);
      }
    }
    return {records: records.reverse(), reasons: dependencies.reasons?.[String(issue.issue)] ?? []};
  }
  function safeLink(value, repo) {
    try {const u = new URL(value); return u.origin === "https://github.com" && u.pathname.startsWith(`/${repo}/`) && !u.username && !u.password;} catch {return false;}
  }
  if (typeof module !== "undefined") module.exports = {controls, select, text, relative, absent, attention, safeLink};
  if (!root.document) return;
  const doc = root.document, byId = id => doc.getElementById(id);
  let csrf = null;
  // Stable keys keep focused buttons and links mounted during polling.
  function put(parent, key, tag, value, className = "") {
    let el = Array.from(parent.children).find(child => child.dataset.key === key);
    if (!el) {el = doc.createElement(tag); el.dataset.key = key; parent.append(el);}
    if (value !== undefined && el.textContent !== String(value)) el.textContent = value == null ? "unknown" : String(value);
    el.className = className;
    return el;
  }
  function trim(parent, keys) {
    for (const child of Array.from(parent.children)) if (!keys.includes(child.dataset.key)) child.remove();
    keys.forEach((key, index) => {
      const child = Array.from(parent.children).find(el => el.dataset.key === key);
      if (parent.children[index] !== child) parent.insertBefore(child, parent.children[index] ?? null);
    });
  }
  function time(parent, key, value) {
    const el = put(parent, key, "time", relative(value));
    const ms = typeof value === "number" ? value * 1000 : Date.parse(value);
    if (Number.isFinite(ms)) {el.dateTime = new Date(ms).toISOString(); el.title = el.dateTime;}
    else {el.removeAttribute("datetime"); el.removeAttribute("title");}
    return el;
  }
  function link(parent, key, label, url, repository) {
    if (!url || !safeLink(url, repository)) return false;
    const el = put(parent, key, "a", label); el.href = url; el.rel = "noreferrer"; return true;
  }
  function connection(label, kind) {const el = byId("connection"); el.textContent = label; el.dataset.state = kind;}
  function observation(kind) {
    const stateLabel = kind === "Disconnected" ? "disconnected" : kind.toLowerCase();
    const value = state.snapshot?.at;
    const ms = typeof value === "number" ? value * 1000 : Date.parse(value);
    const label = value == null || !Number.isFinite(ms) ? "unknown" : relative(value);
    connection(`${kind} · last observation ${label}`, stateLabel);
    const el = byId("connection");
    if (Number.isFinite(ms)) el.title = new Date(ms).toISOString();
    else {el.removeAttribute("title"); delete el.title;}
  }
  function updateControls() {
    if (state.fresh && Date.now() - state.at >= 6000) {state.fresh = false; observation("Stale");}
    const allowed = controls(state);
    for (const id of ["pause", "resume", "cancel"]) byId(id).disabled = !allowed[id];
  }
  function renderSummary(snapshot) {
    const cap = byId("capacity");
    put(cap, "heading", "h2", "Capacity · clone-wide used / queue limit");
    for (const [label, key] of [["Issues", "issues"], ["Workers", "workers"], ["PR backlog", "backlog"]]) put(cap, key, "p", `${label}: ${count(snapshot.clone_wide_used?.[key])} / ${count(snapshot.limits?.[key])}`);
    put(cap, "attempts", "p", `Attempts: ${count(snapshot.limits?.attempts)}`);
    put(cap, "budget", "p", `Time budget: ${seconds(snapshot.limits?.seconds)}`);
    put(cap, "quota", "p", `Quota: ${snapshot.quota?.state ?? "unknown"}`);
    const retry = put(cap, "retry", "p"); put(retry, "label", "span", "Retry at: "); time(retry, "when", snapshot.quota?.retry_at);
    const deps = byId("dependencies"); put(deps, "heading", "h2", "Dependencies");
    put(deps, "source", "p", `Source: ${snapshot.dependencies.status ?? "unknown"}`);
    const observed = put(deps, "observed", "p"); put(observed, "label", "span", "Observed: "); time(observed, "when", snapshot.dependencies.at);
    const history = byId("control-history"); put(history, "heading", "h2", "Control history");
    const keys = ["heading"];
    for (const [i, control] of snapshot.controls.entries()) {const key = `control-${i}`; keys.push(key); const row = put(history, key, "p"); put(row, "label", "span", `${control.event} · `); time(row, "when", control.at);}
    if (!snapshot.controls.length) {put(history, "none", "p", "None recorded"); keys.push("none");}
    trim(history, keys);
  }
  function renderIssues(snapshot) {
    const parent = byId("issues"), keys = [];
    for (const item of snapshot.issues) {
      const key = String(item.issue); keys.push(key);
      const row = put(parent, key, "tr"); row.className = item.issue === state.selected ? "selected" : "";
      const issueCell = put(row, "issue", "td");
      const button = put(issueCell, "select", "button", `#${item.issue}${item.title ? ` · ${item.title}` : ""}`, "issue-button");
      button.setAttribute("aria-current", item.issue === state.selected ? "true" : "false");
      button.onclick = () => {state.selected = item.issue; state.worker = null; render(state.snapshot);};
      const flagged = attention(item, snapshot.dependencies);
      if (flagged.records.length || flagged.reasons.length) put(issueCell, "attention", "span", "Needs you", "attention-marker");
      else trim(issueCell, ["select"]);
      put(put(row, "activity", "td"), "badge", "span", activityLabels[item.activity] ?? "Unknown", `status ${item.activity ?? "unknown"}`);
      put(put(row, "readiness", "td"), "badge", "span", item.readiness ?? "unknown", `readiness ${item.readiness ?? "unknown"}`);
    }
    trim(parent, keys);
  }
  function renderAttention(issue, snapshot) {
    const parent = byId("attention"), keys = [];
    if (!issue) {byId("attention-box").className = "attention quiet"; put(parent, "none", "p", "Select an issue."); trim(parent, ["none"]); return;}
    const flagged = attention(issue, snapshot.dependencies);
    for (const [i, e] of flagged.records.entries()) {
      const key = `e-${i}`; keys.push(key); const box = put(parent, key, "div", undefined, "attention-item");
      put(box, "text", "p", `${e.kind}: ${e.state} · ${e.summary} · freshness ${e.freshness ?? "unknown"}`);
      const childKeys = ["text"];
      if (link(box, "ref", "Open reference in main conversation", e.reference, snapshot.repository)) childKeys.push("ref");
      else {put(box, "missing", "p", "Reference: unknown — no recorded link"); childKeys.push("missing");}
      trim(box, childKeys);
    }
    for (const [i, reason] of flagged.reasons.entries()) {const key = `reason-${i}`; keys.push(key); put(parent, key, "p", `Dependency blocker: ${reason} · reference: unknown`, "attention-item");}
    byId("attention-box").className = keys.length ? "attention" : "attention quiet";
    if (!keys.length) {put(parent, "none", "p", "No recorded pending questions or blockers."); keys.push("none");}
    trim(parent, keys);
  }
  function renderDetail(issue, snapshot) {
    const parent = byId("detail"), keys = [];
    if (!issue) {put(parent, "none", "p", "Select an issue."); trim(parent, ["none"]); renderAttention(null, snapshot); return;}
    put(parent, "heading", "h3", `Issue #${issue.issue}${issue.title ? ` · ${issue.title}` : ""}`); keys.push("heading");
    put(parent, "state", "p", `Activity: ${activityLabels[issue.activity] ?? "Unknown"} · PR readiness: ${issue.readiness ?? "unknown"} · attempt: ${issue.attempt ?? "unknown"}`); keys.push("state");
    put(parent, "wait", "p", `Dependency/capacity wait: ${snapshot.dependencies.issues?.[String(issue.issue)] ?? "unknown"}`); keys.push("wait");
    if (issue.pr && link(parent, "pr", "Recorded PR", issue.pr, snapshot.repository)) keys.push("pr");
    else {put(parent, "pr-missing", "p", "PR: unknown — no recorded link"); keys.push("pr-missing");}
    const evidence = issue.evidence ?? [];
    if (evidence.length) {put(parent, "evidence-heading", "h4", "Recorded evidence"); keys.push("evidence-heading");}
    for (const [i, e] of evidence.entries()) {
      const key = `evidence-${i}`; keys.push(key); const box = put(parent, key, "div", undefined, "evidence");
      put(box, "text", "p", `${e.kind}: ${e.state} · ${e.summary} · ${e.source} · revision freshness ${e.freshness ?? "unknown"}${e.round ? ` · round ${e.round}` : ""}`);
      time(box, "time", e.at); const childKeys = ["text", "time"];
      if (link(box, "ref", "Evidence reference", e.reference, snapshot.repository)) childKeys.push("ref");
      trim(box, childKeys);
    }
    const missing = absent(evidence);
    if (missing.length) {put(parent, "absent", "p", `Not recorded: ${missing.join(", ")} (unknown)`, "muted"); keys.push("absent");}
    const timing = issue.timing ?? {}, phases = timing.phases ?? {};
    const labels = Object.entries({implement: "Implementation", review: "Review", worker_setup: "Worker setup", human_review_wait: "Human review wait", coordinator: "Coordinator"});
    const recorded = labels.filter(([key]) => phases[key] != null);
    put(parent, "timing", "p", `Elapsed: ${seconds(timing.elapsed)}${recorded.length ? ` · ${recorded.map(([key, label]) => `${label}: ${seconds(phases[key])}`).join(" · ")}` : ""}`, "muted"); keys.push("timing");
    const missingTiming = labels.filter(([key]) => phases[key] == null).map(([, label]) => label);
    if (missingTiming.length) {put(parent, "timing-missing", "p", `Phase timing not recorded: ${missingTiming.join(", ")}`, "muted"); keys.push("timing-missing");}
    put(parent, "rounds", "p", `Review worker rounds: ${count(issue.review_rounds)} · Rework: ${count(issue.rework)}`, "muted"); keys.push("rounds");
    trim(parent, keys); renderAttention(issue, snapshot);
  }
  function renderWorkers(issue) {
    const list = byId("worker-list"), keys = [];
    for (const worker of issue?.workers ?? []) {
      const key = worker.worker; keys.push(key);
      const button = put(list, key, "button", `${worker.role} · ${worker.status} · ${worker.executor === "coordinator" ? "coordinator" : "worker"}${worker.route_verified ? "" : " · unverified route"} · ${worker.worker}`);
      button.setAttribute("aria-pressed", state.worker === worker.worker ? "true" : "false");
      button.onclick = () => {state.worker = worker.worker; renderWorkers(issue);};
    }
    if (!keys.length) {put(list, "none", "p", "No workers recorded (unknown outcome)."); keys.push("none");}
    trim(list, keys);
    const panel = byId("worker"), worker = issue?.workers.find(w => w.worker === state.worker);
    if (!worker) {put(panel, "empty", "p", "Select a worker. Missing outcomes and receipts are unknown."); trim(panel, ["empty"]); return;}
    const panelKeys = ["outcome", "executor", "settings", "source", "timing", "usage"];
    put(panel, "outcome", "p", `Recorded worker outcome: ${worker.status}. Completion alone establishes no accepted review, green CI or PR readiness.`);
    put(panel, "executor", "p", `Executor: ${worker.executor === "coordinator" ? "coordinator" : "worker"} · Route: ${worker.route_verified ? "verified" : "unverified route (self-reported or missing receipt)"}${worker.verdict ? ` · Review verdict: ${worker.verdict}, round ${worker.round ?? "unknown"}` : ""}`);
    const table = put(panel, "settings", "table");
    for (const [i, values] of [["Setting", "Requested", "Observed"], ...["provider", "model", "effort"].map(key => [key, worker.requested?.[key] ?? "unknown", worker.observed?.[key] ?? "unknown"])].entries()) {
      const row = put(table, String(i), "tr"); values.forEach((value, j) => put(row, String(j), i ? "td" : "th", value));
    }
    put(panel, "source", "p", `Verification source: ${worker.source ?? "unknown"} · Session: ${worker.session ?? "unknown"}`);
    put(panel, "timing", "p", `Timing — Setup: ${seconds(worker.timing?.setup)} · Running: ${seconds(worker.timing?.running)}`);
    const labels = {totalTokens: "Total tokens", inputTokens: "Input tokens", cachedInputTokens: "Cached input tokens", cacheWriteInputTokens: "Cache write input tokens", outputTokens: "Output tokens", reasoningOutputTokens: "Reasoning output tokens"};
    const usage = Object.entries(labels).filter(([key]) => worker.tokens?.[key] != null).map(([key, label]) => `${label}: ${count(worker.tokens[key])}`);
    put(panel, "usage", "p", `Usage — ${usage.join(" · ") || "unknown"}`);
    for (const [i, milestone] of (worker.milestones ?? []).entries()) {const key = `milestone-${i}`; panelKeys.push(key); const row = put(panel, key, "p"); put(row, "label", "span", `${milestone.event} · `); time(row, "when", milestone.at);}
    trim(panel, panelKeys);
  }
  function render(snapshot) {
    const issue = select(state, snapshot);
    const label = `Queue ${snapshot.queue?.slice(0, 8) ?? "unknown"} · ${modeLabels[snapshot.mode] ?? "Unknown"}`;
    if (byId("context").textContent !== snapshot.repository) byId("context").textContent = snapshot.repository;
    if (byId("mode").textContent !== label) byId("mode").textContent = label;
    if (byId("queue-id").textContent !== snapshot.queue) byId("queue-id").textContent = snapshot.queue ?? "unknown";
    renderSummary(snapshot); renderIssues(snapshot); renderDetail(issue, snapshot); renderWorkers(issue); updateControls();
  }
  async function request(path, body) {
    const response = await fetch(path, {method: body ? "POST" : "GET", cache: "no-store", signal: AbortSignal.timeout(4500), headers: body ? {"Content-Type": "application/json", "X-Ballast-CSRF": csrf ?? ""} : {}, body: body ? JSON.stringify(body) : undefined});
    if (!response.ok) throw new Error("Unavailable"); return response.json();
  }
  async function poll() {
    try {const snapshot = await request("/api/snapshot"); state.fresh = true; state.at = Date.now(); render(snapshot); observation("Live");}
    catch {state.fresh = false; observation("Disconnected"); updateControls();}
    setTimeout(poll, 2000);
  }
  for (const [id, action] of [["pause", "paused"], ["resume", "running"], ["cancel", "cancelled"]]) {
    byId(id).addEventListener("click", async () => {
      if (!controls(state)[id]) return;
      if (id === "cancel" && !root.confirm("Request cancellation? Active workers may remain unknown; this does not release ownership.")) return;
      state.fresh = false; connection("Stale · control requested; awaiting observation", "stale"); updateControls();
      try {await request("/api/control", {action});} catch {connection("Stale · control outcome unknown; observe before acting again", "stale");}
    });
  }
  const capability = root.location.hash.slice(1);
  root.history.replaceState(null, "", "/");
  // Store only the CSRF token; the session credential stays HttpOnly. Reloads observe.
  csrf = root.sessionStorage.getItem("ballast-csrf");
  (async () => {
    if (capability) {try {const session = await request("/api/session", {capability}); csrf = session.csrf; root.sessionStorage.setItem("ballast-csrf", csrf);} catch {connection("Disconnected · authorization failed; reopen the capability URL", "disconnected"); return;}}
    poll();
  })();
  setInterval(updateControls, 1000);
})(globalThis);
