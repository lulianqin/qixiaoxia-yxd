import { api } from "../api.js";
import { state, refreshUser, isAdmin } from "../store.js";
import { statusBadge, emptyCard, barChart, processMini } from "../components.js";
import {
  esc, money, num, pct, icon, toast, openModal, closeModal, confirmDialog,
  fmtDate, navigate,
} from "../core.js";
import { renderBuilder } from "./builder.js";
import { renderLibraries } from "./admin-libraries.js";
import { renderStandardProduct } from "./standard.js";
import { renderCategories } from "./categories.js";
import { renderFactories } from "./factories.js";
import { renderMobileAdmin } from "./mobile.js";
import { renderFactoryPrices } from "./factory-prices.js";

const NAV = [
  { key: "products", label: "商品", href: "#/admin/products", ico: "product" },
  { key: "categories", label: "类目", href: "#/admin/categories", ico: "layers" },
  { key: "advanced", label: "高级设置", href: "#/admin/advanced", ico: "settings" },
];

const TITLES = {
  dashboard: ["建品看板", "类目、商品与标准/非标建品"],
  categories: ["类目管理", "新增类目、排序与商品归属"],
  products: ["商品", "标准定价 / 非标报价商品"],
  advanced: ["高级设置", "工厂、资料库与系统参数"],
  factories: ["报价工厂", "多工厂报价数据源与比价"],
  "new-product": ["新建商品", "先选择建品方式"],
  "edit-product": ["编辑商品", "基础信息与报价规则"],
  standard: ["标准定价商品", "固定售价，沿用商品中心/ERP"],
  preview: ["商品预览", "保存后的展示效果"],
  "mobile-preview": ["手机前端报价", "真实前端非标报价器"],
  "factory-prices": ["工厂价格表", "材料 / 工艺 / 设备 / 包装独立价格"],
  libraries: ["基础资料库", "材料、工艺、设备与计价算法"],
  settings: ["系统参数", "价格链、物流与账号安全"],
  builder: ["非标建品", "展开 → 拼版 → 工艺 → 定价"],
};

export async function renderAdmin(root, params = {}) {
  document.body.className = "admin-body";
  if (!isAdmin()) return renderAdminLogin(root, params);
  const page = params.page || "products";
  if (page === "builder") return renderBuilder(root, params, shell, adminLoginGuard);
  if (page === "standard") return renderStandardProduct(root, params, shell, adminLoginGuard);
  if (page === "categories") return renderCategories(root, params, shell);
  if (page === "factories") return renderFactories(root, params, shell);
  if (page === "factory-prices") return renderFactoryPrices(root, params, shell);
  if (page === "mobile-preview") return renderMobileAdmin(root, params, shell);
  if (page === "libraries") return renderLibraries(root, params, shell);
  if (page === "new-product") return renderNewProductChoice(root, params);
  if (page === "advanced") return renderAdvanced(root, params, shell);
  if (page === "edit-product") return renderEditRouter(root, params);
  if (page === "preview") return renderProductPreview(root, params);
  if (page === "products") return renderAdminProducts(root, params);
  if (page === "settings") return renderAdminSettings(root, params);
  if (page === "quotes" || page === "orders" || page === "agents") return renderAdminProducts(root, params);
  return renderAdminProducts(root, params);
}

function adminLoginGuard(root, params) {
  return renderAdminLogin(root, params);
}

export function shell(content, page = "products", active = "") {
  const [title, desc] = TITLES[page] || TITLES.products;
  const activeKey = active || page;
  document.body.className = "admin-body";
  return `<div class="admin-shell">
    <aside class="admin-side">
      <a class="admin-brand" href="#/admin"><span class="brand-mark">印</span><div><b>印小单</b><span>ADMIN CONSOLE</span></div></a>
      <nav class="admin-nav">
        <div class="nav-label">OPERATION</div>
        ${NAV.map((n) => `<a href="${n.href}" class="${activeKey === n.key ? "active" : ""}">${icon(n.ico, 16)} ${n.label}</a>`).join("")}
      </nav>
      <div class="admin-side-foot">
        <a href="#/admin/products">${icon("product", 13)} 商品</a>
        <a href="#/admin/categories">${icon("layers", 13)} 类目</a>
        <div style="margin-top:8px">v1.2 · 极简版</div>
      </div>
    </aside>
    <div class="admin-main">
      <header class="admin-top">
        <div><div class="crumb">印小单 / ${esc(title)}</div><h1>${esc(title)}</h1></div>
        <div class="right">
          <a class="btn ghost sm" href="${api.exportProductsUrl()}" target="_blank">${icon("download", 14)} 导出商品</a>
          <div class="admin-user"><span class="admin-avatar">${esc((state.user.name || "A").slice(0, 1))}</span><span>${esc(state.user.name || "管理员")}</span></div>
          <button class="icon-btn" id="adminLogout" title="退出">${icon("logout", 15)}</button>
        </div>
      </header>
      <div class="admin-content">
        <div class="page-title"><div><h2>${esc(title)}</h2><p>${esc(desc || "")}</p></div><div class="right">${extraActions(page)}</div></div>
        ${content}
      </div>
    </div>
  </div>`;
}

