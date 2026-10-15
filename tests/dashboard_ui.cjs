"use strict";
const assert = require("node:assert/strict");
const {controls, select, text} = require("../tools/dashboard_assets/app.js");
const snapshot = {mode: "running", issues: [{issue: 1, workers: [{worker: "a"}]}, {issue: 2, workers: []}]};
const state = {fresh: true, at: 100, selected: 1, worker: "a", snapshot};
assert.deepEqual(controls(state, 101), {pause: true, resume: false, cancel: true});
assert.equal(controls(state, 7000).pause, false);
state.fresh = false; assert.equal(controls(state, 101).cancel, false);
state.fresh = true; snapshot.mode = "cancelled";
assert.deepEqual(controls(state, 101), {pause: false, resume: false, cancel: false});
assert.equal(select(state, snapshot).issue, 1); assert.equal(state.worker, "a");
state.selected = 2; select(state, snapshot); assert.equal(state.worker, null);
select(state, {issues: [{issue: 3, workers: []}]}); assert.equal(state.selected, 3);
const element = {};
const doc = {createElement: () => element};
assert.equal(text(doc, "p", "<script>hostile</script>").textContent, "<script>hostile</script>");
assert.equal(element.innerHTML, undefined);
text(doc, "p", null); assert.equal(element.textContent, "unknown");
// Reconnection only selects observed records. No launch/dispatch function exists.
assert.equal(select(state, snapshot).issue, 1);

