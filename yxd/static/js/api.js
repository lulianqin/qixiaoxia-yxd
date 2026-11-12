/* API 客户端 */

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function request(method, path, body, opts = {}) {
  const init = {
    method,
    headers: { "Accept": "application/json" },
    credentials: "same-origin",
  };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let resp;
  try {
    resp = await fetch(path, init);
  } catch (e) {
    throw new ApiError("网络连接失败，请检查服务是否启动", 0, null);
  }
  const text = await resp.text();
  let json = null;
  try { json = text ? JSON.parse(text) : {}; } catch (e) { /* ignore */ }
  if (!resp.ok || !json || json.ok === false) {
    const msg = (json && json.error) || `请求失败（${resp.status}）`;
    throw new ApiError(msg, resp.status, json);
  }
  return json.data;
}

export const api = {
  bootstrap(agent) { return request("GET", "/api/bootstrap" + (agent ? "?a=" + encodeURIComponent(agent) : "")); },
  products(params = {}) {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") q.set(k, v); });
    return request("GET", "/api/products" + (q.toString() ? "?" + q.toString() : ""));
  },
  product(id, agent) { return request("GET", `/api/products/${encodeURIComponent(id)}` + (agent ? "?a=" + encodeURIComponent(agent) : "")); },
  quote(payload) { return request("POST", "/api/quote", payload); },
  quoteTable(payload) { return request("POST", "/api/quote/table", payload); },
  createQuote(payload) { return request("POST", "/api/quotes", payload); },
  quoteByNo(no) { return request("GET", `/api/quotes/${encodeURIComponent(no)}`); },
  createOrder(payload) { return request("POST", "/api/orders", payload); },
  orderByNo(no, phone) { return request("GET", `/api/orders/${encodeURIComponent(no)}` + (phone ? "?phone=" + encodeURIComponent(phone) : "")); },
  lookupOrders(phone) { return request("POST", "/api/orders/lookup", { phone }); },
  me() { return request("GET", "/api/auth/me"); },
  login(username, password) { return request("POST", "/api/auth/login", { username, password }); },
  logout() { return request("POST", "/api/auth/logout", {}); },

  agentSummary() { return request("GET", "/api/agent/summary"); },
  agentQuotes(params = {}) {
    const q = new URLSearchParams(params).toString();
    return request("GET", "/api/agent/quotes" + (q ? "?" + q : ""));
  },
  agentOrders(params = {}) {
    const q = new URLSearchParams(params).toString();
    return request("GET", "/api/agent/orders" + (q ? "?" + q : ""));
  },
  agentProfile(payload) { return request("PATCH", "/api/agent/profile", payload); },

  adminSummary() { return request("GET", "/api/admin/summary"); },
  adminCategories() { return request("GET", "/api/admin/categories"); },
  adminFactories() { return request("GET", "/api/admin/factories"); },
  saveFactory(payload) { return request("POST", "/api/admin/factories", payload); },
  deleteFactory(id) { return request("DELETE", `/api/admin/factories/${encodeURIComponent(id)}`); },
  saveCategory(payload) { return request("POST", "/api/admin/categories", payload); },
  deleteCategory(id) { return request("DELETE", `/api/admin/categories/${encodeURIComponent(id)}`); },
  adminProducts() { return request("GET", "/api/admin/products"); },
  adminProduct(id) { return request("GET", `/api/admin/products/${encodeURIComponent(id)}`); },
  exportProductsUrl() { return "/api/admin/products/export"; },
  exportProductUrl(id) { return `/api/admin/products/${encodeURIComponent(id)}/export`; },
  saveProduct(payload) { return request("POST", "/api/admin/products", payload); },
  setProductStatus(id, status) { return request("PATCH", `/api/admin/products/${encodeURIComponent(id)}/status`, { status }); },
  previewProduct(payload) { return request("POST", "/api/admin/product-preview", payload); },
  quoteCompare(payload) { return request("POST", "/api/admin/quote-compare", payload); },
  adminQuotes(params = {}) {
    const q = new URLSearchParams(params).toString();
    return request("GET", "/api/admin/quotes" + (q ? "?" + q : ""));
  },
  adminOrders(params = {}) {
    const q = new URLSearchParams(params).toString();
    return request("GET", "/api/admin/orders" + (q ? "?" + q : ""));
  },
  adminOrder(no) { return request("GET", `/api/admin/orders/${encodeURIComponent(no)}`); },
  updateOrder(no, payload) { return request("PATCH", `/api/admin/orders/${encodeURIComponent(no)}`, payload); },
  updateQuoteStatus(no, status) { return request("PATCH", `/api/admin/quotes/${encodeURIComponent(no)}`, { status }); },
  agents() { return request("GET", "/api/admin/agents"); },
  createAgent(payload) { return request("POST", "/api/admin/agents", payload); },
  updateAgent(id, payload) { return request("PATCH", `/api/admin/agents/${encodeURIComponent(id)}`, payload); },
  libraries() { return request("GET", "/api/admin/libraries"); },
  saveLibrary(table, item) { return request("POST", `/api/admin/libraries/${table}`, { item }); },
  deleteLibrary(table, id) { return request("DELETE", `/api/admin/libraries/${table}/${encodeURIComponent(id)}`); },
  settings() { return request("GET", "/api/admin/settings"); },
  saveSettings(payload) { return request("PATCH", "/api/admin/settings", payload); },
  changePassword(current, next) { return request("POST", "/api/admin/password", { current, new: next }); },
  upload(file) {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/admin/upload", { method: "POST", body: fd, credentials: "same-origin" })
      .then(async (r) => {
        const json = await r.json().catch(() => null);
        if (!r.ok || !json || json.ok === false) throw new ApiError((json && json.error) || "上传失败", r.status, json);
        return json.data;
      });
  },
  exportOrdersUrl() { return "/api/admin/export/orders.csv"; },
};

export { ApiError };
