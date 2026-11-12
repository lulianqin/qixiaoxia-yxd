import { api } from "../api.js";
import { state, refreshUser } from "../store.js";
import { esc, money, num, icon, toast, openModal, closeModal, confirmDialog, navigate, pct } from "../core.js";
import { emptyCard } from "../components.js";

const TABS = [
  { id: "materials", name: "材料 / 辅料" },
  { id: "processes", name: "生产工艺" },
  { id: "presses", name: "印刷设备" },
  { id: "sheets", name: "上机印张" },
  { id: "packagings", name: "包装方式" },
  { id: "algorithms", name: "计价算法" },
  { id: "structures", name: "展开公式" },
];
const KIND = { paper: "纸张", board: "纸板", corrugated: "瓦楞", label: "不干胶", aux: "辅料" };

export async function renderLibraries(root, params = {}, shell) {
  let libs;
  try { libs = await api.libraries(); } catch (e) { if (e.status === 401) navigate("/admin"); return; }
  const tab = params.tab && TABS.some((t) => t.id === params.tab) ? params.tab : "materials";
  const content = `
    <div class="admin-toolbar">
      <div class="lib-tabs">${TABS.map((t) => `<button data-tab="${t.id}" class="${tab === t.id ? "active" : ""}">${t.name}</button>`).join("")}</div>
      <div class="right">${tab !== "algorithms" && tab !== "structures" ? `<button class="btn primary sm" id="libNew">${icon("plus", 14)} 新增</button>` : ""}</div>
    </div>
    <div id="libBody"></div>`;
  root.innerHTML = shell(content, "libraries");
  bindLogout(root);
  root.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => renderLibraries(root, { tab: b.dataset.tab }, shell)));
  const body = root.querySelector("#libBody");
  const reload = () => renderLibraries(root, { tab }, shell);
  const newBtn = root.querySelector("#libNew");
  if (newBtn) newBtn.addEventListener("click", () => openNew(tab, reload, libs));

  if (tab === "materials") {
    body.innerHTML = `<div class="panel"><div class="panel-body" style="padding:0"><div class="table-wrap"><table class="admin-table">
      <thead><tr><th>材料</th><th>类型</th><th>克重</th><th>单位</th><th>计价算法</th><th>关键参数</th><th>状态</th><th></th></tr></thead>
      <tbody>${(libs.materials || []).map((m) => `<tr>
        <td><div style="display:flex;align-items:center;gap:9px"><img class="lib-thumb" src="${esc(m.image || "")}"><b>${esc(m.name)}</b></div></td>
        <td>${esc(KIND[m.kind] || m.kind)}</td><td class="num">${m.gsm || "—"}</td><td>${esc(m.unit || "")}</td>
        <td class="mono" style="font-size:10px">${esc(m.algorithm_id || "")}</td><td class="muted small">${paramSummary(m.params)}</td>
        <td><span class="pill ${m.enabled ? "green" : "cream"}">${m.enabled ? "启用" : "停用"}</span></td>
        <td><div class="t-actions"><button class="btn soft sm" data-edit="${esc(m.id)}">编辑</button><button class="btn ghost sm" data-del="${esc(m.id)}">${icon("trash", 13)}</button></div></td>
      </tr>`).join("") || `<tr><td colspan="8" class="muted">暂无材料</td></tr>`}</tbody>
    </table></div></div></div>`;
    bindRowActions(body, "materials", libs, reload, (item) => materialModal(item, libs, reload));
  } else if (tab === "processes") {
    body.innerHTML = `<div class="panel"><div class="panel-body" style="padding:0"><div class="table-wrap"><table class="admin-table">
      <thead><tr><th>工艺</th><th>分类</th><th>适用盒型</th><th>材料限制</th><th>生产方式</th><th>状态</th><th></th></tr></thead>
      <tbody>${(libs.processes || []).map((p) => `<tr>
        <td><div style="display:flex;align-items:center;gap:9px"><img class="lib-thumb" src="${esc(p.image || "")}"><b>${esc(p.name)}</b></div></td>
        <td>${esc(p.category || "")}</td><td class="muted small">${(p.applies_to || []).join(" / ")}</td>
        <td class="muted small">${p.constraints && p.constraints.min_gsm ? `≥ ${p.constraints.min_gsm}g` : "—"}</td>
        <td class="muted small">${(p.methods || []).map((m) => esc(m.name)).join(" / ")}</td>
        <td><span class="pill ${p.enabled ? "green" : "cream"}">${p.enabled ? "启用" : "停用"}</span></td>
        <td><div class="t-actions"><button class="btn soft sm" data-edit="${esc(p.id)}">编辑</button><button class="btn ghost sm" data-del="${esc(p.id)}">${icon("trash", 13)}</button></div></td>
      </tr>`).join("") || `<tr><td colspan="7" class="muted">暂无工艺</td></tr>`}</tbody>
    </table></div></div></div>`;
    bindRowActions(body, "processes", libs, reload, (item) => processModal(item, libs, reload));
  } else if (tab === "presses") {
    body.innerHTML = `<div class="panel"><div class="panel-body" style="padding:0"><div class="table-wrap"><table class="admin-table">
      <thead><tr><th>设备</th><th>报价工厂</th><th>类型</th><th>最大上机</th><th>用时</th><th>计价算法</th><th>状态</th><th></th></tr></thead>
      <tbody>${(libs.presses || []).map((p) => `<tr>
        <td><b>${esc(p.name)}</b></td><td>${esc(((libs.factories || []).find((f) => f.id === p.factory_id) || {}).name || "未归属")}</td><td>${esc(p.type)}</td><td class="num">${p.max_w} × ${p.max_h} mm</td><td class="num">${p.days} 天</td>
        <td class="mono" style="font-size:10px">${esc(p.algorithm_id || "")}</td><td><span class="pill ${p.enabled ? "green" : "cream"}">${p.enabled ? "启用" : "停用"}</span></td>
        <td><div class="t-actions"><button class="btn soft sm" data-edit="${esc(p.id)}">编辑</button><button class="btn ghost sm" data-del="${esc(p.id)}">${icon("trash", 13)}</button></div></td>
      </tr>`).join("") || `<tr><td colspan="8" class="muted">暂无设备</td></tr>`}</tbody>
    </table></div></div></div>`;
    bindRowActions(body, "presses", libs, reload, (item) => pressModal(item, libs, reload));
  } else if (tab === "sheets") {
    body.innerHTML = `<div class="panel"><div class="panel-body" style="padding:0"><div class="table-wrap"><table class="admin-table">
      <thead><tr><th>印张</th><th>尺寸</th><th>咬口 / 边距</th><th>说明</th><th></th></tr></thead>
      <tbody>${(libs.sheets || []).map((s) => `<tr>
        <td><b>${esc(s.name)}</b></td><td class="num">${s.w} × ${s.h} mm</td><td class="num">${s.grip} / ${s.edge} mm</td><td class="muted small">${esc(s.note || "")}</td>
        <td><div class="t-actions"><button class="btn soft sm" data-edit="${esc(s.id)}">编辑</button><button class="btn ghost sm" data-del="${esc(s.id)}">${icon("trash", 13)}</button></div></td>
      </tr>`).join("") || `<tr><td colspan="5" class="muted">暂无印张</td></tr>`}</tbody>
    </table></div></div></div>`;
    bindRowActions(body, "sheets", libs, reload, (item) => sheetModal(item, reload));
  } else if (tab === "packagings") {
    body.innerHTML = `<div class="panel"><div class="panel-body" style="padding:0"><div class="table-wrap"><table class="admin-table">
      <thead><tr><th>包装</th><th>装箱数</th><th>箱重</th><th>箱规</th><th>状态</th><th></th></tr></thead>
      <tbody>${(libs.packagings || []).map((p) => `<tr>
        <td><div style="display:flex;align-items:center;gap:9px"><img class="lib-thumb" src="${esc(p.image || "")}"><b>${esc(p.name)}</b></div></td>
        <td class="num">${p.carton_qty} 件/箱</td><td class="num">${p.carton_weight_kg} kg</td><td class="num">${(p.carton_size || []).join(" × ")} mm</td>
        <td><span class="pill ${p.enabled ? "green" : "cream"}">${p.enabled ? "启用" : "停用"}</span></td>
        <td><div class="t-actions"><button class="btn soft sm" data-edit="${esc(p.id)}">编辑</button><button class="btn ghost sm" data-del="${esc(p.id)}">${icon("trash", 13)}</button></div></td>
      </tr>`).join("") || `<tr><td colspan="6" class="muted">暂无包装</td></tr>`}</tbody>
    </table></div></div></div>`;
    bindRowActions(body, "packagings", libs, reload, (item) => packagingModal(item, libs, reload));
  } else if (tab === "algorithms") {
    body.innerHTML = `<div class="grid" style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px">${(libs.algorithms || []).map((a) => `<div class="panel"><div class="panel-body">
      <div style="display:flex;align-items:center;gap:8px"><span class="pill cream">${esc(a.category)}</span><b style="font-size:13px">${esc(a.name)}</b><span class="muted mono" style="margin-left:auto;font-size:9px">${esc(a.id)}</span></div>
      <div class="muted small" style="margin-top:8px;line-height:1.7">${esc(a.formula)}</div>
      <div class="tech-row" style="margin-top:8px"><span>参数</span><b style="font-size:9px">${a.params.map((p) => p.key).join(" / ")}</b></div>
      ${a.note ? `<div class="tiny muted" style="margin-top:6px">${esc(a.note)}</div>` : ""}
    </div></div>`).join("")}</div>`;
  } else if (tab === "structures") {
    body.innerHTML = `<div class="grid" style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px">${(libs.structures || []).map((s) => `<div class="panel"><div class="panel-body">
      <div style="display:flex;align-items:center;gap:8px"><b style="font-size:13px">${esc(s.name)}</b><span class="muted mono" style="margin-left:auto;font-size:9px">${esc(s.id)}</span></div>
      <div class="muted small" style="margin-top:8px;line-height:1.7">${esc(s.formula)}</div>
      <div class="tech-row" style="margin-top:8px"><span>可调余量</span><b style="font-size:9px">${(s.params || []).map((p) => `${p.label} ${p.default}${p.unit || ""}`).join(" / ") || "无"}</b></div>
      <img src="${esc(s.image || "")}" alt="" style="width:100%;border-radius:8px;margin-top:10px;border:1px solid var(--line)">
    </div></div>`).join("")}</div>`;
  }
}

