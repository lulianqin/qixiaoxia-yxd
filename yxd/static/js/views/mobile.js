import { api } from "../api.js";
import { isAdmin } from "../store.js";
import { esc, money, num, icon, toast, navigate } from "../core.js";

const PLACEHOLDER = "/assets/ui/placeholder.svg";
const DEFAULTS = { mode: "home", provider: "统一配送", warehouse: "杭州中心仓", base_fee: 10, per_kg: 1.8, free_over: 3000, lead_days: 1, included: true, note: "全国送货上门" };

function idOf(x) { return typeof x === "string" ? x : (x && x.id) || ""; }

function resolveView(p, libs) {
  const libMats = (libs && libs.materials) || [];
  const libProcs = (libs && libs.processes) || [];
  const libPacks = (libs && libs.packagings) || [];
  const mats = (p.materials || []).map((x) => typeof x === "string" ? libMats.find((m) => m.id === x) : x).filter(Boolean);
  const required = ((p.processes || {}).required || []).map((x) => typeof x === "string" ? libProcs.find((q) => q.id === x) : x).filter(Boolean);
  const optional = ((p.processes || {}).optional || []).map((x) => typeof x === "string" ? libProcs.find((q) => q.id === x) : x).filter(Boolean);
  const packs = (p.packagings || []).map((x) => typeof x === "string" ? libPacks.find((q) => q.id === x) : x).filter(Boolean);
  return { mats, required, optional, packs };
}

function defaultConfig(p, view) {
  const modes = (p.modes || ["custom"]).filter((m) => m !== "standard" && m !== "sample");
  const mode = modes.includes("custom") ? "custom" : (modes[0] || "custom");
  const dims = {};
  if (p.stock && p.stock.dims) Object.assign(dims, p.stock.dims);
  const aux = {};
  (p.aux_groups || []).forEach((g) => {
    const opts = g.options || [];
    const def = opts.find((o) => o.default) || opts[0];
    aux[g.id] = def ? def.material_id : null;
  });
  const matIds = view.mats.map((m) => m.id);
  const packIds = view.packs.map((x) => x.id);
  return {
    mode,
    qty: (p.quantity && p.quantity.min) || 1,
    dims,
    size_name: "自定义",
    material_id: matIds.includes(p.default_material) ? p.default_material : (matIds[0] || ""),
    aux,
    colors: (p.colors || []).includes(p.default_colors) ? p.default_colors : ((p.colors || [1])[0] || 1),
    processes: [],
    packaging_id: packIds.includes(p.default_packaging) ? p.default_packaging : (packIds[0] || ""),
    overprint_method: (p.overprint_methods && p.overprint_methods[0] && p.overprint_methods[0].id) || "",
  };
}

function modeName(m) { return { custom: "全定制", overprint: "成品加印", standard: "标准定价" }[m] || m; }
function dimsText(d) { return [d.L, d.W, d.H].filter((x) => x != null && x !== "").join(" × ") + " mm"; }

