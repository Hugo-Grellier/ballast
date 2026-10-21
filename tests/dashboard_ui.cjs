"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const {controls, select, text, relative, absent, attention, safeLink} = require("../tools/dashboard_assets/app.js");
const base = {mode: "running", issues: [{issue: 1, workers: [{worker: "a"}]}, {issue: 2, workers: []}]};
const state = {fresh: true, at: 100, selected: 1, worker: "a", snapshot: base};
assert.deepEqual(controls(state, 101), {pause: true, resume: false, cancel: true});
assert.equal(controls(state, 7000).pause, false);
state.fresh = false; assert.equal(controls(state, 101).cancel, false);
state.fresh = true; base.mode = "cancelled";
assert.deepEqual(controls(state, 101), {pause: false, resume: false, cancel: false});
assert.equal(select(state, base).issue, 1); assert.equal(state.worker, "a");
state.selected = 2; select(state, base); assert.equal(state.worker, null);
select(state, {issues: [{issue: 3, workers: []}]}); assert.equal(state.selected, 3);
const element = {}, doc = {createElement: () => element};
assert.equal(text(doc, "p", "<script>hostile</script>").textContent, "<script>hostile</script>");
assert.equal(element.innerHTML, undefined);
text(doc, "p", null); assert.equal(element.textContent, "unknown");
assert.equal(relative("2026-01-01T00:00:00Z", Date.parse("2026-01-01T00:02:30Z")), "2 min ago");
assert.equal(relative("2026-01-01T01:00:00Z", Date.parse("2026-01-01T00:00:00Z")), "in 1 h");
assert.equal(relative(null), "unknown");
assert.deepEqual(absent([{kind: "question"}]), ["phase", "plan", "decision", "check", "review", "readiness"]);
assert.equal(attention({issue: 1, evidence: [{kind: "question", state: "pending"}]}, {reasons: {"1": ["blocked"]}}).records.length, 1);
const progress = [
  {kind: "question", state: "pending", reference: "question-1"},
  {kind: "phase", state: "blocked"},
  {kind: "question", state: "answered", reference: "question-1"},
  {kind: "phase", state: "completed"},
  {kind: "review", state: "blocked"},
  {kind: "review", state: "accepted"},
  {kind: "question", state: "pending", reference: "question-2"},
];
assert.deepEqual(attention({issue: 1, evidence: progress}, {reasons: {}}).records, [progress[6]]);
assert.equal(safeLink("https://github.com/example/fixture/issues/1", "example/fixture"), true);
assert.equal(safeLink("https://github.com/other/repo/issues/1", "example/fixture"), false);