function bindLogout(root) {
  const b = root.querySelector("#adminLogout");
  if (b) b.addEventListener("click", async () => { await api.logout(); await refreshUser(); navigate("/admin"); location.reload(); });
}

function bindRowActions(body, table, libs, reload, editFn) {
  body.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => {
    const item = (libs[table] || []).find((x) => x.id === b.dataset.edit);
    if (item) editFn(item);
  }));
  body.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    if (!(await confirmDialog("删除后不可恢复；若商品正在使用会阻止删除。确认删除？"))) return;
    try { await api.deleteLibrary(table, b.dataset.del); toast("已删除", "ok"); reload(); } catch (e) { toast(e.message, "err"); }
  }));
}

function openNew(tab, reload, libs) {
  if (tab === "materials") materialModal(null, libs, reload);
  else if (tab === "processes") processModal(null, libs, reload);
  else if (tab === "presses") pressModal(null, libs, reload);
  else if (tab === "sheets") sheetModal(null, reload);
  else if (tab === "packagings") packagingModal(null, libs, reload);
}

function paramSummary(params) {
  if (!params) return "—";
  return Object.entries(params).filter(([k]) => k !== "min_charge").slice(0, 3).map(([k, v]) => `${k}=${v}`).join(" · ");
}

function algoOptions(libs, categories, selected) {
  return (libs.algorithms || []).filter((a) => categories.includes(a.category)).map((a) => `<option value="${a.id}" ${a.id === selected ? "selected" : ""}>${esc(a.name)}</option>`).join("");
}