// ----------------------------------------------------------- standalone page
export async function renderMobile(root, params = {}) {
  const admin = isAdmin();
  let p;
  let libs = null;
  try {
    if (admin) {
      const [pd, ld] = await Promise.all([api.adminProduct(params.id), api.libraries()]);
      p = pd.product;
      libs = ld;
    } else {
      p = (await api.product(params.id)).product;
    }
  } catch (e) {
    document.body.className = "mobile-preview-body";
    root.innerHTML = `<div class="mp-error">商品页面加载失败：${esc(e.message)}<br><a href="#/admin">返回后台</a></div>`;
    return;
  }
  const isStd = p.pricing_mode === "standard";
  const view = resolveView(p, libs);
  const cfg = defaultConfig(p, view);
  let quote = null;
  let sources = [];
  let err = "";
  let busy = false;
  let quoted = false;

  document.body.className = "mobile-preview-body";
  document.title = "在线报价 · " + (p.name || "印小单");
  renderPage();

  function renderPage(keepScroll = false) {
    const scroll = keepScroll ? (root.querySelector("#mpScroll")?.scrollTop || 0) : 0;
    root.innerHTML = pageHtml(p, cfg, view, quote, sources, admin, isStd, err, busy, quoted, sizeReady());
    bind();
    const sc = root.querySelector("#mpScroll");
    if (sc && scroll) sc.scrollTop = scroll;
  }

  function changed() {
    if (quoted) refresh();
    else syncControls();
  }

  function syncControls() {
    root.querySelectorAll("[data-preset]").forEach((b) => {
      const preset = (p.size_presets || [])[Number(b.dataset.preset)];
      b.classList.toggle("active", !!preset && cfg.size_name === preset.name);
    });
    root.querySelectorAll("[data-custom-size]").forEach((b) => b.classList.toggle("active", cfg.size_name === "自定义"));
    root.querySelectorAll("[data-dim]").forEach((inp) => {
      if (document.activeElement === inp) return;
      const v = cfg.dims[inp.dataset.dim];
      inp.value = v == null ? "" : v;
    });
    root.querySelectorAll("[data-material]").forEach((b) => b.classList.toggle("active", cfg.material_id === b.dataset.material));
    root.querySelectorAll("[data-aux]").forEach((b) => {
      const [gid, mid] = b.dataset.aux.split("::");
      b.classList.toggle("active", (cfg.aux[gid] || "") === (mid || ""));
    });
    root.querySelectorAll("[data-color]").forEach((b) => b.classList.toggle("active", Number(cfg.colors) === Number(b.dataset.color)));
    root.querySelectorAll("[data-proc]").forEach((b) => b.classList.toggle("active", (cfg.processes || []).includes(b.dataset.proc)));
    root.querySelectorAll("[data-pack]").forEach((b) => b.classList.toggle("active", cfg.packaging_id === b.dataset.pack));
    root.querySelectorAll("[data-opm]").forEach((b) => b.classList.toggle("active", cfg.overprint_method === b.dataset.opm));
    root.querySelectorAll("[data-qty]").forEach((b) => b.classList.toggle("active", Number(b.dataset.qty) === Number(cfg.qty)));
    const qty = root.querySelector("#mpQty");
    if (qty && document.activeElement !== qty) qty.value = cfg.qty;
    const hint = root.querySelector("#mpSizeHint");
    if (hint) hint.textContent = Object.values(cfg.dims).some((x) => Number(x) > 0) ? "成品 " + dimsText(cfg.dims) + " · 系统自动展开并加出血" : "选择上方标准尺寸，或直接输入长宽高";
    const btn = root.querySelector("#mpQuote");
    if (btn) {
      const ready = sizeReady();
      btn.disabled = !ready;
      btn.textContent = ready ? "获取报价" : "先选尺寸";
    }
  }

  function sizeReady() {
    if (p.kind === "overprint") return true;
    const fields = (p.dim_fields || []).filter((f) => !f.hidden);
    if (!fields.length) return true;
    return fields.every((f) => {
      const v = Number(cfg.dims[f.key]);
      return v > 0 && (f.min == null || v >= Number(f.min)) && (f.max == null || v <= Number(f.max));
    });
  }

  function requestQuote() {
    if (!sizeReady()) { toast("请先选择预设尺寸，或输入自定义成品尺寸", "err"); return; }
    quoted = true;
    refresh();
  }

  async function refresh() {
    if (busy) return;
    busy = true;
    const u = root.querySelector("#mpUnit");
    if (u) u.textContent = "…";
    try {
      if (admin) {
        const d = await api.quoteCompare({ product_id: p.id, config: quoteConfig() });
        quote = d.recommended_quote || d.quote;
        sources = d.sources || [];
      } else {
        const d = await api.quote({ product_id: p.id, config: quoteConfig() });
        quote = d.quote;
        sources = [];
      }
      err = "";
    } catch (e) {
      quote = null;
      err = e.message || "试算失败";
    } finally {
      busy = false;
      renderPage(true);
    }
  }

  function quoteConfig() {
    const out = {
      mode: cfg.mode, qty: Number(cfg.qty) || 1,
      dims: Object.assign({}, cfg.dims),
      material_id: cfg.material_id,
      aux: Object.assign({}, cfg.aux),
      colors: Number(cfg.colors),
      processes: (cfg.processes || []).slice(),
      packaging_id: cfg.packaging_id,
    };
    if (cfg.overprint_method) out.overprint_method = cfg.overprint_method;
    return out;
  }

  function bind() {
    const back = root.querySelector("[data-mp-back]");
    if (back && !admin) back.setAttribute("href", "#/admin");

    root.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => {
      cfg.mode = b.dataset.mode;
      cfg.qty = Math.max(Number(cfg.qty) || 1, (p.quantity && p.quantity.min) || 1);
      changed();
    }));

    root.querySelectorAll("[data-custom-size]").forEach((b) => b.addEventListener("click", () => {
      cfg.size_name = "自定义";
      changed();
    }));

    root.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => {
      const preset = (p.size_presets || [])[Number(b.dataset.preset)];
      if (!preset) return;
      cfg.dims = Object.assign({}, preset.dims);
      cfg.size_name = preset.name;
      changed();
    }));

    root.querySelectorAll("[data-dim]").forEach((inp) => inp.addEventListener("input", () => {
      cfg.dims[inp.dataset.dim] = inp.value === "" ? null : Number(inp.value);
      cfg.size_name = "自定义";
      const hint = root.querySelector("#mpSizeHint");
      if (hint) hint.textContent = Object.values(cfg.dims).some((x) => Number(x) > 0) ? "成品 " + dimsText(cfg.dims) + " · 系统自动展开并加出血" : "选择上方标准尺寸，或直接输入长宽高";
      const btn = root.querySelector("#mpQuote");
      if (btn) { const ready = sizeReady(); btn.disabled = !ready; btn.textContent = ready ? "获取报价" : "先选尺寸"; }
    }));
    root.querySelectorAll("[data-dim]").forEach((inp) => inp.addEventListener("change", () => {
      cfg.dims[inp.dataset.dim] = inp.value === "" ? null : Number(inp.value);
      cfg.size_name = "自定义";
      changed();
    }));

    root.querySelectorAll("[data-material]").forEach((b) => b.addEventListener("click", () => {
      cfg.material_id = b.dataset.material;
      changed();
    }));

    root.querySelectorAll("[data-aux]").forEach((b) => b.addEventListener("click", () => {
      const [gid, mid] = b.dataset.aux.split("::");
      cfg.aux[gid] = mid || null;
      changed();
    }));

    root.querySelectorAll("[data-color]").forEach((b) => b.addEventListener("click", () => {
      cfg.colors = Number(b.dataset.color);
      changed();
    }));

    root.querySelectorAll("[data-proc]").forEach((b) => b.addEventListener("click", () => {
      const id = b.dataset.proc;
      const arr = cfg.processes || [];
      cfg.processes = arr.includes(id) ? arr.filter((x) => x !== id) : arr.concat([id]);
      changed();
    }));

    root.querySelectorAll("[data-pack]").forEach((b) => b.addEventListener("click", () => {
      cfg.packaging_id = b.dataset.pack;
      changed();
    }));

    root.querySelectorAll("[data-opm]").forEach((b) => b.addEventListener("click", () => {
      cfg.overprint_method = b.dataset.opm;
      changed();
    }));

    root.querySelectorAll("[data-qty]").forEach((b) => b.addEventListener("click", () => {
      cfg.qty = Number(b.dataset.qty);
      changed();
    }));
    root.querySelector("#mpQty")?.addEventListener("change", (e) => {
      cfg.qty = Math.max(Number(e.target.value) || 1, (p.quantity && p.quantity.min) || 1);
      changed();
    });

    root.querySelector("#mpQuote")?.addEventListener("click", requestQuote);
    root.querySelector("#mpCheck")?.addEventListener("click", () => openSheet(true));
    root.querySelector("#mpDetail")?.addEventListener("click", () => openSheet(false));
    const sheet = root.querySelector("#mpSheet");
    if (sheet) {
      sheet.querySelector("[data-mp-close]")?.addEventListener("click", () => sheet.classList.remove("open"));
      sheet.querySelector(".mp-sheet-mask")?.addEventListener("click", () => sheet.classList.remove("open"));
    }
  }

  function openSheet(internal) {
    const sheet = root.querySelector("#mpSheet");
    if (!sheet) return;
    sheet.innerHTML = sheetHtml(p, quote, sources, isStd, admin && internal);
    sheet.classList.add("open");
    sheet.querySelector("[data-mp-close]")?.addEventListener("click", () => sheet.classList.remove("open"));
    sheet.querySelector(".mp-sheet-mask")?.addEventListener("click", () => sheet.classList.remove("open"));
  }
}

