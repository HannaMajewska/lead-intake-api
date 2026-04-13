const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const COLS = 7;

const api = (path, opts = {}) =>
  fetch(path, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });

function showToast(message, type = "info") {
  const el = $("#toast");
  const safeType = ["success", "error", "info", "delete"].includes(type) ? type : "info";
  el.textContent = message;
  el.hidden = false;
  el.className = `toast toast--${safeType}`;
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

const CRM_STATUS_LABELS = {
  "": "All statuses",
  skipped: "Pending sync (skipped)",
  created: "In CRM (created)",
  error: "Error",
};

function setCrmFilterValue(value) {
  const hidden = $("#f-status");
  if (hidden) hidden.value = value;
  const display = $("#crm-status-display");
  if (display) {
    display.textContent = CRM_STATUS_LABELS[value] ?? value ?? "All statuses";
  }
  $$(".custom-select-option").forEach((el) => {
    el.setAttribute("aria-selected", el.dataset.value === value ? "true" : "false");
  });
}

function initCrmStatusDropdown() {
  const wrap = $("#crm-status-wrap");
  const trigger = $("#crm-status-trigger");
  const list = $("#crm-status-dropdown");
  if (!wrap || !trigger || !list) return;

  function syncCrmDropdownPosition() {
    if (list.hidden) return;
    const r = trigger.getBoundingClientRect();
    const gap = 6;
    list.style.left = `${r.left}px`;
    list.style.top = `${r.bottom + gap}px`;
    list.style.width = `${r.width}px`;
  }

  function closeList() {
    list.hidden = true;
    list.classList.remove("is-anchor-fixed");
    list.style.left = "";
    list.style.top = "";
    list.style.width = "";
    trigger.setAttribute("aria-expanded", "false");
    wrap.classList.remove("is-dropdown-open");
    if (list.parentElement === document.body) {
      wrap.appendChild(list);
    }
  }

  function openList() {
    list.hidden = false;
    list.classList.add("is-anchor-fixed");
    trigger.setAttribute("aria-expanded", "true");
    wrap.classList.add("is-dropdown-open");
    /* Body layer: always above .table-glass / filters stacking, no ancestor clip */
    if (list.parentElement !== document.body) {
      document.body.appendChild(list);
    }
    syncCrmDropdownPosition();
    requestAnimationFrame(() => {
      syncCrmDropdownPosition();
    });
  }

  function onViewportChange() {
    if (!list.hidden) syncCrmDropdownPosition();
  }

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    if (list.hidden) openList();
    else closeList();
  });

  list.addEventListener("click", (e) => {
    const opt = e.target.closest(".custom-select-option");
    if (!opt) return;
    const val = opt.dataset.value ?? "";
    setCrmFilterValue(val);
    closeList();
    scheduleFetch(0);
  });

  document.addEventListener("click", (e) => {
    if (wrap.contains(e.target)) return;
    if (list.contains(e.target)) return;
    if (!list.hidden) closeList();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeList();
  });

  window.addEventListener("scroll", onViewportChange, true);
  window.addEventListener("resize", onViewportChange);
}

/** @type {string} */
let currentPreset = "all";
let fetchTimer = null;
/** @type {Array<Record<string, string>>} */
let leadsCache = [];

/** @type {Set<string>} */
const selectedIds = new Set();

const sortState = {
  key: "created_at",
  dir: "desc",
};

const defaultSortDir = {
  created_at: "desc",
  name: "asc",
  email: "asc",
  source: "asc",
  crm_status: "asc",
};

let selectedLeadId = null;

function openFormModal() {
  const dlg = $("#form-modal");
  if (typeof dlg.showModal === "function") dlg.showModal();
  else dlg.setAttribute("open", "");
}

function closeFormModal() {
  const dlg = $("#form-modal");
  if (typeof dlg.close === "function") dlg.close();
  else dlg.removeAttribute("open");
}

function setFilterLoading(isLoading) {
  const el = $("#filter-status");
  el.classList.toggle("is-loading", isLoading);
}

function setFilterSummary(text) {
  $("#filter-status").textContent = text;
}

function getVisibleSortedLeads() {
  return sortLeads(leadsCache, sortState.key, sortState.dir);
}

