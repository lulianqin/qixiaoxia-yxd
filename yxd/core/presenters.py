# -*- coding: utf-8 -*-
"""对外数据裁剪：手机商城不暴露成本、毛利和算法参数。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import formulas
from .engine import QuoteEngine


def _material_public(m: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not m:
        return None
    return {
        "id": m.get("id"),
        "name": m.get("name"),
        "kind": m.get("kind"),
        "gsm": m.get("gsm"),
        "unit": m.get("unit"),
        "image": m.get("image"),
        "color": m.get("color"),
        "note": m.get("note", ""),
    }


def _process_public(p: Optional[Dict[str, Any]], required: bool = False) -> Optional[Dict[str, Any]]:
    if not p:
        return None
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "category": p.get("category"),
        "description": p.get("description", ""),
        "image": p.get("image", ""),
        "constraints": p.get("constraints") or {},
        "required": required,
    }


def _packaging_public(p: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not p:
        return None
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "description": p.get("description", ""),
        "image": p.get("image", ""),
        "carton_qty": p.get("carton_qty"),
    }


def public_product(
    engine: QuoteEngine,
    product: Dict[str, Any],
    agent: Optional[Dict[str, Any]] = None,
    markup: Optional[float] = None,
    detail: bool = False,
) -> Dict[str, Any]:
    modes = product.get("modes") or ["custom"]
    pconf = product.get("processes") or {}
    materials = []
    for mid in product.get("materials") or []:
        m = engine.materials.get(mid)
        if m and m.get("enabled", 1):
            materials.append(_material_public(m))

    aux_groups = []
    for g in product.get("aux_groups") or []:
        opts = []
        for o in g.get("options") or []:
            m = engine.materials.get(o.get("material_id")) if o.get("material_id") else None
            opts.append({
                "material_id": o.get("material_id"),
                "label": o.get("label") or (m or {}).get("name", "不需要"),
                "default": bool(o.get("default")),
                "material": _material_public(m),
            })
        aux_groups.append({
            "id": g.get("id"),
            "name": g.get("name"),
            "per_unit": g.get("per_unit", 1),
            "unit": g.get("unit", ""),
            "optional": bool(g.get("optional")),
            "options": opts,
        })

    required = []
    for pid in pconf.get("required") or []:
        item = _process_public(engine.processes.get(pid), True)
        if item:
            required.append(item)
    optional = []
    for pid in pconf.get("optional") or []:
        item = _process_public(engine.processes.get(pid), False)
        if item:
            optional.append(item)
    groups = []
    for g in pconf.get("groups") or []:
        opts = []
        for pid in g.get("options") or []:
            item = _process_public(engine.processes.get(pid))
            if item:
                opts.append(item)
        groups.append({"id": g.get("id"), "name": g.get("name"), "required": bool(g.get("required")), "options": opts})

    packagings = []
    for pid in product.get("packagings") or []:
        p = _packaging_public(engine.packagings.get(pid))
        if p:
            packagings.append(p)

    stock = product.get("stock") or {}
    stock_public = None
    if stock:
        stock_public = {
            "name": stock.get("name"),
            "dims": stock.get("dims"),
            "stock_qty": stock.get("stock_qty"),
            "lead_days": stock.get("lead_days"),
            "image": stock.get("image") or product.get("image"),
            "weight_kg": stock.get("weight_kg"),
        }

    overprint_methods = []
    for m in product.get("overprint_methods") or []:
        overprint_methods.append({
            "id": m.get("id"),
            "name": m.get("name"),
            "max_colors": m.get("max_colors"),
            "description": m.get("description", ""),
        })

    structure = formulas.get_structure(product.get("structure", "")) if product.get("structure") else None
    structure_public = None
    if structure and product.get("kind") != "overprint":
        structure_public = {
            "id": structure["id"],
            "name": structure["name"],
            "formula": structure["formula"],
            "image": structure.get("image"),
            "params": structure.get("params") or [],
        }

    mode = "custom" if "custom" in modes else modes[0]
    is_standard = (product.get("pricing_mode") or "nonstandard") == "standard"
    price = engine.price_from(product, mode, agent=agent, markup=markup) if is_standard else engine.price_from(product, mode, agent=agent, markup=markup)

    return {
        "id": product.get("id"),
        "kind": product.get("kind", "custom"),
        "pricing_mode": product.get("pricing_mode", "nonstandard"),
        "standard_price": product.get("standard_price"),
        "unit": product.get("unit", "个"),
        "sku": product.get("sku", ""),
        "category": product.get("category", ""),
        "category_name": next((c.get("name") for c in engine.db.categories() if c.get("id") == product.get("category")), ""),
        "name": product.get("name"),
        "subtitle": product.get("subtitle", ""),
        "badge": product.get("badge", ""),
        "description": product.get("description", ""),
        "long_desc": product.get("long_desc", ""),
        "image": product.get("image") or (product.get("images") or [""])[0],
        "images": product.get("images") or [],
        "modes": modes,
        "mode_options": [
            {"id": "custom", "label": "全定制", "desc": "按尺寸/材料/工艺生产"},
            {"id": "overprint", "label": "成品加印", "desc": "现货胚袋，只加印 LOGO"},
        ],
        "structure": product.get("structure", ""),
        "structure_info": structure_public,
        "dim_fields": product.get("dim_fields") or [],
        "formula_params": product.get("formula_params") or {},
        "bleed": product.get("bleed", 3),
        "size_presets": product.get("size_presets") or [],
        "materials": materials,
        "default_material": product.get("default_material"),
        "aux_groups": aux_groups,
        "colors": product.get("colors") or [0],
        "default_colors": product.get("default_colors", 1),
        "processes": {"required": required, "optional": optional, "groups": groups},
        "packagings": packagings,
        "default_packaging": product.get("default_packaging"),
        "quantity": product.get("quantity") or {},
        "sample": None,
        "stock": stock_public,
        "overprint_methods": overprint_methods,
        "lead_days": product.get("lead_days", 5),
        "highlights": product.get("highlights") or [],
        "specs": product.get("specs") or [],
        "faq": product.get("faq") or [],
        "audience": product.get("audience") or [],
        "price_from": price,
        "sample_price_from": None,
        "status": product.get("status", "active"),
        "sort": product.get("sort", 0),
        "logistics": {
            "mode": "home",
            "provider": ((product.get("logistics") or {}).get("provider") or "统一配送"),
            "warehouse": ((product.get("logistics") or {}).get("warehouse") or "杭州中心仓"),
            "lead_days": ((product.get("logistics") or {}).get("lead_days") or 1),
            "note": ((product.get("logistics") or {}).get("note") or "全国送货上门"),
            "included": bool((product.get("logistics") or {}).get("included", True)),
            "free_over": ((product.get("logistics") or {}).get("free_over") or 0),
        },
    }


def admin_product(engine: QuoteEngine, product: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(product)
    data.setdefault("pricing_mode", "nonstandard")
    if data["pricing_mode"] == "standard":
        data["price_from"] = engine.price_from(product)
        data["sample_price_from"] = None
    else:
        data["price_from"] = engine.price_from(product)
        data["sample_price_from"] = None
    return data


def public_materials(engine: QuoteEngine) -> List[Dict[str, Any]]:
    return [_material_public(m) for m in engine.materials.values() if m.get("enabled", 1) and m.get("kind") != "aux"]


def public_aux(engine: QuoteEngine) -> List[Dict[str, Any]]:
    return [_material_public(m) for m in engine.materials.values() if m.get("enabled", 1) and m.get("kind") == "aux"]


def public_processes(engine: QuoteEngine) -> List[Dict[str, Any]]:
    return [_process_public(p) for p in engine.processes.values() if p.get("enabled", 1)]


def public_packagings(engine: QuoteEngine) -> List[Dict[str, Any]]:
    return [_packaging_public(p) for p in engine.packagings.values() if p.get("enabled", 1)]
