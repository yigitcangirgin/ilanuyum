// İlanUyum front-end: plain fetch + DOM APIs (user data only via textContent).
"use strict";

const TOKEN_KEY = "ilanuyum_token";
const STATUSES = ["applied", "interview", "offer", "rejected"];

const $ = (id) => document.getElementById(id);
const getToken = () => {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
};
const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
const clearToken = () => {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
};

function showError(el, message) {
  el.textContent = message;
  el.hidden = !message;
}

// FastAPI returns {detail: "text"} or {detail: [{loc, msg}, ...]} for 422.
function errorMessage(body, fallback) {
  const d = body && body.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d.map((e) => {
      const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : "";
      return field ? `${field}: ${e.msg}` : e.msg;
    }).join("; ");
  }
  return fallback;
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(path, { ...options, headers });
  const isAuthCall = path.startsWith("/auth/login") || path.startsWith("/auth/register");
  if (res.status === 401 && !isAuthCall) {
    clearToken();
    window.location.href = "/";
    throw new Error("Session expired");
  }
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new Error(errorMessage(body, `Request failed (${res.status})`));
  return body;
}

const jsonOptions = (method, data) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

/* ---------- Landing page ---------- */

async function login(email, password) {
  const form = new URLSearchParams({ username: email, password });
  const data = await request("/auth/login", { method: "POST", body: form });
  setToken(data.access_token);
  window.location.href = "/app";
}

function initIndex() {
  if (getToken()) { window.location.href = "/app"; return; }

  $("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("login-error");
    showError(err, "");
    const fd = new FormData(e.target);
    try {
      await login(fd.get("username"), fd.get("password"));
    } catch (ex) {
      showError(err, ex.message);
    }
  });

  $("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("register-error");
    showError(err, "");
    const fd = new FormData(e.target);
    const email = fd.get("email");
    const password = fd.get("password");
    try {
      await request("/auth/register", jsonOptions("POST", { email, password }));
      await login(email, password);
    } catch (ex) {
      showError(err, ex.message);
    }
  });
}

/* ---------- Dashboard ---------- */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function statusSelect(app) {
  const select = el("select", `status-select status-${app.status}`);
  select.setAttribute("aria-label", `Status for ${app.company}`);
  for (const s of STATUSES) {
    const opt = el("option", "", s.charAt(0).toUpperCase() + s.slice(1));
    opt.value = s;
    opt.selected = s === app.status;
    select.appendChild(opt);
  }
  select.addEventListener("change", async () => {
    try {
      await request(`/applications/${app.id}`, jsonOptions("PATCH", { status: select.value }));
      await refresh();
    } catch (ex) {
      showError($("list-error"), ex.message);
      await refresh();
    }
  });
  return select;
}

function renderRow(app) {
  const tr = el("tr");
  const company = el("td");
  if (app.job_url) {
    const a = el("a", "", app.company);
    a.href = app.job_url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    company.appendChild(a);
  } else {
    company.textContent = app.company;
  }
  tr.appendChild(company);
  tr.appendChild(el("td", "", app.position));
  tr.appendChild(el("td", "date", app.applied_at));
  const statusCell = el("td");
  statusCell.appendChild(statusSelect(app));
  tr.appendChild(statusCell);
  tr.appendChild(el("td", "notes", app.notes || ""));

  const actions = el("td");
  const del = el("button", "btn btn-danger", "Delete");
  del.type = "button";
  del.setAttribute("aria-label", `Delete ${app.company} - ${app.position}`);
  del.addEventListener("click", async () => {
    if (!window.confirm(`Delete application at ${app.company}?`)) return;
    try {
      await request(`/applications/${app.id}`, { method: "DELETE" });
      await refresh();
    } catch (ex) {
      showError($("list-error"), ex.message);
    }
  });
  actions.appendChild(del);
  tr.appendChild(actions);
  return tr;
}

async function loadStats() {
  const stats = await request("/applications/stats");
  $("stat-total").textContent = stats.total;
  for (const s of STATUSES) $(`stat-${s}`).textContent = stats.by_status[s] ?? 0;
}

async function loadList() {
  const filter = $("status-filter").value;
  const query = filter ? `?status=${encodeURIComponent(filter)}` : "";
  const items = await request(`/applications${query}`);
  const body = $("app-rows");
  body.replaceChildren(...items.map(renderRow));
  $("empty-msg").hidden = items.length > 0;
}

async function refresh() {
  try {
    showError($("list-error"), "");
    await Promise.all([loadStats(), loadList()]);
  } catch (ex) {
    showError($("list-error"), ex.message);
  }
}

function todayIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

async function onAdd(e) {
  e.preventDefault();
  const err = $("add-error");
  showError(err, "");
  const fd = new FormData(e.target);
  const payload = {
    company: fd.get("company"),
    position: fd.get("position"),
    job_url: fd.get("job_url") || null,
    status: fd.get("status"),
    applied_at: fd.get("applied_at") || todayIso(),
    notes: fd.get("notes") || null,
  };
  try {
    await request("/applications", jsonOptions("POST", payload));
    e.target.reset();
    $("f-date").value = todayIso();
    await refresh();
  } catch (ex) {
    showError(err, ex.message);
  }
}

async function initDashboard() {
  if (!getToken()) { window.location.href = "/"; return; }
  $("f-date").value = todayIso();
  $("logout-btn").addEventListener("click", () => {
    clearToken();
    window.location.href = "/";
  });
  $("add-form").addEventListener("submit", onAdd);
  $("status-filter").addEventListener("change", refresh);
  try {
    const me = await request("/auth/me");
    $("user-email").textContent = me.email;
  } catch (ex) {
    showError($("list-error"), ex.message);
  }
  await refresh();
}

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  if (page === "index") initIndex();
  else if (page === "dashboard") initDashboard();
});
