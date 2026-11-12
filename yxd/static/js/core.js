/* 印小单 · 基础工具 */

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

export function money(n, digits = 2) {
  const x = Number(n);
  if (!isFinite(x)) return "¥0.00";
  return "¥" + x.toFixed(digits).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function moneyShort(n) {
  const x = Number(n) || 0;
  if (x >= 10000) return "¥" + (x / 10000).toFixed(1) + "万";
  return money(x, x >= 1000 ? 0 : 2);
}

export function num(n, digits = 0) {
  const x = Number(n);
  if (!isFinite(x)) return "0";
  return x.toFixed(digits).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function pct(n, digits = 0) {
  return (Number(n || 0) * 100).toFixed(digits) + "%";
}

export function fmtDate(s, withTime = false) {
  if (!s) return "—";
  const str = String(s).replace("T", " ");
  const parts = str.split(" ");
  return withTime ? `${parts[0]} ${(parts[1] || "").slice(0, 5)}` : parts[0];
}

export function timeAgo(s) {
  if (!s) return "";
  const t = new Date(String(s).replace(" ", "T")).getTime();
  if (!t) return "";
  const d = Date.now() - t;
  if (d < 60000) return "刚刚";
  if (d < 3600000) return Math.floor(d / 60000) + " 分钟前";
  if (d < 86400000) return Math.floor(d / 3600000) + " 小时前";
  if (d < 86400000 * 7) return Math.floor(d / 86400000) + " 天前";
  return fmtDate(s);
}

export const STATUS = {
  active: "有效", converted: "已下单", expired: "已过期", closed: "已关闭",
  pending: "待确认", confirmed: "已确认", producing: "生产中",
  shipped: "已发货", completed: "已完成", cancelled: "已取消",
};
export const PAYMENT = { unpaid: "未付款", deposit: "已付定金", paid: "已付全款" };
export const MODES = { sample: "打样", custom: "全定制", overprint: "成品加印" };

export function statusName(s) { return STATUS[s] || s || "—"; }
export function statusClass(s) {
  if (["active", "converted", "expired", "closed", "pending", "confirmed", "producing", "shipped", "completed", "cancelled"].includes(s)) return s;
  return "";
}
export function modeName(s) { return MODES[s] || s || ""; }

export function debounce(fn, wait = 220) {
  let t = null;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

export function nextFrame(fn) { requestAnimationFrame(() => requestAnimationFrame(fn)); }

export function toast(msg, type = "") {
  const root = $("#toast-root");
  if (!root) return;
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  root.appendChild(el);
  setTimeout(() => {
    el.style.transition = "opacity .25s, transform .25s";
    el.style.opacity = "0";
    el.style.transform = "translateY(6px)";
    setTimeout(() => el.remove(), 260);
  }, 2800);
}

export function openModal(html, opts = {}) {
  closeModal();
  const root = $("#modal-root");
  const mask = document.createElement("div");
  mask.className = "modal-mask";
  mask.innerHTML = `<div class="modal ${opts.wide ? "wide" : ""}" role="dialog" aria-modal="true">${html}</div>`;
  root.appendChild(mask);
  const close = () => closeModal();
  mask.addEventListener("click", (e) => { if (e.target === mask) close(); });
  mask.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", close));
  if (opts.onMount) opts.onMount(mask.querySelector(".modal"));
  return mask;
}

export function closeModal() {
  const root = $("#modal-root");
  if (root) root.innerHTML = "";
}

export function confirmDialog(message, opts = {}) {
  return new Promise((resolve) => {
    const mask = openModal(`
      <div class="modal-head"><h3>${esc(opts.title || "请确认")}</h3><button class="x" data-close>×</button></div>
      <div class="modal-body"><p style="font-size:13px;color:var(--ink-2);line-height:1.8">${message}</p></div>
      <div class="modal-foot">
        <button class="btn ghost" data-no>取消</button>
        <button class="btn ${opts.danger ? "danger" : "primary"}" data-yes>${esc(opts.ok || "确认")}</button>
      </div>`, { wide: false });
    mask.querySelector("[data-yes]").addEventListener("click", () => { closeModal(); resolve(true); });
    mask.querySelector("[data-no]").addEventListener("click", () => { closeModal(); resolve(false); });
    mask.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => resolve(false)));
  });
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("已复制", "ok");
    return true;
  } catch (e) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); toast("已复制", "ok"); return true; } catch (e2) { toast("复制失败，请手动选择", "err"); return false; }
  }
}

