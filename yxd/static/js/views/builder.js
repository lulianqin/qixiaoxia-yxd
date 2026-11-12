import { api } from "../api.js";
import { state, refreshUser } from "../store.js";
import { esc, money, num, icon, toast, debounce, navigate, pct, openModal, closeModal } from "../core.js";

const STEPS = [
  { id: 1, name: "基础信息" },
  { id: 2, name: "成品尺寸" },
  { id: 3, name: "拼版" },
  { id: 4, name: "原辅料" },
  { id: 5, name: "生产工艺" },
  { id: 6, name: "包装方式" },
  { id: 7, name: "定制数量" },
  { id: 8, name: "生产方案" },
  { id: 9, name: "计价发布" },
];

const KIND_LABEL = { paper: "纸张", board: "纸板", corrugated: "瓦楞", label: "不干胶", aux: "辅料" };
function priceLabel(m) {
  const p = m.params || {};
  if (p.price_per_m2 != null) return "¥" + p.price_per_m2 + "/m²";
  if (p.price_per_sheet != null) return "¥" + p.price_per_sheet + "/张";
  if (p.price_per_piece != null) return "¥" + p.price_per_piece + "/件";
  if (p.price_per_m != null) return "¥" + p.price_per_m + "/m";
  if (p.price_per_kg != null) return "¥" + p.price_per_kg + "/kg";
  return m.algorithm_id || "";
}
const PLACEHOLDER = "/assets/ui/placeholder.svg";