function paramFields(algo, params = {}, scope = "") {
  if (!algo) return `<div class="muted small">请选择计价算法</div>`;
  const p = params || {};
  return `<div class="param-grid">${(algo.params || []).map((s) => `<div class="field"><label>${esc(s.label)}${s.unit ? ` <span class="muted">${esc(s.unit)}</span>` : ""}</label><input class="input" data-param="${esc(s.key)}" type="number" step="any" value="${p[s.key] != null ? p[s.key] : s.default}"></div>`).join("")}</div>`;
}

function bindImage(m, rootSel, fileSel) {
  const file = m.querySelector(fileSel);
  const url = m.querySelector(rootSel);
  const preview = m.querySelector(rootSel + "Preview");
  if (!file) return;
  file.addEventListener("change", async () => {
    const f = file.files[0];
    if (!f) return;
    try {
      const res = await api.upload(f);
      url.value = res.url;
      if (preview) preview.src = res.url;
      toast("图片已上传", "ok");
    } catch (e) { toast(e.message, "err"); }
  });
}

function materialModal(item, libs, reload) {
  const isNew = !item;
  const m0 = item || { kind: "paper", unit: "g/m²", enabled: 1, gsm: 120, sheet_ids: ["sheet-big", "sheet-std", "sheet-4k"], params: {} };
  const algo0 = (libs.algorithms || []).find((a) => a.id === m0.algorithm_id) || (libs.algorithms || []).find((a) => a.category === "材料") || null;
  const sheetChecks = (libs.sheets || []).map((s) => `<label class="check" style="display:inline-flex;margin:0 12px 6px 0"><input type="checkbox" data-sheet="${s.id}" ${(m0.sheet_ids || []).includes(s.id) ? "checked" : ""} style="width:14px;height:14px"> ${esc(s.name)}</label>`).join("");
  openModal(`
    <div class="modal-head"><h3>${isNew ? "新增材料 / 辅料" : "编辑材料"}</h3><button class="x" data-close>×</button></div>
    <div class="modal-body">
      <div class="form-grid">
        <div class="field"><label>名称 *</label><input class="input" id="lmName" value="${esc(m0.name || "")}" placeholder="如：白卡纸 300g"></div>
        <div class="field"><label>类型</label><select class="select" id="lmKind">${Object.entries(KIND).map(([k, v]) => `<option value="${k}" ${m0.kind === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
        <div class="field"><label>克重</label><input class="input" id="lmGsm" type="number" value="${m0.gsm || 0}"></div>
        <div class="field"><label>单位</label><input class="input" id="lmUnit" value="${esc(m0.unit || "")}" placeholder="g/m² / m / 个"></div>
        <div class="field full"><label>图片</label><div class="copy-row"><input class="input" id="lmImage" value="${esc(m0.image || "")}"><label class="btn soft sm">上传<input type="file" id="lmFile" accept="image/*" hidden></label></div><img id="lmImagePreview" src="${esc(m0.image || "")}" style="width:110px;height:74px;object-fit:cover;border-radius:8px;margin-top:8px;border:1px solid var(--line)"></div>
        <div class="field"><label>排序</label><input class="input" id="lmSort" type="number" value="${m0.sort || 0}"></div>
        <div class="field"><label>启用</label><select class="select" id="lmEnabled"><option value="1" ${m0.enabled ? "selected" : ""}>启用</option><option value="0" ${!m0.enabled ? "selected" : ""}>停用</option></select></div>
        <div class="field"><label>计价算法</label><select class="select" id="lmAlgo">${algoOptions(libs, ["材料", "辅料", "成品加印"], algo0 ? algo0.id : "")}</select></div>
        <div class="field full"><label>算法参数</label><div id="lmParams">${paramFields(algo0, m0.params)}</div></div>
        <div class="field full"><label>可上机印张</label><div>${sheetChecks}</div></div>
        <div class="field full"><label>备注</label><textarea class="textarea" id="lmNote" rows="2">${esc(m0.note || "")}</textarea></div>
      </div>
    </div>
    <div class="modal-foot"><button class="btn ghost" data-close>取消</button><button class="btn primary" id="lmSave">保存</button></div>`, { wide: true, onMount: (m) => {
      bindImage(m, "#lmImage", "#lmFile");
      m.querySelector("#lmAlgo").addEventListener("change", (e) => {
        const a = libs.algorithms.find((x) => x.id === e.target.value);
        m.querySelector("#lmParams").innerHTML = paramFields(a, {});
      });
      m.querySelector("#lmSave").addEventListener("click", async () => {
        const algo = libs.algorithms.find((a) => a.id === m.querySelector("#lmAlgo").value);
        const params = {};
        m.querySelectorAll("#lmParams [data-param]").forEach((i) => params[i.dataset.param] = Number(i.value) || 0);
        const data = {
          id: m0.id || "", name: m.querySelector("#lmName").value.trim(), kind: m.querySelector("#lmKind").value,
          gsm: Number(m.querySelector("#lmGsm").value) || 0, unit: m.querySelector("#lmUnit").value.trim(),
          image: m.querySelector("#lmImage").value.trim(), note: m.querySelector("#lmNote").value.trim(),
          sort: Number(m.querySelector("#lmSort").value) || 0, enabled: Number(m.querySelector("#lmEnabled").value),
          algorithm_id: algo ? algo.id : "", params,
          sheet_ids: Array.from(m.querySelectorAll("[data-sheet]:checked")).map((i) => i.dataset.sheet),
        };
        if (!data.name) return toast("请填写名称", "err");
        try { await api.saveLibrary("materials", data); toast("已保存", "ok"); closeModal(); reload(); } catch (e) { toast(e.message, "err"); }
      });
    } });
}

function processModal(item, libs, reload) {
  const isNew = !item;
  const p0 = item || { category: "表面处理", enabled: 1, methods: [], applies_to: [], material_kinds: ["paper", "board"], constraints: {} };
  const algoCats = ["工艺", "成品加印"];
  const methodHtml = (method, i) => {
    const algo = (libs.algorithms || []).find((a) => a.id === (method ? method.algorithm_id : "")) || (libs.algorithms || []).find((a) => a.category === "工艺") || null;
    return `<div class="method-row" data-mi="${i}">
      <div class="mr-head"><b>生产方式 ${i + 1}</b><button class="btn ghost sm" data-remove-method style="margin-left:auto">${icon("trash", 12)}</button></div>
      <div class="form-row three">
        <div class="field"><label>名称</label><input class="input" data-mname value="${esc(method ? method.name : "")}" placeholder="机器糊袋"></div>
        <div class="field"><label>计价算法</label><select class="select" data-malgo>${algoOptions(libs, algoCats, algo ? algo.id : "")}</select></div>
        <div class="field"><label>交期（天）</label><input class="input" data-mdays type="number" value="${method ? method.days : 1}"></div>
        <div class="field"><label>最低数量</label><input class="input" data-mmin type="number" value="${method ? method.min_qty : 0}"></div>
        <div class="field full"><label>生产方式说明</label><input class="input" data-mnote value="${esc(method ? method.note : "")}" placeholder="300 个以上开机"></div>
        <div class="field full"><label>算法参数</label><div data-mparams>${paramFields(algo, method ? method.params : {})}</div></div>
      </div>
    </div>`;
  };
  openModal(`
    <div class="modal-head"><h3>${isNew ? "新增工艺" : "编辑工艺"}</h3><button class="x" data-close>×</button></div>
    <div class="modal-body">
      <div class="form-grid">
        <div class="field"><label>名称 *</label><input class="input" id="lpName" value="${esc(p0.name || "")}" placeholder="如：覆哑膜"></div>
        <div class="field"><label>分类</label><input class="input" id="lpCategory" value="${esc(p0.category || "")}" placeholder="表面处理 / 后道加工 / 成型"></div>
        <div class="field full"><label>图片</label><div class="copy-row"><input class="input" id="lpImage" value="${esc(p0.image || "")}"><label class="btn soft sm">上传<input type="file" id="lpFile" accept="image/*" hidden></label></div><img id="lpImagePreview" src="${esc(p0.image || "")}" style="width:110px;height:74px;object-fit:cover;border-radius:8px;margin-top:8px;border:1px solid var(--line)"></div>
        <div class="field full"><label>说明</label><textarea class="textarea" id="lpDesc" rows="2">${esc(p0.description || "")}</textarea></div>
        <div class="field"><label>适用盒型（逗号分隔）</label><input class="input" id="lpApplies" value="${esc((p0.applies_to || []).join(","))}" placeholder="bag,cardbox,tray,mailer,sleeve,carton,label,overprint"></div>
        <div class="field"><label>适用材料（逗号分隔）</label><input class="input" id="lpKinds" value="${esc((p0.material_kinds || []).join(","))}" placeholder="paper,board"></div>
        <div class="field"><label>最低克重</label><input class="input" id="lpGsm" type="number" value="${(p0.constraints || {}).min_gsm || 0}"></div>
        <div class="field"><label>排序</label><input class="input" id="lpSort" type="number" value="${p0.sort || 0}"></div>
        <div class="field"><label>启用</label><select class="select" id="lpEnabled"><option value="1" ${p0.enabled ? "selected" : ""}>启用</option><option value="0" ${!p0.enabled ? "selected" : ""}>停用</option></select></div>
      </div>
      <div style="display:flex;align-items:center;gap:8px;margin:18px 0 8px"><b style="font-size:12px">生产方式</b><span class="muted tiny">同一工艺可配置多种方式，按数量/交期自动比选</span><button class="btn soft sm" id="lpAddMethod" style="margin-left:auto">${icon("plus", 12)} 添加方式</button></div>
      <div id="lpMethods">${(p0.methods || []).map((m, i) => methodHtml(m, i)).join("") || methodHtml(null, 0)}</div>
    </div>
    <div class="modal-foot"><button class="btn ghost" data-close>取消</button><button class="btn primary" id="lpSave">保存</button></div>`, { wide: true, onMount: (m) => {
      bindImage(m, "#lpImage", "#lpFile");
      const methods = m.querySelector("#lpMethods");
      let counter = methods.children.length;
      methods.addEventListener("change", (e) => {
        if (e.target.matches("[data-malgo]")) {
          const row = e.target.closest(".method-row");
          const a = libs.algorithms.find((x) => x.id === e.target.value);
          row.querySelector("[data-mparams]").innerHTML = paramFields(a, {});
        }
      });
      m.querySelector("#lpAddMethod").addEventListener("click", () => {
        methods.insertAdjacentHTML("beforeend", methodHtml(null, counter++));
      });
      methods.addEventListener("click", (e) => {
        const b = e.target.closest("[data-remove-method]");
        if (b) b.closest(".method-row").remove();
      });
      m.querySelector("#lpSave").addEventListener("click", async () => {
        const methodsData = Array.from(m.querySelectorAll(".method-row")).map((row) => {
          const algo = libs.algorithms.find((a) => a.id === row.querySelector("[data-malgo]").value);
          const params = {};
          row.querySelectorAll("[data-mparam], [data-param]").forEach((i) => params[i.dataset.param] = Number(i.value) || 0);
          return {
            id: "",
            name: row.querySelector("[data-mname]").value.trim(),
            algorithm_id: algo ? algo.id : "",
            params,
            days: Number(row.querySelector("[data-mdays]").value) || 1,
            min_qty: Number(row.querySelector("[data-mmin]").value) || 0,
            note: row.querySelector("[data-mnote]").value.trim(),
          };
        }).filter((x) => x.name);
        const data = {
          id: p0.id || "", name: m.querySelector("#lpName").value.trim(), category: m.querySelector("#lpCategory").value.trim(),
          description: m.querySelector("#lpDesc").value.trim(), image: m.querySelector("#lpImage").value.trim(),
          applies_to: m.querySelector("#lpApplies").value.split(",").map((s) => s.trim()).filter(Boolean),
          material_kinds: m.querySelector("#lpKinds").value.split(",").map((s) => s.trim()).filter(Boolean),
          constraints: { min_gsm: Number(m.querySelector("#lpGsm").value) || 0 },
          methods: methodsData, sort: Number(m.querySelector("#lpSort").value) || 0,
          enabled: Number(m.querySelector("#lpEnabled").value),
        };
        if (!data.name) return toast("请填写名称", "err");
        try { await api.saveLibrary("processes", data); toast("已保存", "ok"); closeModal(); reload(); } catch (e) { toast(e.message, "err"); }
      });
    } });
}

function pressModal(item, libs, reload) {
  const isNew = !item;
  const p0 = item || { type: "offset", max_w: 740, max_h: 520, days: 2, colors_max: 4, enabled: 1, sheet_ids: [], material_kinds: ["paper", "board"], params: {} };
  const algo0 = (libs.algorithms || []).find((a) => a.id === p0.algorithm_id) || (libs.algorithms || []).find((a) => a.category === "印刷") || null;
  openModal(`
    <div class="modal-head"><h3>${isNew ? "新增设备" : "编辑设备"}</h3><button class="x" data-close>×</button></div>
    <div class="modal-body">
      <div class="form-grid">
        <div class="field"><label>名称 *</label><input class="input" id="prName" value="${esc(p0.name || "")}"></div>
        <div class="field"><label>类型</label><select class="select" id="prType">${["offset", "digital", "label", "flexo", "screen"].map((t) => `<option value="${t}" ${p0.type === t ? "selected" : ""}>${t}</option>`).join("")}</select></div>
        <div class="field"><label>归属报价工厂</label><select class="select" id="prFactory"><option value="">未归属</option>${(libs.factories || []).map((f) => `<option value="${f.id}" ${p0.factory_id === f.id ? "selected" : ""}>${esc(f.name)}</option>`).join("")}</select></div>
        <div class="field"><label>最大宽 mm</label><input class="input" id="prW" type="number" value="${p0.max_w}"></div>
        <div class="field"><label>最大高 mm</label><input class="input" id="prH" type="number" value="${p0.max_h}"></div>
        <div class="field"><label>最多色数</label><input class="input" id="prColors" type="number" value="${p0.colors_max}"></div>
        <div class="field"><label>交期（天）</label><input class="input" id="prDays" type="number" value="${p0.days}"></div>
        <div class="field"><label>计价算法</label><select class="select" id="prAlgo">${algoOptions(libs, ["印刷", "成品加印"], algo0 ? algo0.id : "")}</select></div>
        <div class="field"><label>启用</label><select class="select" id="prEnabled"><option value="1" ${p0.enabled ? "selected" : ""}>启用</option><option value="0" ${!p0.enabled ? "selected" : ""}>停用</option></select></div>
        <div class="field full"><label>算法参数</label><div id="prParams">${paramFields(algo0, p0.params)}</div></div>
        <div class="field full"><label>可用印张</label><div>${(libs.sheets || []).map((s) => `<label class="check" style="display:inline-flex;margin:0 12px 6px 0"><input type="checkbox" data-psheet="${s.id}" ${(p0.sheet_ids || []).includes(s.id) ? "checked" : ""} style="width:14px;height:14px"> ${esc(s.name)}</label>`).join("")}</div></div>
        <div class="field full"><label>适用材料</label><div>${["paper", "board", "corrugated", "label", "stock"].map((k) => `<label class="check" style="display:inline-flex;margin:0 12px 6px 0"><input type="checkbox" data-pkind="${k}" ${(p0.material_kinds || []).includes(k) ? "checked" : ""} style="width:14px;height:14px"> ${KIND[k] || k}</label>`).join("")}</div></div>
      </div>
    </div>
    <div class="modal-foot"><button class="btn ghost" data-close>取消</button><button class="btn primary" id="prSave">保存</button></div>`, { wide: true, onMount: (m) => {
      m.querySelector("#prAlgo").addEventListener("change", (e) => {
        const a = libs.algorithms.find((x) => x.id === e.target.value);
        m.querySelector("#prParams").innerHTML = paramFields(a, {});
      });
      m.querySelector("#prSave").addEventListener("click", async () => {
        const algo = libs.algorithms.find((a) => a.id === m.querySelector("#prAlgo").value);
        const params = {};
        m.querySelectorAll("#prParams [data-param]").forEach((i) => params[i.dataset.param] = Number(i.value) || 0);
        const data = {
          id: p0.id || "", name: m.querySelector("#prName").value.trim(), type: m.querySelector("#prType").value,
          max_w: Number(m.querySelector("#prW").value), max_h: Number(m.querySelector("#prH").value),
          factory_id: m.querySelector("#prFactory").value,
          colors_max: Number(m.querySelector("#prColors").value), days: Number(m.querySelector("#prDays").value),
          algorithm_id: algo ? algo.id : "", params, enabled: Number(m.querySelector("#prEnabled").value),
          sheet_ids: Array.from(m.querySelectorAll("[data-psheet]:checked")).map((i) => i.dataset.psheet),
          material_kinds: Array.from(m.querySelectorAll("[data-pkind]:checked")).map((i) => i.dataset.pkind),
        };
        if (!data.name) return toast("请填写名称", "err");
        try { await api.saveLibrary("presses", data); toast("已保存", "ok"); closeModal(); reload(); } catch (e) { toast(e.message, "err"); }
      });
    } });
}

function sheetModal(item, reload) {
  const isNew = !item;
  const s0 = item || { w: 889, h: 1194, edge: 8, grip: 10, note: "" };
  openModal(`
    <div class="modal-head"><h3>${isNew ? "新增印张" : "编辑印张"}</h3><button class="x" data-close>×</button></div>
    <div class="modal-body">
      <div class="form-grid">
        <div class="field full"><label>名称 *</label><input class="input" id="lsName" value="${esc(s0.name || "")}" placeholder="大度 889×1194"></div>
        <div class="field"><label>宽 mm</label><input class="input" id="lsW" type="number" value="${s0.w}"></div>
        <div class="field"><label>高 mm</label><input class="input" id="lsH" type="number" value="${s0.h}"></div>
        <div class="field"><label>咬口 mm</label><input class="input" id="lsGrip" type="number" value="${s0.grip}"></div>
        <div class="field"><label>边距 mm</label><input class="input" id="lsEdge" type="number" value="${s0.edge}"></div>
        <div class="field full"><label>说明</label><input class="input" id="lsNote" value="${esc(s0.note || "")}"></div>
      </div>
    </div>
    <div class="modal-foot"><button class="btn ghost" data-close>取消</button><button class="btn primary" id="lsSave">保存</button></div>`, { onMount: (m) => {
      m.querySelector("#lsSave").addEventListener("click", async () => {
        const data = { id: s0.id || "", name: m.querySelector("#lsName").value.trim(), w: Number(m.querySelector("#lsW").value), h: Number(m.querySelector("#lsH").value), grip: Number(m.querySelector("#lsGrip").value), edge: Number(m.querySelector("#lsEdge").value), note: m.querySelector("#lsNote").value.trim() };
        if (!data.name) return toast("请填写名称", "err");
        try { await api.saveLibrary("sheets", data); toast("已保存", "ok"); closeModal(); reload(); } catch (e) { toast(e.message, "err"); }
      });
    } });
}

function packagingModal(item, libs, reload) {
  const isNew = !item;
  const p0 = item || { carton_qty: 100, carton_weight_kg: 0.6, carton_size: [600, 400, 400], enabled: 1, params: {} };
  const algo0 = (libs.algorithms || []).find((a) => a.id === p0.algorithm_id) || (libs.algorithms || []).find((a) => a.category === "包装") || null;
  const size = p0.carton_size || [600, 400, 400];
  openModal(`
    <div class="modal-head"><h3>${isNew ? "新增包装方式" : "编辑包装方式"}</h3><button class="x" data-close>×</button></div>
    <div class="modal-body">
      <div class="form-grid">
        <div class="field"><label>名称 *</label><input class="input" id="lpkgName" value="${esc(p0.name || "")}"></div>
        <div class="field"><label>装箱数（件/箱）</label><input class="input" id="lpkgQty" type="number" value="${p0.carton_qty}"></div>
        <div class="field"><label>箱重 kg</label><input class="input" id="lpkgWeight" type="number" step="0.1" value="${p0.carton_weight_kg}"></div>
        <div class="field"><label>箱规 mm（长×宽×高）</label><div style="display:flex;gap:6px"><input class="input" id="lpkgL" type="number" value="${size[0]}"><input class="input" id="lpkgW" type="number" value="${size[1]}"><input class="input" id="lpkgH" type="number" value="${size[2]}"></div></div>
        <div class="field full"><label>图片</label><div class="copy-row"><input class="input" id="lpkgImage" value="${esc(p0.image || "")}"><label class="btn soft sm">上传<input type="file" id="lpkgFile" accept="image/*" hidden></label></div><img id="lpkgImagePreview" src="${esc(p0.image || "")}" style="width:110px;height:74px;object-fit:cover;border-radius:8px;margin-top:8px;border:1px solid var(--line)"></div>
        <div class="field"><label>计价算法</label><select class="select" id="lpkgAlgo">${algoOptions(libs, ["包装"], algo0 ? algo0.id : "")}</select></div>
        <div class="field"><label>启用</label><select class="select" id="lpkgEnabled"><option value="1" ${p0.enabled ? "selected" : ""}>启用</option><option value="0" ${!p0.enabled ? "selected" : ""}>停用</option></select></div>
        <div class="field full"><label>算法参数</label><div id="lpkgParams">${paramFields(algo0, p0.params)}</div></div>
        <div class="field full"><label>说明</label><textarea class="textarea" id="lpkgDesc" rows="2">${esc(p0.description || "")}</textarea></div>
      </div>
    </div>
    <div class="modal-foot"><button class="btn ghost" data-close>取消</button><button class="btn primary" id="lpkgSave">保存</button></div>`, { wide: true, onMount: (m) => {
      bindImage(m, "#lpkgImage", "#lpkgFile");
      m.querySelector("#lpkgAlgo").addEventListener("change", (e) => {
        const a = libs.algorithms.find((x) => x.id === e.target.value);
        m.querySelector("#lpkgParams").innerHTML = paramFields(a, {});
      });
      m.querySelector("#lpkgSave").addEventListener("click", async () => {
        const algo = libs.algorithms.find((a) => a.id === m.querySelector("#lpkgAlgo").value);
        const params = {};
        m.querySelectorAll("#lpkgParams [data-param]").forEach((i) => params[i.dataset.param] = Number(i.value) || 0);
        const data = {
          id: p0.id || "", name: m.querySelector("#lpkgName").value.trim(), description: m.querySelector("#lpkgDesc").value.trim(),
          image: m.querySelector("#lpkgImage").value.trim(), carton_qty: Number(m.querySelector("#lpkgQty").value),
          carton_weight_kg: Number(m.querySelector("#lpkgWeight").value),
          carton_size: [Number(m.querySelector("#lpkgL").value), Number(m.querySelector("#lpkgW").value), Number(m.querySelector("#lpkgH").value)],
          algorithm_id: algo ? algo.id : "", params, enabled: Number(m.querySelector("#lpkgEnabled").value),
        };
        if (!data.name) return toast("请填写名称", "err");
        try { await api.saveLibrary("packagings", data); toast("已保存", "ok"); closeModal(); reload(); } catch (e) { toast(e.message, "err"); }
      });
    } });
}