function extraActions(page) {
  if (page === "libraries") return `<a class="btn soft sm" href="#/admin/products/new">${icon("product", 14)} 用资料库建品</a>`;
  return "";
}

export function afterShell(root) {
  const logout = root.querySelector("#adminLogout");
  if (logout) logout.addEventListener("click", async () => {
    await api.logout();
    await refreshUser();
    toast("已退出", "ok");
    navigate("/admin");
    renderAdminLogin(root);
  });
}

// ---------------------------------------------------------------- login
function renderAdminLogin(root, params = {}) {
  document.body.className = "admin-body";
  const html = `<div class="auth-wrap">
    <div class="auth-card">
      <div class="auth-logo"><span class="brand-mark">印</span><div><div class="brand-name">印小单</div><div class="brand-sub">ADMIN CONSOLE</div></div></div>
      <h1>商品建品中心</h1>
      <p class="auth-desc">类目管理 + 标准定价 / 非标计价商品新建。不再重复做商城、订单和 ERP 已有能力。</p>
      <form id="adminLogin">
        <div class="field" style="margin-bottom:12px"><label>管理员账号</label><input class="input" name="username" autocomplete="username" value="admin"></div>
        <div class="field" style="margin-bottom:16px"><label>密码</label><input class="input" name="password" type="password" autocomplete="current-password" placeholder="••••••"></div>
        <button class="btn dark block lg" type="submit">进入管理后台</button>
      </form>
      <div class="demo-hint">演示账号：<b>admin</b> / <b>admin123</b></div>
      <div class="demo-hint" style="margin-top:12px">演示数据：4 个类目、10 个商品（1 个标准定价 + 9 个非标计价）、4 个报价工厂。</div>
    </div>
  </div>`;
  root.innerHTML = html;
  const form = root.querySelector("#adminLogin");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const btn = form.querySelector("button");
    btn.disabled = true; btn.textContent = "登录中…";
    try {
      const res = await api.login(fd.get("username"), fd.get("password"));
      await refreshUser();
      if (!isAdmin()) {
        await api.logout();
        await refreshUser();
        toast("这不是管理员账号", "err");
        btn.disabled = false; btn.textContent = "进入管理后台";
        return;
      }
      toast("欢迎，" + (res.user.name || "管理员"), "ok");
      history.replaceState(null, "", "#/admin/products");
      renderAdmin(root, { page: "products" });
    } catch (err) {
      toast(err.message, "err");
      btn.disabled = false; btn.textContent = "进入管理后台";
    }
  });
}

// ---------------------------------------------------------------- advanced
async function renderAdvanced(root, params, shell) {
  const content = `<div class="admin-grid" style="grid-template-columns:repeat(3,1fr)">
    <a class="panel" href="#/admin/factories" style="display:block;text-decoration:none"><div class="panel-body"><div class="eyebrow">COST</div><h3 style="font-family:var(--serif);font-size:22px;margin:8px 0">报价工厂</h3><p class="muted small">数码/胶印/标签工厂的价格系数、固定费、交期偏移与设备归属。只影响后端核价。</p></div></a>
    <a class="panel" href="#/admin/libraries" style="display:block;text-decoration:none"><div class="panel-body"><div class="eyebrow">DATA</div><h3 style="font-family:var(--serif);font-size:22px;margin:8px 0">基础资料库</h3><p class="muted small">材料、工艺、设备、印张、包装、算法与展开结构。</p></div></a>
    <a class="panel" href="#/admin/settings" style="display:block;text-decoration:none"><div class="panel-body"><div class="eyebrow">SYSTEM</div><h3 style="font-family:var(--serif);font-size:22px;margin:8px 0">系统参数</h3><p class="muted small">利润率、税率、物流默认值、仓库与 ERP 集成密钥。</p></div></a>
  </div>
  <div class="banner info" style="margin-top:14px">这些是后台默认能力，不需要每次建品都填。先在资料库维护一次，建品时自动带出。</div>`;
  root.innerHTML = shell(content, "advanced", "advanced");
  afterShell(root);
}