export async function renderBuilder(root, params = {}, shell, loginFallback) {
  let libs;
  try { libs = await api.libraries(); } catch (e) { if (e.status === 401) return loginFallback(root, params); return; }
  let draft;
  if (params.id) {
    try { draft = (await api.adminProduct(params.id)).product; }
    catch (e) { toast("商品不存在", "err"); navigate("/admin/products"); return; }
  } else {
    draft = blankDraft(libs);
  }
  draft = normalizeDraft(draft, libs);
  let step = Number(params.step) || 1;
  let preview = null;
  let previewSeq = 0;
  let saving = false;

  const content = `<div class="builder">
    <div class="builder-main">
      <div class="stepper" id="stepper">${STEPS.map((s) => `<button data-step="${s.id}" class="${s.id === step ? "active" : ""}"><span>${s.id}</span>${s.name}</button>`).join("")}</div>
      <div class="builder-panel" id="builderPanel"></div>
    </div>
    <aside class="builder-aside">
      <div class="phone-preview"><div class="phone-screen">
        <div class="phone-top"><span>9:41</span><span class="phone-notch"></span><span>●●●</span></div>
        <div class="phone-hero"><img id="bpImage" src="${esc(draft.images && draft.images[0] || PLACEHOLDER)}" alt=""></div>
        <div class="phone-body">
          <div class="pm-chip" id="bpKind">全定制 · 实时预览</div>
          <h4 id="bpName">${esc(draft.name || "未命名产品")}</h4>
          <div class="pm-sub" id="bpSub">${esc(draft.subtitle || "填写副标题，展示在商城卡片")}</div>
          <div class="pm-price"><b id="bpPrice">—</b><span>/件起</span></div>
          <div class="pm-options" id="bpChips"></div>
          <div class="pm-btn">保存报价单</div>
        </div>
      </div></div>
      <div class="tech-box" id="techBox"><h4>技术校验</h4><div class="muted small">正在校验…</div></div>
      <div class="tech-box">
        <h4>发布</h4>
        <div style="display:grid;gap:7px">
          <button class="btn soft block" id="saveDraft">保存草稿</button>
          <button class="btn primary block" id="publish">发布上架</button>
          <a class="btn ghost block ${draft.id ? "" : "hide"}" id="previewLink" href="#/admin/products/${encodeURIComponent(draft.id || "")}/mobile" target="_blank">${icon("phone", 14)} 手机前端预览</a>
        </div>
        <p class="tiny muted" style="margin-top:10px">草稿仅后台可见；发布后可供前端/ERP 使用。修改资料库价格会影响已发布商品的后续报价。</p>
      </div>
    </aside>
  </div>`;

  root.innerHTML = shell(content, "builder", "products");
  root.querySelector("#adminLogout")?.addEventListener("click", async () => {
    await api.logout(); await refreshUser(); navigate("/admin"); location.reload();
  });
  const panel = root.querySelector("#builderPanel");
  const techBox = root.querySelector("#techBox");

  // ------------------------------------------------------------ navigation
  root.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => {
    step = Number(b.dataset.step);
    renderStep();
    root.querySelectorAll("[data-step]").forEach((x) => x.classList.toggle("active", Number(x.dataset.step) === step));
  }));

  function goStep(n) {
    step = Math.max(1, Math.min(9, n));
    renderStep();
    root.querySelectorAll("[data-step]").forEach((x) => x.classList.toggle("active", Number(x.dataset.step) === step));
    root.querySelector("#builderPanel").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ------------------------------------------------------------ render step
  function renderStep() {
    const s = STEPS.find((x) => x.id === step);
    panel.innerHTML = stepHtml(step, draft, libs, preview) + `
      <div class="builder-foot">
        <button class="btn ghost" id="stepPrev" ${step === 1 ? "disabled" : ""}>上一步</button>
        <span class="muted small" style="align-self:center">第 ${step} / 9 步 · ${esc(s.name)}</span>
        <div class="right">
          <button class="btn soft" id="stepSave">保存草稿</button>
          ${step < 9 ? `<button class="btn primary" id="stepNext">下一步 ${icon("arrow", 14)}</button>` : `<button class="btn primary" id="stepPublish">发布上架</button>`}
        </div>
      </div>`;
    panel.querySelector("#stepPrev")?.addEventListener("click", () => goStep(step - 1));
    panel.querySelector("#stepNext")?.addEventListener("click", () => goStep(step + 1));
    panel.querySelector("#stepSave")?.addEventListener("click", () => saveProduct("draft"));
    panel.querySelector("#stepPublish")?.addEventListener("click", () => saveProduct("active"));
    bindPanel();
    renderPlanPreview();
  }

  // ------------------------------------------------------------ binding
  function bindPanel() {
    panel.querySelectorAll("[data-bind]").forEach((el) => {
      const ev = (el.tagName === "SELECT" || el.type === "checkbox") ? "change" : "input";
      el.addEventListener(ev, () => {
        let v;
        if (el.type === "checkbox") v = el.checked;
        else if (el.dataset.type === "number") v = Number(el.value) || 0;
        else if (el.dataset.type === "lines") v = el.value.split("\n").map((x) => x.trim()).filter(Boolean);
        else if (el.dataset.type === "numlist") v = el.value.split(/[,，\s]+/).map((x) => Number(x)).filter((x) => x > 0);
        else if (el.dataset.type === "commalist") v = el.value.split(/[,，\s]+/).map((x) => x.trim()).filter(Boolean);
        else if (el.dataset.type === "specs") v = el.value.split("\n").map((x) => x.trim()).filter(Boolean).map((x) => { const [label, ...rest] = x.split("|"); return { label: (label || "").trim(), value: rest.join("|").trim() }; }).filter((x) => x.label);
        else if (el.dataset.type === "faq") v = el.value.split("\n").map((x) => x.trim()).filter(Boolean).map((x) => { const [q, ...rest] = x.split("|"); return { q: (q || "").trim(), a: rest.join("|").trim() }; }).filter((x) => x.q);
        else v = el.value;
        setPath(draft, el.dataset.bind, v);
        schedulePreview();
        if (el.dataset.rerender) renderStep();
      });
    });

    // kind
    const kind = panel.querySelector("#kindSelect");
    if (kind) kind.addEventListener("change", () => {
      draft.kind = kind.value;
      if (kind.value === "overprint") {
        draft.modes = ["overprint"];
        if (!draft.stock) draft.stock = { name: "", dims: { L: 220, W: 90, H: 300 }, blank_price: 1.8, stock_qty: 1000, lead_days: 3, image: draft.images[0] || PLACEHOLDER };
        if (!draft.overprint_methods || !draft.overprint_methods.length) draft.overprint_methods = [{ id: "screen", name: "丝印 LOGO", process_id: "proc-screen-stock", max_colors: 2, description: "单色/双色丝印" }];
      } else {
        draft.modes = (draft.modes || []).filter((m) => m !== "sample");
        if (!draft.modes.length) draft.modes = ["custom"];
      }
      renderStep();
      schedulePreview();
    });

    // modes
    panel.querySelectorAll("[data-mode-toggle]").forEach((el) => el.addEventListener("change", () => {
      const m = el.dataset.modeToggle;
      let modes = (draft.modes || []).slice();
      if (el.checked && !modes.includes(m)) modes.push(m);
      if (!el.checked) modes = modes.filter((x) => x !== m);
      if (!modes.length) modes = [m];
      draft.modes = modes;
      schedulePreview();
    }));

    // category drives default quote sources for new products
    const categorySel = panel.querySelector('[data-bind="category"]');
    if (categorySel) categorySel.addEventListener("change", () => {
      if (draft.id) return;
      draft.source_ids = defaultSourceIds(libs, categorySel.value);
      draft.production.press_ids = (libs.presses || []).filter((p) => !p.factory_id || draft.source_ids.includes(p.factory_id)).map((p) => p.id);
      schedulePreview();
    });

    // structure
    const structure = panel.querySelector("#structureSelect");
    if (structure) structure.addEventListener("change", () => {
      const def = (libs.structures || []).find((x) => x.id === structure.value);
      if (!def) return;
      draft.structure = def.id;
      draft.dim_fields = (def.inputs || []).map((i) => ({ key: i.key, label: i.label, min: i.min, max: i.max, default: i.default, hidden: i.hidden || false }));
      draft.formula_params = {};
      (def.params || []).forEach((p) => draft.formula_params[p.key] = p.default);
      draft.size_presets = [];
      renderStep();
      schedulePreview();
    });

    // size presets
    panel.querySelector("#addPreset")?.addEventListener("click", () => {
      const d = defaultDims(draft);
      draft.size_presets = draft.size_presets || [];
      draft.size_presets.push({ name: "新规格 " + (draft.size_presets.length + 1), dims: Object.assign({}, d) });
      renderStep();
    });
    panel.querySelectorAll("[data-remove-preset]").forEach((b) => b.addEventListener("click", () => {
      draft.size_presets.splice(Number(b.dataset.removePreset), 1);
      renderStep();
    }));

    // factories / quote sources
    panel.querySelectorAll("[data-factory]").forEach((el) => el.addEventListener("change", () => {
      const id = el.dataset.factory;
      let arr = (draft.source_ids || []).slice();
      if (el.checked && !arr.includes(id)) arr.push(id);
      if (!el.checked) arr = arr.filter((x) => x !== id);
      draft.source_ids = arr;
      // 移除已取消工厂的设备
      draft.production.press_ids = (draft.production.press_ids || []).filter((pid) => {
        const pr = (libs.presses || []).find((x) => x.id === pid);
        return !pr || !pr.factory_id || arr.includes(pr.factory_id);
      });
      renderStep();
      schedulePreview();
    }));

    // presses / sheets
    panel.querySelectorAll("[data-press]").forEach((el) => el.addEventListener("change", () => {
      const id = el.dataset.press;
      let arr = (draft.production.press_ids || []).slice();
      if (el.checked && !arr.includes(id)) arr.push(id);
      if (!el.checked) arr = arr.filter((x) => x !== id);
      draft.production.press_ids = arr;
      el.closest(".lib-item")?.classList.toggle("active", el.checked);
      schedulePreview();
    }));
    panel.querySelectorAll("[data-sheet]").forEach((el) => el.addEventListener("change", () => {
      const id = el.dataset.sheet;
      let arr = (draft.production.sheet_ids || []).slice();
      if (el.checked && !arr.includes(id)) arr.push(id);
      if (!el.checked) arr = arr.filter((x) => x !== id);
      draft.production.sheet_ids = arr;
      el.closest(".lib-item")?.classList.toggle("active", el.checked);
      schedulePreview();
    }));

    // materials
    panel.querySelectorAll("[data-mat]").forEach((el) => el.addEventListener("change", () => {
      const id = el.dataset.mat;
      let arr = (draft.materials || []).slice();
      if (el.checked && !arr.includes(id)) arr.push(id);
      if (!el.checked) arr = arr.filter((x) => x !== id);
      draft.materials = arr;
      if (!arr.includes(draft.default_material)) draft.default_material = arr[0] || "";
      renderStep();
      schedulePreview();
    }));
    panel.querySelectorAll("[data-default-mat]").forEach((el) => el.addEventListener("change", () => {
      draft.default_material = el.dataset.defaultMat;
      renderStep();
      schedulePreview();
    }));

    // aux group actions
    panel.querySelector("#addAuxGroup")?.addEventListener("click", () => {
      draft.aux_groups = draft.aux_groups || [];
      draft.aux_groups.push({ id: "aux-" + Date.now(), name: "辅料组", per_unit: 1, unit: "个", options: [{ material_id: "", label: "选项 1", default: true }] });
      renderStep();
    });
    panel.querySelectorAll("[data-remove-aux]").forEach((b) => b.addEventListener("click", () => {
      draft.aux_groups.splice(Number(b.dataset.removeAux), 1);
      renderStep();
    }));
    panel.querySelectorAll("[data-add-auxopt]").forEach((b) => b.addEventListener("click", () => {
      const gi = Number(b.dataset.addAuxopt);
      const g = draft.aux_groups[gi];
      g.options = g.options || [];
      g.options.push({ material_id: "", label: "新选项", default: !g.options.length });
      renderStep();
    }));
    panel.querySelectorAll("[data-remove-auxopt]").forEach((b) => b.addEventListener("click", () => {
      const [gi, oi] = b.dataset.removeAuxopt.split(":").map(Number);
      draft.aux_groups[gi].options.splice(oi, 1);
      renderStep();
    }));
    panel.querySelectorAll("[data-aux-default]").forEach((el) => el.addEventListener("change", () => {
      const [gi, oi] = el.dataset.auxDefault.split(":").map(Number);
      draft.aux_groups[gi].options.forEach((o, i) => o.default = i === oi);
      renderStep();
    }));

    // processes
    panel.querySelectorAll("[data-reqproc]").forEach((el) => el.addEventListener("change", () => {
      const id = el.dataset.reqproc;
      draft.processes.required = draft.processes.required || [];
      draft.processes.optional = draft.processes.optional || [];
      if (el.checked) {
        if (!draft.processes.required.includes(id)) draft.processes.required.push(id);
        draft.processes.optional = draft.processes.optional.filter((x) => x !== id);
      } else draft.processes.required = draft.processes.required.filter((x) => x !== id);
      renderStep(); schedulePreview();
    }));
    panel.querySelectorAll("[data-optproc]").forEach((el) => el.addEventListener("change", () => {
      const id = el.dataset.optproc;
      draft.processes.optional = draft.processes.optional || [];
      draft.processes.required = draft.processes.required || [];
      if (el.checked) {
        if (!draft.processes.optional.includes(id)) draft.processes.optional.push(id);
        draft.processes.required = draft.processes.required.filter((x) => x !== id);
      } else draft.processes.optional = draft.processes.optional.filter((x) => x !== id);
      renderStep(); schedulePreview();
    }));

    // overprint methods
    panel.querySelector("#addOpm")?.addEventListener("click", () => {
      draft.overprint_methods = draft.overprint_methods || [];
      draft.overprint_methods.push({ id: "m" + Date.now(), name: "新增加印方式", process_id: "proc-screen-stock", max_colors: 1, description: "" });
      renderStep();
    });
    panel.querySelectorAll("[data-remove-opm]").forEach((b) => b.addEventListener("click", () => {
      draft.overprint_methods.splice(Number(b.dataset.removeOpm), 1);
      renderStep();
    }));

    // packaging
    panel.querySelectorAll("[data-pkg]").forEach((el) => el.addEventListener("change", () => {
      const id = el.dataset.pkg;
      let arr = (draft.packagings || []).slice();
      if (el.checked && !arr.includes(id)) arr.push(id);
      if (!el.checked) arr = arr.filter((x) => x !== id);
      draft.packagings = arr;
      if (!arr.includes(draft.default_packaging)) draft.default_packaging = arr[0] || "";
      renderStep(); schedulePreview();
    }));
    panel.querySelectorAll("[data-default-pkg]").forEach((el) => el.addEventListener("change", () => {
      draft.default_packaging = el.dataset.defaultPkg;
      renderStep(); schedulePreview();
    }));

    // image upload (step 1)
    panel.querySelector("#bImageFile")?.addEventListener("change", async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      try {
        const res = await api.upload(f);
        draft.images = [res.url];
        draft.image = res.url;
        const img = panel.querySelector("#bImagePreview");
        if (img) img.src = res.url;
        root.querySelector("#bpImage").src = res.url;
        toast("图片已上传", "ok");
        schedulePreview();
      } catch (err) { toast(err.message, "err"); }
    });

    // platform margin blank
    const pm = panel.querySelector("#platformMargin");
    if (pm) pm.addEventListener("input", () => {
      const v = pm.value.trim();
      draft.pricing = draft.pricing || {};
      draft.pricing.platform_margin = v === "" ? null : Number(v) / 100;
      schedulePreview();
    });

  }

  // ------------------------------------------------------------ preview
  const schedulePreview = debounce(refreshPreview, 320);

  async function refreshPreview() {
    const my = ++previewSeq;
    const material_id = draft.default_material || (draft.materials || [])[0] || "";
    const qty = previewQty(draft);
    try {
      const res = await api.previewProduct({ draft, dims: previewDims(draft), material_id, qty });
      if (my !== previewSeq) return;
      preview = res;
      renderTech();
      renderPhone();
      renderPlanPreview();
    } catch (e) {
      if (my !== previewSeq) return;
      preview = { errors: [e.message] };
      renderTech();
    }
  }

  function renderTech() {
    if (!techBox) return;
    const errors = (preview && preview.errors) || [];
    const q = preview && preview.quote;
    const u = preview && preview.unfold;
    const plans = (preview && preview.plans) || [];
    techBox.innerHTML = `<h4>技术校验</h4>
      ${errors.length ? `<div class="tech-errors">${errors.map(esc).join("<br>")}</div>` : ""}
      ${u ? `
        <div class="tech-row"><span>成品展开</span><b>${u.flat_w} × ${u.flat_h} mm</b></div>
        <div class="tech-row"><span>含 ${u.bleed}mm 出血</span><b>${u.piece_w} × ${u.piece_h} mm</b></div>
        <div class="tech-row"><span>可用拼版方案</span><b class="${plans.length ? "ok" : "warn"}">${plans.length} 个</b></div>` : ""}
      ${plans.slice(0, 3).map((p) => `<div class="tech-row"><span>${esc(p.press_name)} · ${esc(p.sheet_name)}</span><b>1 张拼 ${p.units_per_sheet} 个</b></div>`).join("")}
      ${q ? `
        <div class="tech-row" style="margin-top:6px"><span>系统推荐</span><b>${esc(q.press || "")}</b></div>
        <div class="tech-row"><span>成本 / 商品报价</span><b>${money(q.cost)} / ${money(q.agent)}</b></div>
        <div class="tech-row"><span>对外零售（含税）</span><b class="ok">${money(q.total)}</b></div>
        <div class="tech-row"><span>单价 / 交期</span><b>${money(q.unit)} · ${q.lead.min}-${q.lead.max} 天</b></div>` : ""}
      ${(preview && preview.sources || []).length ? `<div style="margin-top:8px;padding-top:8px;border-top:1px dashed var(--line)"><div class="tiny muted" style="margin-bottom:5px">工厂比价</div>${preview.sources.map((x) => `<div class="tech-row"><span>${esc(x.factory.name)}${x.is_cheapest ? " · 最低" : ""}${x.is_fastest ? " · 最快" : ""}</span><b>${x.available ? money(x.price) : "不可用"}</b></div>`).join("")}</div>` : ""}
      ${preview && preview.quote_error ? `<div class="tech-errors">试算未完成：${esc(preview.quote_error)}</div>` : ""}
      ${!u && !errors.length ? `<div class="muted small">选择材料与设备后显示技术参数。</div>` : ""}`;
  }

  function renderPhone() {
    const img = root.querySelector("#bpImage");
    const name = root.querySelector("#bpName");
    const sub = root.querySelector("#bpSub");
    const price = root.querySelector("#bpPrice");
    const chips = root.querySelector("#bpChips");
    const kind = root.querySelector("#bpKind");
    if (img) img.src = (draft.images && draft.images[0]) || PLACEHOLDER;
    if (name) name.textContent = draft.name || "未命名产品";
    if (sub) sub.textContent = draft.subtitle || "填写副标题，展示在商城卡片";
    if (price) price.textContent = preview && preview.quote ? money(preview.quote.unit) : "—";
    if (kind) kind.textContent = (draft.modes || []).map((m) => m === "custom" ? "全定制" : "现货加印").join(" · ");
    if (chips) {
      const m = (libs.materials || []).find((x) => x.id === draft.default_material);
      chips.innerHTML = [
        m ? m.name : "未选材料",
        draft.kind === "overprint" ? "成品加印" : "按尺寸拼版",
        preview && preview.quote ? `${preview.quote.qty || previewQty(draft)} 个` : `${previewQty(draft)} 个`,
      ].map((x) => `<span>${esc(x)}</span>`).join("");
    }
  }

  function renderPlanPreview() {
    const wrap = root.querySelector("#planPreview");
    if (!wrap) return;
    if (!preview || !preview.plans || !preview.plans.length) {
      wrap.innerHTML = `<div class="muted small" style="padding:10px 0">选择材料和设备后，这里会显示拼版方案与用纸量。</div>`;
      return;
    }
    wrap.innerHTML = `<table class="tier-table"><thead><tr><th>机型</th><th>印张</th><th>一张拼</th><th>100 个用纸</th><th>成材率</th><th>交期</th></tr></thead><tbody>
      ${preview.plans.map((p) => `<tr><td>${esc(p.press_name)}</td><td>${esc(p.sheet_name)}</td><td>${p.units_per_sheet} 个</td><td>${p.sheets} 张</td><td>${pct(p.utilization || 0, 1)}</td><td>${p.lead_days} 天</td></tr>`).join("")}
    </tbody></table>`;
  }

  // ------------------------------------------------------------ save
  async function saveProduct(status) {
    if (saving) return;
    if (!String(draft.name || "").trim()) {
      toast("请先填写商品名称", "err");
      step = 1; renderStep(); return;
    }
    if (status === "active") {
      if (draft.kind === "custom" && !(draft.materials || []).length) { toast("请至少选择一种材料", "err"); step = 4; renderStep(); return; }
      if (draft.kind === "custom" && !(draft.processes.required || []).length) { toast("请至少配置一种必选工艺", "err"); step = 5; renderStep(); return; }
      if (draft.kind === "custom" && !(draft.production.press_ids || []).length) { toast("请至少选择一台印刷设备", "err"); step = 3; renderStep(); return; }
      if (!(draft.packagings || []).length) { toast("请至少选择一种包装方式", "err"); step = 6; renderStep(); return; }
      if (draft.kind === "overprint" && !(draft.overprint_methods || []).length) { toast("请配置成品加印方式", "err"); step = 5; renderStep(); return; }
    }
    saving = true;
    const btns = ["#saveDraft", "#publish", "#stepSave", "#stepPublish"].map((s) => root.querySelector(s)).filter(Boolean);
    btns.forEach((b) => { b.disabled = true; });
    try {
      draft.status = status;
      const res = await api.saveProduct({ product: draft });
      const saved = res.product;
      const isNew = !draft.id;
      draft.id = saved.id;
      draft.status = saved.status;
      if (isNew) {
        history.replaceState(null, "", "#/admin/products/" + draft.id + "/edit");
        const link = root.querySelector("#previewLink");
        if (link) { link.href = "#/admin/products/" + draft.id + "/mobile"; link.classList.remove("hide"); }
      }
      renderStep();
      renderTech();
      toast(status === "active" ? "已发布上架" : "草稿已保存", "ok");
    } catch (e) {
      toast(e.message, "err");
    } finally {
      saving = false;
      btns.forEach((b) => { b.disabled = false; });
    }
  }

  root.querySelector("#saveDraft").addEventListener("click", () => saveProduct("draft"));
  root.querySelector("#publish").addEventListener("click", () => saveProduct("active"));

  renderStep();
  refreshPreview();
}