function sortLabel() {
  const labels = {
    created_at: "Received",
    name: "Name",
    email: "Email",
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

function updateBulkBar() {
  const bar = $("#bulk-bar");
  const n = selectedIds.size;
  if (n === 0) {
    bar.classList.remove("is-active");
    bar.classList.add("is-collapsed");
    return;
  }
  bar.classList.remove("is-collapsed");
  bar.classList.add("is-active");
  $("#bulk-count").textContent = `${n} selected`;
}

function syncSelectAllCheckbox() {
  const el = $("#select-all");
  const visible = getVisibleSortedLeads().map((r) => r.lead_id);
  if (!visible.length) {
    el.checked = false;
    el.indeterminate = false;
    return;
  }
  const n = visible.filter((id) => selectedIds.has(id)).length;
  el.checked = n === visible.length && n > 0;
  el.indeterminate = n > 0 && n < visible.length;
}

function renderTable() {
  const tbody = $("#tbody");
  const sorted = getVisibleSortedLeads();

  if (!sorted.length) {
    const hasFilters = Boolean(
      $("#f-source").value.trim() ||
        $("#f-status").value ||
        $("#f-from").value ||
        $("#f-to").value ||
        currentPreset !== "all"
    );
    tbody.innerHTML = `<tr><td colspan="${COLS}" class="empty">${
      hasFilters ? "No leads match these filters." : "No leads loaded yet."
    }</td></tr>`;
    $("#count").textContent = "(0)";
    selectedIds.clear();
    updateBulkBar();
    syncSelectAllCheckbox();
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
    .map((row) => {
      const id = row.lead_id;
      const checked = selectedIds.has(id) ? "checked" : "";
      return `
      <tr data-id="${escapeHtml(id)}">
        <td class="td-check">
          <input type="checkbox" class="table-check row-check" data-id="${escapeHtml(id)}" ${checked} aria-label="Select ${escapeHtml(row.name || id)}" />
        </td>
        <td>${formatDate(row.created_at)}</td>
        <td>${escapeHtml(row.name)}</td>
        <td class="table-col-email" title="${escapeHtml(row.email)}">${escapeHtml(row.email)}</td>
        <td><code>${escapeHtml(row.source)}</code></td>
        <td>${statusBadge(row.crm_status)}</td>
        <td class="td-actions">
          <span class="row-actions">
            <button type="button" class="linkish open-detail">View</button>
            <button type="button" class="linkish linkish-danger btn-delete-row" data-id="${escapeHtml(id)}">Delete</button>
          </span>
        </td>
      </tr>
    `;
    })
    .join("");

  syncSelectAllCheckbox();
  updateBulkBar();
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
  tbody.innerHTML = `<tr><td colspan="${COLS}" class="empty">Loading…</td></tr>`;
  setFilterLoading(true);

  try {
    const res = await api(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="${COLS}" class="empty">Could not load leads.</td></tr>`;
      showToast(data.message || `Error ${res.status}`, "error");
      $("#count").textContent = "";
      leadsCache = [];
      setFilterSummary("");
      setFilterLoading(false);
      return;
    }
    leadsCache = data.items || [];
    const validIds = new Set(leadsCache.map((r) => r.lead_id));
    [...selectedIds].forEach((id) => {
      if (!validIds.has(id)) selectedIds.delete(id);
    });
    setFilterLoading(false);
    updateSortHeaders();
    renderTable();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="${COLS}" class="empty">Network error.</td></tr>`;
    showToast(String(e.message || e), "error");
    $("#count").textContent = "";
    leadsCache = [];
    setFilterSummary("");
    setFilterLoading(false);
  }
}

async function deleteLeadById(leadId) {
  if (!leadId) return;
  if (!confirm("Delete this lead from the sheet? This cannot be undone.")) return;
  try {
    const res = await api(`/api/leads/${encodeURIComponent(leadId)}`, { method: "DELETE" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showToast(data.message || `Delete failed (${res.status})`, "error");
      return;
    }
    selectedIds.delete(leadId);
    showToast(data.message || "Lead deleted", "delete");
    scheduleFetch(0);
  } catch (err) {
    showToast(String(err.message || err), "error");
  }
}

async function bulkDeleteSelected() {
  const ids = [...selectedIds];
  if (!ids.length) return;
  if (
    !confirm(`Delete ${ids.length} lead(s) from the sheet? This cannot be undone.`)
  ) {
    return;
  }
  try {
    const res = await api("/api/leads/bulk-delete", {
      method: "POST",
      body: JSON.stringify({ lead_ids: ids }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showToast(data.message || `Bulk delete failed (${res.status})`, "error");
      return;
    }
    selectedIds.clear();
    showToast(data.message || "Leads deleted", "delete");
    scheduleFetch(0);
  } catch (err) {
    showToast(String(err.message || err), "error");
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

$("#select-all").addEventListener("change", (e) => {
  const visible = getVisibleSortedLeads().map((r) => r.lead_id);
  if (e.target.checked) {
    visible.forEach((id) => selectedIds.add(id));
  } else {
    visible.forEach((id) => selectedIds.delete(id));
  }
  renderTable();
});

$("#tbody").addEventListener("change", (e) => {
  const cb = e.target.closest(".row-check");
  if (!cb) return;
  const id = cb.dataset.id;
  if (!id) return;
  if (cb.checked) selectedIds.add(id);
  else selectedIds.delete(id);
  syncSelectAllCheckbox();
  updateBulkBar();
});

$("#bulk-delete").addEventListener("click", () => bulkDeleteSelected());
$("#bulk-clear").addEventListener("click", () => {
  selectedIds.clear();
  renderTable();
});

$("#clear-filters").addEventListener("click", () => {
  $("#f-source").value = "";
  setCrmFilterValue("");
  currentPreset = "all";
  $$(".chip-date").forEach((b) => {
    b.setAttribute("aria-pressed", b.dataset.preset === "all" ? "true" : "false");
  });
  $("#f-from").value = "";
  $("#f-to").value = "";
  $("#date-custom-wrap").classList.add("hidden");
  sortState.key = "created_at";
  sortState.dir = "desc";
  selectedIds.clear();
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
  const delBtn = e.target.closest(".btn-delete-row");
  if (delBtn) {
    e.preventDefault();
    await deleteLeadById(delBtn.dataset.id);
    return;
  }
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

$("#btn-delete-detail").addEventListener("click", async () => {
  if (!selectedLeadId) return;
  const id = selectedLeadId;
  closeModal();
  await deleteLeadById(id);
});

$("#toggle-form").addEventListener("click", () => openFormModal());
$("#cancel-form").addEventListener("click", () => closeFormModal());
$("#form-modal-close").addEventListener("click", () => closeFormModal());
$("#form-modal").addEventListener("cancel", (e) => {
  e.preventDefault();
  closeFormModal();
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
    closeFormModal();
    scheduleFetch(0);
  } catch (err) {
    showToast(String(err.message || err), "error");
  }
});

initCrmStatusDropdown();
setCrmFilterValue("");
updateSortHeaders();
loadLeads();
