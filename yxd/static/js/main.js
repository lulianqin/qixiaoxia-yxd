import { boot, refreshUser } from "./store.js";
import { parseHash, $, toast, closeModal } from "./core.js";
import { api } from "./api.js";
import { renderAdmin } from "./views/admin.js";
import { renderMobile } from "./views/mobile.js";

const app = $("#app");
let rendering = false;
let started = false;

function pageError(root, err) {
  root.innerHTML = `<div class="wrap" style="padding:80px 0"><div class="empty">
    <div class="big">页面加载失败</div>
    <p>${(err && err.message) || "未知错误"}</p>
    <button class="btn primary" onclick="location.reload()">刷新重试</button>
  </div></div>`;
}

async function route() {
  if (rendering) return;
  rendering = true;
  closeModal();
  const { path, query } = parseHash();
  try {
    // 独立手机前端校对页
    const mMobile = path.match(/^\/m\/([^/]+)\/?$/);
    if (mMobile) {
      await renderMobile(app, { id: mMobile[1] });
      return;
    }
    document.body.classList.remove("mobile-preview-body");
    // 商品中心扩展：只保留管理后台 + 商品预览；不再提供独立商城/订单/代理前台。
    let params = { page: "products" };
    if (path === "/" || path === "" || path === "/admin") {
      params = { page: "products" };
    } else if (path === "/admin/advanced") {
      params = { page: "advanced" };
    } else if (path === "/admin/categories") {
      params = { page: "categories" };
    } else if (path === "/admin/factories") {
      params = { page: "factories" };
    } else if (/^\/admin\/factories\/[^/]+\/prices\/?$/.test(path)) {
      params = { page: "factory-prices", id: path.split("/")[3], tab: query.tab };
    } else if (path === "/admin/products") {
      params = { page: "products", category: query.category };
    } else if (path === "/admin/products/new") {
      params = { page: "new-product" };
    } else if (path === "/admin/products/new/standard") {
      params = { page: "standard" };
    } else if (path === "/admin/products/new/nonstandard") {
      params = { page: "builder" };
    } else if (path === "/admin/products/new/advanced") {
      params = { page: "builder" };
    } else if (path === "/admin/libraries") {
      params = { page: "libraries", tab: query.tab };
    } else if (path === "/admin/settings") {
      params = { page: "settings" };
    } else {
      const mEdit = path.match(/^\/admin\/products\/([^/]+)\/edit\/?$/);
      const mPrev = path.match(/^\/admin\/products\/([^/]+)\/preview\/?$/);
      const mMobilePage = path.match(/^\/admin\/products\/([^/]+)\/mobile\/?$/);
      if (mEdit) params = { page: "edit-product", id: mEdit[1] };
      else if (mPrev) params = { page: "preview", id: mPrev[1] };
      else if (mMobilePage) params = { page: "mobile-preview", id: mMobilePage[1] };
      else {
        // 旧商城/订单/代理链接统一回到后台，不报错
        window.location.hash = "#/admin";
        return;
      }
    }
    document.title = "印小单 · 商品建品中心";
    await renderAdmin(app, params);
    window.scrollTo({ top: 0, behavior: "auto" });
  } catch (e) {
    console.error(e);
    pageError(app, e);
  } finally {
    rendering = false;
  }
}

async function start() {
  if (started) return;
  started = true;
  try {
    await boot();
  } catch (e) {
    started = false;
    app.innerHTML = `<div class="wrap" style="padding:80px 0"><div class="empty"><div class="big">服务未启动</div><p>${e.message || ""}</p><p class="small">在项目目录运行 <b class="mono">python3 server.py</b> 后刷新。</p></div></div>`;
    return;
  }
  route();
}

document.addEventListener("click", async (e) => {
  const out = e.target.closest("[data-agent-logout]");
  if (out) {
    e.preventDefault();
    try { await api.logout(); } catch (err) {}
    await refreshUser();
    toast("已退出", "ok");
    location.hash = "#/admin";
    route();
  }
});

window.addEventListener("hashchange", route);
start();