function pageHtml(p, cfg, view, quote, sources, admin, isStd, err, busy, quoted, ready) {
  const imgs = p.images && p.images.length ? p.images : [p.image || PLACEHOLDER];
  const modes = (p.modes || []).filter((m) => m !== "standard" && m !== "sample");
  const shown = isStd || (quoted && quote);
  const unit = isStd ? (p.standard_price || 0) : (quoted && quote ? quote.totals.unit_retail : null);
  const total = !isStd && quoted && quote ? quote.totals.retail : null;
  const lead = !isStd && quoted && quote ? quote.lead : null;
  return `<div class="mp-page">
    <header class="mp-topbar">
      ${admin ? `<a href="#/admin/products/${encodeURIComponent(p.id)}/preview" class="mp-back" data-mp-back>‹</a>` : `<span class="mp-back" style="opacity:0"></span>`}
      <div class="mp-brand"><span class="mp-mark">印</span><span>印小单</span></div>
      <span class="mp-proof-pill">${admin ? "校对预览" : "在线报价"}</span>
    </header>
    <div class="mp-scroll" id="mpScroll">
      <div class="mp-hero">
        <img src="${esc(imgs[0])}" alt="">
        <div class="mp-hero-tags"><span class="pill ${isStd ? "cream" : "gold"}">${isStd ? "标准定价" : "非标计价"}</span>${modes.map((m) => `<span class="pill cream">${esc(modeName(m))}</span>`).join("")}</div>
      </div>
      <div class="mp-content">
        <div class="mp-cat">${esc((p.category_name || p.category || "").toString().toUpperCase())}</div>
        <h1>${esc(p.name)}</h1>
        <p class="mp-sub">${esc(p.subtitle || p.description || "")}</p>
        <div class="mp-price-card">
          <div class="mp-price-main">
            <div class="mp-price-label">${isStd ? "固定售价" : (quoted ? "实时报价" : "待报价")}</div>
            <div class="mp-unit"><b id="mpUnit">${busy ? "…" : (shown ? money(unit) : "—")}</b><span> /${esc(p.unit || "个")}</span></div>
            <div class="mp-price-sub">${isStd ? `起订 ${(p.quantity && p.quantity.min) || 1} · 含税送货上门` : (total != null ? `合计 ${money(total)} · 含税送货上门` : "选择规格后点「获取报价」")}</div>
          </div>
          <div class="mp-price-side">${isStd ? `<span>交期</span><b>${p.lead_days || 3} 天</b>` : `<span>交期</span><b>${lead ? lead.min + "-" + lead.max + " 天" : "—"}</b>`}</div>
        </div>
        ${!isStd && !quoted ? `<div class="mp-quote-hint">先选择标准尺寸，或直接输入自定义长宽高；再点底部「获取报价」。</div>` : ""}
        ${err ? `<div class="mp-error">${esc(err)}</div>` : ""}
        <div class="mp-block" id="mpLogistics">${logisticsHtml(p, quote)}</div>

        ${!isStd && modes.length > 1 ? `<div class="mp-mode-tabs">${modes.map((m) => `<button class="mp-mode-tab ${cfg.mode === m ? "active" : ""}" data-mode="${m}">${esc(modeName(m))}</button>`).join("")}</div>` : ""}

        ${isStd ? standardBlock(p) : configBlocks(p, cfg, view, quote)}

        <div class="mp-block">
          <div class="mp-block-head"><h3>商品说明</h3></div>
          <p class="mp-desc">${esc(p.description || p.long_desc || "暂无描述")}</p>
          ${(p.specs || []).map((s) => `<div class="mp-spec"><span>${esc(s.label)}</span><b>${esc(s.value)}</b></div>`).join("")}
        </div>
        <div class="mp-note">${admin ? "这是后台生成的手机前端校对页，仅管理员可见；不提供下单/支付。" : "价格为实时试算，最终以业务确认和合同为准；不提供在线支付。"}</div>
      </div>
    </div>
    <div class="mp-bottombar">
      <div class="mp-bottom-price"><b id="mpBottomPrice">${busy ? "…" : (shown ? money(unit) : "—")}</b><span id="mpBottomSub">${isStd ? "固定价格" : (total != null ? `${num(cfg.qty)} 个 · 合计 ${money(total)}` : "选择规格后获取报价")}</span></div>
      ${!isStd && (!quoted || err) ? `<button class="mp-check-btn primary" id="mpQuote" ${!ready && !err ? "disabled" : ""}>${err ? "重新报价" : (ready ? "获取报价" : "先选尺寸")}</button>` : (admin ? `<button class="mp-check-btn" id="mpCheck">内部核价</button>` : `<button class="mp-check-btn" id="mpDetail">报价明细</button>`)}
    </div>
    <div class="mp-sheet" id="mpSheet"></div>
  </div>`;
}

