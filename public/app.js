// Interface CareOps Hub : deux espaces qui lisent le même état partagé (/api/state).

const SEVERITIES = ["Critical", "Medium", "Low"];
const ISSUE_STATES = ["Open", "In Progress", "Resolved"];
const MILESTONE_STATES = ["To Do", "In Progress", "Done", "Blocked"];
const FEATURE_STATES = ["Planned", "In Development", "Shipped"];
const STATUS_CLASS = { "Not Ready": "s-not-ready", "At Risk": "s-at-risk", "Ready": "s-ready", "In Progress": "s-in-progress" };

let state = null;
let lastJson = "";
let selectedClientId = null;

const $ = (sel) => document.querySelector(sel);

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const options = (list, selected) =>
  list.map((v) => `<option value="${esc(v)}"${v === selected ? " selected" : ""}>${esc(v)}</option>`).join("");

function formatDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.className = isError ? "error" : "";
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.hidden = true), 3500);
}

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || `Error ${res.status}`);
  return json;
}

// --- Chargement et synchronisation --------------------------------------------

async function refresh(force = false) {
  const next = await api("GET", "/api/state");
  const json = JSON.stringify(next);
  if (!force && json === lastJson) return;
  // Ne pas écraser une saisie en cours dans un tableau pendant la synchro automatique.
  if (!force && document.activeElement?.closest("table")) return;
  lastJson = json;
  state = next;
  if (!state.clients.some((c) => c.id === selectedClientId)) selectedClientId = state.clients[0]?.id ?? null;
  render();
}

async function mutate(method, url, body, message) {
  try {
    await api(method, url, body);
    await refresh(true);
    if (message) toast(message);
    return true;
  } catch (error) {
    toast(error.message, true);
    return false;
  }
}

// Synchro entre deux fenêtres (Brahim et Sarah) toutes les 4 secondes.
setInterval(() => refresh().catch(() => {}), 4000);

// --- Rendu ---------------------------------------------------------------------

const clientName = (id) => state.clients.find((c) => c.id === id)?.name ?? "—";
const featureName = (id) => state.features.find((f) => f.id === id)?.name ?? "—";
const milestoneName = (id) => state.milestones.find((m) => m.id === id)?.name;
// Étape retardée par le problème, affichée sous ses clients.
const stepNote = (i) => (milestoneName(i.milestoneId) ? `<div class="sub">Milestone: ${esc(milestoneName(i.milestoneId))}</div>` : "");

function render() {
  renderReadinessCards();
  renderProduct();
  renderImplementation();
  for (const btn of document.querySelectorAll("button.ai")) {
    btn.title = state.aiEnabled ? "" : "Add ANTHROPIC_API_KEY to .env to turn on Claude";
  }
}

function renderReadinessCards() {
  $("#readiness-cards").innerHTML = state.clients
    .map((c) => {
      const r = state.readiness[c.id];
      return `<button class="card ${STATUS_CLASS[r.status]}" data-client="${esc(c.id)}">
        <div class="name">${esc(c.name)} <span class="pill">${esc(r.status)}</span></div>
        <div class="golive">Go-live: ${formatDate(c.goLiveDate)}</div>
        <div class="reason">${esc(r.reasons[0])}</div>
      </button>`;
    })
    .join("");
}

