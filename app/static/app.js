const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const api = (path, opts = {}) =>
  fetch(path, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });

function showToast(message, type = "info") {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  el.className = `toast ${type}`;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    el.hidden = true;
  }, 5200);
}

function statusBadge(crmStatus) {
  const s = (crmStatus || "").toLowerCase();
  let cls = "badge-muted";
  let label = crmStatus || "—";
  if (s === "created") cls = "badge-ok";
  else if (s === "skipped") cls = "badge-warn";
  else if (s.includes("error") || s.includes("fail")) cls = "badge-danger";
  return `<span class="badge badge-dot ${cls}">${escapeHtml(label)}</span>`;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return escapeHtml(iso);
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function toYMD(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** @type {string} */
let currentPreset = "all";
let fetchTimer = null;
/** @type {Array<Record<string, string>>} */
let leadsCache = [];

const sortState = {
  key: "created_at",
  dir: "desc",
};

const defaultSortDir = {
  created_at: "desc",
  name: "asc",
  source: "asc",
  crm_status: "asc",
};

let selectedLeadId = null;

function setFilterLoading(isLoading) {
  const el = $("#filter-status");
  el.classList.toggle("is-loading", isLoading);
}

function setFilterSummary(text) {
  $("#filter-status").textContent = text;
}

function sortLabel() {
  const labels = {
    created_at: "Received",
    name: "Name",
    source: "Source",
    crm_status: "Status",
  };
  const col = labels[sortState.key] || sortState.key;
  const order =
    sortState.key === "created_at"
      ? sortState.dir === "desc"
        ? "newest first"
        : "oldest first"
      : sortState.dir === "asc"
        ? "A → Z"
        : "Z → A";
  return `${col}: ${order}`;
}

function scheduleFetch(delayMs = 0) {
  clearTimeout(fetchTimer);
  setFilterLoading(true);
  fetchTimer = setTimeout(() => {
    fetchTimer = null;
    loadLeads();
  }, delayMs);
}

function applyDatePreset(preset) {
  currentPreset = preset;
  const fromEl = $("#f-from");
  const toEl = $("#f-to");
  const customWrap = $("#date-custom-wrap");
  const today = new Date();
  today.setHours(12, 0, 0, 0);

  if (preset === "all") {
    fromEl.value = "";
    toEl.value = "";
    customWrap.classList.add("hidden");
  } else if (preset === "7d") {
    const start = new Date(today);
    start.setDate(start.getDate() - 6);
    fromEl.value = toYMD(start);
    toEl.value = toYMD(today);
    customWrap.classList.add("hidden");
  } else if (preset === "30d") {
    const start = new Date(today);
    start.setDate(start.getDate() - 29);
    fromEl.value = toYMD(start);
    toEl.value = toYMD(today);
    customWrap.classList.add("hidden");
  } else if (preset === "custom") {
    customWrap.classList.remove("hidden");
    if (!fromEl.value) fromEl.value = toYMD(today);
    if (!toEl.value) toEl.value = toYMD(today);
  }

  $$(".chip-date").forEach((b) => {
    b.setAttribute("aria-pressed", b.dataset.preset === preset ? "true" : "false");
  });

  scheduleFetch(0);
}

function sortLeads(items, key, dir) {
  const mult = dir === "asc" ? 1 : -1;
  return [...items].sort((a, b) => {
    let cmp = 0;
    if (key === "created_at") {
      const ta = new Date(a.created_at || 0).getTime();
      const tb = new Date(b.created_at || 0).getTime();
      cmp = (Number.isNaN(ta) ? 0 : ta) - (Number.isNaN(tb) ? 0 : tb);
    } else {
      const va = String(a[key] ?? "").toLowerCase();
      const vb = String(b[key] ?? "").toLowerCase();
      cmp = va.localeCompare(vb, undefined, { sensitivity: "base" });
    }
    if (cmp !== 0) return cmp * mult;
    return String(a.lead_id).localeCompare(String(b.lead_id));
  });
}

function updateSortHeaders() {
  $$(".th-sort").forEach((btn) => {
    const k = btn.dataset.sort;
    if (k === sortState.key) {
      btn.setAttribute("aria-sort", sortState.dir === "asc" ? "ascending" : "descending");
    } else {
      btn.setAttribute("aria-sort", "none");
    }
  });
}

function renderTable() {
  const tbody = $("#tbody");
  const sorted = sortLeads(leadsCache, sortState.key, sortState.dir);

  if (!sorted.length) {
    const hasFilters = Boolean(
      $("#f-source").value.trim() ||
        $("#f-status").value ||
        $("#f-from").value ||
        $("#f-to").value ||
        currentPreset !== "all"
    );
    tbody.innerHTML = `<tr><td colspan="5" class="empty">${
      hasFilters ? "No leads match these filters." : "No leads loaded yet."
    }</td></tr>`;
    $("#count").textContent = "(0)";
    setFilterSummary(
      hasFilters
        ? "Try a wider date range, another status, or reset filters."
        : "Submit a lead or send data to the API — the table will fill from Google Sheets."
    );
    return;
  }

  $("#count").textContent = `(${sorted.length})`;
  setFilterSummary(`Showing ${sorted.length} lead${sorted.length === 1 ? "" : "s"} · ${sortLabel()}`);

  tbody.innerHTML = sorted
    .map(
      (row) => `
      <tr data-id="${escapeHtml(row.lead_id)}">
        <td>${formatDate(row.created_at)}</td>
        <td>${escapeHtml(row.name)}</td>
        <td><code>${escapeHtml(row.source)}</code></td>
        <td>${statusBadge(row.crm_status)}</td>
        <td><button type="button" class="linkish open-detail">View</button></td>
      </tr>
    `
    )
    .join("");
}

async function loadLeads() {
  const params = new URLSearchParams();
  const source = $("#f-source").value.trim();
  const status = $("#f-status").value;
  const from = $("#f-from").value;
  const to = $("#f-to").value;
  if (source) params.set("source", source);
  if (status) params.set("crm_status", status);
  if (from) params.set("date_from", from);
  if (to) params.set("date_to", to);

  const q = params.toString();
  const url = `/api/leads${q ? `?${q}` : ""}`;
  const tbody = $("#tbody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty">Loading…</td></tr>`;
  setFilterLoading(true);

  try {
    const res = await api(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty">Could not load leads.</td></tr>`;
      showToast(data.message || `Error ${res.status}`, "error");
      $("#count").textContent = "";
      leadsCache = [];
      setFilterSummary("");
      setFilterLoading(false);
      return;
    }
    leadsCache = data.items || [];
    setFilterLoading(false);
    updateSortHeaders();
    renderTable();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty">Network error.</td></tr>`;
    showToast(String(e.message || e), "error");
    $("#count").textContent = "";
    leadsCache = [];
    setFilterSummary("");
    setFilterLoading(false);
  }
}

function onSortHeaderClick(key) {
  if (sortState.key === key) {
    sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
  } else {
    sortState.key = key;
    sortState.dir = defaultSortDir[key] || "asc";
  }
  updateSortHeaders();
  renderTable();
}

$$(".th-sort").forEach((btn) => {
  btn.addEventListener("click", () => onSortHeaderClick(btn.dataset.sort));
});

$$(".chip-date").forEach((btn) => {
  btn.addEventListener("click", () => applyDatePreset(btn.dataset.preset));
});

$("#f-source").addEventListener("input", () => scheduleFetch(320));
$("#f-status").addEventListener("change", () => scheduleFetch(0));
$("#f-from").addEventListener("change", () => {
  if (currentPreset !== "custom") {
    currentPreset = "custom";
    $$(".chip-date").forEach((b) => {
      b.setAttribute("aria-pressed", b.dataset.preset === "custom" ? "true" : "false");
    });
    $("#date-custom-wrap").classList.remove("hidden");
  }
  scheduleFetch(0);
});
$("#f-to").addEventListener("change", () => {
  if (currentPreset !== "custom") {
    currentPreset = "custom";
    $$(".chip-date").forEach((b) => {
      b.setAttribute("aria-pressed", b.dataset.preset === "custom" ? "true" : "false");
    });
    $("#date-custom-wrap").classList.remove("hidden");
  }
  scheduleFetch(0);
});

$("#clear-filters").addEventListener("click", () => {
  $("#f-source").value = "";
  $("#f-status").value = "";
  currentPreset = "all";
  $$(".chip-date").forEach((b) => {
    b.setAttribute("aria-pressed", b.dataset.preset === "all" ? "true" : "false");
  });
  $("#f-from").value = "";
  $("#f-to").value = "";
  $("#date-custom-wrap").classList.add("hidden");
  sortState.key = "created_at";
  sortState.dir = "desc";
  updateSortHeaders();
  scheduleFetch(0);
});

$("#refresh").addEventListener("click", () => scheduleFetch(0));

function openModal(lead) {
  selectedLeadId = lead.lead_id;
  $("#detail-title").textContent = lead.name || lead.lead_id;
  const body = $("#detail-body");
  body.innerHTML = `
    <div class="detail-status">${statusBadge(lead.crm_status)}</div>
    <dl>
      <dt>Lead ID</dt><dd><code>${escapeHtml(lead.lead_id)}</code></dd>
      <dt>Created</dt><dd>${formatDate(lead.created_at)}</dd>
      <dt>Email</dt><dd>${escapeHtml(lead.email)}</dd>
      <dt>Phone</dt><dd>${escapeHtml(lead.phone)}</dd>
      <dt>Source</dt><dd><code>${escapeHtml(lead.source)}</code></dd>
      <dt>Campaign</dt><dd>${escapeHtml(lead.campaign || "—")}</dd>
      <dt>City</dt><dd>${escapeHtml(lead.city || "—")}</dd>
      <dt>Message</dt><dd>${escapeHtml(lead.message || "—")}</dd>
      <dt>CRM record</dt><dd>${escapeHtml(lead.crm_record_id || "—")}</dd>
    </dl>
  `;
  const dlg = $("#detail-modal");
  if (typeof dlg.showModal === "function") dlg.showModal();
  else dlg.setAttribute("open", "");
}

function closeModal() {
  selectedLeadId = null;
  const dlg = $("#detail-modal");
  if (typeof dlg.close === "function") dlg.close();
  else dlg.removeAttribute("open");
}

$("#tbody").addEventListener("click", async (e) => {
  const btn = e.target.closest(".open-detail");
  if (!btn) return;
  const tr = btn.closest("tr");
  const id = tr?.dataset?.id;
  if (!id) return;
  try {
    const res = await api(`/api/leads/${encodeURIComponent(id)}`);
    const data = await res.json();
    if (!res.ok) {
      showToast(data.message || "Could not open lead", "error");
      return;
    }
    openModal(data);
  } catch (err) {
    showToast(String(err.message || err), "error");
  }
});

$("#modal-close").addEventListener("click", closeModal);
$("#detail-modal").addEventListener("cancel", (e) => {
  e.preventDefault();
  closeModal();
});

$("#btn-resend").addEventListener("click", async () => {
  if (!selectedLeadId) return;
  try {
    const res = await api(`/api/leads/${encodeURIComponent(selectedLeadId)}/resend-crm`, {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.message || `Resend failed (${res.status})`, "error");
      return;
    }
    showToast(data.message || "Resent to CRM", "success");
    closeModal();
    scheduleFetch(0);
  } catch (err) {
    showToast(String(err.message || err), "error");
  }
});

$("#toggle-form").addEventListener("click", () => {
  const p = $("#form-panel");
  p.hidden = !p.hidden;
});
$("#cancel-form").addEventListener("click", () => {
  $("#form-panel").hidden = true;
});

$("#lead-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = {
    name: fd.get("name")?.toString().trim(),
    email: fd.get("email")?.toString().trim(),
    phone: fd.get("phone")?.toString().trim(),
    source: fd.get("source")?.toString().trim(),
    campaign: fd.get("campaign")?.toString().trim() || null,
    city: fd.get("city")?.toString().trim() || null,
    message: fd.get("message")?.toString().trim() || null,
  };

  try {
    const res = await api("/api/leads", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.status === 409) {
      showToast(`Duplicate: ${data.message}`, "error");
      return;
    }
    if (!res.ok) {
      showToast(data.message || `Error ${res.status}`, "error");
      return;
    }
    showToast(`Saved · ${data.lead_id}`, "success");
    e.target.reset();
    $("#form-panel").hidden = true;
    scheduleFetch(0);
  } catch (err) {
    showToast(String(err.message || err), "error");
  }
});

updateSortHeaders();
loadLeads();