function standardBlock(p) {
  return `<div class="mp-block"><h3>标准商品信息</h3>
    <div class="mp-spec"><span>SKU</span><b>${esc(p.sku || "—")}</b></div>
    <div class="mp-spec"><span>起订量</span><b>${(p.quantity && p.quantity.min) || 1}</b></div>
    <div class="mp-spec"><span>计价单位</span><b>${esc(p.unit || "个")}</b></div>
    <div class="mp-spec"><span>价格</span><b>${money(p.standard_price || 0)} / ${esc(p.unit || "个")}</b></div>
  </div>`;
}

function configBlocks(p, cfg, view, quote) {
  const dims = p.kind === "overprint" ? null : (p.dim_fields || []).filter((f) => !f.hidden);
  const colors = (p.colors || []).filter((c) => Number(c) >= 0);
  const out = [];

  if (p.kind !== "overprint" && dims.length) {
    out.push(`<div class="mp-block">
      <div class="mp-block-head"><h3>尺寸</h3><span>成品尺寸</span></div>
      <div class="mp-chips" style="margin-top:0">${(p.size_presets || []).map((s, i) => `<button class="mp-chip ${cfg.size_name === s.name ? "active" : ""}" data-preset="${i}">${esc(s.name)}</button>`).join("")}<button class="mp-chip ${cfg.size_name === "自定义" ? "active" : ""}" data-custom-size>自定义尺寸</button></div>
      <div class="mp-dim-grid">${dims.map((f) => `<label class="mp-dim"><span>${esc(f.label || f.key)}</span><input type="number" data-dim="${esc(f.key)}" value="${cfg.dims[f.key] != null ? cfg.dims[f.key] : ""}" placeholder="${f.min != null ? f.min + "-" + f.max : "自定义"}" min="${f.min != null ? f.min : 0}" max="${f.max != null ? f.max : 9999}"></label>`).join("")}</div>
      <div class="mp-hint" id="mpSizeHint">${Object.values(cfg.dims).some((x) => Number(x) > 0) ? "成品 " + dimsText(cfg.dims) + " · 系统自动展开并加出血" : "选择上方标准尺寸，或直接输入长宽高"}</div>
    </div>`);
  }

  if (p.kind === "overprint" && p.stock) {
    out.push(`<div class="mp-block"><div class="mp-block-head"><h3>现货规格</h3><span>成品加印</span></div>
      <div class="mp-spec"><span>现货</span><b>${esc(p.stock.name || "")}</b></div>
      <div class="mp-spec"><span>尺寸</span><b>${dimsText(p.stock.dims || {})}</b></div>
      <div class="mp-spec"><span>库存</span><b>${num(p.stock.stock_qty || 0)} 个</b></div>
      ${(p.overprint_methods || []).length ? `<div class="mp-chips">${p.overprint_methods.map((m) => `<button class="mp-chip ${cfg.overprint_method === m.id ? "active" : ""}" data-opm="${esc(m.id)}">${esc(m.name)}</button>`).join("")}</div>` : ""}
    </div>`);
  }

  if (view.mats.length) {
    out.push(`<div class="mp-block"><div class="mp-block-head"><h3>材料</h3><span>选择材质</span></div>
      <div class="mp-material-grid">${view.mats.map((m) => `<button class="mp-material ${cfg.material_id === m.id ? "active" : ""}" data-material="${esc(m.id)}">
        <img src="${esc(m.image || PLACEHOLDER)}" alt="">
        <div><b>${esc(m.name)}</b><span>${esc([m.gsm ? m.gsm + "g" : "", m.kind || ""].filter(Boolean).join(" · "))}</span></div>
      </button>`).join("")}</div>
    </div>`);
  }

  if ((p.aux_groups || []).length) {
    out.push(`<div class="mp-block"><div class="mp-block-head"><h3>辅料</h3><span>按需选择</span></div>
      ${p.aux_groups.map((g) => `<div class="mp-control-row"><span class="mp-control-label">${esc(g.name)}</span><div class="mp-chips">${(g.options || []).map((o) => `<button class="mp-chip ${cfg.aux[g.id] === o.material_id ? "active" : ""}" data-aux="${esc(g.id)}::${esc(o.material_id || "")}">${esc(o.label)}</button>`).join("")}</div></div>`).join("")}
    </div>`);
  }

  if (colors.length) {
    out.push(`<div class="mp-block"><div class="mp-block-head"><h3>印刷颜色</h3><span>单面</span></div>
      <div class="mp-chips">${colors.map((c) => `<button class="mp-chip ${Number(cfg.colors) === Number(c) ? "active" : ""}" data-color="${Number(c)}">${Number(c) === 0 ? "不印刷" : Number(c) + " 色"}</button>`).join("")}</div>
    </div>`);
  }

  const opt = view.optional || [];
  out.push(`<div class="mp-block"><div class="mp-block-head"><h3>工艺</h3><span>必选 + 可选</span></div>
    <div class="mp-chips">${view.required.map((q) => `<span class="mp-chip locked">✓ ${esc(q.name)}</span>`).join("")}${opt.map((q) => `<button class="mp-chip ${((cfg.processes || []).includes(q.id)) ? "active" : ""}" data-proc="${esc(q.id)}">${esc(q.name)}</button>`).join("")}</div>
    ${opt.length ? `<div class="mp-hint">可选工艺按需勾选，价格实时变化</div>` : ""}
  </div>`);

  if (view.packs.length) {
    out.push(`<div class="mp-block"><div class="mp-block-head"><h3>包装</h3><span>影响箱规/物流</span></div>
      <div class="mp-chips">${view.packs.map((x) => `<button class="mp-chip ${cfg.packaging_id === x.id ? "active" : ""}" data-pack="${esc(x.id)}">${esc(x.name)}</button>`).join("")}</div>
    </div>`);
  }

  const qtyMin = (p.quantity && p.quantity.min) || 1;
  const presets = (p.quantity && p.quantity.presets && p.quantity.presets.length) ? p.quantity.presets : [cfg.qty, 300, 500, 1000, 3000];
  out.push(`<div class="mp-block"><div class="mp-block-head"><h3>数量</h3><span>改数量实时比价</span></div>
    <div class="mp-qty-row"><input class="mp-qty-input" id="mpQty" type="number" value="${cfg.qty}" min="${qtyMin}"><span class="mp-qty-unit">个</span></div>
    <div class="mp-chips" style="margin-top:9px">${presets.map((q) => `<button class="mp-chip ${Number(q) === Number(cfg.qty) ? "active" : ""}" data-qty="${q}">${num(q)}</button>`).join("")}</div>
  </div>`);

  return out.join("");
}

