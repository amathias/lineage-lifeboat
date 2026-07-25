const $ = (id) => document.getElementById(id);
let activeRun = null;

async function call(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

function notice(message, error = false) {
  $("notice").textContent = message;
  $("notice").style.color = error ? "var(--red)" : "var(--muted)";
}

function shortName(urn) {
  const match = urn.match(/,([^,]+),PROD\)$/);
  return match ? match[1].replace("lifeboat.", "") : urn;
}

async function refreshGraph() {
  const graph = await call("/api/demo/graph");
  $("asset-count").textContent = graph.nodes.length;
  $("graph").innerHTML = graph.nodes.map((node) => {
    const excluded = node.name === "inventory.forecast" ? " excluded" : "";
    const state = node.available ? "READY" : "OUTAGE";
    return `<div class="node ${node.available ? "" : "down"}${excluded}"><small>${node.type} · ${node.owner?.split(":").pop() || "unowned"}</small><strong>${node.name}</strong><span>${state}</span></div>`;
  }).join("");
}

function renderRun(run) {
  activeRun = run;
  $("run-status").textContent = run.status.toUpperCase();
  $("graph-mode").textContent = run.context_evidence.mode.replaceAll("_", " ");
  $("approve").disabled = Boolean(run.approval);
  $("execute").disabled = !run.approval || run.status === "completed";
  $("execute").textContent = run.status === "failed" ? "Resume recovery" : "Execute recovery";
  const byId = Object.fromEntries(run.plan.steps.map((step) => [step.step_id, step]));
  $("waves").innerHTML = run.plan.waves.map((wave, index) => `<div class="wave"><div class="wave-index">${String(index + 1).padStart(2, "0")}</div><div class="wave-steps">${wave.map((id) => `<div>${shortName(byId[id].target_urn)}</div>`).join("")}</div></div>`).join("");
  $("timeline").innerHTML = run.steps.map((step) => {
    const checks = step.validations.length ? `${step.validations.filter((v) => v.passed).length}/${step.validations.length} validations` : "awaiting evidence";
    const action = step.adapter_evidence?.action || step.error_type || checks;
    return `<div class="event ${step.status}"><i class="event-dot"></i><div><strong>${shortName(step.target_urn)}</strong><p>${action} · ${checks} · attempt ${step.attempts}</p></div><span>${step.status}</span></div>`;
  }).join("");
  const verified = run.steps.filter((step) => step.status === "verified").length;
  $("verified-count").textContent = `${verified} / ${run.steps.length}`;
  $("writeback-status").textContent = run.datahub_outcome.status.toUpperCase();
}

async function action(fn) {
  try { await fn(); } catch (error) { notice(error.message, true); }
}

$("initialize").onclick = () => action(async () => {
  await call("/api/demo/initialize", {method: "POST", body: JSON.stringify({confirm_project: "lineage-lifeboat"})});
  await refreshGraph(); notice("Disposable estate initialized. Eight assets are healthy.");
});
$("outage").onclick = () => action(async () => {
  await call("/api/demo/outage", {method: "POST", body: JSON.stringify({confirm_project: "lineage-lifeboat"})});
  await refreshGraph(); notice("Outage executed locally. Six connected assets are unavailable; unrelated inventory is untouched.");
});
$("compile").onclick = () => action(async () => {
  const runId = $("run-id").value.trim();
  const run = await call("/api/recovery/plan", {method: "POST", body: JSON.stringify({run_id: runId, requester: "demo-incident-commander"})});
  renderRun(run); notice(`Plan ${run.plan.plan_id} compiled. Review dependency waves, then approve the exact plan.`);
});
$("approve").onclick = () => action(async () => {
  if (!activeRun) throw new Error("Compile a plan first.");
  const run = await call(`/api/recovery/${activeRun.run_id}/approve`, {method: "POST", body: JSON.stringify({plan_id: activeRun.plan.plan_id, approved_by: "demo-incident-commander"})});
  renderRun(run); notice("Exact plan approved by the incident commander. Execution is now enabled.");
});
$("execute").onclick = () => action(async () => {
  if (!activeRun) throw new Error("Compile and approve a plan first.");
  notice("Executing dependency-correct adapters and required validations…");
  const endpoint = activeRun.status === "failed" ? "resume" : "execute";
  const run = await call(`/api/recovery/${activeRun.run_id}/${endpoint}`, {method: "POST", body: "{}"});
  renderRun(run); await refreshGraph();
  notice(run.status === "completed" ? "Recovery complete. Every step is verified and report evidence is persisted." : "Execution failed closed. Correct the local fault and resume; verified steps will not rerun.", run.status !== "completed");
});

call("/api/demo/state").then((state) => { if (state.initialized) refreshGraph(); }).catch(() => {});