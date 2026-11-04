// Interface CareOps Hub : deux espaces qui lisent le même état partagé (/api/state).

const SEVERITIES = ["Critique", "Moyenne", "Faible"];
const ISSUE_STATES = ["Ouvert", "En cours", "Résolu"];
const MILESTONE_STATES = ["À faire", "En cours", "Terminé", "Bloqué"];
const FEATURE_STATES = ["Planifiée", "En développement", "Livrée"];
const STATUS_CLASS = { "Non prêt": "s-not-ready", "À risque": "s-at-risk", "Prêt": "s-ready", "En cours": "s-in-progress" };

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
  return new Date(y, m - 1, d).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
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
  if (!res.ok) throw new Error(json.error || `Erreur ${res.status}`);
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

function render() {
  renderReadinessCards();
  renderProduct();
  renderImplementation();
  for (const btn of document.querySelectorAll("button.ai")) {
    btn.title = state.aiEnabled ? "" : "Ajoutez ANTHROPIC_API_KEY dans .env pour activer Claude";
  }
}

function renderReadinessCards() {
  $("#readiness-cards").innerHTML = state.clients
    .map((c) => {
      const r = state.readiness[c.id];
      return `<button class="card ${STATUS_CLASS[r.status]}" data-client="${esc(c.id)}">
        <div class="name">${esc(c.name)} <span class="pill">${esc(r.status)}</span></div>
        <div class="golive">Go-live : ${formatDate(c.goLiveDate)}</div>
        <div class="reason">${esc(r.reasons[0])}</div>
      </button>`;
    })
    .join("");
}

function renderProduct() {
  const sev = $("#filter-severity").value;
  const st = $("#filter-state").value;
  const cl = $("#filter-client").value;

  fillSelect("#filter-client", [["", "Tous les clients"], ...state.clients.map((c) => [c.id, c.name])], cl);

  const rank = (i) => (i.state === "Résolu" ? 10 : 0) + SEVERITIES.indexOf(i.severity);
  const issues = state.issues
    .filter((i) => (!sev || i.severity === sev) && (!st || i.state === st) && (!cl || i.clientIds.includes(cl)))
    .sort((a, b) => rank(a) - rank(b));

  $("#issues-table").innerHTML = `
    <thead><tr><th>Problème</th><th>Fonctionnalité</th><th>Clients touchés</th><th>Gravité</th><th>État</th><th></th></tr></thead>
    <tbody>${
      issues.length
        ? issues
            .map(
              (i) => `<tr class="${i.state === "Résolu" ? "resolved" : ""}" data-id="${esc(i.id)}">
          <td><strong>${esc(i.title)}</strong><div class="sub">${esc(i.description)}</div></td>
          <td>${esc(featureName(i.featureId))}</td>
          <td>${i.clientIds.map((id) => esc(clientName(id))).join("<br>") || "—"}</td>
          <td><select class="sev sev-${esc(i.severity)}" data-field="severity" aria-label="Gravité">${options(SEVERITIES, i.severity)}</select></td>
          <td><select data-field="state" aria-label="État">${options(ISSUE_STATES, i.state)}</select></td>
          <td><button class="icon" data-delete="issues" title="Supprimer">✕</button></td>
        </tr>`
            )
            .join("")
        : `<tr><td colspan="6" class="empty">Aucun problème pour ces filtres.</td></tr>`
    }</tbody>`;

  $("#features-table").innerHTML = `
    <thead><tr><th>Fonctionnalité</th><th>Description</th><th>Problèmes ouverts</th><th>Statut</th><th></th></tr></thead>
    <tbody>${state.features
      .map((f) => {
        const open = state.issues.filter((i) => i.featureId === f.id && i.state !== "Résolu").length;
        return `<tr data-id="${esc(f.id)}">
          <td><strong>${esc(f.name)}</strong></td>
          <td>${esc(f.description)}</td>
          <td>${open}</td>
          <td><select data-field="status" aria-label="Statut">${options(FEATURE_STATES, f.status)}</select></td>
          <td><button class="icon" data-delete="features" title="Supprimer">✕</button></td>
        </tr>`;
      })
      .join("")}</tbody>`;

  const form = $("#issue-form");
  fillSelect(form.elements.featureId, [["", "— Aucune —"], ...state.features.map((f) => [f.id, f.name])], form.elements.featureId.value);
  const checked = new Set([...form.querySelectorAll("input[name=clientIds]:checked")].map((x) => x.value));
  $("#issue-clients").innerHTML = state.clients
    .map((c) => `<label><input type="checkbox" name="clientIds" value="${esc(c.id)}"${checked.has(c.id) ? " checked" : ""}> ${esc(c.name)}</label>`)
    .join("");
}

