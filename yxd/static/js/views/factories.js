import { api } from "../api.js";
import { esc, icon, toast, openModal, closeModal, confirmDialog } from "../core.js";

const TYPE = { digital: "数码印刷", offset: "传统胶印", label: "标签轮转", flexo: "瓦楞水印", other: "其他" };

export async function renderFactories(root, params = {}, shell) {
  let facts = [];
  try { facts = (await api.adminFactories()).factories || []; }
  catch (e) { if (e.status === 401) return; toast(e.message, "err"); return; }
  const content = `
    <div class="admin-toolbar">
      <div class="search">${icon("search", 15)}<input class="input" id="facSearch" placeholder="搜索工厂名称 / 类型"></div>
      <div class="right"><button class="btn primary sm" id="addFactory">${icon("plus", 14)} 新增报价工厂</button></div>
    </div>
    <div class="panel"><div class="panel-body" style="padding:0">
      <div class="table-wrap"><table class="admin-table" id="facTable">
        <thead><tr><th>报价工厂 / 数据源</th><th>类型</th><th>价格系数</th><th>固定服务费</th><th>交期偏移</th><th>设备</th><th>引用商品</th><th>状态</th><th></th></tr></thead>
        <tbody>${facts.map((f) => `<tr data-text="${esc((f.name + " " + (TYPE[f.type] || f.type)).toLowerCase())}">
          <td><b>${esc(f.name)}</b><div class="muted" style="font-size:9.5px">${esc(f.note || "")}</div></td>
          <td><span class="pill cream">${esc(TYPE[f.type] || f.type)}</span></td>
          <td class="num">${Number(f.price_factor || 1).toFixed(2)}×</td>
          <td class="num">${f.fixed_fee ? "¥" + Number(f.fixed_fee).toFixed(2) : "—"}</td>
          <td class="num">${f.lead_days > 0 ? "+" + f.lead_days + " 天" : "—"}</td>
          <td class="num">${f.press_count || 0} 台</td>
          <td class="num">${f.product_count || 0} 个</td>
          <td><span class="pill ${f.enabled ? "green" : "cream"}">${f.enabled ? "启用" : "停用"}</span></td>
          <td><div class="t-actions"><a class="btn gold sm" href="#/admin/factories/${encodeURIComponent(f.id)}/prices">${icon("calc", 13)} 价格表</a><button class="btn soft sm" data-edit="${esc(f.id)}">编辑</button><button class="btn ghost sm" data-del="${esc(f.id)}">${icon("trash", 13)}</button></div></td>
        </tr>`).join("") || `<tr><td colspan="9" class="muted">还没有报价工厂</td></tr>`}</tbody>
      </table></div>
    </div></div>
    <div class="banner info" style="margin-top:14px">${icon("layers", 15)} 同一个商品可以挂多个报价工厂。每家工厂有独立的材料/工艺/设备/包装价格表；系统分别按价格表和设备算成本，再比较成本与交期。</div>`;
  root.innerHTML = shell(content, "factories");
  const logout = root.querySelector("#adminLogout");
  if (logout) logout.addEventListener("click", () => { location.hash = "#/admin"; });
  const table = root.querySelector("#facTable");
  root.querySelector("#facSearch").addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    table.querySelectorAll("tbody tr").forEach((tr) => { tr.style.display = !q || (tr.dataset.text || "").includes(q) ? "" : "none"; });
  });
  const reload = () => renderFactories(root, params, shell);
  root.querySelector("#addFactory").addEventListener("click", () => factoryModal(null, reload));
  table.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => {
    factoryModal(facts.find((x) => x.id === b.dataset.edit), reload);
  }));
  table.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    if (!(await confirmDialog("删除工厂前会检查是否有设备/商品引用。确认删除？", { danger: true, ok: "删除" }))) return;
    try { await api.deleteFactory(b.dataset.del); toast("已删除", "ok"); reload(); } catch (e) { toast(e.message, "err"); }
  }));
}

function factoryModal(f, reload) {
  const isNew = !f;
  const v = f || { type: "offset", price_factor: 1, fixed_fee: 0, lead_days: 0, enabled: 1, sort: 0 };
  openModal(`
    <div class="modal-head"><h3>${isNew ? "新增报价工厂" : "编辑报价工厂"}</h3><button class="x" data-close>×</button></div>
    <div class="modal-body">
      <div class="form-grid">
        <div class="field"><label>工厂名称 *</label><input class="input" id="facName" value="${esc(v.name || "")}" placeholder="如：传统胶印厂"></div>
        <div class="field"><label>类型</label><select class="select" id="facType">${Object.entries(TYPE).map(([k, n]) => `<option value="${k}" ${v.type === k ? "selected" : ""}>${n}</option>`).join("")}</select></div>
        <div class="field"><label>整单调整系数</label><input class="input" id="facFactor" type="number" step="0.01" value="${v.price_factor || 1}"><span class="hint">一般填 1；特殊返点才用，真实价格在「价格表」里配</span></div>
        <div class="field"><label>固定服务费</label><input class="input" id="facFee" type="number" step="0.01" value="${v.fixed_fee || 0}"></div>
        <div class="field"><label>交期偏移（天）</label><input class="input" id="facLead" type="number" value="${v.lead_days || 0}"></div>
        <div class="field"><label>排序</label><input class="input" id="facSort" type="number" value="${v.sort || 0}"></div>
        <div class="field"><label>状态</label><select class="select" id="facEnabled"><option value="1" ${v.enabled !== 0 ? "selected" : ""}>启用</option><option value="0" ${v.enabled === 0 ? "selected" : ""}>停用</option></select></div>
        <div class="field full"><label>说明</label><textarea class="textarea" id="facNote" rows="2" placeholder="如：版费高、千张印工低，适合大批量">${esc(v.note || "")}</textarea></div>
      </div>
    </div>
    <div class="modal-foot"><button class="btn ghost" data-close>取消</button><button class="btn primary" id="facSave">保存</button></div>`, { onMount: (m) => {
      m.querySelector("#facSave").addEventListener("click", async () => {
        const name = m.querySelector("#facName").value.trim();
        if (!name) return toast("请填写工厂名称", "err");
        const payload = {
          id: v.id || "", name,
          type: m.querySelector("#facType").value,
          price_factor: Number(m.querySelector("#facFactor").value) || 1,
          fixed_fee: Number(m.querySelector("#facFee").value) || 0,
          lead_days: Number(m.querySelector("#facLead").value) || 0,
          sort: Number(m.querySelector("#facSort").value) || 0,
          enabled: Number(m.querySelector("#facEnabled").value),
          note: m.querySelector("#facNote").value.trim(),
          prices: v.prices || {},
        };
        try { await api.saveFactory(payload); toast("工厂已保存", "ok"); closeModal(); reload(); } catch (e) { toast(e.message, "err"); }
      });
    } });
}
