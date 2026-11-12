import { api } from "../api.js";
import { esc, icon, toast, navigate } from "../core.js";

const TABS = [
  { id: "materials", name: "材料价格" },
  { id: "processes", name: "工艺价格" },
  { id: "presses", name: "设备价格" },
  { id: "packagings", name: "包装价格" },
];

function clone(x) { return JSON.parse(JSON.stringify(x || {})); }

function defaultsFrom(libs) {
  const out = { materials: {}, processes: {}, presses: {}, packagings: {} };
  (libs.materials || []).forEach((m) => { if (m.enabled !== 0) out.materials[m.id] = { algorithm_id: m.algorithm_id, params: clone(m.params) }; });
  (libs.processes || []).forEach((p) => {
    if (p.enabled === 0) return;
    out.processes[p.id] = { methods: (p.methods || []).map((m) => ({ id: m.id, name: m.name, algorithm_id: m.algorithm_id, params: clone(m.params), days: m.days, min_qty: m.min_qty || 0, note: m.note || "" })) };
  });
  (libs.presses || []).forEach((p) => { if (p.enabled !== 0) out.presses[p.id] = { algorithm_id: p.algorithm_id, params: clone(p.params) }; });
  (libs.packagings || []).forEach((p) => { if (p.enabled !== 0) out.packagings[p.id] = { algorithm_id: p.algorithm_id, params: clone(p.params) }; });
  return out;
}

function paramInputs(kind, id, params, methodId = "") {
  return Object.entries(params || {}).map(([k, v]) => {
    if (typeof v !== "number") return `<span class="tiny muted">${esc(k)}=${esc(String(v))}</span>`;
    return `<label class="fp-param"><span>${esc(k)}</span><input type="number" step="0.01" data-kind="${kind}" data-id="${esc(id)}" ${methodId ? `data-method="${esc(methodId)}"` : ""} data-param="${esc(k)}" value="${v}"></label>`;
  }).join("");
}

export async function renderFactoryPrices(root, params = {}, shell) {
  let factories = [];
  let libs = {};
  try {
    [factories, libs] = await Promise.all([
      api.adminFactories().then((x) => x.factories || []),
      api.libraries(),
    ]);
  } catch (e) { toast(e.message, "err"); return; }
  const factory = factories.find((f) => f.id === params.id);
  if (!factory) { toast("工厂不存在", "err"); navigate("/admin/factories"); return; }
  const defaults = defaultsFrom(libs);
  const book = factory.prices && Object.keys(factory.prices.materials || {}).length ? clone(factory.prices) : clone(defaults);
  ["materials", "processes", "presses", "packagings"].forEach((kind) => {
    book[kind] = book[kind] || {};
    Object.entries(defaults[kind] || {}).forEach(([id, val]) => { if (!book[kind][id]) book[kind][id] = clone(val); });
  });
  let tab = params.tab || "materials";

  function render() {
    const content = `
      <div class="admin-toolbar">
        <span class="pill gold">${esc(factory.name)}</span>
        <span class="muted small">工厂独立价格表 · 不再用全局价乘系数</span>
        <div class="right">
          <a class="btn soft sm" href="#/admin/factories">${icon("arrow", 14)} 返回工厂</a>
          <button class="btn primary sm" id="fpSave">保存价格表</button>
        </div>
      </div>
      <div class="mp-mode-tabs" style="max-width:620px">
        ${TABS.map((t) => `<button class="mp-mode-tab ${tab === t.id ? "active" : ""}" data-fptab="${t.id}">${t.name}</button>`).join("")}
      </div>
      <div class="panel"><div class="panel-body" style="padding:0">
        <div class="table-wrap"><table class="admin-table fp-table">
          <thead><tr><th>${tab === "processes" ? "工艺 / 生产方式" : "项目"}</th><th>算法</th><th>价格参数</th></tr></thead>
          <tbody>${bodyHtml()}</tbody>
        </table></div>
      </div></div>
      <div class="banner info" style="margin-top:12px">这里的价格只对「${esc(factory.name)}」生效。商品报价时会分别加载每家工厂的价格表，再比较成本和交期。</div>`;
    root.innerHTML = shell(content, "factory-prices", "advanced");
    root.querySelector("#adminLogout")?.addEventListener("click", () => { location.hash = "#/admin"; });
    root.querySelectorAll("[data-fptab]").forEach((b) => b.addEventListener("click", () => { tab = b.dataset.fptab; render(); }));
    root.querySelector("#fpSave")?.addEventListener("click", save);
  }

  function bodyHtml() {
    if (tab === "processes") {
      return Object.entries(book.processes || {}).map(([pid, p]) => {
        const proc = (libs.processes || []).find((x) => x.id === pid) || {};
        return (p.methods || []).map((m, i) => `<tr>
          <td><b>${esc(proc.name || pid)}</b><div class="tiny muted">${esc(m.name || m.id || "")}</div></td>
          <td class="mono tiny">${esc(m.algorithm_id || "")}</td>
          <td><div class="fp-params">${paramInputs("processes", pid, m.params, m.id || String(i))}</div></td>
        </tr>`).join("");
      }).join("");
    }
    const src = tab === "materials" ? libs.materials : tab === "presses" ? libs.presses : libs.packagings;
    return Object.entries(book[tab] || {}).map(([id, item]) => {
      const base = (src || []).find((x) => x.id === id) || {};
      return `<tr>
        <td><b>${esc(base.name || id)}</b>${base.gsm ? `<div class="tiny muted">${base.gsm}g</div>` : ""}</td>
        <td class="mono tiny">${esc(item.algorithm_id || "")}</td>
        <td><div class="fp-params">${paramInputs(tab, id, item.params)}</div></td>
      </tr>`;
    }).join("");
  }

  function save() {
    root.querySelectorAll("[data-kind]").forEach((inp) => {
      const kind = inp.dataset.kind;
      const id = inp.dataset.id;
      const method = inp.dataset.method;
      const param = inp.dataset.param;
      const val = Number(inp.value);
      if (method) {
        const m = ((book[kind] || {})[id] || {}).methods || [];
        const hit = m.find((x) => String(x.id) === String(method));
        if (hit) hit.params[param] = val;
      } else {
        const item = (book[kind] || {})[id];
        if (item) item.params[param] = val;
      }
    });
    factory.prices = book;
    api.saveFactory(factory).then(() => toast("价格表已保存", "ok")).catch((e) => toast(e.message, "err"));
  }

  render();
}
