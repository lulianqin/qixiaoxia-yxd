/* 复用组件 */

import { esc, money, num, statusName, statusClass, modeName, pct, icon } from "./core.js";

export function modePills(p) {
  const modes = p.modes || [];
  return modes.map((m) => {
    if (m === "sample") return `<span class="pill green">可打样</span>`;
    if (m === "custom") return `<span class="pill cream">全定制</span>`;
    if (m === "overprint") return `<span class="pill gold">现货加印</span>`;
    return `<span class="pill cream">${esc(modeName(m))}</span>`;
  }).join("");
}

export function productCard(p, opts = {}) {
  const price = p.price_from || p.sample_price_from;
  const unit = price ? price.unit : null;
  const qty = (p.quantity && p.quantity.min) || (p.sample && p.sample.min) || 1;
  const ctaMode = opts.mode || (p.modes.includes("custom") ? "custom" : p.modes[0]);
  return `<a class="product-card" href="#/p/${encodeURIComponent(p.id)}?mode=${ctaMode}">
    <div class="p-media">
      <img src="${esc(p.image)}" alt="${esc(p.name)}" loading="lazy">
      ${p.badge ? `<span class="p-badge">${esc(p.badge)}</span>` : ""}
      <div class="p-mode">${modePills(p)}</div>
    </div>
    <div class="p-body">
      <div class="p-cat">${esc(p.category_name || p.category || "SMALL BATCH")}</div>
      <h3>${esc(p.name)}</h3>
      <p class="p-sub">${esc(p.subtitle || p.description || "")}</p>
      <div class="p-foot">
        <div class="p-price">${unit != null ? money(unit) : "—"}<small> /件起</small></div>
        <div class="p-meta">${num(qty)} 起做<br>${p.lead_days || 5} 天出货</div>
      </div>
    </div>
  </a>`;
}

export function statusBadge(s) {
  return `<span class="status-badge ${statusClass(s)}">${esc(statusName(s))}</span>`;
}

export function sectionHead(kicker, title, desc = "", link = "") {
  return `<div class="section-head">
    <div><div class="kicker">${esc(kicker)}</div><h2 class="section-title">${title}</h2></div>
    ${desc ? `<div class="section-desc">${desc}</div>` : ""}
    ${link || ""}
  </div>`;
}

export function emptyCard(title, desc, action = "") {
  return `<div class="empty"><div class="big">${esc(title)}</div><p>${esc(desc)}</p>${action}</div>`;
}

export function processMini(p) {
  return `<div class="process-mini">
    ${p.image ? `<img src="${esc(p.image)}" alt="${esc(p.name)}" loading="lazy">` : ""}
    <div><b>${esc(p.name)}</b><span>${esc(p.method || p.category || "")}${p.days ? " · " + p.days + " 天" : ""}</span></div>
  </div>`;
}

export function specRow(label, value) {
  return `<dt>${esc(label)}</dt><dd>${value}</dd>`;
}

export function statusDot(s) {
  return `<i style="display:inline-block;width:6px;height:6px;border-radius:50%;background:currentColor;margin-right:5px"></i>`;
}

export function barChart(rows, opts = {}) {
  const max = Math.max(1, ...rows.map((r) => Number(r.n || 0)));
  return `<div class="chart">${rows.map((r) => {
    const n = Number(r.n || 0);
    const h = n ? Math.max(8, Math.round((n / max) * 100)) : 3;
    const label = n ? (opts.money ? money(r.s || 0, 0) : n) : "";
    return `<div class="bar-col"><b>${label}</b><div class="bar" style="height:${h}%;opacity:${n ? 1 : .12}"></div><span>${esc((r.d || "").slice(5))}</span></div>`;
  }).join("")}</div>`;
}