function sourcesBlock(sources) {
  if (!sources || !sources.length) return "";
  return `<div class="mp-block" id="mpSources"><div class="mp-block-head"><h3>工厂比价</h3><span>内部校对</span></div>${sources.map((s) => `<div class="mp-source ${s.available ? "" : "off"}">
    <div class="mp-source-main"><b>${esc(s.factory.name)}</b><span>${esc((s.plan || {}).press_name || (s.available ? "" : s.error || "不可用"))}</span></div>
    <div class="mp-source-side">${s.available ? `<b>${money(s.price)}</b><span>${s.lead.min}-${s.lead.max} 天</span>` : `<b>—</b><span>不可用</span>`}</div>
    <div class="mp-source-tags">${s.is_cheapest ? "最低" : ""}${s.is_cheapest && s.is_fastest ? " · " : ""}${s.is_fastest ? "最快" : ""}</div>
  </div>`).join("")}</div>`;
}

function logisticsHtml(p, q) {
  const l = Object.assign({}, DEFAULTS, p.logistics || {});
  const cur = (q && q.logistics) || l;
  const free = cur.free === true;
  const included = l.included !== false;
  const feeText = free ? "已免运费" : (included ? "含运费" : "运费另计");
  const freeOver = Number(l.free_over) > 0 ? ` · 满 ${money(l.free_over)} 免运` : "";
  return `<div class="mp-block-head"><h3>交付</h3><span>统一送货上门</span></div>
    <div class="mp-spec"><span>交付方式</span><b>送货上门</b></div>
    <div class="mp-spec"><span>发货仓</span><b>${esc(cur.warehouse || l.warehouse)}</b></div>
    <div class="mp-spec"><span>配送</span><b>${esc(cur.provider || l.provider)} · 约 ${cur.lead_days || l.lead_days || 1} 天</b></div>
    <div class="mp-spec"><span>运费</span><b>${feeText}${freeOver}</b></div>
    <p class="mp-note" style="padding-top:6px">${esc(cur.note || l.note)}</p>`;
}