// ------------------------------------------------------------------ helpers
function blankDraft(libs) {
  const def = (libs.structures || []).find((s) => s.id === "bag") || (libs.structures || [])[0] || { inputs: [], params: [] };
  const dims = {};
  (def.inputs || []).forEach((i) => dims[i.key] = i.default);
  const fp = {};
  (def.params || []).forEach((p) => fp[p.key] = p.default);
  const sourceIds = defaultSourceIds(libs, "bag");
  const presses = (libs.presses || []).filter((p) => p.enabled && p.type !== "screen" && (!p.factory_id || sourceIds.includes(p.factory_id))).map((p) => p.id);
  return {
    id: "", pricing_mode: "nonstandard", kind: "custom", category: "bag", name: "", subtitle: "", badge: "", description: "", long_desc: "",
    images: [PLACEHOLDER], image: PLACEHOLDER, modes: ["custom"],
    structure: def.id, dim_fields: (def.inputs || []).map((i) => ({ key: i.key, label: i.label, min: i.min, max: i.max, default: i.default, hidden: i.hidden || false })),
    formula_params: fp, bleed: 3, size_presets: [],
    materials: [], default_material: "", aux_groups: [],
    colors: [0, 1, 2, 3, 4], default_colors: 2,
    processes: { required: [], optional: [], groups: [] },
    packagings: [], default_packaging: "",
    quantity: { min: 100, max: 20000, step: 50, presets: [100, 300, 500, 1000] },
    source_ids: sourceIds,
    logistics: Object.assign({ mode: "home", provider: "统一配送", warehouse: "杭州中心仓", base_fee: 10, per_kg: 1.8, free_over: 3000, lead_days: 1, included: true, note: "全国送货上门，满 3000 元免运费，偏远地区另议。" }, libs.logistics_defaults || {}),
    production: { press_ids: presses, sheet_ids: [], objective: "cost", loss_rate: 0.05 },
    lead_days: 6, pricing: { platform_margin: null, agent_markup: 0.28 },
    highlights: [], specs: [], faq: [], audience: [], status: "draft", sort: 0,
    stock: null, overprint_methods: [],
  };
}

