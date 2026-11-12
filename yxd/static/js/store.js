/* 全局状态：站点信息、登录身份、渠道、订单缓存 */

import { api } from "./api.js";
import { agentCode as readAgentCode, setAgentCode } from "./core.js";

export const state = {
  site: null,
  categories: [],
  user: null,
  agent: null,
  agentCode: "",
  structures: [],
  booted: false,
  markup: null,
};

export async function boot() {
  let code = readAgentCode();
  if (code) setAgentCode(code);
  let data;
  try {
    data = await api.bootstrap(code);
  } catch (e) {
    data = await api.bootstrap("");
    code = "";
  }
  state.site = data.site;
  state.categories = data.categories || [];
  state.structures = data.structures || [];
  state.agent = data.agent || null;
  if (code && !data.agent) {
    // 无效渠道码：不阻断访问，清掉以免影响报价
    setAgentCode("");
    state.agentCode = "";
  } else {
    state.agentCode = code || "";
  }
  if (state.agent && localStorage.getItem("yxd_markup_" + state.agentCode)) {
    state.markup = Number(localStorage.getItem("yxd_markup_" + state.agentCode));
  }
  try {
    const me = await api.me();
    state.user = me.user || null;
  } catch (e) {
    state.user = null;
  }
  state.booted = true;
}

export async function refreshUser() {
  try {
    const me = await api.me();
    state.user = me.user || null;
  } catch (e) {
    state.user = null;
  }
  return state.user;
}

export function isAdmin() { return state.user && state.user.role === "admin"; }
export function isAgent() { return state.user && state.user.role === "agent"; }

export function setMarkup(v) {
  state.markup = Number(v);
  if (state.agentCode) localStorage.setItem("yxd_markup_" + state.agentCode, String(v));
}

export function markupFor(agent) {
  if (state.markup !== null && isAgent()) return state.markup;
  if (agent && agent.default_markup != null) return Number(agent.default_markup);
  return Number(state.user && state.user.default_markup) || 0.28;
}

export function saveCustomerDraft(obj) {
  try { localStorage.setItem("yxd_customer", JSON.stringify(obj)); } catch (e) {}
}
export function loadCustomerDraft() {
  try { return JSON.parse(localStorage.getItem("yxd_customer") || "{}") || {}; } catch (e) { return {}; }
}

export function saveLastOrder(order) {
  try { sessionStorage.setItem("yxd_last_order_" + order.no, JSON.stringify(order)); } catch (e) {}
}
export function getLastOrder(no) {
  try { return JSON.parse(sessionStorage.getItem("yxd_last_order_" + no) || "null"); } catch (e) { return null; }
}

export function saveOrderPhone(phone) {
  try { localStorage.setItem("yxd_order_phone", phone); } catch (e) {}
}
export function getOrderPhone() {
  try { return localStorage.getItem("yxd_order_phone") || ""; } catch (e) { return ""; }
}