export function qrSvg(text, size = 200) {
  try {
    const qr = window.qrcode(0, "M");
    qr.addData(text);
    qr.make();
    return qr.createSvgTag({ cellSize: 4, margin: 2, scalable: true });
  } catch (e) {
    return "";
  }
}

export function parseHash() {
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, qs] = raw.split("?");
  const query = {};
  new URLSearchParams(qs || "").forEach((v, k) => { query[k] = v; });
  return { path: path || "/", query, raw };
}

export function navigate(path, replace = false) {
  const target = "#" + (path.startsWith("/") ? path : "/" + path);
  if (replace) history.replaceState(null, "", target);
  else location.hash = target;
}

export function goBack(fallback = "/") {
  if (history.length > 1) history.back();
  else navigate(fallback);
}

export function agentCode() {
  const q = new URLSearchParams(location.search);
  return (q.get("a") || localStorage.getItem("yxd_agent_code") || "").toUpperCase();
}

export function setAgentCode(code) {
  if (code) localStorage.setItem("yxd_agent_code", String(code).toUpperCase());
  else localStorage.removeItem("yxd_agent_code");
}

export function qs(params) {
  const p = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, v);
  });
  const s = p.toString();
  return s ? "?" + s : "";
}

export function absoluteUrl(path) {
  return location.origin + (path.startsWith("/") ? path : "/" + path);
}

export function skeleton(w = "100%", h = 14) {
  return `<span class="skeleton" style="display:inline-block;width:${w};height:${h}px;vertical-align:middle"></span>`;
}

export function emptyState(title, desc = "", action = "") {
  return `<div class="empty"><div class="big">${esc(title)}</div><p>${esc(desc)}</p>${action || ""}</div>`;
}

export function priceFrom(p) {
  if (!p || !p.price_from) return "";
  return p.price_from;
}

export function qtyText(n) { return num(n) + " 件"; }

export const ICONS = {
  home: '<path d="M3 10.6 12 3l9 7.6"/><path d="M5.5 9.5V21h13V9.5"/><path d="M9.5 21v-6h5v6"/>',
  shop: '<path d="M4 8h16l-1 12H5L4 8Z"/><path d="M8 8V6a4 4 0 0 1 8 0v2"/><path d="M9 12h6"/>',
  orders: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5"/><path d="M9 12h7M9 16h5"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  admin: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 4v5M16 4v5"/><path d="M7 14h4M7 17h7"/>',
  arrow: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  back: '<path d="M19 12H5"/><path d="m11 6-6 6 6 6"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  phone: '<path d="M5 4h4l2 5-3 2a12 12 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/>',
  print: '<path d="M7 8V3h10v5"/><rect x="4" y="8" width="16" height="9" rx="2"/><path d="M7 14h10v7H7z"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 10.5 6.8-4M8.6 13.5l6.8 4"/>',
  link: '<path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/>',
  download: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M4 21h16"/>',
  truck: '<path d="M3 6h11v10H3z"/><path d="M14 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
  shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3Z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/>',
  calc: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h2M14 11h2M8 15h2M14 15h2M8 19h2M14 19h2"/>',
  edit: '<path d="M4 20h4L20 8l-4-4L4 16v4Z"/><path d="m14 6 4 4"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14"/><path d="M10 11v6M14 11v6"/>',
  qr: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3h-3zM20 14v3M14 20h3M20 20h1"/>',
  logout: '<path d="M10 4H4v16h6"/><path d="M14 8l4 4-4 4M8 12h10"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21h-4v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H3v-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6V3h4v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.1v4H21a1.7 1.7 0 0 0-1.6 1Z"/>',
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  product: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/>',
  library: '<path d="M4 4h4v16H4zM10 4h4v16h-4zM16 5l4 15-4 1-4-15z"/>',
  factory: '<path d="M3 21V9l6 4V9l6 4V4h3v17H3Z"/><path d="M7 17h2M13 17h2M19 17h1"/>',
  phone: '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
  agents: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 21c1-4 3.6-6 6.5-6s5.5 2 6.5 6"/><circle cx="18" cy="9" r="2.5"/><path d="M16 15c2.8-.5 5 1.2 5.5 4"/>',
  quote: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
  spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  filter: '<path d="M3 5h18M6 12h12M10 19h4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  boxes: '<path d="m12 3 7 4v6l-7 4-7-4V7l7-4Z"/><path d="m5 7 7 4 7-4M12 11v6"/><path d="m3 13 5 3v5l-5-3v-5ZM21 13l-5 3v5l5-3v-5Z"/>',
};

export function icon(name, size = 18, stroke = 1.7) {
  return `<svg class="ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.spark}</svg>`;
}
