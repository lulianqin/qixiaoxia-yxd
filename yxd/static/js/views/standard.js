import { api } from "../api.js";
import { esc, money, num, icon, toast, navigate, openModal, closeModal } from "../core.js";

const PLACEHOLDER = "/assets/ui/placeholder.svg";

export async function renderStandardProduct(root, params = {}, shell, loginFallback) {
  let product = null;
  let libs;
  try {
    libs = await api.libraries();
    if (params.id) product = (await api.adminProduct(params.id)).product;
  } catch (e) {
    if (e.status === 401) return loginFallback(root, params);
    toast(e.message, "err");
    return;
  }
  if (product && (product.pricing_mode || "nonstandard") !== "standard") {
    navigate("/admin/products/" + product.id + "/edit");
    return;
  }
  const p = product || {};
  const cats = (libs.categories || []).filter((c) => c.enabled !== 0);
  const img = (p.images && p.images[0]) || p.image || PLACEHOLDER;
  const content = `
    <div class="admin-grid" style="grid-template-columns:1.15fr .55fr;margin-top:0;align-items:start">
      <div class="panel">
        <div class="panel-head"><h3>标准定价信息</h3><span class="right">固定售价 · 不进入非标计价</span></div>
        <div class="panel-body">
          <div class="banner info">${icon("product", 15)} 标准商品沿用商品中心/ERP 的固定价格；这里只补充建品信息与对外展示内容。</div>
          <div class="form-grid">
            <div class="field full"><label>商品名称 *</label><input class="input" id="stName" value="${esc(p.name || "")}" placeholder="如：现货牛皮纸袋 220×90×300"></div>
            <div class="field"><label>商品编码 / SKU</label><input class="input" id="stSku" value="${esc(p.sku || "")}" placeholder="与 ERP 编码一致"></div>
            <div class="field"><label>类目 *</label><select class="select" id="stCategory">${cats.map((c) => `<option value="${c.id}" ${p.category === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select><span class="hint"><a class="link-btn" href="#/admin/categories">管理类目 →</a></span></div>
            <div class="field"><label>标准售价 *</label><input class="input" id="stPrice" type="number" step="0.01" value="${p.standard_price != null ? p.standard_price : ""}" placeholder="0.00"></div>
            <div class="field"><label>计价单位</label><input class="input" id="stUnit" value="${esc(p.unit || "个")}" placeholder="个 / 套 / 张"></div>
            <div class="field"><label>起订量</label><input class="input" id="stMoq" type="number" value="${(p.quantity && p.quantity.min) || 1}"></div>
            <div class="field"><label>交期（天）</label><input class="input" id="stLead" type="number" value="${p.lead_days || 3}"></div>
            <div class="field"><label>交付方式</label><select class="select" id="stDelivery"><option value="home" selected>送货上门</option></select></div>
            <div class="field"><label>发货仓</label><input class="input" id="stWarehouse" value="${esc((p.logistics || {}).warehouse || "杭州中心仓")}"></div>
            <div class="field"><label>运费</label><select class="select" id="stFreight"><option value="1" ${!(p.logistics && p.logistics.included === false) ? "selected" : ""}>售价含送货上门运费</option><option value="0" ${p.logistics && p.logistics.included === false ? "selected" : ""}>运费另计</option></select></div>
            <div class="field full"><label>物流说明</label><input class="input" id="stLogisticsNote" value="${esc((p.logistics || {}).note || "全国送货上门，偏远地区另议。")}"></div>
            <div class="field full"><label>副标题</label><input class="input" id="stSubtitle" value="${esc(p.subtitle || "")}" placeholder="一句话说明规格与卖点"></div>
            <div class="field full"><label>商品主图</label>
              <div class="copy-row"><input class="input" id="stImage" value="${esc(img)}"><label class="btn soft sm">上传<input type="file" id="stFile" accept="image/*" hidden></label></div>
              <img id="stImagePreview" src="${esc(img)}" style="width:180px;height:120px;object-fit:cover;border-radius:10px;margin-top:9px;border:1px solid var(--line)">
            </div>
            <div class="field full"><label>详情描述</label><textarea class="textarea" id="stDesc" rows="3">${esc(p.description || "")}</textarea></div>
            <div class="field"><label>角标</label><input class="input" id="stBadge" value="${esc(p.badge || "")}" placeholder="热销 / 新品 / 现货"></div>
            <div class="field"><label>排序</label><input class="input" id="stSort" type="number" value="${p.sort || 0}"></div>
            <div class="field"><label>状态</label><select class="select" id="stStatus"><option value="draft" ${p.status !== "active" ? "selected" : ""}>草稿</option><option value="active" ${p.status === "active" ? "selected" : ""}>上架</option><option value="disabled" ${p.status === "disabled" ? "selected" : ""}>下架</option></select></div>
          </div>
        </div>
        <div class="panel-head" style="border-top:1px solid var(--line);border-bottom:0;justify-content:flex-end">
          <button class="btn ghost" id="stCancel">取消</button>
          <button class="btn soft" id="stDraft">保存草稿</button>
          <button class="btn primary" id="stPublish">保存并上架</button>
        </div>
      </div>

      <div>
        <div class="phone-preview"><div class="phone-screen">
          <div class="phone-top"><span>9:41</span><span class="phone-notch"></span><span>●●●</span></div>
          <div class="phone-hero"><img id="stPhoneImg" src="${esc(img)}" alt=""></div>
          <div class="phone-body">
            <div class="pm-chip">标准定价 · 固定价格</div>
            <h4 id="stPhoneName">${esc(p.name || "未命名商品")}</h4>
            <div class="pm-sub" id="stPhoneSub">${esc(p.subtitle || "填写副标题，展示在商品卡片")}</div>
            <div class="pm-price"><b id="stPhonePrice">${p.standard_price ? money(p.standard_price) : "—"}</b><span>/<span id="stPhoneUnit">${esc(p.unit || "个")}</span></span></div>
            <div class="pm-options"><span>${p.sku ? "SKU " + esc(p.sku) : "未填 SKU"}</span><span>起订 ${(p.quantity && p.quantity.min) || 1}</span></div>
            <div class="pm-btn">查看商品</div>
          </div>
        </div></div>
        <div class="tech-box">
          <h4>标准商品说明</h4>
          <div class="tech-row"><span>计价方式</span><b>固定单价</b></div>
          <div class="tech-row"><span>不参与</span><b>展开/拼版/工艺比选</b></div>
          <div class="tech-row"><span>适合</span><b>ERP 已有标准价的商品</b></div>
          <p class="tiny muted" style="margin-top:10px">非标商品请从「新建商品 → 非标计价」进入 8 步建品向导。</p>
        </div>
        <div class="tech-box" style="margin-top:12px">
          <h4>数据导出</h4>
          <div style="display:grid;gap:7px">
            <a class="btn soft block ${p.id ? "" : "hide"}" id="stPreviewLink" href="#/admin/products/${encodeURIComponent(p.id || "")}/preview">${icon("shop", 14)} 商品预览</a>
            <a class="btn ghost block ${p.id ? "" : "hide"}" id="stMobileLink" href="#/admin/products/${encodeURIComponent(p.id || "")}/mobile">${icon("phone", 14)} 手机前端预览</a>
            <a class="btn ghost block ${p.id ? "" : "hide"}" id="stExportLink" href="/api/admin/products/${encodeURIComponent(p.id || "")}/export" target="_blank">${icon("download", 14)} 导出商品 JSON</a>
          </div>
          <p class="tiny muted" style="margin-top:10px">导出的 JSON 可直接交给商品中心/ERP 建品。</p>
        </div>
      </div>
    </div>`;
  root.innerHTML = shell(content, "standard", "products");
  const $ = (s) => root.querySelector(s);
  const logout = root.querySelector("#adminLogout");
  if (logout) logout.addEventListener("click", () => { location.hash = "#/admin"; });

  // bind live preview
  const bindPreview = () => {
    $("#stPhoneName").textContent = $("#stName").value || "未命名商品";
    $("#stPhoneSub").textContent = $("#stSubtitle").value || "填写副标题，展示在商品卡片";
    $("#stPhonePrice").textContent = $("#stPrice").value ? money($("#stPrice").value) : "—";
    $("#stPhoneUnit").textContent = $("#stUnit").value || "个";
  };
  ["#stName", "#stSubtitle", "#stPrice", "#stUnit"].forEach((sel) => $(sel).addEventListener("input", bindPreview));

  $("#stFile").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const res = await api.upload(f);
      $("#stImage").value = res.url;
      $("#stImagePreview").src = res.url;
      $("#stPhoneImg").src = res.url;
      toast("图片已上传", "ok");
    } catch (err) { toast(err.message, "err"); }
  });

  async function save(status) {
    const name = $("#stName").value.trim();
    const category = $("#stCategory").value;
    const price = Number($("#stPrice").value);
    if (!name) return toast("请填写商品名称", "err");
    if (!category) return toast("请选择类目", "err");
    if (!(price > 0)) return toast("请填写标准售价", "err");
    const image = $("#stImage").value.trim() || PLACEHOLDER;
    const payload = {
      id: p.id || "",
      pricing_mode: "standard",
      kind: "standard",
      modes: ["standard"],
      name,
      sku: $("#stSku").value.trim(),
      category,
      standard_price: price,
      unit: $("#stUnit").value.trim() || "个",
      subtotal: "",
      status,
      badge: $("#stBadge").value.trim(),
      sort: Number($("#stSort").value) || 0,
      lead_days: Number($("#stLead").value) || 3,
      subtitle: $("#stSubtitle").value.trim(),
      description: $("#stDesc").value.trim(),
      images: [image],
      image,
      quantity: { min: Number($("#stMoq").value) || 1, max: 999999, step: 1, presets: [] },
      logistics: {
        mode: "home", provider: "统一配送", warehouse: $("#stWarehouse").value.trim() || "杭州中心仓",
        included: $("#stFreight").value === "1", base_fee: 10, per_kg: 1.8, free_over: 3000, lead_days: 1,
        note: $("#stLogisticsNote").value.trim(),
      },
    };
    try {
      const res = await api.saveProduct({ product: payload });
      const saved = res.product;
      p.id = saved.id;
      if (!params.id) history.replaceState(null, "", "#/admin/products/" + saved.id + "/edit");
      $("#stPreviewLink").href = "#/admin/products/" + saved.id + "/preview";
      $("#stPreviewLink").classList.remove("hide");
      $("#stExportLink").href = "/api/admin/products/" + saved.id + "/export";
      $("#stExportLink").classList.remove("hide");
      toast(status === "active" ? "已保存并上架" : "草稿已保存", "ok");
      if (status === "active") navigate("/admin/products");
    } catch (e) { toast(e.message, "err"); }
  }
  $("#stPublish").addEventListener("click", () => save("active"));
  $("#stDraft").addEventListener("click", () => save("draft"));
  $("#stCancel").addEventListener("click", () => navigate("/admin/products"));
}