function sheetHtml(p, q, sources, isStd, internal) {
  if (isStd) {
    return `<div class="mp-sheet-mask"></div><div class="mp-sheet-body"><div class="mp-sheet-head"><h3>标准定价</h3><button data-mp-close>×</button></div>
      <div class="mp-sheet-content"><p class="mp-note">标准商品使用 ERP/商品中心固定价格，不参与展开、拼版和工艺计算。</p>
      <div class="mp-spec"><span>售价</span><b>${money(p.standard_price || 0)} / ${esc(p.unit || "个")}</b></div>
      <div class="mp-spec"><span>SKU</span><b>${esc(p.sku || "—")}</b></div></div></div>`;
  }
  if (!q) return `<div class="mp-sheet-mask"></div><div class="mp-sheet-body"><div class="mp-sheet-head"><h3>报价明细</h3><button data-mp-close>×</button></div><div class="mp-sheet-content">暂未算出报价</div></div>`;
  if (!internal) {
    return `<div class="mp-sheet-mask"></div><div class="mp-sheet-body"><div class="mp-sheet-head"><h3>报价明细</h3><button data-mp-close>×</button></div>
      <div class="mp-sheet-content">
        <div class="mp-sheet-kpis"><div><span>合计</span><b>${money(q.totals.retail)}</b></div><div><span>单件</span><b>${money(q.totals.unit_retail)}</b></div><div><span>交期</span><b>${q.lead.min}-${q.lead.max} 天</b></div></div>
        ${(q.customer_lines || []).map((l) => `<div class="mp-line"><span>${esc(l.label)}</span><b>${money(l.amount)}</b></div>`).join("")}
        <p class="mp-note">价格含税、送货上门；最终以业务确认和合同为准。</p>
      </div></div>`;
  }
  const lines = (q.lines || []).map((l) => `<div class="mp-line"><span>${esc(l.label)}</span><b>${money(l.amount)}</b></div>`).join("");
  const cust = (q.customer_lines || []).map((l) => `<div class="mp-line"><span>${esc(l.label)}</span><b>${money(l.amount)}</b></div>`).join("");
  return `<div class="mp-sheet-mask"></div><div class="mp-sheet-body">
    <div class="mp-sheet-head"><h3>内部核价</h3><button data-mp-close>×</button></div>
    <div class="mp-sheet-content">
      <div class="mp-sheet-kpis"><div><span>成本</span><b>${money(q.totals.cost)}</b></div><div><span>对外报价</span><b>${money(q.totals.retail)}</b></div><div><span>单件</span><b>${money(q.totals.unit_retail)}</b></div></div>
      <div class="mp-spec"><span>生产方案</span><b>${esc((q.plan || {}).press_name || "")}</b></div>
      <div class="mp-spec"><span>拼版</span><b>${(q.plan || {}).units_per_sheet || 0} 个 / 张</b></div>
      <div class="mp-spec"><span>交期</span><b>${q.lead.min}-${q.lead.max} 天</b></div>
      <h4>对外报价构成</h4>${cust}
      <h4>内部成本明细</h4>${lines}
      <h4>物流</h4><div class="mp-spec"><span>${esc((q.logistics || {}).warehouse || "")}</span><b>${esc((q.logistics || {}).provider || "")} · ${(q.logistics || {}).free ? "免运费" : money((q.logistics || {}).fee || 0)}</b></div>
      <h4>工厂比价</h4>${sourcesBlock(sources)}
      <p class="mp-note">内部信息仅用于校对，客户前端不展示。</p>
    </div>
  </div>`;
}