// ---------------------------------------------------------------- dashboard
async function renderAdminDashboard(root, params) {
  let products = [];
  let cats = [];
  let facts = [];
  try {
    const [p, c, f] = await Promise.all([api.adminProducts(), api.adminCategories(), api.adminFactories()]);
    products = p.products || [];
    cats = c.categories || [];
    facts = f.factories || [];
  } catch (e) { if (e.status === 401) return renderAdminLogin(root); throw e; }
  const standard = products.filter((p) => p.pricing_mode === "standard");
  const nonstandard = products.filter((p) => p.pricing_mode !== "standard");
  const active = products.filter((p) => p.status === "active");
  const content = `
    <div class="kpi-grid">
      <div class="kpi accent"><div class="k-label">商品总数</div><div class="k-value">${products.length}</div><div class="k-sub">${active.length} 个已上架</div></div>
      <div class="kpi"><div class="k-label">类目 / 报价工厂</div><div class="k-value">${cats.length} / ${facts.length}</div><div class="k-sub">${cats.filter((c) => c.enabled !== 0).length} 个类目启用</div></div>
      <div class="kpi"><div class="k-label">标准定价商品</div><div class="k-value">${standard.length}</div><div class="k-sub">固定价格 · 沿用 ERP</div></div>
      <div class="kpi"><div class="k-label">非标计价商品</div><div class="k-value">${nonstandard.length}</div><div class="k-sub">按尺寸/材料/工艺计算</div></div>
    </div>

    <div class="admin-grid">
      <div class="panel">
        <div class="panel-head"><h3>新建商品</h3><span class="right">两种建品方式</span></div>
        <div class="panel-body" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <a href="#/admin/products/new/standard" style="display:block;border:1px solid var(--line);border-radius:12px;padding:18px;background:var(--white)">
            <span class="pill cream">标准定价</span>
            <div style="font-family:var(--serif);font-size:20px;margin:9px 0 5px">固定价格商品</div>
            <p class="muted small" style="line-height:1.7">已有 ERP 价格、SKU、固定单位的商品，补充类目和展示信息即可。</p>
            <span class="link-btn" style="display:inline-block;margin-top:10px">去新建 →</span>
          </a>
          <a href="#/admin/products/new/nonstandard" style="display:block;border:1px solid var(--line);border-radius:12px;padding:18px;background:var(--white)">
            <span class="pill gold">非标计价</span>
            <div style="font-family:var(--serif);font-size:20px;margin:9px 0 5px">按配置报价商品</div>
            <p class="muted small" style="line-height:1.7">配置尺寸公式、材料、工艺、拼版与机型，系统实时试算价格。</p>
            <span class="link-btn" style="display:inline-block;margin-top:10px">去新建 →</span>
          </a>
        </div>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>建品方式分布</h3><span class="right">共 ${products.length} 个</span></div>
        <div class="panel-body">
          <div class="status-bars">
            ${[["标准定价", standard.length, "var(--gold)"], ["非标计价", nonstandard.length, "var(--accent)"]].map(([name, n, color]) => `<div class="status-bar"><div class="sb-top"><span>${name}</span><b>${n}</b></div><div class="track"><div class="fill" style="width:${products.length ? Math.round((n / products.length) * 100) : 0}%;background:${color}"></div></div></div>`).join("")}
          </div>
          <div class="banner info" style="margin-top:16px">${icon("spark", 15)} 过去只有标准定价；现在非标商品可以在建品时把计价规则一起配置好，后续报价直接复用。</div>
        </div>
      </div>
    </div>

    <div class="admin-grid">
      <div class="panel">
        <div class="panel-head"><h3>最近商品</h3><a class="right" href="#/admin/products" style="color:var(--accent)">全部 →</a></div>
        <div class="panel-body" style="padding:0">
          <div class="table-wrap"><table class="admin-table"><thead><tr><th>商品</th><th>类目</th><th>建品方式</th><th>状态</th></tr></thead><tbody>
            ${products.slice(0, 7).map((p) => `<tr style="cursor:pointer" onclick="location.hash='#/admin/products/${encodeURIComponent(p.id)}/edit'">
              <td><div style="display:flex;align-items:center;gap:8px"><img class="lib-thumb" src="${esc(p.image || "")}"><b>${esc(p.name || "")}</b></div></td>
              <td>${esc((cats.find((c) => c.id === p.category) || {}).name || p.category || "—")}</td>
              <td><span class="pill ${p.pricing_mode === "standard" ? "cream" : "gold"}">${p.pricing_mode === "standard" ? "标准定价" : "非标计价"}</span></td>
              <td><span class="pill ${p.status === "active" ? "green" : "cream"}">${p.status === "active" ? "已上架" : p.status === "draft" ? "草稿" : "已下架"}</span></td>
            </tr>`).join("") || `<tr><td colspan="4" class="muted">还没有商品</td></tr>`}
          </tbody></table></div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>类目概览</h3><a class="right" href="#/admin/categories" style="color:var(--accent)">管理 →</a></div>
        <div class="panel-body">
          ${cats.map((c) => `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px dashed var(--line);font-size:11.5px"><span>${esc(c.name)}<br><span class="muted" style="font-size:9.5px">${esc(c.code || c.id)}</span></span><span class="mono">${c.product_count || 0} 个</span></div>`).join("") || `<div class="muted small">还没有类目</div>`}
        </div>
      </div>
    </div>`;
  root.innerHTML = shell(content, "dashboard");
  afterShell(root);
}

// ----------------------------------------------------------- new product choice
async function renderNewProductChoice(root, params) {
  let cats = [];
  try { cats = (await api.adminCategories()).categories || []; } catch (e) {}
  const content = `
    <div class="banner info" style="margin-top:0">${icon("layers", 15)} 先选建品方式：固定价格走「标准定价」，需要按尺寸/材料/工艺计算走「非标计价」。类目可在建品前先新增。</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:4px">
      <a href="#/admin/products/new/standard" class="panel" style="display:block;text-decoration:none;color:inherit">
        <div class="panel-body" style="padding:28px">
          <span class="pill cream">STANDARD PRICE</span>
          <h2 style="font-family:var(--serif);font-weight:400;font-size:30px;margin:14px 0 8px">标准定价商品</h2>
          <p class="muted small" style="line-height:1.9">商品有固定售价、固定单位、SKU，价格已经在商品中心/ERP 里维护。这里补齐类目、图片、详情和上架状态。</p>
          <div class="tech-box" style="margin-top:18px;background:var(--paper)">
            <div class="tech-row"><span>计价</span><b>固定单价</b></div>
            <div class="tech-row"><span>适合</span><b>现货、标品、已有 ERP 价</b></div>
            <div class="tech-row"><span>必填</span><b>类目 / 售价 / 单位</b></div>
          </div>
          <span class="btn primary" style="margin-top:20px">新建标准商品 →</span>
        </div>
      </a>
      <a href="#/admin/products/new/nonstandard" class="panel" style="display:block;text-decoration:none;color:inherit">
        <div class="panel-body" style="padding:28px">
          <span class="pill gold">NON-STANDARD PRICING</span>
          <h2 style="font-family:var(--serif);font-weight:400;font-size:30px;margin:14px 0 8px">非标计价商品</h2>
          <p class="muted small" style="line-height:1.9">按成品尺寸、材料、印刷、工艺、数量和物流实时计算。建品时把展开公式、拼版、工序和计价参数一起配置好。</p>
          <div class="tech-box" style="margin-top:18px;background:var(--paper)">
            <div class="tech-row"><span>计价</span><b>展开 → 拼版 → 工艺 → 价格</b></div>
            <div class="tech-row"><span>适合</span><b>定制袋 / 盒 / 标签 / 纸箱</b></div>
            <div class="tech-row"><span>必填</span><b>公式 / 材料 / 工艺 / 设备</b></div>
          </div>
          <span class="btn gold" style="margin-top:20px">新建非标商品 →</span>
          <div style="margin-top:14px" class="muted tiny">进入 9 步独立测算：尺寸 → 拼版 → 原辅料 → 工艺 → 包装 → 数量 → 方案 → 计价</div>
        </div>
      </a>
    </div>
    <div class="panel" style="margin-top:16px"><div class="panel-body">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <b style="font-size:12px">类目（${cats.length}）</b>
        <div class="cat-chips">${cats.map((c) => `<span class="chip" style="cursor:default">${esc(c.name)} · ${c.product_count || 0}</span>`).join("")}</div>
        <a class="btn soft sm" href="#/admin/categories" style="margin-left:auto">${icon("plus", 13)} 新增 / 管理类目</a>
      </div>
    </div></div>`;
  root.innerHTML = shell(content, "new-product", "products");
  afterShell(root);
}

// ----------------------------------------------------------- edit router
async function renderEditRouter(root, params) {
  let product;
  try { product = (await api.adminProduct(params.id)).product; }
  catch (e) { toast(e.message, "err"); navigate("/admin/products"); return; }
  if (product.pricing_mode === "standard") {
    return renderStandardProduct(root, { id: params.id }, shell, adminLoginGuard);
  }
  return renderBuilder(root, { id: params.id }, shell, adminLoginGuard);
}

// ----------------------------------------------------------- product preview
async function renderProductPreview(root, params) {
  let p;
  let preview = null;
  try {
    p = (await api.adminProduct(params.id)).product;
    if (p.pricing_mode !== "standard") {
      try { preview = await api.previewProduct({ draft: p, qty: (p.quantity && p.quantity.min) || 100 }); } catch (e) { preview = null; }
    }
  } catch (e) { toast(e.message, "err"); navigate("/admin/products"); return; }
  const isStd = p.pricing_mode === "standard";
  const content = `
    <div class="admin-toolbar">
      <span class="pill ${isStd ? "cream" : "gold"}">${isStd ? "标准定价" : "非标计价"}</span>
      <span class="muted small">${esc(p.sku || "")}</span>
      <div class="right"><a class="btn soft sm" href="#/admin/products/${encodeURIComponent(p.id)}/mobile">${icon("phone", 14)} 手机前端</a><a class="btn soft sm" href="#/admin/products/${encodeURIComponent(p.id)}/edit">${icon("edit", 14)} 编辑</a><a class="btn primary sm" href="#/admin/products">返回列表</a></div>
    </div>
    <div class="admin-grid" style="grid-template-columns:1.2fr .55fr;margin-top:0;align-items:start">
      <div class="detail-card">
        <div style="display:flex;gap:18px;flex-wrap:wrap">
          <img src="${esc(p.image || "")}" alt="" style="width:220px;height:170px;object-fit:cover;border-radius:14px;border:1px solid var(--line)">
          <div style="flex:1;min-width:220px">
            <div class="eyebrow" style="color:var(--muted)">商品预览</div>
            <h1 style="font-family:var(--serif);font-weight:400;font-size:32px;margin:6px 0">${esc(p.name || "")}</h1>
            <p class="muted small">${esc(p.subtitle || "")}</p>
            <div class="price-row" style="padding:14px 0">
              <div class="big" id="previewPrice" style="font-size:32px;color:var(--accent);font-family:var(--mono)">${isStd ? money(p.standard_price || 0) : (preview && preview.quote ? money(preview.quote.unit) : "—")}<small style="font-family:var(--sans);font-size:11px;color:var(--muted)"> /${esc(p.unit || "个")}${!isStd ? " 起" : ""}</small></div>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:6px">
              <span class="pill cream">起订 ${(p.quantity && p.quantity.min) || 1}</span>
              <span class="pill cream">交期 ${p.lead_days || 5} 天</span>
              <span class="pill ${isStd ? "cream" : "gold"}">${isStd ? "固定价格" : "按配置报价"}</span>
              <span class="pill cream">送货上门</span>
              ${!isStd ? `<span class="pill cream">${(p.source_ids || []).length} 家报价工厂</span>` : ""}
            </div>
          </div>
        </div>
        <hr class="divider">
        <h3 style="font-family:var(--serif);font-size:20px;font-weight:400;margin-bottom:8px">商品说明</h3>
        <p class="small" style="line-height:2;color:var(--ink-2)">${esc(p.description || p.long_desc || "暂无描述")}</p>
        ${(p.specs || []).length ? `<dl class="spec-table" style="margin-top:14px">${p.specs.map((s) => `<dt>${esc(s.label)}</dt><dd>${esc(s.value)}</dd>`).join("")}</dl>` : ""}
        ${!isStd ? `<hr class="divider"><h3 style="font-family:var(--serif);font-size:20px;font-weight:400;margin-bottom:8px">配置摘要</h3>
          <div class="tech-row"><span>展开结构</span><b>${esc((p.structure || "").toUpperCase())}</b></div>
          <div class="tech-row"><span>材料</span><b>${(p.materials || []).length} 种</b></div>
          <div class="tech-row"><span>必选工艺</span><b>${((p.processes || {}).required || []).length} 项</b></div>
          <div class="tech-row"><span>设备</span><b>${((p.production || {}).press_ids || []).length} 台</b></div>` : ""}
      </div>
      <aside id="previewSide">${previewSideHtml(p, preview, isStd, (p.quantity && p.quantity.min) || 100)}</aside>
    </div>`;
  root.innerHTML = shell(content, "preview", "products");
  afterShell(root);
  bindPreviewSide(root, p, isStd);
}

function previewSideHtml(p, preview, isStd, qty) {
  qty = qty || (p.quantity && p.quantity.min) || 100;
  if (isStd) {
    return `<div class="tech-box">
      <h4>标准定价</h4>
      <div class="tech-row"><span>售价</span><b>${money(p.standard_price || 0)} / ${esc(p.unit || "个")}</b></div>
      <div class="tech-row"><span>起订量</span><b>${(p.quantity && p.quantity.min) || 1}</b></div>
      <div class="tech-row"><span>SKU</span><b>${esc(p.sku || "—")}</b></div>
      <div class="tech-row"><span>交付</span><b>送货上门 · ${esc((p.logistics || {}).warehouse || "杭州中心仓")}</b></div>
      <div class="tech-row"><span>运费</span><b>${(p.logistics || {}).included !== false ? "售价含运费" : "运费另计"}</b></div>
    </div>
    <div class="tech-box" style="margin-top:12px">
      <h4>导出</h4>
      <a class="btn soft block" href="/api/admin/products/${encodeURIComponent(p.id)}/export" target="_blank">${icon("download", 14)} 导出商品 JSON</a>
      <p class="tiny muted" style="margin-top:10px">可交给商品中心/ERP 直接建品。</p>
    </div>`;
  }
  const presets = (p.quantity && p.quantity.presets && p.quantity.presets.length) ? p.quantity.presets : [qty, 500, 1000, 3000];
  return `<div class="tech-box">
    <h4>工厂比价</h4>
    <div class="field" style="margin-bottom:10px"><label>试算数量</label>
      <div style="display:flex;gap:6px"><input class="input" id="pvQty" type="number" value="${qty}" min="${(p.quantity && p.quantity.min) || 1}" style="height:36px"><button class="btn primary sm" id="pvRun">试算</button></div>
      <div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:7px">${presets.map((q) => `<button class="mini-chip ${Number(q) === Number(qty) ? "active" : ""}" data-pvq="${q}" style="font-size:9px">${num(q)}</button>`).join("")}</div>
    </div>
    ${preview && preview.quote ? `
      <div class="tech-row"><span>成本 / 商品价</span><b>${money(preview.quote.cost)} / ${money(preview.quote.total)}</b></div>
      <div class="tech-row"><span>单件</span><b>${money(preview.quote.unit)}</b></div>
      <div class="tech-row"><span>交期</span><b>${preview.quote.lead.min}-${preview.quote.lead.max} 天</b></div>
      <div class="tech-row"><span>基础推荐</span><b>${esc(preview.quote.press || "")}</b></div>
      <div style="margin-top:9px;padding-top:8px;border-top:1px dashed var(--line)">
        ${(preview.sources || []).length ? preview.sources.map((x) => `<div class="tech-row" style="align-items:flex-start"><span>${esc(x.factory.name)}${x.is_cheapest ? ' <span class="pill green" style="font-size:8px;padding:1px 5px">最低</span>' : ""}${x.is_fastest ? ' <span class="pill gold" style="font-size:8px;padding:1px 5px">最快</span>' : ""}<br><i style="font-style:normal;font-size:9px;color:var(--muted)">${x.available ? esc((x.plan || {}).press_name || "") : "不可用"}</i></span><b>${x.available ? money(x.price) + "<br><i style='font-style:normal;font-weight:400;font-size:9px;color:var(--muted)'>" + x.lead.min + "-" + x.lead.max + " 天</i>" : esc(x.error || "")}</b></div>`).join("") : `<div class="muted small">未配置报价工厂</div>`}
      </div>
    ` : `<div class="muted small">配置不完整，暂无法试算。</div>`}
    </div>
    <div class="tech-box" style="margin-top:12px">
      <h4>交付</h4>
      <div class="tech-row"><span>方式</span><b>送货上门</b></div>
      <div class="tech-row"><span>发货仓</span><b>${esc(((preview && preview.quote && preview.quote.logistics) || p.logistics || {}).warehouse || "杭州中心仓")}</b></div>
      <div class="tech-row"><span>运费</span><b>${preview && preview.quote && preview.quote.logistics ? (preview.quote.logistics.free ? "已免运费" : money(preview.quote.logistics.fee)) : "按重量计费"}</b></div>
    </div>
    <div class="tech-box" style="margin-top:12px">
      <h4>导出</h4>
      <a class="btn soft block" href="/api/admin/products/${encodeURIComponent(p.id)}/export" target="_blank">${icon("download", 14)} 导出商品 JSON</a>
      <p class="tiny muted" style="margin-top:10px">可交给商品中心/ERP 直接建品或同步非标计价规则。</p>
    </div>`;
}

function bindPreviewSide(root, p, isStd) {
  if (isStd) return;
  const run = async (q) => {
    const input = root.querySelector("#pvQty");
    let qty = Number(q || (input && input.value)) || ((p.quantity && p.quantity.min) || 100);
    qty = Math.max(qty, (p.quantity && p.quantity.min) || 1);
    const side = root.querySelector("#previewSide");
    side.innerHTML = `<div class="tech-box"><h4>工厂比价</h4><div class="muted small">正在按 ${num(qty)} 个试算…</div></div>`;
    try {
      const preview = await api.previewProduct({ draft: p, qty });
      side.innerHTML = previewSideHtml(p, preview, false, qty);
      const priceEl = root.querySelector("#previewPrice");
      if (priceEl && preview && preview.quote) {
        priceEl.innerHTML = `${money(preview.quote.unit)}<small style="font-family:var(--sans);font-size:11px;color:var(--muted)"> /${esc(p.unit || "个")} 起</small>`;
      }
      bindPreviewSide(root, p, false);
    } catch (e) {
      side.innerHTML = `<div class="tech-box"><h4>工厂比价</h4><div class="quote-error">${esc(e.message)}</div></div>`;
      bindPreviewSide(root, p, false);
    }
  };
  root.querySelector("#pvRun")?.addEventListener("click", () => run());
  root.querySelector("#pvQty")?.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
  root.querySelectorAll("[data-pvq]").forEach((b) => b.addEventListener("click", () => {
    const input = root.querySelector("#pvQty");
    if (input) input.value = b.dataset.pvq;
    run(b.dataset.pvq);
  }));
}

// ---------------------------------------------------------------- products
async function renderAdminProducts(root, params) {
  let products = [];
  let cats = [];
  try {
    const [pd, cd] = await Promise.all([api.adminProducts(), api.adminCategories()]);
    products = pd.products || [];
    cats = cd.categories || [];
  } catch (e) { if (e.status === 401) return renderAdminLogin(root); }
  const catMap = {};
  cats.forEach((c) => catMap[c.id] = c);
  const content = `
    <div class="admin-toolbar">
      <div class="search">${icon("search", 15)}<input class="input" id="apSearch" placeholder="搜索商品名 / SKU / 类目"></div>
      <select class="select" id="apMode"><option value="">全部建品方式</option><option value="standard">标准定价</option><option value="nonstandard">非标计价</option></select>
      <select class="select" id="apCat"><option value="">全部类目</option>${cats.map((c) => `<option value="${c.id}" ${params.category === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
      <div class="right">
        <a class="btn soft sm" href="${api.exportProductsUrl()}" target="_blank">${icon("download", 14)} 导出全部 JSON</a>
        <a class="btn primary sm" href="#/admin/products/new">${icon("plus", 14)} 新建商品</a>
      </div>
    </div>
    <div class="admin-products">
      ${products.map((p) => {
        const std = p.pricing_mode === "standard";
        const cat = catMap[p.category];
        const price = std ? money(p.standard_price || 0) : (p.price_from ? money(p.price_from.unit) : "—");
        const unit = std ? (p.unit || "个") : "件";
        return `<div class="admin-product" data-mode="${std ? "standard" : "nonstandard"}" data-cat="${esc(p.category || "")}" data-text="${esc((p.name + " " + (p.sku || "") + " " + (cat ? cat.name : "")).toLowerCase())}">
          <img src="${esc(p.image || "")}" alt="">
          <div class="ap-body">
            <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap">
              <span class="pill ${p.status === "active" ? "green" : "cream"}">${p.status === "active" ? "已上架" : p.status === "draft" ? "草稿" : "已下架"}</span>
              <span class="pill ${std ? "cream" : "gold"}">${std ? "标准定价" : "非标计价"}</span>
              ${p.kind === "overprint" ? `<span class="pill cream">成品加印</span>` : ""}
            </div>
            <h4 style="margin-top:7px">${esc(p.name)}</h4>
            <div class="ap-meta">${esc(cat ? cat.name : p.category || "未归类")}${p.sku ? " · " + esc(p.sku) : ""}</div>
            <div class="ap-foot">
              <span class="ap-price">${price}</span><span class="muted" style="font-size:9px">/${esc(unit)}${std ? "" : " 起"}</span>
              <div class="ap-actions">
                <a class="btn ghost sm" href="#/admin/products/${encodeURIComponent(p.id)}/mobile" title="手机前端预览">${icon("phone", 13)}</a>
                <a class="btn ghost sm" href="#/admin/products/${encodeURIComponent(p.id)}/preview" title="商品预览">${icon("shop", 13)}</a>
                <a class="btn ghost sm" href="/api/admin/products/${encodeURIComponent(p.id)}/export" target="_blank" title="导出 JSON">${icon("download", 13)}</a>
                <a class="btn soft sm" href="#/admin/products/${encodeURIComponent(p.id)}/edit">编辑</a>
              </div>
            </div>
            <div style="margin-top:8px;display:flex;gap:5px">
              <button class="btn ghost sm" data-toggle="${p.id}" data-status="${p.status === "active" ? "draft" : "active"}">${p.status === "active" ? "下架" : "上架"}</button>
              ${p.status !== "disabled" ? `<button class="btn danger sm" data-disable="${p.id}">停用</button>` : ""}
            </div>
          </div>
        </div>`;
      }).join("") || emptyCard("还没有商品", "先新建标准定价商品，或使用非标计价向导配置定制商品。", `<a class="btn primary" href="#/admin/products/new">新建商品</a>`)}
    </div>`;
  root.innerHTML = shell(content, "products");
  afterShell(root);
  const filter = () => {
    const q = root.querySelector("#apSearch").value.toLowerCase();
    const mode = root.querySelector("#apMode").value;
    const cat = root.querySelector("#apCat").value;
    root.querySelectorAll(".admin-product").forEach((c) => {
      c.style.display = (!q || c.dataset.text.includes(q)) && (!mode || c.dataset.mode === mode) && (!cat || c.dataset.cat === cat) ? "" : "none";
    });
  };
  root.querySelector("#apSearch").addEventListener("input", filter);
  root.querySelector("#apMode").addEventListener("change", filter);
  root.querySelector("#apCat").addEventListener("change", filter);
  filter();
  root.querySelectorAll("[data-toggle]").forEach((b) => b.addEventListener("click", async () => {
    try { await api.setProductStatus(b.dataset.toggle, b.dataset.status); toast("已更新", "ok"); renderAdminProducts(root, params); } catch (e) { toast(e.message, "err"); }
  }));
  root.querySelectorAll("[data-disable]").forEach((b) => b.addEventListener("click", async () => {
    if (!(await confirmDialog("停用后商品不再参与建品/展示，确认？"))) return;
    try { await api.setProductStatus(b.dataset.disable, "disabled"); toast("已停用", "ok"); renderAdminProducts(root, params); } catch (e) { toast(e.message, "err"); }
  }));
}

// ---------------------------------------------------------------- settings
async function renderAdminSettings(root, params) {
  let s;
  try { s = (await api.settings()).settings; } catch (e) { if (e.status === 401) return renderAdminLogin(root); }
  const content = `
    <div class="admin-grid" style="grid-template-columns:1.2fr .8fr;margin-top:0">
      <div class="panel">
        <div class="panel-head"><h3>站点与价格链</h3><span class="right">保存后立即生效</span></div>
        <div class="panel-body">
          <form id="settingsForm">
            <div class="form-grid">
              <div class="field"><label>站点名称</label><input class="input" name="site_name" value="${esc(s.site_name || "")}"></div>
              <div class="field"><label>站点副标题</label><input class="input" name="site_slogan" value="${esc(s.site_slogan || "")}"></div>
              <div class="field"><label>客服电话</label><input class="input" name="service_phone" value="${esc(s.service_phone || "")}"></div>
              <div class="field"><label>发货仓</label><input class="input" name="warehouse" value="${esc(s.warehouse || "")}"></div>
              <div class="field"><label>报价有效期（天）</label><input class="input" name="quote_valid_days" type="number" value="${s.quote_valid_days || 15}"></div>
              <div class="field"><label>平台利润率</label><input class="input" name="platform_margin" type="number" step="0.01" value="${s.platform_margin || 0.18}"><span class="hint">成本 × (1 + 平台利润率) = 商品报价</span></div>
              <div class="field"><label>增值税率</label><input class="input" name="tax_rate" type="number" step="0.01" value="${s.tax_rate || 0.06}"></div>
              <div class="field"><label>管理费率</label><input class="input" name="overhead_rate" type="number" step="0.01" value="${s.overhead_rate || 0.06}"></div>
              <div class="field"><label>默认损耗率</label><input class="input" name="loss_rate" type="number" step="0.01" value="${s.loss_rate || 0.05}"></div>
              <div class="field"><label>物流起步价</label><input class="input" name="shipping_base" type="number" step="0.1" value="${s.shipping_base || 10}"></div>
              <div class="field"><label>每公斤续重</label><input class="input" name="shipping_per_kg" type="number" step="0.1" value="${s.shipping_per_kg || 1.8}"></div>
              <div class="field"><label>满额免运费</label><input class="input" name="free_shipping_over" type="number" value="${s.free_shipping_over || 3000}"></div>
              <div class="field"><label>最低起做金额</label><input class="input" name="min_order_total" type="number" value="${s.min_order_total || 300}"></div>
              <div class="field full"><label>ERP 集成密钥</label><input class="input" name="integration_key" value="${esc(s.integration_key || "")}"><span class="hint">ERP 通过 /api/integration/products?key=... 拉取商品 JSON；演示默认 yxd-demo-key</span></div>
              <div class="field full"><label>报价说明</label><textarea class="textarea" name="quote_note" rows="2">${esc(s.quote_note || "")}</textarea></div>
              <div class="field full"><label>交付说明</label><textarea class="textarea" name="delivery_note" rows="2">${esc(s.delivery_note || "")}</textarea></div>
              <div class="field full"><label>付款说明</label><textarea class="textarea" name="payment_note" rows="2">${esc(s.payment_note || "")}</textarea></div>
            </div>
            <div style="margin-top:18px"><button class="btn primary" type="submit">保存参数</button></div>
          </form>
        </div>
      </div>
      <div>
        <div class="panel">
          <div class="panel-head"><h3>修改管理员密码</h3></div>
          <div class="panel-body">
            <div class="field"><label>当前密码</label><input class="input" id="pwdCurrent" type="password"></div>
            <div class="field" style="margin-top:10px"><label>新密码</label><input class="input" id="pwdNew" type="password"></div>
            <button class="btn dark" id="pwdSave" style="margin-top:14px">更新密码</button>
          </div>
        </div>
        <div class="panel" style="margin-top:14px">
          <div class="panel-head"><h3>演示账号</h3></div>
          <div class="panel-body small muted" style="line-height:1.9">
            管理员：<b class="mono">admin / admin123</b><br>
            代理商：<b class="mono">13800000001 / agent123</b><br>
            代理商：<b class="mono">13800000002 / agent123</b><br><br>
            所有密码均以 PBKDF2 哈希存储；上线前请修改默认密码。
          </div>
        </div>
        <div class="panel" style="margin-top:14px">
          <div class="panel-head"><h3>系统说明</h3></div>
          <div class="panel-body small muted" style="line-height:1.9">
            计价内核为纯 Python 标准库，无外部依赖。报价、订单、资料库存储在本地 SQLite：<b class="mono">data/mall.db</b>。备份时复制该文件即可。
          </div>
        </div>
      </div>
    </div>`;
  root.innerHTML = shell(content, "settings");
  afterShell(root);
  root.querySelector("#settingsForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {};
    fd.forEach((v, k) => {
      if (["site_name", "site_slogan", "service_phone", "warehouse", "quote_note", "delivery_note", "payment_note", "integration_key"].includes(k)) payload[k] = v;
      else if (k === "quote_valid_days") payload[k] = Number(v);
      else payload[k] = Number(v);
    });
    try { await api.saveSettings(payload); toast("参数已保存", "ok"); } catch (err) { toast(err.message, "err"); }
  });
  root.querySelector("#pwdSave").addEventListener("click", async () => {
    try {
      await api.changePassword(root.querySelector("#pwdCurrent").value, root.querySelector("#pwdNew").value);
      toast("密码已更新", "ok");
      root.querySelector("#pwdCurrent").value = "";
      root.querySelector("#pwdNew").value = "";
    } catch (e) { toast(e.message, "err"); }
  });
}