class Element {
  constructor(tag) {this.tag = tag; this.children = []; this.dataset = {}; this.listeners = {}; this.attributes = {}; this.disabled = false; this._text = "";}
  get textContent() {return this._text + this.children.map(c => c.textContent).join("");}
  set textContent(value) {this._text = String(value); this.children = [];}
  append(...items) {for (const item of items) {if (item.parent) item.remove(); item.parent = this; this.children.push(item);}}
  insertBefore(item, next) {if (item.parent) item.remove(); item.parent = this; this.children.splice(next ? this.children.indexOf(next) : this.children.length, 0, item);}
  remove() {this.parent.children.splice(this.parent.children.indexOf(this), 1); this.focused = false; for (const child of this.children) child.focused = false;}
  focus() {this.focused = true;}
  addEventListener(name, fn) {this.listeners[name] = fn;}
  setAttribute(name, value) {this.attributes[name] = value;}
  removeAttribute(name) {delete this.attributes[name];}
  set innerHTML(_) {throw new Error("HTML rendering forbidden");}
}
const find = (parent, key) => parent.children.find(child => child.dataset.key === key);
(async () => {
  const ids = new Map();
  const document = {createElement: tag => new Element(tag), getElementById: id => {if (!ids.has(id)) ids.set(id, new Element(id)); return ids.get(id);}};
  const worker = {worker: "abc", role: "implement", status: "completed", requested: {model: "requested"}, observed: {model: "verified"}, timing: {setup: .123456, running: 12.3456}, tokens: {totalTokens: 25, inputTokens: 10}, milestones: []};
  const question = {kind: "question", state: "pending", summary: "<img onerror=attack>", source: "coordinator-recorded", freshness: "unknown", at: "2026-01-01T00:00:00Z", reference: "https://github.com/example/fixture/issues/1"};
  const futureRetry = new Date(Date.now() + 2 * 3600 * 1000).toISOString();
  let observed = {repository: "example/fixture", queue: "0123456789abcdef0123456789abcdef", mode: "running", at: new Date().toISOString(), limits: {issues: 2, workers: 3, backlog: 4, attempts: 5, seconds: 3600}, clone_wide_used: {issues: 1, workers: 2, backlog: 0}, quota: {state: "paused", retry_at: futureRetry}, dependencies: {status: "observed", at: "2026-01-01T00:00:00Z", issues: {"1": "blocked"}, reasons: {"1": ["prerequisite #2 has no merged change"]}}, controls: [], issues: [{issue: 1, activity: "active", readiness: "unknown", workers: [worker], timing: {elapsed: 1.2345, phases: {implement: .9876}}, evidence: [question]}]};
  const calls = [], timers = [];
  let disconnected = false, loseMutationResponse = false;
  const context = {document, location: {hash: "#cap"}, history: {replaceState() {}}, sessionStorage: {getItem() {return null;}, setItem() {}}, URL, AbortSignal, confirm: () => true, setTimeout: fn => timers.push(fn), setInterval: () => {}, fetch: async (path, options) => {
    calls.push([path, options]);
    if (disconnected || (loseMutationResponse && path === "/api/control")) throw new Error("offline");
    return {ok: true, json: async () => path === "/api/session" ? {csrf: "csrf"} : observed};
  }};
  vm.runInNewContext(fs.readFileSync(require.resolve("../tools/dashboard_assets/app.js"), "utf8"), context);
  const flush = () => new Promise(resolve => setImmediate(resolve));
  await flush();
  const connection = ids.get("connection");
  assert.match(connection.textContent, /^Live · last observation /);
  assert.equal(connection.title, new Date(observed.at).toISOString());
  assert.equal(ids.get("pause").disabled, false);
  assert.equal(ids.get("context").textContent, "example/fixture");
  assert.equal(ids.get("queue-id").textContent, observed.queue);
  assert.match(ids.get("capacity").textContent, /Issues: 1 \/ 2/);
  assert.match(ids.get("capacity").textContent, /Retry at: /);
  assert.equal(find(find(ids.get("capacity"), "retry"), "when").title, futureRetry);
  assert.equal(find(find(ids.get("capacity"), "retry"), "when").dateTime, futureRetry);
  assert.match(find(find(ids.get("capacity"), "retry"), "when").textContent, /in 2 h/);
  assert.match(ids.get("detail").textContent, /Not recorded: phase, plan, decision, check, review, readiness \(unknown\)/);
  assert.equal(ids.get("detail").textContent.match(/Not recorded:/g).length, 1);
  assert.match(ids.get("detail").textContent, /Phase timing not recorded: Review, Worker setup, Human review wait, Coordinator/);
  assert.match(ids.get("attention").textContent, /<img onerror=attack>/);
  assert.match(ids.get("attention").textContent, /prerequisite #2/);
  assert.equal(find(find(ids.get("attention"), "e-0"), "ref").href, question.reference);
  const row = find(ids.get("issues"), "1"), issueButton = find(find(row, "issue"), "select");
  assert.match(row.textContent, /Needs you/);
  assert.equal(find(row, "activity").className, "");
  assert.equal(find(find(row, "activity"), "badge").className, "status active");
  assert.equal(ids.get("attention-box").className, "attention");
  const workerButton = find(ids.get("worker-list"), "abc");
  workerButton.onclick();
  assert.match(ids.get("worker").textContent, /requested/);
  assert.match(ids.get("worker").textContent, /verified/);
  assert.match(ids.get("worker").textContent, /Completion alone/);
  assert.match(workerButton.textContent, /implement · completed · worker · unverified route · abc/);
  assert.match(ids.get("worker").textContent, /Executor: worker · Route: unverified route/);
  const evidenceLink = find(find(ids.get("detail"), "evidence-0"), "ref");
  const evidenceTime = find(find(ids.get("detail"), "evidence-0"), "time");
  assert.equal(evidenceTime.dateTime, question.at.replace("Z", ".000Z"));
  observed = {...observed, at: new Date().toISOString(), issues: [{...observed.issues[0], readiness: "draft"}]};
  await timers.shift()();
  assert.equal(find(ids.get("issues"), "1"), row);
  assert.equal(find(find(row, "issue"), "select"), issueButton);
  assert.equal(find(ids.get("worker-list"), "abc"), workerButton);
  assert.equal(find(find(ids.get("detail"), "evidence-0"), "ref"), evidenceLink);
  assert.equal(find(find(ids.get("detail"), "evidence-0"), "time"), evidenceTime);
  assert.equal(workerButton.attributes["aria-pressed"], "true");
  assert.match(row.textContent, /draft/);
  observed = {...observed, issues: [{...observed.issues[0], evidence: []}]};
  await timers.shift()();
  const firstEvidence = question;
  observed = {...observed, dependencies: {...observed.dependencies, reasons: {}}, issues: [{...observed.issues[0], evidence: [firstEvidence]}]};
  await timers.shift()();
  const detail = ids.get("detail"), firstBox = find(detail, "evidence-0");
  assert.ok(detail.children.indexOf(find(detail, "evidence-heading")) < detail.children.indexOf(find(detail, "absent")));
  assert.ok(detail.children.indexOf(firstBox) < detail.children.indexOf(find(detail, "timing")));
  const firstLink = find(firstBox, "ref");
  firstLink.focus();
  const answer = {...question, state: "answered"};
  observed = {...observed, issues: [{...observed.issues[0], evidence: [firstEvidence, answer]}]};
  await timers.shift()();
  assert.equal(find(detail, "evidence-0"), firstBox);
  assert.equal(find(firstBox, "ref"), firstLink);
  assert.equal(firstLink.focused, true);
  assert.ok(detail.children.indexOf(find(detail, "evidence-1")) < detail.children.indexOf(find(detail, "timing")));
  assert.doesNotMatch(row.textContent, /Needs you/);
  const secondEvidence = {kind: "phase", state: "blocked", summary: "Waiting", source: "coordinator-recorded", at: question.at};
  observed = {...observed, issues: [{...observed.issues[0], evidence: [firstEvidence, answer, secondEvidence]}]};
  await timers.shift()();
  assert.equal(find(detail, "evidence-0"), firstBox);
  assert.ok(detail.children.indexOf(find(detail, "evidence-2")) < detail.children.indexOf(find(detail, "timing")));
  assert.match(row.textContent, /Needs you/);
  observed = {...observed, issues: [{...observed.issues[0], evidence: [firstEvidence, answer, secondEvidence, {...secondEvidence, state: "completed"}]}]};
  await timers.shift()();
  assert.doesNotMatch(row.textContent, /Needs you/);
  assert.match(find(detail, "evidence-0").textContent, /question: pending/);
  assert.match(find(detail, "evidence-1").textContent, /question: answered/);
  assert.match(find(detail, "evidence-2").textContent, /phase: blocked/);
  assert.match(find(detail, "evidence-3").textContent, /phase: completed/);
  loseMutationResponse = true;
  await ids.get("pause").listeners.click();
  assert.match(ids.get("connection").textContent, /outcome unknown/);
  issueButton.onclick(); workerButton.onclick();
  await ids.get("pause").listeners.click();
  assert.equal(ids.get("pause").disabled, true);
  assert.equal(calls.filter(c => c[0] === "/api/control").length, 1);
  disconnected = true; await timers.shift()();
  assert.equal(ids.get("connection").dataset.state, "disconnected");
  assert.match(ids.get("connection").textContent, /^Disconnected · last observation /);
  assert.equal(ids.get("connection").title, new Date(observed.at).toISOString());
  observed = {...observed, at: null}; disconnected = false; await timers.shift()();
  assert.match(ids.get("connection").textContent, /last observation unknown/);
  assert.equal(ids.get("connection").title, undefined);
  loseMutationResponse = false;
  observed = {...observed, mode: "paused"}; await timers.shift()();
  assert.equal(ids.get("resume").disabled, false);
  worker.tokens = {}; worker.timing = {}; Object.assign(worker, {executor: "coordinator", verdict: "approved", round: 1});
  workerButton.onclick();
  assert.match(ids.get("worker").textContent, /Executor: coordinator · Route: unverified route .* Review verdict: approved, round 1/);
  assert.match(ids.get("worker").textContent, /Setup: unknown · Running: unknown/);
  assert.match(ids.get("worker").textContent, /Usage — unknown/);
  observed = {...observed, mode: "cancelled", limits: {}, clone_wide_used: {}, quota: {}, issues: [{issue: 2, activity: "unclaimed", readiness: "unknown", evidence: [], workers: []}]};
  await timers.shift()();
  assert.match(ids.get("detail").textContent, /Issue #2/);
  assert.match(ids.get("capacity").textContent, /Issues: unknown \/ unknown/);
  assert.match(ids.get("detail").textContent, /Elapsed: unknown/);
  for (const id of ["pause", "resume", "cancel"]) assert.equal(ids.get(id).disabled, true);
  assert.equal(calls.filter(c => c[0] === "/api/control").length, 1);
  assert.equal(calls.some(c => /launch|dispatch|release|answer/.test(c[0])), false);
})().catch(error => {console.error(error); process.exitCode = 1;});