// ----------------------------------------------------------- admin iframe page
export async function renderMobileAdmin(root, params = {}, shell) {
  let p;
  try { p = (await api.adminProduct(params.id)).product; }
  catch (e) { toast(e.message, "err"); navigate("/admin/products"); return; }
  const url = "/#/m/" + encodeURIComponent(p.id);
  const shareUrl = location.origin + url;
  const localOnly = ["localhost", "127.0.0.1", "::1"].includes(location.hostname);
  const content = `
    <div class="admin-toolbar">
      <span class="pill ${p.pricing_mode === "standard" ? "cream" : "gold"}">${p.pricing_mode === "standard" ? "标准定价" : "非标计价"}</span>
      <span class="muted small">${esc(p.name)}</span>
      <div class="right">
        <a class="btn soft sm" href="${url}" target="_blank">${icon("share", 14)} 打开公开页</a>
        <a class="btn primary sm" href="#/admin/products/${encodeURIComponent(p.id)}/preview">返回商品预览</a>
      </div>
    </div>
    <div class="mp-admin-grid">
      <div class="mp-phone-frame"><div class="mp-phone-notch"></div><iframe src="${url}" title="手机前端预览"></iframe></div>
      <div>
        <div class="tech-box">
          <h4>手机前端 / 非标报价器</h4>
          <p class="small muted" style="line-height:1.8">这是实际生成的前端页面，可直接改尺寸、材料、工艺、数量并实时报价。桌面/手机都能打开。</p>
          <div class="tech-row"><span>商品</span><b>${esc(p.name)}</b></div>
          <div class="tech-row"><span>建品方式</span><b>${p.pricing_mode === "standard" ? "标准定价" : "非标计价"}</b></div>
          <div class="tech-row"><span>工厂数</span><b>${(p.source_ids || []).length} 家</b></div>
          <div class="tech-row"><span>起订量</span><b>${(p.quantity && p.quantity.min) || 1}</b></div>
          <div class="tech-row"><span>上架状态</span><b class="${p.status === "active" ? "ok" : "warn"}">${p.status === "active" ? "已上架，外部可见" : "未上架，外部不可见"}</b></div>
        </div>
        <div class="tech-box" style="margin-top:12px">
          <h4>外部分享</h4>
          <div class="copy-row"><input class="input" id="mpShareUrl" readonly value="${esc(shareUrl)}"><button class="btn primary sm" id="mpCopy">复制</button></div>
          ${localOnly ? `<div class="banner warn" style="margin-top:10px">当前地址是 localhost，只能本机打开。请用局域网 IP 或公网域名打开后台，再复制这里。</div>` : ""}
          <p class="tiny muted" style="margin-top:9px">公开页无需登录；客户只能看到价格和规格，看不到成本、工厂和内部核价。手机与电脑同 Wi-Fi 可直接访问局域网地址；外网需域名或隧道。</p>
        </div>
        <div class="tech-box" style="margin-top:12px">
          <h4>校对建议</h4>
          <p class="small muted" style="line-height:1.9">1. 改尺寸/材料/工艺/数量，确认前端展示与后台规则一致。<br>2. 点「内部核价」核对成本、拼版、物流与工厂比价。<br>3. 和业务/工厂确认最终价格后再上架。</p>
        </div>
      </div>
    </div>`;
  root.innerHTML = shell(content, "mobile-preview", "products");
  const logout = root.querySelector("#adminLogout");
  if (logout) logout.addEventListener("click", () => { location.hash = "#/admin"; });
  root.querySelector("#mpCopy")?.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(shareUrl); toast("分享链接已复制", "ok"); }
    catch (e) { toast("复制失败，请手动复制地址栏", "err"); }
  });
}
