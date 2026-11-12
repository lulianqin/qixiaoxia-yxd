# -*- coding: utf-8 -*-
"""成品尺寸 → 展开尺寸公式库。

每个结构（袋 / 盒 / 箱 / 标签）都是「输入成品尺寸 + 工艺余量参数 → 输出展开尺寸」。
后台选择结构并填写余量，前端输入长宽高即可实时换算；出血在展开尺寸之后统一增加。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _num(v: Any, d: float = 0) -> float:
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else d
    except (TypeError, ValueError):
        return d


def _fmt(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ("%.1f" % v).rstrip("0").rstrip(".")


def _step(label: str, expr: str, value: float, unit: str = "mm") -> Dict[str, Any]:
    return {"label": label, "expr": expr, "value": round(value, 2), "unit": unit}


# ---------------------------------------------------------------------------
# 结构定义
# 输入统一用 L / W / H 三个键，展示名可按产品覆盖。
# calc 返回展开宽高、每套成品需要的坯片数、计算步骤。
# ---------------------------------------------------------------------------

def _bag(d, p):
    glue = _num(p.get("glue"), 18)
    bottom = _num(p.get("bottom"), 35)
    top = _num(p.get("top_fold"), 30)
    fw = 2 * d["L"] + 2 * d["W"] + glue
    fh = d["H"] + bottom + top
    return {
        "flat_w": fw,
        "flat_h": fh,
        "pieces_per_unit": 1,
        "steps": [
            _step("展开宽", "2×%s + 2×%s + %s" % (_fmt(d["L"]), _fmt(d["W"]), _fmt(glue)), fw),
            _step("展开高", "%s + %s + %s" % (_fmt(d["H"]), _fmt(bottom), _fmt(top)), fh),
        ],
        "note": "含粘口、袋底与袋口折边；提绳/穿绳另计。",
    }


def _cardbox(d, p):
    glue = _num(p.get("glue"), 18)
    flap = _num(p.get("flap"), 15)
    fw = 2 * d["L"] + 2 * d["W"] + glue
    fh = d["H"] + 2 * flap
    return {
        "flat_w": fw,
        "flat_h": fh,
        "pieces_per_unit": 1,
        "steps": [
            _step("展开宽", "2×%s + 2×%s + %s" % (_fmt(d["L"]), _fmt(d["W"]), _fmt(glue)), fw),
            _step("展开高", "%s + 2×%s" % (_fmt(d["H"]), _fmt(flap)), fh),
        ],
        "note": "插舌卡盒，含上下插舌与粘口；开窗、内衬另计。",
    }


def _tray(d, p):
    margin = _num(p.get("margin"), 8)
    fw = d["L"] + 2 * d["H"] + 2 * margin
    fh = d["W"] + 2 * d["H"] + 2 * margin
    return {
        "flat_w": fw,
        "flat_h": fh,
        "pieces_per_unit": 2,
        "steps": [
            _step("单片展开宽", "%s + 2×%s + 2×%s" % (_fmt(d["L"]), _fmt(d["H"]), _fmt(margin)), fw),
            _step("单片展开高", "%s + 2×%s + 2×%s" % (_fmt(d["W"]), _fmt(d["H"]), _fmt(margin)), fh),
        ],
        "note": "天地盖按「盖 + 底」2 片坯料计，已含折边余量；面纸/灰板组合另计。",
    }


def _mailer(d, p):
    glue = _num(p.get("glue"), 18)
    flap = _num(p.get("flap"), 15)
    fw = 2 * d["L"] + 2 * d["W"] + glue
    fh = d["H"] + d["W"] + 2 * flap
    return {
        "flat_w": fw,
        "flat_h": fh,
        "pieces_per_unit": 1,
        "steps": [
            _step("展开宽", "2×%s + 2×%s + %s" % (_fmt(d["L"]), _fmt(d["W"]), _fmt(glue)), fw),
            _step("展开高", "%s + %s + 2×%s" % (_fmt(d["H"]), _fmt(d["W"]), _fmt(flap)), fh),
        ],
        "note": "飞机盒（电商包装盒），含前后插舌与侧翼；刀模费另计。",
    }


def _sleeve(d, p):
    glue = _num(p.get("glue"), 18)
    fw = 2 * (d["W"] + d["H"]) + glue
    fh = d["L"]
    return {
        "flat_w": fw,
        "flat_h": fh,
        "pieces_per_unit": 1,
        "steps": [
            _step("展开宽", "2×(%s + %s) + %s" % (_fmt(d["W"]), _fmt(d["H"]), _fmt(glue)), fw),
            _step("展开高", "长 %s" % _fmt(d["L"]), fh),
        ],
        "note": "书型盒/封套结构，绕盒一周；磁吸、内衬另计。",
    }


def _carton(d, p):
    lap = _num(p.get("lap"), 40)
    trim = _num(p.get("trim"), 10)
    fw = 2 * (d["L"] + d["W"]) + lap
    fh = d["H"] + d["W"] + trim
    return {
        "flat_w": fw,
        "flat_h": fh,
        "pieces_per_unit": 1,
        "steps": [
            _step("展开宽", "2×(%s + %s) + %s" % (_fmt(d["L"]), _fmt(d["W"]), _fmt(lap)), fw),
            _step("展开高", "%s + %s + %s（上下摇盖）" % (_fmt(d["H"]), _fmt(d["W"]), _fmt(trim)), fh),
        ],
        "note": "0201 标准开槽纸箱，上下摇盖各按 1/2 宽计；打钉/粘箱另计。",
    }


def _flat(d, p):
    fw = d["L"]
    fh = d["W"]
    return {
        "flat_w": fw,
        "flat_h": fh,
        "pieces_per_unit": 1,
        "steps": [
            _step("成品宽", "%s" % _fmt(d["L"]), fw),
            _step("成品高", "%s" % _fmt(d["W"]), fh),
        ],
        "note": "单张平面产品，出血在展开尺寸外统一增加。",
    }


STRUCTURES: Dict[str, Dict[str, Any]] = {
    "bag": {
        "id": "bag",
        "name": "手提纸袋",
        "formula": "展开宽 = 2×袋宽 + 2×侧深 + 粘口；展开高 = 袋高 + 袋底 + 袋口折边",
        "inputs": [
            {"key": "L", "label": "袋宽", "default": 220, "min": 80, "max": 600},
            {"key": "W", "label": "侧深", "default": 90, "min": 30, "max": 300},
            {"key": "H", "label": "袋高", "default": 300, "min": 100, "max": 700},
        ],
        "params": [
            {"key": "glue", "label": "粘口", "default": 18, "min": 10, "max": 50, "unit": "mm"},
            {"key": "bottom", "label": "袋底", "default": 35, "min": 15, "max": 100, "unit": "mm"},
            {"key": "top_fold", "label": "袋口折边", "default": 30, "min": 15, "max": 80, "unit": "mm"},
        ],
        "calc": _bag,
        "image": "/assets/ui/structure-bag.svg",
    },
    "cardbox": {
        "id": "cardbox",
        "name": "插舌卡盒",
        "formula": "展开宽 = 2×长 + 2×宽 + 粘口；展开高 = 高 + 2×插舌",
        "inputs": [
            {"key": "L", "label": "长", "default": 160, "min": 40, "max": 600},
            {"key": "W", "label": "宽", "default": 100, "min": 30, "max": 500},
            {"key": "H", "label": "高", "default": 60, "min": 20, "max": 400},
        ],
        "params": [
            {"key": "glue", "label": "粘口", "default": 18, "min": 10, "max": 50, "unit": "mm"},
            {"key": "flap", "label": "上下插舌", "default": 15, "min": 8, "max": 40, "unit": "mm"},
        ],
        "calc": _cardbox,
        "image": "/assets/ui/structure-cardbox.svg",
    },
    "tray": {
        "id": "tray",
        "name": "天地盖礼盒",
        "formula": "单片展开 = (长 + 2×高 + 2×余量) × (宽 + 2×高 + 2×余量)，按盖+底 2 片计",
        "inputs": [
            {"key": "L", "label": "长", "default": 240, "min": 60, "max": 600},
            {"key": "W", "label": "宽", "default": 180, "min": 40, "max": 500},
            {"key": "H", "label": "高", "default": 70, "min": 20, "max": 300},
        ],
        "params": [
            {"key": "margin", "label": "折边余量", "default": 8, "min": 2, "max": 30, "unit": "mm"},
        ],
        "calc": _tray,
        "image": "/assets/ui/structure-tray.svg",
    },
    "mailer": {
        "id": "mailer",
        "name": "飞机盒",
        "formula": "展开宽 = 2×长 + 2×宽 + 粘口；展开高 = 高 + 宽 + 2×插舌",
        "inputs": [
            {"key": "L", "label": "长", "default": 260, "min": 60, "max": 600},
            {"key": "W", "label": "宽", "default": 180, "min": 40, "max": 500},
            {"key": "H", "label": "高", "default": 80, "min": 20, "max": 300},
        ],
        "params": [
            {"key": "glue", "label": "粘口", "default": 18, "min": 10, "max": 50, "unit": "mm"},
            {"key": "flap", "label": "插舌", "default": 15, "min": 8, "max": 40, "unit": "mm"},
        ],
        "calc": _mailer,
        "image": "/assets/ui/structure-mailer.svg",
    },
    "sleeve": {
        "id": "sleeve",
        "name": "书型盒 / 封套",
        "formula": "展开宽 = 2×(宽 + 高) + 粘口；展开高 = 长",
        "inputs": [
            {"key": "L", "label": "长", "default": 220, "min": 60, "max": 600},
            {"key": "W", "label": "宽", "default": 160, "min": 40, "max": 500},
            {"key": "H", "label": "高", "default": 45, "min": 15, "max": 200},
        ],
        "params": [
            {"key": "glue", "label": "粘口", "default": 18, "min": 10, "max": 50, "unit": "mm"},
        ],
        "calc": _sleeve,
        "image": "/assets/ui/structure-sleeve.svg",
    },
    "carton": {
        "id": "carton",
        "name": "瓦楞纸箱",
        "formula": "展开宽 = 2×(长 + 宽) + 搭接；展开高 = 高 + 宽 + 修边",
        "inputs": [
            {"key": "L", "label": "外长", "default": 400, "min": 100, "max": 1200},
            {"key": "W", "label": "外宽", "default": 300, "min": 80, "max": 900},
            {"key": "H", "label": "外高", "default": 200, "min": 60, "max": 900},
        ],
        "params": [
            {"key": "lap", "label": "搭接舌", "default": 40, "min": 20, "max": 80, "unit": "mm"},
            {"key": "trim", "label": "修边", "default": 10, "min": 0, "max": 30, "unit": "mm"},
        ],
        "calc": _carton,
        "image": "/assets/ui/structure-carton.svg",
    },
    "label": {
        "id": "label",
        "name": "不干胶标签",
        "formula": "展开尺寸 = 成品宽 × 成品高（四周另加出血）",
        "inputs": [
            {"key": "L", "label": "标签宽", "default": 80, "min": 10, "max": 400},
            {"key": "W", "label": "标签高", "default": 50, "min": 10, "max": 400},
            {"key": "H", "label": "单张数量", "default": 1, "min": 1, "max": 1, "hidden": True},
        ],
        "params": [],
        "calc": _flat,
        "image": "/assets/ui/structure-label.svg",
    },
    "sheet": {
        "id": "sheet",
        "name": "单页 / 卡片",
        "formula": "展开尺寸 = 成品宽 × 成品高（四周另加出血）",
        "inputs": [
            {"key": "L", "label": "成品宽", "default": 210, "min": 30, "max": 900},
            {"key": "W", "label": "成品高", "default": 285, "min": 30, "max": 1200},
            {"key": "H", "label": "厚度", "default": 1, "min": 1, "max": 1, "hidden": True},
        ],
        "params": [],
        "calc": _flat,
        "image": "/assets/ui/structure-sheet.svg",
    },
}


def list_structures(public: bool = True) -> List[Dict[str, Any]]:
    out = []
    for s in STRUCTURES.values():
        item = {
            "id": s["id"],
            "name": s["name"],
            "formula": s["formula"],
            "inputs": s["inputs"],
            "params": s["params"],
            "image": s["image"],
        }
        out.append(item)
    return out


def get_structure(structure_id: str) -> Dict[str, Any]:
    return STRUCTURES.get(structure_id or "", STRUCTURES["cardbox"])


def _normalize_params(structure: Dict[str, Any], params: Optional[Dict[str, Any]]) -> Dict[str, float]:
    out = {}
    supplied = params or {}
    for p in structure.get("params", []):
        out[p["key"]] = _num(supplied.get(p["key"]), float(p["default"]))
    return out


def unfold(
    structure_id: str,
    dims: Dict[str, Any],
    params: Optional[Dict[str, Any]] = None,
    bleed: float = 3,
    input_labels: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """计算展开尺寸。dims 使用 L/W/H，单位 mm。"""
    structure = get_structure(structure_id)
    clean = {}
    for inp in structure["inputs"]:
        key = inp["key"]
        clean[key] = _num(dims.get(key), float(inp["default"]))
    p = _normalize_params(structure, params)
    result = structure["calc"](clean, p)
    b = max(0.0, _num(bleed, 3))
    piece_w = round(result["flat_w"] + 2 * b, 2)
    piece_h = round(result["flat_h"] + 2 * b, 2)
    ppu = max(1, int(result.get("pieces_per_unit", 1)))
    unit_area = (result["flat_w"] * result["flat_h"] * ppu) / 1_000_000.0
    bleed_area = (piece_w * piece_h * ppu) / 1_000_000.0
    labels = {i["key"]: i["label"] for i in structure["inputs"]}
    if input_labels:
        labels.update({k: v for k, v in input_labels.items() if v})
    steps = []
    for st in result.get("steps", []):
        s = dict(st)
        s["label"] = s["label"]
        steps.append(s)
    return {
        "structure": structure["id"],
        "structure_name": structure["name"],
        "formula": structure["formula"],
        "dims": clean,
        "dims_labeled": [
            {"key": k, "label": labels.get(k, k), "value": clean[k]}
            for k in ("L", "W", "H")
            if k in clean and not _is_hidden(structure, k)
        ],
        "params": p,
        "steps": steps,
        "flat_w": round(result["flat_w"], 2),
        "flat_h": round(result["flat_h"], 2),
        "pieces_per_unit": ppu,
        "unit_area_m2": round(unit_area, 4),
        "bleed": b,
        "piece_w": piece_w,
        "piece_h": piece_h,
        "bleed_w": piece_w,
        "bleed_h": piece_h,
        "bleed_area_m2": round(bleed_area, 4),
        "note": result.get("note", ""),
    }


def _is_hidden(structure: Dict[str, Any], key: str) -> bool:
    for inp in structure.get("inputs", []):
        if inp["key"] == key:
            return bool(inp.get("hidden"))
    return False


def validate_dims(structure_id: str, dims: Dict[str, Any], fields: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """按结构默认范围或产品自定义范围校验尺寸。"""
    structure = get_structure(structure_id)
    ranges = {i["key"]: i for i in structure["inputs"]}
    if fields:
        for f in fields:
            if f.get("key") in ranges:
                merged = dict(ranges[f["key"]])
                for k in ("label", "min", "max", "default"):
                    if f.get(k) is not None:
                        merged[k] = f[k]
                ranges[f["key"]] = merged
    errs = []
    for key, meta in ranges.items():
        if meta.get("hidden"):
            continue
        v = _num(dims.get(key), -1)
        if v <= 0:
            errs.append("%s必须大于 0" % meta["label"])
            continue
        if v < _num(meta.get("min"), 0):
            errs.append("%s不能小于 %s mm" % (meta["label"], _fmt(_num(meta.get("min"), 0))))
        if v > _num(meta.get("max"), 99999):
            errs.append("%s不能大于 %s mm" % (meta["label"], _fmt(_num(meta.get("max"), 99999))))
    return errs
