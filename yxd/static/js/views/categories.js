import { api } from "../api.js";
import { esc, icon, toast, openModal, closeModal, confirmDialog, navigate } from "../core.js";

const PLACEHOLDER = "/assets/ui/placeholder.svg";

export async function renderCategories(root, params = {}, shell) {
  let cats = [];
  try { cats = (await api.adminCategories()).categories || []; }
  catch (e) { if (e.status === 401) return; toast(e.message, "err"); return; }

  const content = `
    <div class="admin-toolbar">
      <div class="search">${icon("search", 15)}<input class="input" id="catSearch" placeholder="搜索类目名称 / 编码"></div>
      <div class="right"><button class="btn primary sm" id="addCategory">${icon("plus", 14)} 新增类目</button></div>
    </div>
    <div class="panel"><div class="panel-body" style="padding:0">
      <div class="table-wrap"><table class="admin-table" id="catTable">
        <thead><tr><th>类目</th><th>编码</th><th>上级类目</th><th>默认建品方式</th><th>商品数</th><th>状态</th><th></th></tr></thead>
        <tbody>${cats.map((c) => {
          const parent = cats.find((x) => x.id === c.parent_id);
          return `<tr data-text="${esc((c.name + " " + (c.code || "")).toLowerCase())}">
            <td><div style="display:flex;align-items:center;gap:9px"><img class="lib-thumb" src="${esc(c.image || PLACEHOLDER)}"><b>${esc(c.name)}</b><div class="muted" style="font-size:9px">${esc(c.desc || "")}</div></div></td>
            <td class="mono">${esc(c.code || c.id)}</td>
            <td>${esc(parent ? parent.name : "—")}</td>
            <td><span class="pill ${c.pricing_default === "standard" ? "cream" : "gold"}">${c.pricing_default === "standard" ? "标准定价" : c.pricing_default === "both" ? "标准 + 非标" : "非标计价"}</span></td>
            <td class="num">${c.product_count || 0}</td>
            <td><span class="pill ${c.enabled !== 0 ? "green" : "cream"}">${c.enabled !== 0 ? "启用" : "停用"}</span></td>
            <td><div class="t-actions"><a class="btn ghost sm" href="#/admin/products?category=${encodeURIComponent(c.id)}">${icon("product", 13)} 商品</a><button class="btn soft sm" data-edit="${esc(c.id)}">编辑</button><button class="btn ghost sm" data-del="${esc(c.id)}">${icon("trash", 13)}</button></div></td>
          </tr>`;
        }).join("") || `<tr><td colspan="7" class="muted">还没有类目</td></tr>`}</tbody>
      </table></div>
    </div></div>
    <div class="banner info" style="margin-top:14px">${icon("layers", 15)} 类目用于商品归属、商品列表筛选和建品时选择；类目下还有商品时不能删除，只能停用。</div>`;

  root.innerHTML = shell(content, "categories");
  const logout = root.querySelector("#adminLogout");
  if (logout) logout.addEventListener("click", () => { location.hash = "#/admin"; });
  const table = root.querySelector("#catTable");
  root.querySelector("#catSearch").addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    table.querySelectorAll("tbody tr").forEach((tr) => { tr.style.display = !q || (tr.dataset.text || "").includes(q) ? "" : "none"; });
  });
  const reload = () => renderCategories(root, params, shell);
  root.querySelector("#addCategory").addEventListener("click", () => categoryModal(null, cats, reload));
  table.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => {
    const c = cats.find((x) => x.id === b.dataset.edit);
    categoryModal(c, cats, reload);
  }));
  table.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    const c = cats.find((x) => x.id === b.dataset.del);
    if (!(await confirmDialog(`删除类目「${esc(c.name)}」？类目下还有商品时会被阻止。`, { danger: true, ok: "删除" }))) return;
    try {
      await api.deleteCategory(b.dataset.del);
      toast("类目已删除", "ok");
      reload();
    } catch (e) { toast(e.message, "err"); }
  }));
}

function categoryModal(c, cats, reload) {
  const isNew = !c;
  const c0 = c || { enabled: 1, pricing_default: "nonstandard", sort: cats.length + 1 };
  openModal(`
    <div class="modal-head"><h3>${isNew ? "新增类目" : "编辑类目"}</h3><button class="x" data-close>×</button></div>
    <div class="modal-body">
      <div class="form-grid">
        <div class="field"><label>类目名称 *</label><input class="input" id="catName" value="${esc(c0.name || "")}" placeholder="如：手提纸袋"></div>
        <div class="field"><label>类目编码</label><input class="input" id="catCode" value="${esc(c0.code || "")}" placeholder="BAG / BOX"></div>
        <div class="field"><label>上级类目</label><select class="select" id="catParent"><option value="">无（一级类目）</option>${cats.filter((x) => x.id !== c0.id).map((x) => `<option value="${x.id}" ${c0.parent_id === x.id ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div>
        <div class="field"><label>默认建品方式</label><select class="select" id="catDefault"><option value="nonstandard" ${c0.pricing_default === "nonstandard" ? "selected" : ""}>非标计价</option><option value="standard" ${c0.pricing_default === "standard" ? "selected" : ""}>标准定价</option><option value="both" ${c0.pricing_default === "both" ? "selected" : ""}>两者都支持</option></select></div>
        <div class="field"><label>排序</label><input class="input" id="catSort" type="number" value="${c0.sort || 0}"></div>
        <div class="field"><label>状态</label><select class="select" id="catEnabled"><option value="1" ${c0.enabled !== 0 ? "selected" : ""}>启用</option><option value="0" ${c0.enabled === 0 ? "selected" : ""}>停用</option></select></div>
        <div class="field full"><label>类目图片</label><div class="copy-row"><input class="input" id="catImage" value="${esc(c0.image || "")}"><label class="btn soft sm">上传<input type="file" id="catFile" accept="image/*" hidden></label></div><img id="catImagePreview" src="${esc(c0.image || PLACEHOLDER)}" style="width:110px;height:74px;object-fit:cover;border-radius:8px;margin-top:8px;border:1px solid var(--line)"></div>
        <div class="field full"><label>类目说明</label><textarea class="textarea" id="catDesc" rows="2">${esc(c0.desc || "")}</textarea></div>
      </div>
    </div>
    <div class="modal-foot"><button class="btn ghost" data-close>取消</button><button class="btn primary" id="catSave">保存</button></div>`, { onMount: (m) => {
      m.querySelector("#catFile").addEventListener("change", async (e) => {
        const f = e.target.files[0];
        if (!f) return;
        try {
          const res = await api.upload(f);
          m.querySelector("#catImage").value = res.url;
          m.querySelector("#catImagePreview").src = res.url;
          toast("图片已上传", "ok");
        } catch (err) { toast(err.message, "err"); }
      });
      m.querySelector("#catSave").addEventListener("click", async () => {
        const name = m.querySelector("#catName").value.trim();
        if (!name) return toast("请填写类目名称", "err");
        const payload = {
          id: c0.id || "",
          name,
          code: m.querySelector("#catCode").value.trim(),
          parent_id: m.querySelector("#catParent").value,
          pricing_default: m.querySelector("#catDefault").value,
          sort: Number(m.querySelector("#catSort").value) || 0,
          enabled: Number(m.querySelector("#catEnabled").value),
          image: m.querySelector("#catImage").value.trim(),
          desc: m.querySelector("#catDesc").value.trim(),
        };
        try {
          await api.saveCategory(payload);
          toast("类目已保存", "ok");
          closeModal();
          reload();
        } catch (e) { toast(e.message, "err"); }
      });
    } });
}