// Execute the complete browser script against a minimal text-only native DOM.
const fs = require("node:fs");
const vm = require("node:vm");
class Element {
  constructor(tag) {this.tag = tag; this.children = []; this.listeners = {}; this.disabled = false;}
  append(...items) {this.children.push(...items);}
  replaceChildren() {this.children = []; this.textContent = "";}
  addEventListener(name, fn) {this.listeners[name] = fn;}
  set innerHTML(_) {throw new Error("HTML rendering forbidden");}
}
(async () => {
  const ids = new Map();
  const document = {createElement: tag => new Element(tag), getElementById: id => {if (!ids.has(id)) ids.set(id, new Element(id)); return ids.get(id);}};
  const worker = {worker: "abc", role: "implement", status: "completed", requested: {model: "requested"}, observed: {model: "verified"}, timing: {setup: 0.123456, running: 12.3456}, tokens: {totalTokens: 25, inputTokens: 10}, milestones: []};
  let observed = {repository: "example/fixture", queue: "0123456789abcdef0123456789abcdef", mode: "running", at: "fixture-time", limits: {issues: 2, workers: 3, backlog: 4, attempts: 5, seconds: 3600}, clone_wide_used: {issues: 1, workers: 2, backlog: 0}, quota: {state: "paused", retry_at: 1}, dependencies: {status: "observed", issues: {"1": "blocked"}, reasons: {"1": ["prerequisite #2 has no merged change"]}}, controls: [], issues: [{issue: 1, activity: "active", readiness: "unknown", workers: [worker], timing: {elapsed: 1.2345, phases: {implement: 0.9876, coordinator: 0.2469}}, evidence: [{kind: "question", state: "pending", summary: "<img onerror=attack>", source: "coordinator-recorded", freshness: "unknown"}]}]};
  const calls = [], timers = [];
  let disconnected = false, loseMutationResponse = false;
  const context = {document, location: {hash: "#cap"}, history: {replaceState() {}}, sessionStorage: {getItem() {return null;}, setItem() {}}, URL, AbortSignal, confirm: () => true, setTimeout: fn => timers.push(fn), setInterval: () => {}, fetch: async (path, options) => {
    calls.push([path, options]);
    if (disconnected || (loseMutationResponse && path === "/api/control")) throw new Error("offline");
    return {ok: true, json: async () => path === "/api/session" ? {csrf: "csrf"} : observed};
  }};
  vm.runInNewContext(fs.readFileSync(require.resolve("../tools/dashboard_assets/app.js"), "utf8"), context);
  const flush = () => new Promise(resolve => setImmediate(resolve));
  const strings = element => [element.textContent || "", ...element.children.map(strings)].join(" ");
  await flush();
  assert.equal(ids.get("pause").disabled, false);
  assert.equal(ids.get("context").textContent, "example/fixture · Queue 01234567 · running");
  assert.equal(ids.get("queue-id").textContent, "Complete queue ID: 0123456789abcdef0123456789abcdef");
  assert.match(ids.get("capacity").textContent, /Issues: 1 · Workers: 2 · PR backlog: 0/);
  assert.match(ids.get("capacity").textContent, /Attempts: 5 · Time budget: 3600 s/);
  assert.match(ids.get("capacity").textContent, /Quota: paused · Retry at: 1970-01-01T00:00:01.000Z/);
  assert.match(strings(ids.get("detail")), /Elapsed: 1.2 s · Implementation: 1 s · Review: unknown/);
  assert.match(strings(ids.get("detail")), /Recorded dependency reason: prerequisite #2 has no merged change/);
  assert.match(strings(ids.get("detail")), /<img onerror=attack>/);
  const workerButton = ids.get("detail").children.find(e => e.tag === "button");
  workerButton.listeners.click();
  assert.match(strings(ids.get("worker")), /requested/);
  assert.match(strings(ids.get("worker")), /verified/);
  assert.match(strings(ids.get("worker")), /Completion alone/);
  assert.match(strings(ids.get("worker")), /Setup: 0.1 s · Running: 12.3 s/);
  assert.match(strings(ids.get("worker")), /Usage — Total tokens: 25 · Input tokens: 10/);
  assert.doesNotMatch(strings(ids.get("worker")), /Cached input tokens|totalTokens|\{/);
  // A lost response may have applied the mutation: never replay it, and require
  // a successful observation before another action becomes available.
  loseMutationResponse = true;
  await ids.get("pause").listeners.click();
  assert.match(ids.get("connection").textContent, /Control outcome unknown/);
  const clickIssue = () => ids.get("issues").children[0].children[0].children[0].listeners.click();
  clickIssue();
  ids.get("detail").children.find(e => e.tag === "button").listeners.click();
  assert.match(ids.get("connection").textContent, /Control outcome unknown/);
  await ids.get("pause").listeners.click();
  assert.equal(ids.get("pause").disabled, true);
  assert.equal(calls.filter(c => c[0] === "/api/control").length, 1);
  disconnected = true;
  await timers.shift()();
  assert.match(ids.get("connection").textContent, /Disconnected/);
  assert.equal(ids.get("resume").disabled, true);
  clickIssue();
  ids.get("detail").children.find(e => e.tag === "button").listeners.click();
  assert.match(ids.get("connection").textContent, /Disconnected.*stale/);
  for (const id of ["pause", "resume", "cancel"]) assert.equal(ids.get(id).disabled, true);
  disconnected = false; loseMutationResponse = false;
  observed = {...observed, mode: "paused"};
  await timers.shift()();
  assert.match(ids.get("connection").textContent, /Connected/);
  assert.equal(ids.get("resume").disabled, false);
  assert.equal(calls.filter(c => c[0] === "/api/control").length, 1);
  worker.tokens = {}; worker.timing = {};
  ids.get("detail").children.find(e => e.tag === "button").listeners.click();
  assert.match(strings(ids.get("worker")), /Setup: unknown · Running: unknown/);
  assert.match(strings(ids.get("worker")), /Usage — unknown/);
  observed = {...observed, mode: "cancelled", limits: {}, clone_wide_used: {}, quota: {}, issues: [{issue: 2, activity: "unclaimed", readiness: "unknown", evidence: [], workers: []}]};
  await timers.shift()();
  assert.match(strings(ids.get("detail")), /Issue #2/);
  assert.match(ids.get("capacity").textContent, /Issues: unknown · Workers: unknown · PR backlog: unknown/);
  assert.match(ids.get("capacity").textContent, /Quota: unknown · Retry at: unknown/);
  for (const id of ["capacity", "detail", "worker"]) assert.doesNotMatch(strings(ids.get(id)), /\{|\}/);
  assert.match(strings(ids.get("detail")), /Elapsed: unknown/);
  assert.match(strings(ids.get("detail")), /Dependency\/capacity wait: unknown/);
  for (const id of ["pause", "resume", "cancel"]) assert.equal(ids.get(id).disabled, true);
  assert.equal(calls.filter(c => c[0] === "/api/control").length, 1);
  assert.equal(calls.some(c => /launch|dispatch|release|answer/.test(c[0])), false);
})().catch(error => {console.error(error); process.exitCode = 1;});