function renderProduct() {
  const sev = $("#filter-severity").value;
  const st = $("#filter-state").value;
  const cl = $("#filter-client").value;

  fillSelect("#filter-client", [["", "All clients"], ...state.clients.map((c) => [c.id, c.name])], cl);

  const rank = (i) => (i.state === "Resolved" ? 10 : 0) + SEVERITIES.indexOf(i.severity);
  const issues = state.issues
    .filter((i) => (!sev || i.severity === sev) && (!st || i.state === st) && (!cl || affects(i, cl)))
    .sort((a, b) => rank(a) - rank(b));

  $("#issues-table").innerHTML = `
    <thead><tr><th>Issue</th><th>Feature</th><th>Affected clients</th><th>Severity</th><th>State</th><th></th></tr></thead>
    <tbody>${
      issues.length
        ? issues
            .map(
              (i) => `<tr class="${i.state === "Resolved" ? "resolved" : ""}" data-id="${esc(i.id)}">
          <td><strong>${esc(i.title)}</strong><div class="sub">${esc(i.description)}</div></td>
          <td>${esc(featureName(i.featureId))}</td>
          <td>${i.allClients ? `<span class="pill">All clients</span>` : i.clientIds.map((id) => esc(clientName(id))).join("<br>") || untriagedTag(i)}${stepNote(i)}</td>
          <td><select class="sev sev-${esc(i.severity)}" data-field="severity" aria-label="Severity">${options(SEVERITIES, i.severity)}</select></td>
          <td><select data-field="state" aria-label="State">${options(ISSUE_STATES, i.state)}</select></td>
          <td><button class="icon" data-delete="issues" title="Delete">✕</button></td>
        </tr>`
            )
            .join("")
        : `<tr><td colspan="6" class="empty">No issues match these filters.</td></tr>`
    }</tbody>`;

  $("#features-table").innerHTML = `
    <thead><tr><th>Feature</th><th>Description</th><th>Open issues</th><th>Status</th><th></th></tr></thead>
    <tbody>${state.features
      .map((f) => {
        const open = state.issues.filter((i) => i.featureId === f.id && i.state !== "Resolved").length;
        return `<tr data-id="${esc(f.id)}">
          <td><strong>${esc(f.name)}</strong></td>
          <td>${esc(f.description)}</td>
          <td>${open}</td>
          <td><select data-field="status" aria-label="Status">${options(FEATURE_STATES, f.status)}</select></td>
          <td><button class="icon" data-delete="features" title="Delete">✕</button></td>
        </tr>`;
      })
      .join("")}</tbody>`;

  const form = $("#issue-form");
  fillSelect(form.elements.featureId, [["", "— None —"], ...state.features.map((f) => [f.id, f.name])], form.elements.featureId.value);
  const checked = new Set([...form.querySelectorAll("input[name=clientIds]:checked")].map((x) => x.value));
  $("#issue-clients").innerHTML = state.clients
    .map((c) => `<label><input type="checkbox" name="clientIds" value="${esc(c.id)}"${checked.has(c.id) ? " checked" : ""}> ${esc(c.name)}</label>`)
    .join("");
  syncAllClients();

  // Étape concernée (facultatif), regroupée par client ; la choisir relie aussi son client côté serveur.
  const chosen = form.elements.milestoneId.value;
  form.elements.milestoneId.innerHTML =
    `<option value="">— None —</option>` +
    state.clients
      .map((c) => {
        const steps = state.milestones.filter((m) => m.clientId === c.id);
        return steps.length
          ? `<optgroup label="${esc(c.name)}">${steps.map((m) => `<option value="${esc(m.id)}"${m.id === chosen ? " selected" : ""}>${esc(m.name)}</option>`).join("")}</optgroup>`
          : "";
      })
      .join("");
}

// « Tous les clients » remplace la sélection individuelle : on grise les cases des clients.
function syncAllClients() {
  const all = $("#issue-all-clients").checked;
  for (const box of $("#issue-clients").querySelectorAll("input")) box.disabled = all;
}
$("#issue-all-clients").addEventListener("change", syncAllClients);