function normalizeDraft(d, libs) {
  const base = blankDraft(libs);
  const out = Object.assign({}, base, d || {});
  out.pricing_mode = "nonstandard";
  out.processes = Object.assign({ required: [], optional: [], groups: [] }, d.processes || {});
  out.quantity = Object.assign({}, base.quantity, d.quantity || {});
  out.production = Object.assign({}, base.production, d.production || {});
  const allowedPress = new Set((libs.presses || []).filter((p) => !p.factory_id || (out.source_ids || []).includes(p.factory_id)).map((p) => p.id));
  out.production.press_ids = (out.production.press_ids || []).filter((id) => allowedPress.has(id));
  out.pricing = Object.assign({}, base.pricing, d.pricing || {});
  out.images = (d.images && d.images.length) ? d.images : [d.image || PLACEHOLDER];
  out.image = out.images[0];
  if (!out.formula_params) out.formula_params = {};
  if (!out.dim_fields) out.dim_fields = base.dim_fields;
  if (!out.size_presets) out.size_presets = [];
  if (!out.materials) out.materials = [];
  if (!out.aux_groups) out.aux_groups = [];
  if (!out.source_ids || !out.source_ids.length) out.source_ids = defaultSourceIds(libs, out.category);
  out.logistics = Object.assign({ mode: "home", provider: "统一配送", warehouse: "杭州中心仓", base_fee: 10, per_kg: 1.8, free_over: 3000, lead_days: 1, included: true, note: "全国送货上门" }, libs.logistics_defaults || {}, out.logistics || {});
  if (!out.packagings) out.packagings = [];
  if (!out.highlights) out.highlights = [];
  if (!out.specs) out.specs = [];
  if (!out.faq) out.faq = [];
  if (!out.audience) out.audience = [];
  if (!out.overprint_methods) out.overprint_methods = [];
  if (out.kind === "overprint" && !out.modes.includes("overprint")) out.modes = ["overprint"];
  return out;
}

function defaultSourceIds(libs, category) {
  const all = (libs.factories || []).filter((f) => f.enabled !== 0);
  const pick = (ids) => all.filter((f) => ids.includes(f.id)).map((f) => f.id);
  if (category === "label") return pick(["fac-label"]) || [];
  if (category === "carton") return pick(["fac-flexo"]) || [];
  if (category === "bag" || category === "box") return pick(["fac-digital", "fac-offset"]);
  return all.map((f) => f.id);
}

function setPath(obj, path, val) {
  const parts = String(path).split(".");
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const k = parts[i];
    if (cur[k] == null) cur[k] = /^\d+$/.test(parts[i + 1]) ? [] : {};
    cur = cur[k];
  }
  cur[parts[parts.length - 1]] = val;
}

function defaultDims(draft) {
  if (draft.size_presets && draft.size_presets.length) return Object.assign({}, draft.size_presets[0].dims);
  const out = {};
  (draft.dim_fields || []).forEach((f) => out[f.key] = Number(f.default) || 0);
  return out;
}

function previewDims(draft) {
  if (draft.kind === "overprint") return (draft.stock && draft.stock.dims) || {};
  return defaultDims(draft);
}

function previewQty(draft) {
  if (draft.modes && draft.modes.includes("custom")) return Number(draft.quantity.min) || 100;
  if (draft.kind === "overprint") return Number(draft.quantity.min) || 100;
  return Number(draft.quantity.min) || 1;
}

// ------------------------------------------------------------------ step html
function stepHtml(step, draft, libs, preview) {
  if (step === 1) return step1(draft, libs);
  if (step === 2) return step2(draft, libs, preview);
  if (step === 3) return step3(draft, libs, preview);
  if (step === 4) return step4(draft, libs);
  if (step === 5) return step5(draft, libs);
  if (step === 6) return step6(draft, libs);
  if (step === 7) return step7Quantity(draft, libs);
  if (step === 8) return step7(draft, libs, preview);
  return step8(draft, libs, preview);
}

