# -*- coding: utf-8 -*-
"""报价内核。

流程：
  成品尺寸 → 展开公式 → 加出血 → 上机印张拼版 → 印刷方案比选
  → 材料/辅料/工艺/包装 → 管理费/税/物流 → 成本
  → 平台代理价（成本 + 平台利润）→ 代理加价 → 对外零售价

同一份计算同时服务：手机商城、代理商报价、后台预览。
"""

from __future__ import annotations

import copy
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from . import algorithms, formulas, imposition
from .db import Database

MODE_NAMES = {"sample": "打样", "custom": "全定制", "overprint": "成品加印"}
STATUS_NAMES = {
    "active": "有效", "converted": "已下单", "expired": "已过期", "closed": "已关闭",
    "pending": "待确认", "confirmed": "已确认", "producing": "生产中",
    "shipped": "已发货", "completed": "已完成", "cancelled": "已取消",
}
PAYMENT_NAMES = {"unpaid": "未付款", "deposit": "已付定金", "paid": "已付全款"}


class EngineError(Exception):
    pass


def _n(v: Any, d: float = 0.0) -> float:
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else d
    except (TypeError, ValueError):
        return d


def _i(v: Any, d: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def _r2(x: float) -> float:
    return round(x + 1e-9, 2)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _ceil_div(a: int, b: int) -> int:
    return int(math.ceil(a / float(b))) if b else 0


def _money(x: float) -> str:
    return "¥%.2f" % _r2(x)


def _mask_phone(phone: str) -> str:
    p = str(phone or "")
    return (p[:3] + "****" + p[-4:]) if len(p) >= 7 else p


class QuoteEngine:
    def __init__(self, db: Database):
        self.db = db
        self.settings = db.settings()
        self.materials = {m["id"]: m for m in db.list_library("materials")}
        self.presses = {p["id"]: p for p in db.list_library("presses")}
        self.sheets = {s["id"]: s for s in db.list_library("sheets")}
        self.processes = {p["id"]: p for p in db.list_library("processes")}
        self.packagings = {p["id"]: p for p in db.list_library("packagings")}
        self.factories = {f["id"]: f for f in db.list_factories()}

    # ================================================================ helpers
    def setting(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def default_config(self, product: Dict[str, Any], mode: Optional[str] = None) -> Dict[str, Any]:
        modes = product.get("modes") or ["custom"]
        mode = mode or ("custom" if "custom" in modes else modes[0])
        if mode not in modes:
            mode = modes[0]
        qty_conf = product.get("quantity") or {}
        if mode == "sample":
            sp = product.get("sample") or {}
            qty = _i(sp.get("min"), 1)
            qty = max(1, qty)
        else:
            qty = _i(qty_conf.get("min"), 1)

        dims = {}
        presets = product.get("size_presets") or []
        if presets:
            dims = dict(presets[0].get("dims") or {})
        else:
            for f in product.get("dim_fields") or []:
                dims[f.get("key")] = _n(f.get("default"), 0)
        if product.get("stock"):
            dims = dict((product.get("stock") or {}).get("dims") or dims)

        aux = {}
        for g in product.get("aux_groups") or []:
            opts = g.get("options") or []
            pick = next((o for o in opts if o.get("default")), opts[0] if opts else None)
            aux[g.get("id")] = (pick or {}).get("material_id")

        method = None
        methods = product.get("overprint_methods") or []
        if methods:
            method = methods[0].get("id")

        return {
            "mode": mode,
            "qty": qty,
            "dims": dims,
            "size_name": (presets[0] or {}).get("name") if presets else "自定义",
            "material_id": product.get("default_material") or (product.get("materials") or [None])[0],
            "aux": aux,
            "colors": _i(product.get("default_colors"), 1),
            "processes": [],
            "packaging_id": product.get("default_packaging") or (product.get("packagings") or [None])[0],
            "overprint_method": method,
            "note": "",
        }

    def normalize_config(self, product: Dict[str, Any], cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        base = self.default_config(product, (cfg or {}).get("mode"))
        out = copy.deepcopy(base)
        cfg = cfg or {}
        for k in ("mode", "size_name", "material_id", "packaging_id", "overprint_method", "note"):
            if cfg.get(k) is not None:
                out[k] = cfg[k]
        if cfg.get("qty") is not None:
            out["qty"] = _i(cfg.get("qty"), out["qty"])
        if isinstance(cfg.get("dims"), dict):
            out["dims"] = {k: _n(v) for k, v in cfg["dims"].items() if v is not None}
        if cfg.get("colors") is not None:
            out["colors"] = _i(cfg.get("colors"), out["colors"])
        if isinstance(cfg.get("aux"), dict):
            out["aux"] = dict(cfg["aux"])
        elif isinstance(cfg.get("aux"), list):
            for item in cfg["aux"]:
                if isinstance(item, dict) and item.get("group_id"):
                    out["aux"][item["group_id"]] = item.get("material_id")
        procs = cfg.get("processes")
        if isinstance(procs, list):
            out["processes"] = [str(p) for p in procs]
        return out

    # ================================================================ main API
    def _apply_factory_prices(self, factory: Optional[Dict[str, Any]]):
        """把该工厂的价格表临时覆盖到引擎资料库；返回原值用于恢复。"""
        if not factory:
            return None
        prices = factory.get("prices") or {}
        if not prices:
            return None
        old = (self.materials, self.processes, self.presses, self.packagings)
        self.materials = copy.deepcopy(self.materials)
        self.processes = copy.deepcopy(self.processes)
        self.presses = copy.deepcopy(self.presses)
        self.packagings = copy.deepcopy(self.packagings)
        for mid, ov in (prices.get("materials") or {}).items():
            if mid in self.materials:
                if ov.get("algorithm_id"):
                    self.materials[mid]["algorithm_id"] = ov["algorithm_id"]
                self.materials[mid]["params"] = copy.deepcopy(ov.get("params") or {})
        for pid, ov in (prices.get("presses") or {}).items():
            if pid in self.presses:
                if ov.get("algorithm_id"):
                    self.presses[pid]["algorithm_id"] = ov["algorithm_id"]
                self.presses[pid]["params"] = copy.deepcopy(ov.get("params") or {})
        for pid, ov in (prices.get("processes") or {}).items():
            if pid in self.processes and ov.get("methods"):
                self.processes[pid]["methods"] = copy.deepcopy(ov["methods"])
        for pid, ov in (prices.get("packagings") or {}).items():
            if pid in self.packagings:
                if ov.get("algorithm_id"):
                    self.packagings[pid]["algorithm_id"] = ov["algorithm_id"]
                self.packagings[pid]["params"] = copy.deepcopy(ov.get("params") or {})
        return old

    def _restore_prices(self, old) -> None:
        if old:
            self.materials, self.processes, self.presses, self.packagings = old

    def quote(
        self,
        product: Dict[str, Any],
        cfg: Optional[Dict[str, Any]] = None,
        agent: Optional[Dict[str, Any]] = None,
        viewer: str = "customer",
        markup: Optional[float] = None,
        factory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not product:
            raise EngineError("商品不存在")
        config = self.normalize_config(product, cfg)
        mode = config.get("mode")
        modes = product.get("modes") or ["custom"]
        if mode not in modes:
            raise EngineError("该商品不支持「%s」模式" % MODE_NAMES.get(mode or "", mode))

        if agent and not agent.get("enabled"):
            agent = None
        if markup is None:
            markup = _n(agent.get("default_markup"), self.setting("direct_markup", 0.35)) if agent else _n(self.setting("direct_markup"), 0.35)
        markup = _clamp(_n(markup, 0), 0.0, 1.5)

        scope = self._apply_factory_prices(factory)
        try:
            if mode == "overprint":
                result = self._quote_overprint(product, config, agent, markup, factory)
            else:
                result = self._quote_custom(product, config, agent, markup, factory)
        finally:
            self._restore_prices(scope)

        result["view"] = viewer
        result["mode_name"] = MODE_NAMES.get(mode, mode)
        result["markup"] = round(markup, 4)
        result["agent"] = self._agent_public(agent)
        result["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        result["quote_note"] = self.setting("quote_note", "")
        result["delivery_note"] = self.setting("delivery_note", "")
        result["payment_note"] = self.setting("payment_note", "")
        result["valid_days"] = _i(self.setting("quote_valid_days"), 15)
        result["terms"] = [
            "报价含 6% 增值税与标准送货上门费用。",
            "报价有效期 %d 天，逾期以重新核价为准。" % result["valid_days"],
            "确认订单后支付 50% 定金安排生产，余款发货前结清。",
            "文件请提供 AI / PDF / 刀模文件，色彩以打样确认为准。",
        ]
        return result

    def _agent_public(self, agent: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not agent:
            return None
        return {
            "id": agent.get("id"),
            "name": agent.get("name"),
            "company": agent.get("company"),
            "code": agent.get("agent_code"),
            "phone": agent.get("phone"),
        }

    # ============================================================== custom path
    def _quote_custom(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        agent: Optional[Dict[str, Any]],
        markup: float,
        factory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        mode = config["mode"]
        warnings: List[str] = []

        # ---- 尺寸与展开
        if product.get("kind") == "overprint":
            raise EngineError("该商品为成品加印，请选择加印模式")
        dims = config.get("dims") or {}
        errs = formulas.validate_dims(product.get("structure", "cardbox"), dims, product.get("dim_fields"))
        if errs:
            raise EngineError("；".join(errs[:3]))
        unfold = formulas.unfold(
            product.get("structure", "cardbox"),
            dims,
            product.get("formula_params"),
            _n(product.get("bleed"), 3),
            {f["key"]: f["label"] for f in product.get("dim_fields") or [] if f.get("key")},
        )

        # ---- 材料 / 数量 / 颜色
        allowed_materials = product.get("materials") or []
        material_id = config.get("material_id")
        if material_id not in allowed_materials:
            material_id = product.get("default_material") or (allowed_materials[0] if allowed_materials else "")
        material = self.materials.get(material_id)
        if not material:
            raise EngineError("请选择材料")

        qty = max(1, _i(config.get("qty"), 1))
        qconf = product.get("quantity") or {}
        if mode == "sample":
            sp = product.get("sample") or {}
            if not sp.get("enabled"):
                raise EngineError("该商品暂不支持打样")
            lo, hi = _i(sp.get("min"), 1), _i(sp.get("max"), 10)
            qty = int(_clamp(qty, lo, hi))
        else:
            lo, hi = _i(qconf.get("min"), 1), _i(qconf.get("max"), 1000000)
            if qty < lo or qty > hi:
                raise EngineError("数量需在 %d - %d 之间" % (lo, hi))

        color_options = product.get("colors") or [0]
        colors = _i(config.get("colors"), 1)
        if colors not in color_options:
            colors = color_options[0]
        if colors < 0:
            colors = 0

        # ---- 工艺集合
        selected, process_notes = self._resolve_processes(product, config, material, qty, warnings)

        # ---- 包装
        packaging = self._resolve_packaging(product, config)

        # ---- 辅料
        aux_lines, aux_total, aux_notes = self._calc_aux(product, config, qty)

        # ---- 枚举上机方案
        plans = self._iter_custom_plans(product, material, unfold, qty, colors, selected, mode, packaging, aux_total, aux_lines, agent, markup, warnings, factory)
        if not plans:
            raise EngineError("当前尺寸/材料没有可用的上机拼版方案，请调整尺寸或材料")

        objective = (product.get("production") or {}).get("objective", "cost")
        if mode == "sample":
            objective = "cost"
        plans.sort(key=lambda p: (p["sort_cost"], p["sort_days"]) if objective == "cost" else (p["sort_days"], p["sort_cost"]))
        best = plans[0]
        for p in plans:
            p["chosen"] = p is best
        max_cost = max(p["totals"]["cost"] for p in plans)
        savings = _r2(max_cost - best["totals"]["cost"])

        result = best["result"]
        result["warnings"] = warnings + process_notes
        result["optimization"] = {
            "objective": objective,
            "plans_compared": len(plans),
            "savings": savings,
            "message": "系统比选 %d 个生产方案，已选择%s方案，较最高方案节省 %s" % (
                len(plans),
                "交期最优" if objective == "lead" else "成本更优",
                _money(savings) if savings > 0 else "0",
            ),
        }
        result["alternatives"] = [
            {
                "press_name": p["plan"]["press_name"],
                "sheet_name": p["plan"]["sheet_name"],
                "units_per_sheet": p["plan"]["units_per_sheet"],
                "sheets": p["plan"]["sheets"],
                "cost": p["totals"]["cost"],
                "agent": p["totals"]["agent"],
                "retail": p["totals"]["retail"],
                "lead_min": p["lead"]["min"],
                "lead_max": p["lead"]["max"],
                "chosen": p["chosen"],
            }
            for p in sorted(plans, key=lambda x: x["totals"]["cost"])[:4]
        ]
        return result

    def _iter_custom_plans(
        self,
        product: Dict[str, Any],
        material: Dict[str, Any],
        unfold: Dict[str, Any],
        qty: int,
        colors: int,
        selected: List[str],
        mode: str,
        packaging: Dict[str, Any],
        aux_total: float,
        aux_lines: List[Dict[str, Any]],
        agent: Optional[Dict[str, Any]],
        markup: float,
        warnings: List[str],
        factory: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        production = product.get("production") or {}
        press_ids = production.get("press_ids") or []
        allowed_sheet_ids = production.get("sheet_ids") or []
        loss = _n(production.get("loss_rate"), self.setting("loss_rate", 0.05))
        objective = "cost" if mode == "sample" else production.get("objective", "cost")
        out = []

        for press_id in press_ids:
            press = self.presses.get(press_id)
            if not press or not press.get("enabled", 1):
                continue
            if factory and press.get("factory_id") != factory.get("id"):
                continue
            if material.get("kind") not in (press.get("material_kinds") or []):
                continue
            if press.get("type") == "label":
                if material.get("kind") != "label":
                    continue
                roll = None
                for sid in press.get("sheet_ids") or []:
                    if allowed_sheet_ids and sid not in allowed_sheet_ids:
                        continue
                    if sid in (material.get("sheet_ids") or []):
                        roll = self.sheets.get(sid)
                        break
                if not roll:
                    continue
                plan = imposition.label_plan(unfold, roll, press, qty, loss)
                if plan["units_per_sheet"] <= 0:
                    continue
                evaluated = self._evaluate_plan(product, material, unfold, plan, press, qty, colors, selected, mode, packaging, aux_total, aux_lines, agent, markup, warnings, objective, factory)
                if evaluated:
                    out.append(evaluated)
                continue

            for sid in press.get("sheet_ids") or []:
                if allowed_sheet_ids and sid not in allowed_sheet_ids:
                    continue
                if sid not in (material.get("sheet_ids") or []):
                    continue
                sheet = self.sheets.get(sid)
                if not sheet:
                    continue
                if not self._sheet_fits(sheet, press):
                    continue
                plan = imposition.make_plan(unfold, sheet, press, qty, loss)
                if plan["units_per_sheet"] <= 0:
                    continue
                evaluated = self._evaluate_plan(product, material, unfold, plan, press, qty, colors, selected, mode, packaging, aux_total, aux_lines, agent, markup, warnings, objective, factory)
                if evaluated:
                    out.append(evaluated)
        return out

    def _sheet_fits(self, sheet: Dict[str, Any], press: Dict[str, Any]) -> bool:
        sw, sh = _n(sheet.get("w")), _n(sheet.get("h"))
        mw, mh = _n(press.get("max_w"), 1e9), _n(press.get("max_h"), 1e9)
        return (sw <= mw and sh <= mh) or (sw <= mh and sh <= mw)

    def _evaluate_plan(
        self,
        product: Dict[str, Any],
        material: Dict[str, Any],
        unfold: Dict[str, Any],
        plan: Dict[str, Any],
        press: Dict[str, Any],
        qty: int,
        colors: int,
        selected: List[str],
        mode: str,
        packaging: Dict[str, Any],
        aux_total: float,
        aux_lines: List[Dict[str, Any]],
        agent: Optional[Dict[str, Any]],
        markup: float,
        warnings: List[str],
        objective: str,
        factory: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        ctx = {
            "qty": qty,
            "colors": colors,
            "sheets": plan.get("sheets", 0),
            "area_m2": plan.get("material_area_m2", 0),
            "flat_w": unfold.get("flat_w"),
            "flat_h": unfold.get("flat_h"),
            "piece_w": unfold.get("piece_w"),
            "piece_h": unfold.get("piece_h"),
            "units_per_sheet": plan.get("units_per_sheet", 0),
        }

        material_cost = algorithms.calc(material.get("algorithm_id"), material.get("params"), ctx)
        if plan.get("label_roll"):
            mat_detail = "%s · %.2f m²（含损耗）" % (plan["sheet_name"], plan["material_area_m2"])
        else:
            mat_detail = "%s · %d 张 · %.2f m²" % (plan["sheet_name"], plan["sheets"], plan["material_area_m2"])

        print_cost = algorithms.calc(press.get("algorithm_id"), press.get("params"), ctx)
        print_detail = "%s · %d 色 · %s" % (
            press["name"], colors,
            ("%d 张" % plan["sheets"]) if plan.get("sheets") else ("%.2f m²" % plan.get("material_area_m2", 0)),
        )

        lines = [
            {"key": "material", "label": "材料费", "amount": material_cost, "detail": mat_detail, "group": "production"},
            {"key": "print", "label": "印刷费", "amount": print_cost, "detail": print_detail, "group": "production"},
        ]
        process_lines = []
        max_process_days = 0
        proc_total = 0.0
        for pid in selected:
            proc = self.processes.get(pid)
            if not proc:
                continue
            allowed, reason = self._process_allowed(proc, product.get("structure", ""), material, colors)
            if not allowed:
                if pid in (product.get("processes") or {}).get("required", []):
                    return None
                warnings.append("%s：%s，已跳过" % (proc["name"], reason))
                continue
            method, method_cost, method_days = self._choose_method(proc, ctx, qty, objective)
            if not method:
                if pid in (product.get("processes") or {}).get("required", []):
                    return None
                warnings.append("%s：当前数量没有可用生产方式，已跳过" % proc["name"])
                continue
            amount = 0.0 if mode == "sample" else method_cost
            if mode == "sample":
                note = "打样包含，不另计"
            else:
                note = method.get("note", "")
            line = {
                "key": "process:" + pid,
                "label": proc["name"],
                "amount": _r2(amount),
                "detail": "%s · %s" % (method.get("name", ""), note or ("%d 件" % qty)),
                "group": "production",
                "process_id": pid,
                "method": method.get("name", ""),
                "days": method_days,
                "image": proc.get("image", ""),
                "description": proc.get("description", ""),
                "waived": mode == "sample",
                "list_amount": _r2(method_cost),
            }
            lines.append(line)
            process_lines.append(line)
            proc_total += amount
            max_process_days = max(max_process_days, method_days)

        for al in aux_lines:
            lines.append(al)
        aux_total_rounded = _r2(aux_total)
        if aux_total_rounded > 0:
            # 辅料已按行加入，这里仅用于合计
            pass

        packaging_cost = algorithms.calc(packaging.get("algorithm_id"), packaging.get("params"), ctx)
        lines.append({
            "key": "packaging",
            "label": "包装费",
            "amount": packaging_cost,
            "detail": "%s · %d 件/箱" % (packaging.get("name", "标准包装"), _i(packaging.get("carton_qty"), 50)),
            "group": "production",
        })

        sample_fee = 0.0
        if mode == "sample":
            sample_fee = _n((product.get("sample") or {}).get("fee"), _n(self.setting("sample_fee"), 180))
            lines.append({
                "key": "sample_fee",
                "label": "打样服务费",
                "amount": _r2(sample_fee),
                "detail": "含刀模/调机/打样制作",
                "group": "production",
            })

        base_subtotal = _r2(sum(_n(l["amount"]) for l in lines if l.get("group") == "production"))
        if factory:
            factor = _n(factory.get("price_factor"), 1.0)
            fixed_fee = _n(factory.get("fixed_fee"), 0)
            adjusted = _r2(base_subtotal * factor + fixed_fee)
            diff = _r2(adjusted - base_subtotal)
            if abs(diff) >= 0.01:
                lines.append({
                    "key": "factory_adjust", "label": "工厂价格系数/服务费",
                    "amount": diff,
                    "detail": "%s · 系数 %.2f + 服务费 %s" % (factory.get("name", ""), factor, _money(fixed_fee)),
                    "group": "production",
                })
            production_subtotal = adjusted
        else:
            production_subtotal = base_subtotal
        overhead_rate = _n(product.get("production", {}).get("overhead_rate"), _n(self.setting("overhead_rate"), 0.06))
        overhead = _r2(production_subtotal * overhead_rate)

        unit_weight = self._unit_weight(plan, material, qty)
        shipping, weight = self._shipping(
            qty, unit_weight, packaging, production_subtotal,
            sample=(mode == "sample"), product=product,
        )

        tax_rate = _n(self.setting("tax_rate"), 0.06)
        taxable = _r2(production_subtotal + overhead + shipping)
        tax = _r2(taxable * tax_rate)
        cost_total = _r2(taxable + tax)

        totals = self._price_chain(cost_total, qty, agent, markup, mode, product)

        lead = self._lead_days(product, press, max_process_days, qty, mode, _i((factory or {}).get("lead_days"), 0))
        plan_out = {
            "press_id": press["id"],
            "press_name": press["name"],
            "press_type": press.get("type"),
            "sheet_id": plan.get("sheet_id"),
            "sheet_name": plan.get("sheet_name"),
            "sheet_w": plan.get("sheet_w"),
            "sheet_h": plan.get("sheet_h"),
            "piece_w": plan.get("piece_w"),
            "piece_h": plan.get("piece_h"),
            "flat_w": unfold.get("flat_w"),
            "flat_h": unfold.get("flat_h"),
            "bleed": unfold.get("bleed"),
            "pieces_per_unit": plan.get("pieces_per_unit", 1),
            "units_per_sheet": plan.get("units_per_sheet", 0),
            "blanks_per_sheet": plan.get("blanks_per_sheet", 0),
            "cols": plan.get("cols", 0),
            "rows": plan.get("rows", 0),
            "rotated": plan.get("rotated", False),
            "sheets": plan.get("sheets", 0),
            "utilization": plan.get("utilization", 0),
            "material_area_m2": plan.get("material_area_m2", 0),
            "label_roll": plan.get("label_roll", False),
            "roll_length_m": plan.get("roll_length_m"),
        }

        result = self._build_result(
            product=product,
            config={"mode": mode, "qty": qty, "dims": unfold["dims"], "colors": colors},
            unfold=unfold,
            plan=plan_out,
            material=material,
            packaging=packaging,
            aux_lines=aux_lines,
            lines=lines,
            process_lines=process_lines,
            production_subtotal=production_subtotal,
            overhead=overhead,
            shipping=shipping,
            tax=tax,
            cost=cost_total,
            totals=totals,
            lead=lead,
            weight=weight,
            sample=(mode == "sample"),
            agent=agent,
            markup=markup,
            warnings=warnings,
        )
        result["factory"] = self._factory_public(factory)
        result["plan"]["factory_id"] = (factory or {}).get("id")
        result["plan"]["factory_name"] = (factory or {}).get("name")
        return {
            "result": result,
            "plan": plan_out,
            "totals": totals,
            "lead": lead,
            "sort_cost": totals["cost"],
            "sort_days": lead["min"],
            "chosen": False,
        }

    # =========================================================== overprint path
    def _quote_overprint(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        agent: Optional[Dict[str, Any]],
        markup: float,
        factory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        stock = product.get("stock") or {}
        qty = max(1, _i(config.get("qty"), 1))
        qconf = product.get("quantity") or {}
        lo, hi = _i(qconf.get("min"), 1), _i(qconf.get("max"), 100000)
        if qty < lo or qty > hi:
            raise EngineError("数量需在 %d - %d 之间" % (lo, hi))
        stock_qty = _i(stock.get("stock_qty"), 0)
        if stock_qty and qty > stock_qty:
            raise EngineError("现货库存仅剩 %d 个，请减少数量或选择全定制" % stock_qty)

        methods = product.get("overprint_methods") or []
        method_id = config.get("overprint_method") or (methods[0] if methods else {}).get("id")
        method_conf = next((m for m in methods if m.get("id") == method_id), methods[0] if methods else None)
        if not method_conf:
            raise EngineError("请选择加印工艺")
        colors = _i(config.get("colors"), 1)
        colors = int(_clamp(colors, 1, _i(method_conf.get("max_colors"), 1)))
        proc = self.processes.get(method_conf.get("process_id"))
        if not proc:
            raise EngineError("加印工艺未配置")

        blank_price = _n(stock.get("blank_price"), 0)
        blank_total = _r2(blank_price * qty)

        ctx = {"qty": qty, "colors": colors, "sheets": 0, "area_m2": 0}
        method, method_cost, method_days = self._choose_method(proc, ctx, qty, "cost")
        if not method:
            raise EngineError("该加印工艺没有可用生产方式")

        lines = [
            {"key": "stock", "label": "现货胚袋", "amount": blank_total,
             "detail": "%s × %d 个" % (stock.get("name", "现货成品"), qty), "group": "production"},
            {"key": "print", "label": method_conf.get("name", "成品加印"), "amount": _r2(method_cost),
             "detail": "%s · %d 色" % (method.get("name", ""), colors), "group": "production",
             "process_id": proc["id"], "method": method.get("name", ""), "days": method_days,
             "image": proc.get("image", ""), "description": proc.get("description", "")},
        ]

        packaging = self._resolve_packaging(product, config)
        packaging_cost = algorithms.calc(packaging.get("algorithm_id"), packaging.get("params"), ctx)
        lines.append({
            "key": "packaging", "label": "包装费", "amount": packaging_cost,
            "detail": "%s · %d 件/箱" % (packaging.get("name", "标准包装"), _i(packaging.get("carton_qty"), 50)),
            "group": "production",
        })

        base_subtotal = _r2(sum(l["amount"] for l in lines))
        if factory:
            factor = _n(factory.get("price_factor"), 1.0)
            fixed_fee = _n(factory.get("fixed_fee"), 0)
            adjusted = _r2(base_subtotal * factor + fixed_fee)
            diff = _r2(adjusted - base_subtotal)
            if abs(diff) >= 0.01:
                lines.append({
                    "key": "factory_adjust", "label": "工厂价格系数/服务费",
                    "amount": diff,
                    "detail": "%s · 系数 %.2f + 服务费 %s" % (factory.get("name", ""), factor, _money(fixed_fee)),
                    "group": "production",
                })
            production_subtotal = adjusted
        else:
            production_subtotal = base_subtotal
        overhead_rate = _n(self.setting("overhead_rate"), 0.06)
        overhead = _r2(production_subtotal * overhead_rate)

        unit_weight = _n(stock.get("weight_kg"), 0.045)
        shipping, weight = self._shipping(qty, unit_weight, packaging, production_subtotal, sample=False, product=product)
        tax_rate = _n(self.setting("tax_rate"), 0.06)
        taxable = _r2(production_subtotal + overhead + shipping)
        tax = _r2(taxable * tax_rate)
        cost_total = _r2(taxable + tax)
        totals = self._price_chain(cost_total, qty, agent, markup, "overprint", product)

        lead_min = _i(stock.get("lead_days"), 3) + method_days + _i((factory or {}).get("lead_days"), 0)
        lead = {"min": lead_min, "max": lead_min + 1, "text": "%d-%d 个工作日" % (lead_min, lead_min + 1)}

        plan_out = {
            "stock": True,
            "stock_name": stock.get("name", ""),
            "stock_qty": stock_qty,
            "method_name": method_conf.get("name", ""),
            "press_name": method.get("name", ""),
            "sheet_name": "成品加印（无需拼版）",
            "units_per_sheet": 0,
            "sheets": 0,
            "flat_w": (stock.get("dims") or {}).get("L"),
            "flat_h": (stock.get("dims") or {}).get("W"),
            "bleed": 0,
        }

        result = self._build_result(
            product=product,
            config={"mode": "overprint", "qty": qty, "dims": stock.get("dims") or {}, "colors": colors,
                    "overprint_method": method_conf.get("id"), "overprint_method_name": method_conf.get("name")},
            unfold=None,
            plan=plan_out,
            material=None,
            packaging=packaging,
            aux_lines=[],
            lines=lines,
            process_lines=[lines[1]],
            production_subtotal=production_subtotal,
            overhead=overhead,
            shipping=shipping,
            tax=tax,
            cost=cost_total,
            totals=totals,
            lead=lead,
            weight=weight,
            sample=False,
            agent=agent,
            markup=markup,
            warnings=[],
        )
        result["factory"] = self._factory_public(factory)
        result["plan"]["factory_id"] = (factory or {}).get("id")
        result["plan"]["factory_name"] = (factory or {}).get("name")
        result["optimization"] = {
            "objective": "cost", "plans_compared": 1, "savings": 0,
            "message": "现货加印，无需重新制版拼版，已按成品胚价 + 加印工艺核价。",
        }
        result["alternatives"] = []
        return result

    # ============================================================== components
    def _resolve_processes(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        material: Dict[str, Any],
        qty: int,
        warnings: List[str],
    ) -> Tuple[List[str], List[str]]:
        pconf = product.get("processes") or {}
        required = list(pconf.get("required") or [])
        optional = list(pconf.get("optional") or [])
        selected = set(required)
        notes: List[str] = []
        for pid in config.get("processes") or []:
            if pid in optional:
                selected.add(pid)
            elif pid not in required:
                warnings.append("未知或不适用的工艺：%s" % pid)
        for group in pconf.get("groups") or []:
            opts = group.get("options") or []
            chosen = next((p for p in opts if p in selected), None)
            if not chosen and group.get("required") and opts:
                chosen = opts[0]
            if chosen:
                selected.add(chosen)
            for p in opts:
                if p != chosen:
                    selected.discard(p)
        # 校验必选工艺
        for pid in required:
            proc = self.processes.get(pid)
            if not proc:
                raise EngineError("商品工艺配置缺失：%s" % pid)
            ok, reason = self._process_allowed(proc, product.get("structure", ""), material, _i(config.get("colors"), 1))
            if not ok:
                raise EngineError("所选材料不满足「%s」：%s。请更换材料或工艺。" % (proc["name"], reason))
        return [p for p in selected if p in self.processes], notes

    def _process_allowed(self, proc: Dict[str, Any], structure: str, material: Optional[Dict[str, Any]], colors: int) -> Tuple[bool, str]:
        if not proc or not proc.get("enabled", 1):
            return False, "工艺已停用"
        applies = proc.get("applies_to") or []
        if structure and structure not in applies and "*" not in applies:
            return False, "不适用于该盒型"
        kinds = proc.get("material_kinds") or []
        if material and kinds and material.get("kind") not in kinds:
            return False, "不适用于该材料"
        constraints = proc.get("constraints") or {}
        min_gsm = _n(constraints.get("min_gsm"), 0)
        if material and min_gsm and _n(material.get("gsm"), 0) < min_gsm:
            return False, "材料克重需 ≥ %d g/m²（当前 %d g/m²）" % (min_gsm, _n(material.get("gsm"), 0))
        max_colors = constraints.get("max_colors")
        if max_colors is not None and colors > _i(max_colors, 99):
            return False, "最多 %d 色" % _i(max_colors, 99)
        return True, ""

    def _choose_method(
        self, proc: Dict[str, Any], ctx: Dict[str, Any], qty: int, objective: str
    ) -> Tuple[Optional[Dict[str, Any]], float, int]:
        methods = proc.get("methods") or []
        feasible = []
        for m in methods:
            if qty < _i(m.get("min_qty"), 0):
                continue
            amount = algorithms.calc(m.get("algorithm_id"), m.get("params"), ctx)
            feasible.append((m, amount, _i(m.get("days"), 1)))
        if not feasible:
            return None, 0.0, 0
        if objective == "lead":
            feasible.sort(key=lambda x: (x[2], x[1]))
        else:
            feasible.sort(key=lambda x: (x[1], x[2]))
        return feasible[0]

    def _resolve_packaging(self, product: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        allowed = product.get("packagings") or []
        pid = config.get("packaging_id")
        if pid not in allowed:
            pid = product.get("default_packaging") or (allowed[0] if allowed else "")
        pkg = self.packagings.get(pid)
        if not pkg:
            pkg = {
                "id": "pkg-default", "name": "标准包装", "carton_qty": 50,
                "carton_weight_kg": 0.6, "carton_size": [600, 400, 350],
                "algorithm_id": "packaging_order",
                "params": {"price_per_order": 8, "price_per_piece": 0.12},
            }
        return pkg

    def _calc_aux(
        self, product: Dict[str, Any], config: Dict[str, Any], qty: int
    ) -> Tuple[List[Dict[str, Any]], float, List[str]]:
        lines: List[Dict[str, Any]] = []
        notes: List[str] = []
        total = 0.0
        selected = config.get("aux") or {}
        for group in product.get("aux_groups") or []:
            gid = group.get("id")
            opts = group.get("options") or []
            mat_id = selected.get(gid)
            opt = next((o for o in opts if o.get("material_id") == mat_id), None)
            if not opt:
                opt = next((o for o in opts if o.get("default")), opts[0] if opts else None)
            if not opt or not opt.get("material_id"):
                continue
            mat = self.materials.get(opt["material_id"])
            if not mat:
                continue
            per = _n(group.get("per_unit"), 1)
            ctx = {"qty": qty, "aux_per_unit": per, "color": 0}
            amount = algorithms.calc(mat.get("algorithm_id"), mat.get("params"), ctx)
            if amount <= 0:
                continue
            line = {
                "key": "aux:" + str(gid),
                "label": "辅料 · " + str(group.get("name", mat.get("name", ""))),
                "amount": _r2(amount),
                "detail": "%s · %.2f%s/件 × %d 件" % (opt.get("label") or mat.get("name"), per, group.get("unit", ""), qty),
                "group": "production",
                "image": mat.get("image", ""),
            }
            lines.append(line)
            total += amount
        return lines, _r2(total), notes

    def _unit_weight(self, plan: Dict[str, Any], material: Dict[str, Any], qty: int) -> float:
        gsm = _n(material.get("gsm"), 120)
        if plan.get("label_roll"):
            area = _n(plan.get("material_area_m2"), 0) / max(1, qty)
            kg = area * gsm / 1000.0
        else:
            sheet_area = _n(plan.get("sheet_area_m2"), 0)
            ups = max(1, _i(plan.get("units_per_sheet"), 1))
            kg = sheet_area * gsm / 1000.0 / ups
        return max(0.002, kg * 1.08)

    def _logistics_conf(self, product: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        l = (product or {}).get("logistics") or {}
        return {
            "mode": "home",
            "provider": str(l.get("provider") or "统一配送"),
            "warehouse": str(l.get("warehouse") or self.setting("warehouse", "杭州中心仓")),
            "base_fee": _n(l.get("base_fee"), _n(self.setting("shipping_base"), 10)),
            "per_kg": _n(l.get("per_kg"), _n(self.setting("shipping_per_kg"), 1.8)),
            "free_over": _n(l.get("free_over"), _n(self.setting("free_shipping_over"), 3000)),
            "lead_days": _i(l.get("lead_days"), 1),
            "note": str(l.get("note") or self.setting("delivery_note", "")),
            "included": bool(l.get("included", True)),
        }

    def _shipping(
        self,
        qty: int,
        unit_weight: float,
        packaging: Dict[str, Any],
        production_subtotal: float,
        sample: bool,
        product: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        if sample:
            fee = _r2(_n(self.setting("sample_shipping"), 18))
            return fee, {"chargeable_kg": 0.5, "cartons": 1, "note": "打样统一快递", "free": False}
        conf = self._logistics_conf(product)
        free_over = conf["free_over"]
        if free_over > 0 and production_subtotal >= free_over:
            return 0.0, {"chargeable_kg": 0, "cartons": 0, "note": "满额免运费 · 送货上门", "free": True, "provider": conf["provider"], "warehouse": conf["warehouse"]}

        carton_qty = max(1, _i(packaging.get("carton_qty"), 50))
        cartons = _ceil_div(qty, carton_qty)
        carton_w = _n(packaging.get("carton_weight_kg"), 0.6)
        size = packaging.get("carton_size") or [600, 400, 350]
        try:
            cm = [_n(x) / 10.0 for x in size]  # mm -> cm
            volumetric = cartons * (cm[0] * cm[1] * cm[2]) / 12000.0
        except Exception:
            volumetric = 0.0
        actual = qty * unit_weight + cartons * carton_w
        chargeable = max(1.0, actual, volumetric)
        base = conf["base_fee"]
        per_kg = conf["per_kg"]
        fee = _r2(base + per_kg * max(0.0, chargeable - 1.0))
        return fee, {
            "chargeable_kg": round(chargeable, 2),
            "actual_kg": round(actual, 2),
            "cartons": cartons,
            "note": "送货上门",
            "free": False,
            "provider": conf["provider"],
            "warehouse": conf["warehouse"],
        }

    def _price_chain(
        self,
        cost: float,
        qty: int,
        agent: Optional[Dict[str, Any]],
        markup: float,
        mode: str,
        product: Dict[str, Any],
    ) -> Dict[str, Any]:
        platform_margin = _n((product.get("pricing") or {}).get("platform_margin"), _n(self.setting("platform_margin"), 0.18))
        platform_margin = _clamp(platform_margin, 0, 0.8)
        platform_fee = _r2(cost * platform_margin)
        agent_total = _r2(cost + platform_fee)
        retail_base = _r2(agent_total * (1 + markup))
        min_total = _n(self.setting("min_order_total"), 300)
        min_fee = 0.0
        if mode != "sample":
            min_fee = _r2(max(0.0, min_total - retail_base))
        retail = _r2(retail_base + min_fee)
        if agent:
            agent_profit = _r2(retail - agent_total)
            platform_profit = _r2(platform_fee)
        else:
            agent_profit = 0.0
            platform_profit = _r2(retail - cost)
        return {
            "cost": _r2(cost),
            "platform_fee": _r2(platform_fee),
            "agent": agent_total,
            "retail": retail,
            "retail_base": retail_base,
            "min_fee": min_fee,
            "unit_cost": _r2(cost / max(1, qty)),
            "unit_agent": _r2(agent_total / max(1, qty)),
            "unit_retail": _r2(retail / max(1, qty)),
            "agent_profit": agent_profit,
            "platform_profit": platform_profit,
            "markup": round(markup, 4),
            "platform_margin": round(platform_margin, 4),
        }

    def _lead_days(
        self, product: Dict[str, Any], press: Dict[str, Any], process_days: int, qty: int, mode: str, extra_days: int = 0
    ) -> Dict[str, Any]:
        if mode == "sample":
            base = _i((product.get("sample") or {}).get("lead_days"), 3)
        else:
            base = _i(product.get("lead_days"), 5)
            computed = _i(press.get("days"), 2) + process_days + 1
            base = max(base, computed)
            if qty >= 3000:
                base += 1
            if qty >= 10000:
                base += 1
        base += max(0, extra_days)
        return {"min": base, "max": base + 2, "text": "%d-%d 个工作日" % (base, base + 2)}

    # ================================================================ builders
    def _build_result(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        unfold: Optional[Dict[str, Any]],
        plan: Dict[str, Any],
        material: Optional[Dict[str, Any]],
        packaging: Dict[str, Any],
        aux_lines: List[Dict[str, Any]],
        lines: List[Dict[str, Any]],
        process_lines: List[Dict[str, Any]],
        production_subtotal: float,
        overhead: float,
        shipping: float,
        tax: float,
        cost: float,
        totals: Dict[str, Any],
        lead: Dict[str, Any],
        weight: Dict[str, Any],
        sample: bool,
        agent: Optional[Dict[str, Any]],
        markup: float,
        warnings: List[str],
    ) -> Dict[str, Any]:
        internal_lines = []
        for line in lines:
            if line.get("group") == "production":
                internal_lines.append(dict(line))
        internal_lines.append({
            "key": "overhead", "label": "管理费", "amount": _r2(overhead),
            "detail": "按制作成本 %d%% 计" % round(_n(self.setting("overhead_rate"), 0.06) * 100),
            "group": "overhead",
        })
        internal_lines.append({
            "key": "shipping", "label": "物流费", "amount": _r2(shipping),
            "detail": "%s · 计费重 %s kg" % (weight.get("note", "送货上门"), weight.get("chargeable_kg", 0)),
            "group": "logistics",
        })
        internal_lines.append({
            "key": "tax", "label": "增值税", "amount": _r2(tax),
            "detail": "按 %d%% 计" % round(_n(self.setting("tax_rate"), 0.06) * 100),
            "group": "tax",
        })

        # 客户端展示：分组折算到零售价，不暴露成本与平台/代理利润
        factor = (totals["retail"] / cost) if cost > 0 else 1.0
        goods_cost = sum(_n(l["amount"]) for l in lines if l.get("group") == "production")
        goods = _r2(goods_cost * factor)
        logistics = _r2(shipping * factor)
        service = _r2(totals["retail"] - goods - logistics - totals["min_fee"])
        if service < 0:
            goods = _r2(max(0, goods + service))
            service = 0.0
        customer_lines = [
            {"key": "goods", "label": ("打样制作" if sample else "商品制作"), "amount": goods, "detail": "材料 / 印刷 / 工艺 / 包装"},
            {"key": "logistics", "label": "包装物流", "amount": logistics, "detail": weight.get("note", "送货上门")},
        ]
        if totals["min_fee"] > 0:
            customer_lines.append({"key": "min_fee", "label": "小单服务费", "amount": totals["min_fee"], "detail": "小批量订单服务成本"})
        customer_lines.append({"key": "service", "label": "税费与服务", "amount": service, "detail": "含增值税、售后与交付服务"})

        product_pub = {
            "id": product.get("id"),
            "name": product.get("name"),
            "subtitle": product.get("subtitle", ""),
            "description": product.get("description", ""),
            "long_desc": product.get("long_desc", ""),
            "image": product.get("image") or (product.get("images") or [""])[0],
            "category": product.get("category", ""),
            "kind": product.get("kind", "custom"),
        }

        config_pub = {
            "mode": config.get("mode"),
            "qty": config.get("qty"),
            "dims": config.get("dims"),
            "colors": config.get("colors"),
            "size_name": config.get("size_name", ""),
            "material": ({
                "id": material.get("id"), "name": material.get("name"), "gsm": material.get("gsm"),
                "image": material.get("image"), "kind": material.get("kind"), "color": material.get("color"),
            } if material else None),
            "packaging": {"id": packaging.get("id"), "name": packaging.get("name"), "image": packaging.get("image")},
            "overprint_method": config.get("overprint_method"),
            "overprint_method_name": config.get("overprint_method_name"),
        }
        if sample:
            config_pub["sample"] = True

        return {
            "mode": config.get("mode"),
            "qty": config.get("qty"),
            "product": product_pub,
            "config": config_pub,
            "unfold": unfold,
            "plan": plan,
            "aux_lines": aux_lines,
            "lines": lines,
            "internal_lines": internal_lines,
            "process_lines": process_lines,
            "customer_lines": customer_lines,
            "totals": totals,
            "subtotal": _r2(production_subtotal),
            "overhead": _r2(overhead),
            "shipping": _r2(shipping),
            "tax": _r2(tax),
            "cost": _r2(cost),
            "lead": lead,
            "weight": weight,
            "logistics": {**self._logistics_conf(product), "fee": _r2(shipping), "free": bool(weight.get("free")), "chargeable_kg": weight.get("chargeable_kg", 0)},
            "sample": sample,
            "markup": round(markup, 4),
            "agent_id": (agent or {}).get("id"),
            "agent_code": (agent or {}).get("agent_code"),
            "warnings": warnings,
        }

    # ============================================================ presentation
    def present(self, quote: Dict[str, Any], viewer: str) -> Dict[str, Any]:
        """按角色裁剪报价数据，避免成本/利润泄露。"""
        data = copy.deepcopy(quote)
        data.pop("internal_lines", None)
        data.pop("lines", None)
        data.pop("cost", None)
        data.pop("subtotal", None)
        data.pop("overhead", None)
        data.pop("tax", None)
        data.pop("shipping", None)
        if viewer == "admin":
            data["lines"] = quote.get("internal_lines") or []
            data["totals"] = quote.get("totals") or {}
            data["profit"] = {
                "platform": (quote.get("totals") or {}).get("platform_profit", 0),
                "agent": (quote.get("totals") or {}).get("agent_profit", 0),
            }
            data["view"] = "admin"
            return data
        if viewer == "agent":
            logi = data.get("logistics") or {}
            data["logistics"] = {k: logi.get(k) for k in ("mode", "provider", "warehouse", "lead_days", "note", "included", "free")}
            totals = quote.get("totals") or {}
            data["totals"] = {
                "agent": totals.get("agent"),
                "retail": totals.get("retail"),
                "unit_agent": totals.get("unit_agent"),
                "unit_retail": totals.get("unit_retail"),
                "agent_profit": totals.get("agent_profit"),
                "markup": totals.get("markup"),
            }
            data.pop("factory", None)
            if isinstance(data.get("plan"), dict):
                data["plan"].pop("factory_id", None)
                data["plan"].pop("factory_name", None)
            data["view"] = "agent"
            data["process_lines"] = [
                {k: v for k, v in p.items() if k not in ("amount", "list_amount")}
                for p in quote.get("process_lines") or []
            ]
            data["aux_lines"] = [
                {k: v for k, v in p.items() if k not in ("amount", "list_amount")}
                for p in quote.get("aux_lines") or []
            ]
            data["alternatives"] = [
                {k: v for k, v in p.items() if k not in ("cost",)}
                for p in quote.get("alternatives") or []
            ]
            if isinstance(data.get("optimization"), dict):
                data["optimization"] = {
                    "objective": data["optimization"].get("objective"),
                    "plans_compared": data["optimization"].get("plans_compared"),
                    "message": "系统已比选 %s 个生产方案，选择成本与交期更平衡的方案。" % data["optimization"].get("plans_compared", ""),
                }
            data["customer_lines"] = quote.get("customer_lines") or []
            return data
        # customer / public
        logi = data.get("logistics") or {}
        data["logistics"] = {k: logi.get(k) for k in ("mode", "provider", "warehouse", "lead_days", "note", "included", "free")}
        totals = quote.get("totals") or {}
        data["totals"] = {
            "retail": totals.get("retail"),
            "unit_retail": totals.get("unit_retail"),
            "shipping_included": True,
        }
        data.pop("factory", None)
        if isinstance(data.get("plan"), dict):
            data["plan"].pop("factory_id", None)
            data["plan"].pop("factory_name", None)
        data["view"] = "customer"
        data["process_lines"] = [
            {k: v for k, v in p.items() if k not in ("amount", "list_amount", "waived")}
            for p in quote.get("process_lines") or []
        ]
        data["aux_lines"] = [
            {k: v for k, v in p.items() if k not in ("amount", "list_amount")}
            for p in quote.get("aux_lines") or []
        ]
        data["customer_lines"] = quote.get("customer_lines") or []
        if data.get("customer"):
            data["customer"] = {
                "name": data["customer"].get("name", ""),
                "phone": _mask_phone(data["customer"].get("phone", "")),
                "company": data["customer"].get("company", ""),
                "address": data["customer"].get("address", ""),
            }
        data.pop("alternatives", None)
        if isinstance(data.get("optimization"), dict):
            data["optimization"] = {
                "objective": data["optimization"].get("objective"),
                "plans_compared": data["optimization"].get("plans_compared"),
                "message": "系统已比选 %s 个生产方案，选择成本与交期更平衡的方案。" % data["optimization"].get("plans_compared", ""),
            }
        data.pop("markup", None)
        data.pop("agent_id", None)
        data.pop("agent_code", None)
        return data

    # ============================================================== factories
    def _factory_public(self, factory: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not factory:
            return None
        return {
            "id": factory.get("id"),
            "name": factory.get("name"),
            "type": factory.get("type"),
            "price_factor": factory.get("price_factor", 1),
            "fixed_fee": factory.get("fixed_fee", 0),
            "lead_days": factory.get("lead_days", 0),
            "note": factory.get("note", ""),
        }

    def compare_sources(
        self,
        product: Dict[str, Any],
        cfg: Optional[Dict[str, Any]] = None,
        agent: Optional[Dict[str, Any]] = None,
        markup: Optional[float] = None,
    ) -> Dict[str, Any]:
        """同一商品在多个工厂/报价源下的对比。"""
        base = self.quote(product, cfg, agent=agent, viewer="admin", markup=markup)
        ids = product.get("source_ids") or []
        sources = []
        for fid in ids:
            fac = self.factories.get(fid)
            if not fac or not fac.get("enabled", 1):
                continue
            try:
                q = self.quote(product, cfg, agent=agent, viewer="admin", markup=markup, factory=fac)
                sources.append({
                    "factory": self._factory_public(fac),
                    "available": True,
                    "cost": q["totals"]["cost"],
                    "agent": q["totals"]["agent"],
                    "price": q["totals"]["retail"],
                    "unit": q["totals"]["unit_retail"],
                    "qty": q["qty"],
                    "mode": q["mode"],
                    "lead": q["lead"],
                    "logistics": q.get("logistics"),
                    "plan": {
                        "press_name": q["plan"].get("press_name"),
                        "press_type": q["plan"].get("press_type"),
                        "sheet_name": q["plan"].get("sheet_name"),
                        "units_per_sheet": q["plan"].get("units_per_sheet"),
                        "sheets": q["plan"].get("sheets"),
                    },
                    "optimization": q.get("optimization"),
                })
            except EngineError as e:
                sources.append({
                    "factory": self._factory_public(fac),
                    "available": False,
                    "error": str(e),
                })
        avail = [x for x in sources if x.get("available")]
        if avail:
            cheap = min(avail, key=lambda x: (x["cost"], x["lead"]["min"]))
            fast = min(avail, key=lambda x: (x["lead"]["min"], x["cost"]))
            for x in avail:
                x["is_cheapest"] = x is cheap
                x["is_fastest"] = x is fast
        rec = None
        if avail:
            rec = min(avail, key=lambda x: (x["cost"], x["lead"]["min"])).get("factory")
        return {"base": base, "sources": sources, "recommended": rec}

    # ============================================================== price table
    def price_table(
        self,
        product: Dict[str, Any],
        cfg: Dict[str, Any],
        agent: Optional[Dict[str, Any]],
        markup: Optional[float] = None,
        quantities: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        base = self.normalize_config(product, cfg)
        mode = base.get("mode")
        if quantities is None:
            if mode == "sample":
                quantities = list((product.get("sample") or {}).get("presets") or [1, 3, 5, 10])
            else:
                quantities = list((product.get("quantity") or {}).get("presets") or [])
        rows = []
        seen = set()
        for q in quantities[:6]:
            q = _i(q, 0)
            if q <= 0 or q in seen:
                continue
            seen.add(q)
            c = copy.deepcopy(base)
            c["qty"] = q
            try:
                r = self.quote(product, c, agent=agent, viewer="customer", markup=markup)
                rows.append({
                    "qty": q,
                    "unit_retail": r["totals"]["unit_retail"],
                    "retail": r["totals"]["retail"],
                    "unit_agent": r["totals"]["unit_agent"],
                    "agent": r["totals"]["agent"],
                    "lead": r["lead"],
                    "press": r["plan"].get("press_name", ""),
                })
            except EngineError:
                continue
        return {"rows": rows, "mode": mode}

    # ================================================================ defaults
    def price_from(self, product: Dict[str, Any], mode: Optional[str] = None, agent: Optional[Dict[str, Any]] = None, markup: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if (product.get("pricing_mode") or "nonstandard") == "standard":
            price = _n(product.get("standard_price"), 0)
            qty = _i((product.get("quantity") or {}).get("min"), 1)
            return {"unit": _r2(price), "total": _r2(price * qty), "qty": qty, "mode": "standard", "label": "¥"}
        try:
            cfg = self.default_config(product, mode)
            if markup is None:
                markup = _n(agent.get("default_markup"), self.setting("default_agent_markup", 0.28)) if agent else _n(self.setting("direct_markup"), 0.35)
            r = self.quote(product, cfg, agent=agent, viewer="customer", markup=markup)
            return {
                "unit": r["totals"]["unit_retail"],
                "total": r["totals"]["retail"],
                "qty": r["qty"],
                "mode": r["mode"],
                "label": "起",
            }
        except Exception:
            return None

    # ============================================================== preview API
    def technical_preview(
        self,
        draft: Dict[str, Any],
        dims: Optional[Dict[str, Any]] = None,
        material_id: Optional[str] = None,
        qty: Optional[int] = None,
    ) -> Dict[str, Any]:
        """后台建品时的技术预览：展开尺寸 + 拼版方案 + 试算，容错返回。"""
        out: Dict[str, Any] = {"ok": False, "errors": []}
        structure = draft.get("structure")
        if draft.get("kind") == "overprint":
            out["ok"] = True
            out["stock"] = draft.get("stock") or {}
            return out
        try:
            d = dims or {}
            if not d:
                presets = draft.get("size_presets") or []
                if presets:
                    d = dict(presets[0].get("dims") or {})
                else:
                    for f in draft.get("dim_fields") or []:
                        d[f.get("key")] = _n(f.get("default"), 0)
            errs = formulas.validate_dims(structure, d, draft.get("dim_fields"))
            if errs:
                out["errors"] = errs
            unfold = formulas.unfold(structure, d, draft.get("formula_params"), _n(draft.get("bleed"), 3),
                                     {f["key"]: f["label"] for f in draft.get("dim_fields") or [] if f.get("key")})
            out["unfold"] = unfold

            mats = draft.get("materials") or []
            mid = material_id or draft.get("default_material") or (mats[0] if mats else "")
            material = self.materials.get(mid)
            if not material:
                raise EngineError("请先选择至少一种材料")
            production = draft.get("production") or {}
            loss = _n(production.get("loss_rate"), self.setting("loss_rate", 0.05))
            plans = []
            for press_id in production.get("press_ids") or []:
                press = self.presses.get(press_id)
                if not press or material.get("kind") not in (press.get("material_kinds") or []):
                    continue
                if press.get("type") == "label":
                    for sid in press.get("sheet_ids") or []:
                        if sid not in (material.get("sheet_ids") or []):
                            continue
                        roll = self.sheets.get(sid)
                        if not roll:
                            continue
                        plan = imposition.label_plan(unfold, roll, press, 100, loss)
                        if plan["units_per_sheet"] > 0:
                            plans.append(plan)
                    continue
                for sid in press.get("sheet_ids") or []:
                    if sid not in (material.get("sheet_ids") or []):
                        continue
                    sheet = self.sheets.get(sid)
                    if not sheet or not self._sheet_fits(sheet, press):
                        continue
                    plan = imposition.make_plan(unfold, sheet, press, 100, loss)
                    if plan["units_per_sheet"] > 0:
                        plans.append(plan)
            out["plans"] = plans
            out["material"] = {"id": material["id"], "name": material["name"], "gsm": material.get("gsm")}
            out["ok"] = bool(plans)

            # 试算
            try:
                cfg = self.default_config(draft)
                if qty:
                    cfg["qty"] = qty
                if material_id:
                    cfg["material_id"] = material_id
                if dims:
                    cfg["dims"] = dims
                comp = self.compare_sources(draft, cfg, agent=None, markup=_n(self.setting("direct_markup"), 0))
                q = comp["base"]
                out["quote"] = {
                    "total": q["totals"]["retail"],
                    "unit": q["totals"]["unit_retail"],
                    "cost": q["totals"]["cost"],
                    "agent": q["totals"]["agent"],
                    "lead": q["lead"],
                    "press": q["plan"].get("press_name"),
                    "sheet": q["plan"].get("sheet_name"),
                    "units_per_sheet": q["plan"].get("units_per_sheet"),
                    "mode": q["mode"],
                    "qty": q["qty"],
                    "logistics": q.get("logistics"),
                }
                out["sources"] = comp["sources"]
                out["recommended_factory"] = comp.get("recommended")
                rec = comp.get("recommended") or {}
                rec_src = next((x for x in comp.get("sources", []) if x.get("available") and (x.get("factory") or {}).get("id") == rec.get("id")), None)
                if rec_src:
                    out["quote"] = {
                        "total": rec_src.get("price"),
                        "unit": rec_src.get("unit"),
                        "cost": rec_src.get("cost"),
                        "agent": rec_src.get("agent"),
                        "lead": rec_src.get("lead"),
                        "press": (rec_src.get("plan") or {}).get("press_name"),
                        "sheet": (rec_src.get("plan") or {}).get("sheet_name"),
                        "units_per_sheet": (rec_src.get("plan") or {}).get("units_per_sheet"),
                        "mode": rec_src.get("mode"),
                        "qty": rec_src.get("qty"),
                        "factory": rec,
                        "logistics": rec_src.get("logistics"),
                    }
            except EngineError as e:
                out["quote_error"] = str(e)
            except Exception as e:
                out["quote_error"] = str(e)
            out["ok"] = bool(plans)
            return out
        except EngineError as e:
            out["errors"] = [str(e)]
            return out
        except Exception as e:
            out["errors"] = ["预览失败：%s" % e]
            return out