function renderImplementation() {
  fillSelect("#client-select", state.clients.map((c) => [c.id, c.name]), selectedClientId);
  const client = state.clients.find((c) => c.id === selectedClientId);
  if (!client) {
    $("#readiness-banner").innerHTML = "No clients yet. Add one to get started.";
    $("#milestones-table").innerHTML = "";
    $("#client-issues").innerHTML = "";
    return;
  }

  const r = state.readiness[client.id];
  const banner = $("#readiness-banner");
  banner.className = `banner ${STATUS_CLASS[r.status]}`;
  banner.innerHTML = `<div class="title">${esc(r.status)}</div>
    <div>Planned go-live: ${formatDate(client.goLiveDate)}</div>
    <ul>${r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;

  const milestones = state.milestones
    .filter((m) => m.clientId === client.id)
    .sort((a, b) => (a.dueDate || "9999").localeCompare(b.dueDate || "9999"));

  $("#milestones-table").innerHTML = `
    <thead><tr><th>Milestone</th><th>Due date</th><th>Owner</th><th>Status</th><th>Blocker</th><th></th></tr></thead>
    <tbody>${
      milestones.length
        ? milestones
            .map((m) => {
              const late = m.status !== "Done" && m.dueDate && m.dueDate < state.today;
              return `<tr data-id="${esc(m.id)}">
          <td><strong>${esc(m.name)}</strong></td>
          <td>${formatDate(m.dueDate)}${late ? `<div class="late">Late</div>` : ""}</td>
          <td><input data-field="owner" value="${esc(m.owner)}" aria-label="Owner"></td>
          <td><select data-field="status" aria-label="Status">${options(MILESTONE_STATES, m.status)}</select></td>
          <td><input data-field="blocker" value="${esc(m.blocker)}" placeholder="None" aria-label="Blocker"></td>
          <td><button class="icon" data-delete="milestones" title="Delete">✕</button></td>
        </tr>`;
            })
            .join("")
        : `<tr><td colspan="6" class="empty">No milestones for this client yet.</td></tr>`
    }</tbody>`;

  // Un Critique ouvert « À trier » bloque tous les clients : on le montre aussi ici.
  const issues = state.issues.filter((i) => affects(i, client.id) || isUntriagedCritical(i));
  $("#client-issues").innerHTML = issues.length
    ? issues
        .map(
          (i) => `<li class="${i.state === "Resolved" ? "resolved" : ""}">
        <span class="sev sev-${esc(i.severity)}">${esc(i.severity)}</span>
        <span>${esc(i.title)}${isUntriagedCritical(i) ? ` ${untriagedTag(i)}` : ""}${milestoneName(i.milestoneId) && affects(i, client.id) ? ` <span class="muted">· milestone “${esc(milestoneName(i.milestoneId))}”</span>` : ""}</span>
        <span class="pill">${esc(i.state)}</span>
      </li>`
        )
        .join("")
    : `<li class="muted">No issues reported for this client.</li>`;
}

// Problème sans client : « À trier ». S'il est Critique et ouvert, il bloque tous les clients jusqu'au tri.
function isUntriagedCritical(i) {
  return i.severity === "Critical" && i.state !== "Resolved" && i.clientIds.length === 0 && !i.allClients;
}

// Calculé par le serveur (readiness.is_overdue_for_triage) : une seule source pour la règle.
function isOverdueForTriage(i) {
  return Boolean(i.overdueForTriage);
}

// Règle active envoyée par le serveur (CAREOPS_HOLIDAYS, CAREOPS_TZ) : la même sur tous les postes.
function overdueRule() {
  const calendar = state.triageCalendar;
  const rule = "Not triaged by the end of the business day it was created";
  return calendar ? `${rule} (${calendar.label})` : rule;
}

function affects(i, clientId) {
  return i.allClients || i.clientIds.includes(clientId);
}

function untriagedTag(i) {
  const baseTag = isUntriagedCritical(i)
    ? `<span class="pill s-not-ready" title="Blocks every client until it is linked to the affected clients">To triage · blocks every client</span>`
    : `<span class="pill">To triage</span>`;
  if (isOverdueForTriage(i)) {
    return `${baseTag} <span class="pill pill-overdue" title="${overdueRule()}">Overdue for triage</span>`;
  }
  return baseTag;
}

function fillSelect(target, pairs, selected) {
  const el = typeof target === "string" ? $(target) : target;
  el.innerHTML = pairs.map(([v, label]) => `<option value="${esc(v)}"${v === selected ? " selected" : ""}>${esc(label)}</option>`).join("");
}

// --- Événements ----------------------------------------------------------------

function switchTab(name) {
  for (const t of document.querySelectorAll(".tab")) t.setAttribute("aria-selected", String(t.dataset.tab === name));
  $("#tab-product").hidden = name !== "product";
  $("#tab-implementation").hidden = name !== "implementation";
}

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));

$("#readiness-cards").addEventListener("click", (e) => {
  const card = e.target.closest(".card");
  if (!card) return;
  selectedClientId = card.dataset.client;
  renderImplementation();
  switchTab("implementation");
});

$("#client-select").addEventListener("change", (e) => {
  selectedClientId = e.target.value;
  $("#summary-output").value = "";
  $("#email-output").value = "";
  renderImplementation();
});

["#filter-severity", "#filter-state", "#filter-client"].forEach((sel) => $(sel).addEventListener("change", renderProduct));

// Modifications en ligne dans les tableaux (sélecteurs et champs texte).
for (const [table, collection] of [["#issues-table", "issues"], ["#features-table", "features"], ["#milestones-table", "milestones"]]) {
  const el = $(table);
  el.addEventListener("change", (e) => {
    const field = e.target.dataset.field;
    const id = e.target.closest("tr")?.dataset.id;
    if (!field || !id) return;
    e.target.blur();
    const body = { [field]: e.target.value };
    // Une étape Bloquée doit avoir une cause : on la demande si le champ est vide.
    if (collection === "milestones" && field === "status" && e.target.value === "Blocked") {
      const current = e.target.closest("tr").querySelector('[data-field="blocker"]')?.value.trim();
      if (!current) {
        const cause = prompt("What is blocking this milestone?")?.trim();
        if (!cause) {
          toast("Milestone not blocked: a cause is required.", true);
          refresh(true);
          return;
        }
        body.blocker = cause;
      }
    }
    // Si le serveur refuse (ex. Critique sans client, étape bloquée sans cause), on réaffiche la valeur enregistrée.
    mutate("PUT", `/api/${collection}/${id}`, body, "Saved").then((ok) => ok || refresh(true));
  });
  el.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-delete]");
    if (!btn) return;
    const id = btn.closest("tr").dataset.id;
    if (confirm("Delete this item?")) mutate("DELETE", `/api/${collection}/${id}`, null, "Deleted");
  });
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

$("#issue-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const allClients = $("#issue-all-clients").checked;
  const clientIds = allClients ? [] : [...form.querySelectorAll("input[name=clientIds]:checked")].map((x) => x.value);
  const body = { ...formData(form), clientIds, allClients };
  if (!(await mutate("POST", "/api/issues", body, "Issue created"))) return;
  form.reset();
  syncAllClients();
  $("#severity-suggestion").hidden = true;
  renderProduct();
});

$("#feature-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (await mutate("POST", "/api/features", formData(e.target), "Feature created")) e.target.reset();
});

$("#milestone-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { ...formData(e.target), clientId: selectedClientId };
  if (body.status === "Blocked" && !body.blocker?.trim()) {
    toast("A blocked milestone needs a cause: describe what is blocking it.", true);
    e.target.elements.blocker.focus();
    return;
  }
  if (await mutate("POST", "/api/milestones", body, "Milestone added")) e.target.reset();
});

$("#client-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const client = await api("POST", "/api/clients", formData(e.target));
    selectedClientId = client.id;
    await refresh(true);
    e.target.reset();
    toast("Client added");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#reset").addEventListener("click", () => {
  if (confirm("Restore all demo data? Your changes will be lost.")) mutate("POST", "/api/reset", null, "Demo data restored");
});

// --- Claude --------------------------------------------------------------------

async function withBusy(button, label, fn) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = label;
  try {
    await fn();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

$("#suggest-severity").addEventListener("click", (e) =>
  withBusy(e.target, "Claude is thinking…", async () => {
    const form = $("#issue-form");
    const result = await api("POST", "/api/ai/severity", {
      // form.elements : form.title renverrait l'attribut title du formulaire, pas le champ.
      title: form.elements.title.value,
      description: form.elements.description.value,
      featureId: form.elements.featureId.value,
    });
    form.elements.severity.value = result.severity;
    const note = $("#severity-suggestion");
    note.textContent = `Suggestion: ${result.severity}. ${result.justification} You can change it before creating the issue.`;
    note.hidden = false;
  })
);

$("#ai-summary").addEventListener("click", (e) =>
  withBusy(e.target, "Claude is writing…", async () => {
    const { text } = await api("POST", "/api/ai/summary", { clientId: selectedClientId });
    $("#summary-output").value = text;
  })
);

$("#ai-email").addEventListener("click", (e) =>
  withBusy(e.target, "Claude is writing…", async () => {
    const { text } = await api("POST", "/api/ai/email", { clientId: selectedClientId, summary: $("#summary-output").value });
    $("#email-output").value = text;
  })
);

$("#copy-email").addEventListener("click", async () => {
  const text = $("#email-output").value;
  if (!text) return toast("No email to copy.", true);
  await navigator.clipboard.writeText(text);
  toast("Email copied");
});

// --- Démarrage -----------------------------------------------------------------

fillSelect("#filter-severity", [["", "All severities"], ...SEVERITIES.map((s) => [s, s])], "");
fillSelect("#filter-state", [["", "All states"], ...ISSUE_STATES.map((s) => [s, s])], "");
fillSelect($("#issue-form").elements.severity, SEVERITIES.map((s) => [s, s]), "Medium");
fillSelect($("#issue-form").elements.state, ISSUE_STATES.map((s) => [s, s]), "Open");
fillSelect($("#milestone-form").elements.status, MILESTONE_STATES.map((s) => [s, s]), "To Do");

refresh(true).catch((error) => toast(`Cannot reach the server: ${error.message}`, true));