function step1(draft, libs) {
  return `<h2>基础信息</h2><p class="step-desc">先定义商品身份与前台展示内容。图片、卖点、参数会直接出现在手机商城和报价页。</p>
    <div class="form-grid">
      <div class="field full"><label>商品名称 *</label><input class="input" data-bind="name" value="${esc(draft.name || "")}" placeholder="如：牛皮纸手提袋"></div>
      <div class="field"><label>商品类型</label><select class="select" id="kindSelect"><option value="custom" ${draft.kind === "custom" ? "selected" : ""}>全定制（按尺寸生产）</option><option value="overprint" ${draft.kind === "overprint" ? "selected" : ""}>成品加印（现货胚 + LOGO）</option></select></div>
      <div class="field"><label>品类</label><select class="select" data-bind="category">${(libs.categories || []).map((c) => `<option value="${c.id}" ${draft.category === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></div>
      <div class="field full"><label>副标题</label><input class="input" data-bind="subtitle" value="${esc(draft.subtitle || "")}" placeholder="一句话说明材质、起订量与卖点"></div>
      <div class="field"><label>角标</label><input class="input" data-bind="badge" value="${esc(draft.badge || "")}" placeholder="热销 / 新品 / 现货"></div>
      <div class="field"><label>排序</label><input class="input" type="number" data-bind="sort" data-type="number" value="${draft.sort || 0}"></div>
      <div class="field full"><label>销售模式</label><div style="display:flex;gap:18px;flex-wrap:wrap;padding-top:6px">
        ${draft.kind === "custom" ? `<label class="check"><input type="checkbox" checked disabled> 全定制（按起订量报价）</label>` : `<label class="check"><input type="checkbox" checked disabled> 成品加印</label>`}
      </div></div>
      <div class="field full"><label>商品主图</label><div class="copy-row"><input class="input" id="bImagePreviewHidden" value="${esc((draft.images || [])[0] || "")}" readonly><label class="btn soft sm">上传图片<input type="file" id="bImageFile" accept="image/*" hidden></label></div><img id="bImagePreview" src="${esc((draft.images || [])[0] || PLACEHOLDER)}" style="width:180px;height:120px;object-fit:cover;border-radius:10px;margin-top:9px;border:1px solid var(--line)"></div>
      <div class="field full"><label>详情描述</label><textarea class="textarea" data-bind="description" rows="3" placeholder="出现在商品卡片与详情页开头">${esc(draft.description || "")}</textarea></div>
      <div class="field full"><label>长描述</label><textarea class="textarea" data-bind="long_desc" rows="3">${esc(draft.long_desc || "")}</textarea></div>
      <div class="field full"><label>卖点（每行一条）</label><textarea class="textarea" data-bind="highlights" data-type="lines" rows="3" placeholder="100 个起做&#10;3 天出样">${esc((draft.highlights || []).join("\n"))}</textarea></div>
      <div class="field"><label>规格参数（每行：名称|值）</label><textarea class="textarea" data-bind="specs" data-type="specs" rows="4" placeholder="起订量|100 个&#10;交期|5-7 个工作日">${esc((draft.specs || []).map((s) => s.label + "|" + s.value).join("\n"))}</textarea></div>
      <div class="field"><label>常见问题（每行：问题|回答）</label><textarea class="textarea" data-bind="faq" data-type="faq" rows="4" placeholder="起订量多少？|100 个起做。">${esc((draft.faq || []).map((f) => f.q + "|" + f.a).join("\n"))}</textarea></div>
      <div class="field full"><label>适用场景（逗号分隔）</label><input class="input" data-bind="audience" data-type="commalist" value="${esc((draft.audience || []).join("，"))}" placeholder="烘焙，服饰，伴手礼">
        <span class="hint">注：适用场景会原样展示，请用中文逗号分隔。</span>
      </div>
    </div>`;
}

function step2(draft, libs, preview) {
  if (draft.kind === "overprint") {
    const s = draft.stock || {};
    return `<h2>成品规格</h2><p class="step-desc">成品加印使用已成型现货，尺寸固定；只需配置现货规格、胚价与库存。</p>
      <div class="form-grid">
        <div class="field full"><label>现货名称 *</label><input class="input" data-bind="stock.name" value="${esc(s.name || "")}" placeholder="现货牛皮纸袋 220×90×300mm"></div>
        <div class="field"><label>长 mm</label><input class="input" type="number" data-bind="stock.dims.L" data-type="number" value="${(s.dims || {}).L || 220}"></div>
        <div class="field"><label>宽 mm</label><input class="input" type="number" data-bind="stock.dims.W" data-type="number" value="${(s.dims || {}).W || 90}"></div>
        <div class="field"><label>高 mm</label><input class="input" type="number" data-bind="stock.dims.H" data-type="number" value="${(s.dims || {}).H || 300}"></div>
        <div class="field"><label>现货胚价（成本）</label><input class="input" type="number" step="0.01" data-bind="stock.blank_price" data-type="number" value="${s.blank_price || 0}"><span class="hint">内部成本，不对客户展示</span></div>
        <div class="field"><label>现货库存</label><input class="input" type="number" data-bind="stock.stock_qty" data-type="number" value="${s.stock_qty || 0}"></div>
        <div class="field"><label>加印后交期（天）</label><input class="input" type="number" data-bind="stock.lead_days" data-type="number" value="${s.lead_days || 3}"></div>
      </div>
      <div class="banner info" style="margin-top:16px">${icon("layers", 15)} 成品加印不需要展开公式和拼版，价格 = 现货胚价 × 数量 + 加印工艺费 + 包装物流。</div>`;
  }
  const def = (libs.structures || []).find((s) => s.id === draft.structure) || {};
  return `<h2>成品尺寸</h2><p class="step-desc">前端只输入成品长宽高；这里限定字段范围，并确认展开公式，系统自动换算展开尺寸。</p>
    <div class="form-grid">
      <div class="field"><label>展开结构 / 公式</label><select class="select" id="structureSelect">${(libs.structures || []).map((s) => `<option value="${s.id}" ${draft.structure === s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select></div>
      <div class="field full"><div class="banner info" style="margin:0">${icon("calc", 15)} ${esc(def.formula || "")}</div></div>
      <div class="field full"><label>成品尺寸输入项（前端字段 / 范围）</label>
        <div class="table-wrap"><table class="admin-table"><thead><tr><th>字段名</th><th>最小值</th><th>最大值</th><th>默认值</th></tr></thead><tbody>
          ${(draft.dim_fields || []).filter((f) => !f.hidden).map((f, i) => `<tr>
            <td><input class="input" style="height:32px" data-bind="dim_fields.${i}.label" value="${esc(f.label)}"></td>
            <td><input class="input" style="height:32px" type="number" data-bind="dim_fields.${i}.min" data-type="number" value="${f.min}"></td>
            <td><input class="input" style="height:32px" type="number" data-bind="dim_fields.${i}.max" data-type="number" value="${f.max}"></td>
            <td><input class="input" style="height:32px" type="number" data-bind="dim_fields.${i}.default" data-type="number" value="${f.default}"></td>
          </tr>`).join("")}
        </tbody></table></div>
      </div>
      <div class="field full"><label>公式余量参数</label><div class="form-row three">
        ${(def.params || []).map((p) => `<div class="field"><label>${esc(p.label)}（${p.unit || "mm"}）</label><input class="input" type="number" data-bind="formula_params.${p.key}" data-type="number" value="${draft.formula_params[p.key] != null ? draft.formula_params[p.key] : p.default}"></div>`).join("") || `<div class="muted small">该结构无额外余量参数。</div>`}
      </div></div>
    </div>
    <div style="display:flex;align-items:center;gap:8px;margin:18px 0 8px"><b style="font-size:12px">尺寸预设</b><span class="muted tiny">给客户快速选择的常用规格</span><button class="btn soft sm" id="addPreset" style="margin-left:auto">${icon("plus", 12)} 添加预设</button></div>
    <div class="table-wrap"><table class="admin-table"><thead><tr><th>名称</th><th>长</th><th>宽</th><th>高</th><th></th></tr></thead><tbody>
      ${(draft.size_presets || []).map((p, i) => `<tr>
        <td><input class="input" style="height:32px" data-bind="size_presets.${i}.name" value="${esc(p.name)}"></td>
        <td><input class="input" style="height:32px" type="number" data-bind="size_presets.${i}.dims.L" data-type="number" value="${(p.dims || {}).L || 0}"></td>
        <td><input class="input" style="height:32px" type="number" data-bind="size_presets.${i}.dims.W" data-type="number" value="${(p.dims || {}).W || 0}"></td>
        <td><input class="input" style="height:32px" type="number" data-bind="size_presets.${i}.dims.H" data-type="number" value="${(p.dims || {}).H || 0}"></td>
        <td><button class="btn ghost sm" data-remove-preset="${i}">${icon("trash", 12)}</button></td>
      </tr>`).join("") || `<tr><td colspan="5" class="muted">暂未设置预设，客户可自定义尺寸。</td></tr>`}
    </tbody></table></div>
    ${preview && preview.unfold ? `<div class="banner info" style="margin-top:14px">${icon("calc", 15)} 当前默认尺寸展开：<b>${preview.unfold.flat_w} × ${preview.unfold.flat_h} mm</b>，加 ${preview.unfold.bleed}mm 出血后 ${preview.unfold.piece_w} × ${preview.unfold.piece_h} mm。</div>` : ""}`;
}

function step3(draft, libs, preview) {
  if (draft.kind === "overprint") return `<h2>拼版与机型</h2><p class="step-desc">成品加印不需要拼版，直接使用成品丝印/烫金设备。可在下一步配置加印方式。</p><div class="banner info">${icon("layers", 15)} 现货加印按件计价，无需上机印张。</div>`;
  return `<h2>拼版</h2><p class="step-desc">先定四周出血，再把展开尺寸放到固定印张上拼；工厂、设备与印张由后台指定。</p>
    <div class="form-row three">
      <div class="field"><label>出血（四周各）</label><div class="input-group"><input class="input" type="number" data-bind="bleed" data-type="number" value="${draft.bleed || 3}"><span class="suffix">mm</span></div></div>
    </div>
    <div class="config-head" style="margin-top:18px"><h3 style="font-size:13px">报价工厂 / 数据源</h3><span class="right">至少选 1 家</span></div>
    <div class="lib-grid">
      ${(libs.factories || []).filter((f) => f.enabled !== 0 && (defaultSourceIds(libs, draft.category).includes(f.id) || (draft.source_ids || []).includes(f.id))).map((f) => `<label class="lib-item ${(draft.source_ids || []).includes(f.id) ? "active" : ""}">
        <input type="checkbox" data-factory="${f.id}" ${(draft.source_ids || []).includes(f.id) ? "checked" : ""} style="width:15px;height:15px">
        <div><b>${esc(f.name)}</b><span>${esc(f.type)} · 系数 ${Number(f.price_factor || 1).toFixed(2)} · ${f.fixed_fee ? "服务费 ¥" + f.fixed_fee : "无固定费"} · ${f.lead_days ? "+" + f.lead_days + " 天" : "标准交期"}</span></div>
      </label>`).join("")}
    </div>
    <div class="config-head" style="margin-top:18px"><h3 style="font-size:13px">可用印刷设备</h3><span class="right">仅显示已选工厂的设备</span></div>
    <div class="lib-grid">
      ${(libs.presses || []).filter((p) => p.enabled && p.type !== "screen" && (!p.factory_id || (draft.source_ids || []).includes(p.factory_id))).map((p) => {
        const fac = (libs.factories || []).find((x) => x.id === p.factory_id);
        return `<label class="lib-item ${((draft.production.press_ids || []).includes(p.id)) ? "active" : ""}">
        <input type="checkbox" data-press="${p.id}" ${(draft.production.press_ids || []).includes(p.id) ? "checked" : ""} style="width:15px;height:15px">
        <div><b>${esc(p.name)}</b><span>${esc(fac ? fac.name : "未归属")} · ${p.type} · 最大 ${p.max_w}×${p.max_h} · ${p.days} 天</span></div>
      </label>`;
      }).join("")}
    </div>
    <div class="config-head" style="margin-top:18px"><h3 style="font-size:13px">限定上机印张（可不选）</h3><span class="right">不选 = 按材料自动匹配</span></div>
    <div class="lib-grid">
      ${(libs.sheets || []).map((s) => `<label class="lib-item ${((draft.production.sheet_ids || []).includes(s.id)) ? "active" : ""}">
        <input type="checkbox" data-sheet="${s.id}" ${(draft.production.sheet_ids || []).includes(s.id) ? "checked" : ""} style="width:15px;height:15px">
        <div><b>${esc(s.name)}</b><span>${s.w}×${s.h} · 咬口 ${s.grip} / 边距 ${s.edge}</span></div>
      </label>`).join("")}
    </div>
    <div style="display:flex;align-items:center;gap:8px;margin:18px 0 8px"><b style="font-size:12px">拼版预览</b><span class="muted tiny">按默认尺寸 + 默认材料试算，100 个</span></div>
    <div id="planPreview"></div>`;
}

function step4(draft, libs) {
  const mats = (libs.materials || []).filter((m) => m.enabled && m.kind !== "aux");
  const aux = (libs.materials || []).filter((m) => m.enabled && m.kind === "aux");
  return `<h2>原辅料库</h2><p class="step-desc">从资料库勾选这个商品可选的材料与辅料；材料单价、克重、图片都在资料库维护。</p>
    <div class="config-head" style="margin-top:2px"><h3 style="font-size:13px">主材料</h3><span class="right">至少选 1 种</span></div>
    <div class="lib-grid">
      ${mats.map((m) => `<label class="lib-item ${((draft.materials || []).includes(m.id)) ? "active" : ""}">
        <input type="checkbox" data-mat="${m.id}" ${(draft.materials || []).includes(m.id) ? "checked" : ""} style="width:15px;height:15px">
        <img src="${esc(m.image || "")}" alt="">
        <div><b>${esc(m.name)}</b><span>${KIND_LABEL[m.kind] || m.kind} · ${m.gsm || 0}g · ${esc(priceLabel(m))}</span></div>
      </label>`).join("") || `<div class="muted small">资料库暂无材料，请先到「基础资料库」新增。</div>`}
    </div>
    <div class="field" style="margin-top:14px;max-width:280px"><label>默认材料</label><select class="select" data-bind="default_material">${(draft.materials || []).map((id) => { const m = mats.find((x) => x.id === id); return m ? `<option value="${id}" ${draft.default_material === id ? "selected" : ""}>${esc(m.name)}</option>` : ""; }).join("") || `<option value="">先勾选材料</option>`}</select></div>

    <div style="display:flex;align-items:center;gap:8px;margin:20px 0 8px"><b style="font-size:12px">辅料 / 配件</b><span class="muted tiny">如提绳、磁铁、内衬；按件用量计价</span><button class="btn soft sm" id="addAuxGroup" style="margin-left:auto">${icon("plus", 12)} 添加辅料组</button></div>
    ${(draft.aux_groups || []).length ? (draft.aux_groups || []).map((g, gi) => `<div class="method-row" style="background:var(--cream)">
      <div class="mr-head"><b>辅料组 ${gi + 1}</b><button class="btn ghost sm" data-remove-aux="${gi}" style="margin-left:auto">${icon("trash", 12)}</button></div>
      <div class="form-row three">
        <div class="field"><label>组名</label><input class="input" data-bind="aux_groups.${gi}.name" value="${esc(g.name || "")}"></div>
        <div class="field"><label>单件用量</label><input class="input" type="number" step="0.01" data-bind="aux_groups.${gi}.per_unit" data-type="number" value="${g.per_unit || 1}"></div>
        <div class="field"><label>单位</label><input class="input" data-bind="aux_groups.${gi}.unit" value="${esc(g.unit || "")}" placeholder="m / 个"></div>
      </div>
      <div style="margin-top:8px">
        ${(g.options || []).map((o, oi) => `<div class="form-row" style="margin-bottom:7px;align-items:end">
          <div class="field"><label>选项名称</label><input class="input" data-bind="aux_groups.${gi}.options.${oi}.label" value="${esc(o.label || "")}"></div>
          <div class="field"><label>辅料</label><select class="select" data-bind="aux_groups.${gi}.options.${oi}.material_id"><option value="">不需要</option>${aux.map((m) => `<option value="${m.id}" ${o.material_id === m.id ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select></div>
          <div style="display:flex;gap:8px;align-items:center;padding-bottom:8px"><label class="check nowrap"><input type="radio" name="auxdef-${gi}" data-aux-default="${gi}:${oi}" ${o.default ? "checked" : ""}> 默认</label><button class="btn ghost sm" data-remove-auxopt="${gi}:${oi}">${icon("trash", 12)}</button></div>
        </div>`).join("")}
        <button class="btn soft sm" data-add-auxopt="${gi}">${icon("plus", 12)} 添加选项</button>
      </div>
    </div>`).join("") : `<div class="muted small">该商品没有辅料组。纸袋可添加「提绳」组，盒类可添加「磁铁 / 内衬」组。</div>`}`;
}

function step5(draft, libs) {
  if (draft.kind === "overprint") {
    const procs = (libs.processes || []).filter((p) => p.enabled && (p.applies_to || []).includes("overprint"));
    return `<h2>成品加印工艺</h2><p class="step-desc">现货已成型，只能选择成品丝印、成品烫金等加印方式。</p>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><b style="font-size:12px">加印方式</b><button class="btn soft sm" id="addOpm" style="margin-left:auto">${icon("plus", 12)} 添加方式</button></div>
      ${(draft.overprint_methods || []).map((m, i) => `<div class="method-row">
        <div class="mr-head"><b>方式 ${i + 1}</b><button class="btn ghost sm" data-remove-opm="${i}" style="margin-left:auto">${icon("trash", 12)}</button></div>
        <div class="form-row three">
          <div class="field"><label>名称</label><input class="input" data-bind="overprint_methods.${i}.name" value="${esc(m.name || "")}"></div>
          <div class="field"><label>关联工艺</label><select class="select" data-bind="overprint_methods.${i}.process_id">${procs.map((p) => `<option value="${p.id}" ${m.process_id === p.id ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></div>
          <div class="field"><label>最多颜色数</label><input class="input" type="number" data-bind="overprint_methods.${i}.max_colors" data-type="number" value="${m.max_colors || 1}"></div>
          <div class="field full"><label>说明</label><input class="input" data-bind="overprint_methods.${i}.description" value="${esc(m.description || "")}"></div>
        </div>
      </div>`).join("") || `<div class="muted small">还没有加印方式。</div>`}`;
  }
  const procs = (libs.processes || []).filter((p) => p.enabled && p.category !== "成品加印" && ((p.applies_to || []).includes(draft.structure) || (p.applies_to || []).includes("*")));
  return `<h2>生产工艺</h2><p class="step-desc">必选工艺是生产的基础工序；可选工艺由客户在前端按需勾选。系统会在每条工艺的多种生产方式中自动比选。</p>
    <div class="config-head"><h3 style="font-size:13px">必选工艺</h3><span class="right">基础工序</span></div>
    <div class="lib-grid">
      ${procs.map((p) => `<label class="lib-item ${(draft.processes.required || []).includes(p.id) ? "active" : ""}">
        <input type="checkbox" data-reqproc="${p.id}" ${(draft.processes.required || []).includes(p.id) ? "checked" : ""} style="width:15px;height:15px">
        <img src="${esc(p.image || "")}" alt="">
        <div><b>${esc(p.name)}</b><span>${esc(p.category || "")}${p.constraints && p.constraints.min_gsm ? ` · ≥${p.constraints.min_gsm}g` : ""}</span></div>
      </label>`).join("")}
    </div>
    <div class="config-head" style="margin-top:18px"><h3 style="font-size:13px">可选工艺</h3><span class="right">客户可勾选</span></div>
    <div class="lib-grid">
      ${procs.map((p) => `<label class="lib-item ${(draft.processes.optional || []).includes(p.id) ? "active" : ""}">
        <input type="checkbox" data-optproc="${p.id}" ${(draft.processes.optional || []).includes(p.id) ? "checked" : ""} style="width:15px;height:15px">
        <img src="${esc(p.image || "")}" alt="">
        <div><b>${esc(p.name)}</b><span>${esc((p.description || "").slice(0, 26))}</span></div>
      </label>`).join("")}
    </div>
    <div class="banner info" style="margin-top:14px">${icon("spark", 15)} 同一工艺配置了多种生产方式（如机器/手工糊袋）时，系统会按当前数量与交期要求选择更省的方式。</div>`;
}

function step6(draft, libs) {
  return `<h2>包装方式</h2><p class="step-desc">包装方式会影响箱数、体积重和物流费；统一从杭州仓发货、送货上门。</p>
    <div class="config-head"><h3 style="font-size:13px">包装方式</h3><span class="right">至少选 1 种</span></div>
    <div class="lib-grid">
      ${(libs.packagings || []).filter((p) => p.enabled).map((p) => `<label class="lib-item ${(draft.packagings || []).includes(p.id) ? "active" : ""}">
        <input type="checkbox" data-pkg="${p.id}" ${(draft.packagings || []).includes(p.id) ? "checked" : ""} style="width:15px;height:15px">
        <img src="${esc(p.image || "")}" alt="">
        <div><b>${esc(p.name)}</b><span>${p.carton_qty} 件/箱 · ${p.carton_weight_kg}kg</span></div>
      </label>`).join("")}
    </div>
    <div class="field" style="margin-top:12px;max-width:280px"><label>默认包装</label><select class="select" data-bind="default_packaging">${(draft.packagings || []).map((id) => { const p = (libs.packagings || []).find((x) => x.id === id); return p ? `<option value="${id}" ${draft.default_packaging === id ? "selected" : ""}>${esc(p.name)}</option>` : ""; }).join("") || `<option value="">先勾选包装</option>`}</select></div>

    <div class="config-head" style="margin-top:22px"><h3 style="font-size:13px">物流交付</h3><span class="right">统一送货上门</span></div>
    <div class="form-row three">
      <div class="field"><label>交付方式</label><select class="select" data-bind="logistics.mode"><option value="home" selected>送货上门</option></select></div>
      <div class="field"><label>发货仓</label><input class="input" data-bind="logistics.warehouse" value="${esc((draft.logistics || {}).warehouse || "")}"></div>
      <div class="field"><label>配送服务商</label><input class="input" data-bind="logistics.provider" value="${esc((draft.logistics || {}).provider || "")}" placeholder="统一配送 / 顺丰 / 物流专线"></div>
      <div class="field"><label>起步运费（元）</label><input class="input" type="number" step="0.1" data-bind="logistics.base_fee" data-type="number" value="${(draft.logistics || {}).base_fee || 0}"></div>
      <div class="field"><label>每公斤续重（元）</label><input class="input" type="number" step="0.1" data-bind="logistics.per_kg" data-type="number" value="${(draft.logistics || {}).per_kg || 0}"></div>
      <div class="field"><label>满额免运费（元）</label><input class="input" type="number" data-bind="logistics.free_over" data-type="number" value="${(draft.logistics || {}).free_over || 0}"></div>
      <div class="field"><label>配送时效（天）</label><input class="input" type="number" data-bind="logistics.lead_days" data-type="number" value="${(draft.logistics || {}).lead_days || 1}"></div>
      <div class="field full"><label>物流说明</label><input class="input" data-bind="logistics.note" value="${esc((draft.logistics || {}).note || "")}" placeholder="全国送货上门，偏远地区另议"></div>
    </div>
    <div class="banner info" style="margin-top:12px">${icon("truck", 15)} 运费按实际重量/体积重自动计入报价；满额免运。客户端和报价页统一显示「送货上门」。</div>
  </div>`;
}

function step7Quantity(draft, libs) {
  return `<h2>定制数量</h2><p class="step-desc">一个商品只有一个起订量，客户在前端按数量阶梯报价；不再区分打样/大货。</p>
    <div class="form-row three">
      <div class="field"><label>起订量 *</label><input class="input" type="number" data-bind="quantity.min" data-type="number" value="${draft.quantity.min}"></div>
      <div class="field"><label>最大数量</label><input class="input" type="number" data-bind="quantity.max" data-type="number" value="${draft.quantity.max}"></div>
      <div class="field"><label>数量步长</label><input class="input" type="number" data-bind="quantity.step" data-type="number" value="${draft.quantity.step}"></div>
      <div class="field full"><label>数量快捷选项（逗号分隔）</label><input class="input" data-bind="quantity.presets" data-type="numlist" value="${(draft.quantity.presets || []).join("，")}"></div>
    </div>
    <div class="form-row three" style="margin-top:16px">
      <div class="field"><label>大货交期（天）</label><input class="input" type="number" data-bind="lead_days" data-type="number" value="${draft.lead_days}"></div>
      <div class="field"><label>默认颜色数</label><input class="input" type="number" data-bind="default_colors" data-type="number" value="${draft.default_colors}"></div>
      <div class="field"><label>可选颜色数（逗号分隔）</label><input class="input" data-bind="colors" data-type="numlist" value="${(draft.colors || []).join("，")}"></div>
    </div>
    <div class="banner info" style="margin-top:14px">系统按起订量试算一次；客户在前端可以改数量重新报价。</div>`;
}

function step7(draft, libs, preview) {
  const q = preview && preview.quote;
  return `<h2>生产方案比选</h2><p class="step-desc">系统会枚举设备 × 印张 × 工艺方式的组合，按你设定的目标选出最优方案。这里可以看到每个组合的拼版结果。</p>
    <div class="form-row three">
      <div class="field"><label>比选目标</label><select class="select" data-bind="production.objective"><option value="cost" ${draft.production.objective === "cost" ? "selected" : ""}>成本优先</option><option value="lead" ${draft.production.objective === "lead" ? "selected" : ""}>交期优先</option></select></div>
      <div class="field"><label>材料损耗率</label><input class="input" type="number" step="0.01" data-bind="production.loss_rate" data-type="number" value="${draft.production.loss_rate}"></div>
      <div class="field"><label>管理费率覆盖</label><input class="input" type="number" step="0.01" data-bind="production.overhead_rate" data-type="number" value="${draft.production.overhead_rate != null ? draft.production.overhead_rate : 0.06}"><span class="hint">留空使用系统参数</span></div>
    </div>
    <div class="banner info" style="margin-top:14px">${icon("layers", 15)} 打印机型与印张数量来自第 3 步；材料来自第 4 步；工艺方式来自第 5 步。</div>
    <div id="planPreview" style="margin-top:10px"></div>
    ${q ? `<div class="internal-box" style="margin-top:16px">
      <h4>默认配置试算（${num(q.qty)} 个）</h4>
      <div class="internal-grid">
        <div class="ig"><span>成本合计</span><b>${money(q.cost)}</b></div>
        <div class="ig"><span>商品报价</span><b>${money(q.total)}</b></div>
        <div class="ig profit"><span>单件报价</span><b>${money(q.unit)}</b></div>
        <div class="ig"><span>参考交期</span><b>${q.lead.min}-${q.lead.max} 天</b></div>
      </div>
      <div class="internal-note">推荐：${esc(q.press || "")} · ${esc(q.sheet || "")} · 一张拼 ${q.units_per_sheet} 个 · ${q.lead.min}-${q.lead.max} 天。</div>
    </div>` : `<div class="muted small" style="margin-top:14px">完成材料、工艺和数量配置后显示试算。</div>`}`;
}

function step8(draft, libs, preview) {
  const q = preview && preview.quote;
  return `<h2>计价与发布</h2><p class="step-desc">商品报价 = 成本 + 平台利润；商品可以覆盖平台默认利润率。<a href="#/admin/libraries?tab=algorithms" class="link-btn">去计价算法库 →</a></p>
    <div class="form-row">
      <div class="field"><label>平台利润率覆盖（%）</label><input class="input" id="platformMargin" type="number" step="0.1" value="${draft.pricing.platform_margin != null ? (draft.pricing.platform_margin * 100).toFixed(1) : ""}" placeholder="留空使用系统 ${pct((state.site && state.site.platform_margin) || 0.18, 0)}"><span class="hint">成本 × (1 + 利润率) = 商品报价</span></div>
      <div class="field"><label>发布状态</label><select class="select" data-bind="status"><option value="draft" ${draft.status !== "active" ? "selected" : ""}>草稿</option><option value="active" ${draft.status === "active" ? "selected" : ""}>上架</option><option value="disabled" ${draft.status === "disabled" ? "selected" : ""}>下架</option></select></div>
    </div>
    <div class="admin-grid" style="grid-template-columns:1fr 1fr;margin-top:18px">
      <div class="panel"><div class="panel-head"><h3>前台展示检查</h3></div><div class="panel-body small">
        <div class="tech-row"><span>商品名称</span><b class="${draft.name ? "ok" : "warn"}">${draft.name ? "已填写" : "未填写"}</b></div>
        <div class="tech-row"><span>主图</span><b class="${draft.images && draft.images[0] ? "ok" : "warn"}">${draft.images && draft.images[0] ? "已设置" : "使用占位图"}</b></div>
        <div class="tech-row"><span>材料</span><b class="${(draft.materials || []).length ? "ok" : "warn"}">${(draft.materials || []).length} 种</b></div>
        <div class="tech-row"><span>必选工艺</span><b class="${(draft.processes.required || []).length ? "ok" : "warn"}">${(draft.processes.required || []).length} 项</b></div>
        <div class="tech-row"><span>尺寸预设</span><b>${(draft.size_presets || []).length} 个</b></div>
        <div class="tech-row"><span>卖点 / FAQ</span><b>${(draft.highlights || []).length} / ${(draft.faq || []).length}</b></div>
      </div></div>
      <div class="panel"><div class="panel-head"><h3>试算价格</h3></div><div class="panel-body">
        ${q ? `<div class="tech-row"><span>默认配置</span><b>${num(q.qty)} 个</b></div>
        <div class="tech-row"><span>成本合计</span><b>${money(q.cost)}</b></div>
        <div class="tech-row"><span>商品报价</span><b class="ok">${money(q.total)}</b></div>
        <div class="tech-row"><span>单件 / 交期</span><b>${money(q.unit)} · ${q.lead.min}-${q.lead.max} 天</b></div>` : `<div class="muted small">暂无法试算，请检查材料/工艺/设备。</div>`}
      </div></div>
    </div>
    <div class="banner warn" style="margin-top:16px">${icon("shield", 15)} 发布前建议先保存草稿，打开前台预览检查手机端展示；确认后再点「发布上架」。</div>`;
}