function renderImplementation() {
  fillSelect("#client-select", state.clients.map((c) => [c.id, c.name]), selectedClientId);
  const client = state.clients.find((c) => c.id === selectedClientId);
  if (!client) {
    $("#readiness-banner").innerHTML = "Aucun client. Ajoutez-en un pour commencer.";
    $("#milestones-table").innerHTML = "";
    $("#client-issues").innerHTML = "";
    return;
  }

  const r = state.readiness[client.id];
  const banner = $("#readiness-banner");
  banner.className = `banner ${STATUS_CLASS[r.status]}`;
  banner.innerHTML = `<div class="title">${esc(r.status)}</div>
    <div>Go-live prévu : ${formatDate(client.goLiveDate)}</div>
    <ul>${r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;

  const milestones = state.milestones
    .filter((m) => m.clientId === client.id)
    .sort((a, b) => (a.dueDate || "9999").localeCompare(b.dueDate || "9999"));

  $("#milestones-table").innerHTML = `
    <thead><tr><th>Étape</th><th>Échéance</th><th>Responsable</th><th>Statut</th><th>Point de blocage</th><th></th></tr></thead>
    <tbody>${
      milestones.length
        ? milestones
            .map((m) => {
              const late = m.status !== "Terminé" && m.dueDate && m.dueDate < state.today;
              return `<tr data-id="${esc(m.id)}">
          <td><strong>${esc(m.name)}</strong></td>
          <td>${formatDate(m.dueDate)}${late ? `<div class="late">En retard</div>` : ""}</td>
          <td><input data-field="owner" value="${esc(m.owner)}" aria-label="Responsable"></td>
          <td><select data-field="status" aria-label="Statut">${options(MILESTONE_STATES, m.status)}</select></td>
          <td><input data-field="blocker" value="${esc(m.blocker)}" placeholder="Aucun" aria-label="Point de blocage"></td>
          <td><button class="icon" data-delete="milestones" title="Supprimer">✕</button></td>
        </tr>`;
            })
            .join("")
        : `<tr><td colspan="6" class="empty">Aucune étape pour ce client.</td></tr>`
    }</tbody>`;

  const issues = state.issues.filter((i) => i.clientIds.includes(client.id));
  $("#client-issues").innerHTML = issues.length
    ? issues
        .map(
          (i) => `<li class="${i.state === "Résolu" ? "resolved" : ""}">
        <span class="sev sev-${esc(i.severity)}">${esc(i.severity)}</span>
        <span>${esc(i.title)}</span>
        <span class="pill">${esc(i.state)}</span>
      </li>`
        )
        .join("")
    : `<li class="muted">Aucun problème signalé pour ce client.</li>`;
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
    mutate("PUT", `/api/${collection}/${id}`, { [field]: e.target.value }, "Enregistré");
  });
  el.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-delete]");
    if (!btn) return;
    const id = btn.closest("tr").dataset.id;
    if (confirm("Supprimer cet élément ?")) mutate("DELETE", `/api/${collection}/${id}`, null, "Supprimé");
  });
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

$("#issue-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const body = { ...formData(form), clientIds: [...form.querySelectorAll("input[name=clientIds]:checked")].map((x) => x.value) };
  if (!(await mutate("POST", "/api/issues", body, "Problème créé"))) return;
  form.reset();
  $("#severity-suggestion").hidden = true;
  renderProduct();
});

$("#feature-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (await mutate("POST", "/api/features", formData(e.target), "Fonctionnalité créée")) e.target.reset();
});

$("#milestone-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (await mutate("POST", "/api/milestones", { ...formData(e.target), clientId: selectedClientId }, "Étape ajoutée")) e.target.reset();
});

$("#client-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const client = await api("POST", "/api/clients", formData(e.target));
    selectedClientId = client.id;
    await refresh(true);
    e.target.reset();
    toast("Client ajouté");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#reset").addEventListener("click", () => {
  if (confirm("Remettre toutes les données de démo ? Vos changements seront perdus.")) mutate("POST", "/api/reset", null, "Données de démo restaurées");
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
  withBusy(e.target, "Claude réfléchit…", async () => {
    const form = $("#issue-form");
    const result = await api("POST", "/api/ai/severity", {
      // form.elements : form.title renverrait l'attribut title du formulaire, pas le champ.
      title: form.elements.title.value,
      description: form.elements.description.value,
      featureId: form.elements.featureId.value,
    });
    form.elements.severity.value = result.severity;
    const note = $("#severity-suggestion");
    note.textContent = `Suggestion : ${result.severity}. ${result.justification} Vous pouvez la changer avant de créer le problème.`;
    note.hidden = false;
  })
);

$("#ai-summary").addEventListener("click", (e) =>
  withBusy(e.target, "Claude rédige…", async () => {
    const { text } = await api("POST", "/api/ai/summary", { clientId: selectedClientId });
    $("#summary-output").value = text;
  })
);

$("#ai-email").addEventListener("click", (e) =>
  withBusy(e.target, "Claude rédige…", async () => {
    const { text } = await api("POST", "/api/ai/email", { clientId: selectedClientId, summary: $("#summary-output").value });
    $("#email-output").value = text;
  })
);

$("#copy-email").addEventListener("click", async () => {
  const text = $("#email-output").value;
  if (!text) return toast("Aucun e-mail à copier.", true);
  await navigator.clipboard.writeText(text);
  toast("E-mail copié");
});

// --- Démarrage -----------------------------------------------------------------

fillSelect("#filter-severity", [["", "Toutes les gravités"], ...SEVERITIES.map((s) => [s, s])], "");
fillSelect("#filter-state", [["", "Tous les états"], ...ISSUE_STATES.map((s) => [s, s])], "");
fillSelect($("#issue-form").elements.severity, SEVERITIES.map((s) => [s, s]), "Moyenne");
fillSelect($("#issue-form").elements.state, ISSUE_STATES.map((s) => [s, s]), "Ouvert");
fillSelect($("#milestone-form").elements.status, MILESTONE_STATES.map((s) => [s, s]), "À faire");

refresh(true).catch((error) => toast(`Serveur injoignable : ${error.message}`, true));
