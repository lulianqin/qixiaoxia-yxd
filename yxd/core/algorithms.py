# -*- coding: utf-8 -*-
"""计价算法模块库。

材料、工艺、设备、包装等资料都关联一个算法模块 + 参数。
新增资料时只需选择算法并填参数，不需要改代码；新增产品完全由后台配置。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _n(v: Any, d: float = 0.0) -> float:
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else d
    except (TypeError, ValueError):
        return d


def _r2(x: float) -> float:
    return round(x + 1e-9, 2)


def _p(params: Dict[str, Any], key: str, default: float = 0.0) -> float:
    return _n((params or {}).get(key), default)


def _ctx(ctx: Dict[str, Any], key: str, default: float = 0.0) -> float:
    return _n(ctx.get(key), default)


def _min_charge(value: float, params: Dict[str, Any]) -> float:
    return max(value, _p(params, "min_charge"))


# ---------------------------------------------------------------------------
# 每个算法：参数 schema + 计算函数
# ---------------------------------------------------------------------------

def _material_m2(p, c):
    return _p(p, "price_per_m2") * _ctx(c, "area_m2")


def _material_sheet(p, c):
    return _p(p, "price_per_sheet") * _ctx(c, "sheets")


def _material_piece(p, c):
    return _p(p, "price_per_piece") * _ctx(c, "qty")


def _aux_meter(p, c):
    return _p(p, "price_per_meter") * _ctx(c, "aux_per_unit", 1) * _ctx(c, "qty")


def _aux_piece(p, c):
    return _p(p, "price_per_piece") * _ctx(c, "aux_per_unit", 1) * _ctx(c, "qty")


def _press_offset(p, c):
    colors = max(1, int(_ctx(c, "colors", 1)))
    sheets = _ctx(c, "sheets")
    run = _p(p, "per_1000_per_color") * colors * sheets / 1000.0
    value = _p(p, "plate_cost") * colors + _p(p, "setup") + run
    return _min_charge(value, p)


def _press_digital(p, c):
    colors = max(1, int(_ctx(c, "colors", 1)))
    sheets = _ctx(c, "sheets")
    factor = 1 + _p(p, "color_factor", 0.08) * (colors - 1)
    value = _p(p, "setup") + _p(p, "per_sheet") * sheets * factor
    return _min_charge(value, p)


def _press_flexo(p, c):
    colors = max(1, int(_ctx(c, "colors", 1)))
    sheets = _ctx(c, "sheets")
    value = _p(p, "plate_cost") * colors + _p(p, "setup") + _p(p, "per_sheet") * sheets
    return _min_charge(value, p)


def _press_label(p, c):
    colors = max(1, int(_ctx(c, "colors", 1)))
    area = _ctx(c, "area_m2")
    value = _p(p, "plate_cost") * colors + _p(p, "setup") + _p(p, "per_m2_per_color") * area * colors
    return _min_charge(value, p)


def _press_screen(p, c):
    colors = max(1, int(_ctx(c, "colors", 1)))
    qty = _ctx(c, "qty")
    value = _p(p, "plate_cost") * colors + _p(p, "setup") + _p(p, "per_piece") * colors * qty
    return _min_charge(value, p)


def _process_piece(p, c):
    return _min_charge(_p(p, "setup") + _p(p, "price_per_piece") * _ctx(c, "qty"), p)


def _process_1000_pieces(p, c):
    return _min_charge(_p(p, "setup") + _p(p, "price_per_1000") * _ctx(c, "qty") / 1000.0, p)


def _process_sheet(p, c):
    return _min_charge(_p(p, "setup") + _p(p, "price_per_sheet") * _ctx(c, "sheets"), p)


def _process_1000_sheets(p, c):
    return _min_charge(_p(p, "setup") + _p(p, "price_per_1000_sheets") * _ctx(c, "sheets") / 1000.0, p)


def _process_m2(p, c):
    return _min_charge(_p(p, "setup") + _p(p, "price_per_m2") * _ctx(c, "area_m2"), p)


def _process_order(p, c):
    return _min_charge(_p(p, "setup") + _p(p, "price_per_order"), p)


def _process_piece_plate(p, c):
    colors = max(1, int(_ctx(c, "colors", 1)))
    value = _p(p, "plate_cost") * colors + _p(p, "setup") + _p(p, "price_per_piece") * colors * _ctx(c, "qty")
    return _min_charge(value, p)


def _packaging_order(p, c):
    return max(0.0, _p(p, "price_per_order") + _p(p, "price_per_piece") * _ctx(c, "qty"))


def _packaging_piece(p, c):
    return max(0.0, _p(p, "price_per_piece") * _ctx(c, "qty"))


def _fixed(p, c):
    return max(0.0, _p(p, "price"))


def _stock_piece(p, c):
    return _p(p, "price_per_piece") * _ctx(c, "qty")


def _overprint_piece(p, c):
    colors = max(1, int(_ctx(c, "colors", 1)))
    value = _p(p, "plate_cost") * colors + _p(p, "setup") + _p(p, "price_per_piece") * colors * _ctx(c, "qty")
    return _min_charge(value, p)


def _make_schema(items):
    out = []
    for it in items:
        base = {"key": it[0], "label": it[1], "type": "number", "unit": it[3] if len(it) > 3 else ""}
        base["default"] = it[2]
        if len(it) > 4:
            base.update(it[4])
        out.append(base)
    return out


PRICE = [
    ("price_per_piece", "每件单价", 0.0, "元/件"),
    ("price_per_1000", "每千件单价", 0.0, "元/千件"),
    ("price_per_1000_sheets", "每千张单价", 0.0, "元/千张"),
    ("price_per_sheet", "每张单价", 0.0, "元/张"),
    ("price_per_m2", "每平方米单价", 0.0, "元/m²"),
    ("price_per_order", "每单固定价", 0.0, "元/单"),
    ("price_per_meter", "每米单价", 0.0, "元/m"),
    ("price", "固定金额", 0.0, "元"),
]
FEE = [
    ("setup", "调机/起步费", 0.0, "元"),
    ("min_charge", "最低收费", 0.0, "元"),
    ("plate_cost", "每色版费", 0.0, "元/色"),
    ("per_1000_per_color", "每千张每色印工", 0.0, "元"),
    ("per_sheet", "每张印工", 0.0, "元/张"),
    ("per_m2_per_color", "每平米每色印工", 0.0, "元"),
    ("per_piece", "每件加工费", 0.0, "元/件"),
    ("color_factor", "每增加一色系数", 0.08, ""),
]

ALGORITHMS: Dict[str, Dict[str, Any]] = {}


def _reg(aid, name, category, unit, formula, params, fn, note=""):
    ALGORITHMS[aid] = {
        "id": aid,
        "name": name,
        "category": category,
        "unit": unit,
        "formula": formula,
        "params": params,
        "note": note,
        "calc": fn,
    }


_reg(
    "material_m2", "材料按面积计价", "材料", "元",
    "材料费 = 用纸面积（m²） × 每平米单价",
    _make_schema([PRICE[4], FEE[1]]), _material_m2,
    "适合纸张、纸板、不干胶等卷材/张材。用纸面积已含拼版损耗。",
)
_reg(
    "material_sheet", "材料按张计价", "材料", "元",
    "材料费 = 用纸张数 × 每张单价",
    _make_schema([PRICE[3], FEE[1]]), _material_sheet,
    "适合固定规格的特种纸、灰板等。",
)
_reg(
    "material_piece", "材料按件计价", "材料", "元",
    "材料费 = 数量 × 每件单价",
    _make_schema([PRICE[0], FEE[1]]), _material_piece,
    "适合成品胚、内衬、磁铁等按件采购的材料。",
)
_reg(
    "aux_meter", "辅料按米计价", "辅料", "元",
    "辅料费 = 数量 × 单件用量（m） × 每米单价",
    _make_schema([PRICE[6], FEE[1]]), _aux_meter,
    "适合提绳、丝带、松紧带等。",
)
_reg(
    "aux_piece", "辅料按件计价", "辅料", "元",
    "辅料费 = 数量 × 单件用量（件） × 每件单价",
    _make_schema([PRICE[0], FEE[1]]), _aux_piece,
    "适合磁铁、扣件、内衬等。",
)
_reg(
    "press_offset", "胶印机计价", "印刷", "元",
    "印工 = 版费×色数 + 调机费 + 千张每色印工×色数×印张/1000（不低于最低收费）",
    _make_schema([FEE[2], FEE[0], FEE[3], FEE[1]]), _press_offset,
)
_reg(
    "press_digital", "数码印刷计价", "印刷", "元",
    "印工 = 调机费 + 每张印工×印张×（1 + 加色系数×（色数-1））（不低于最低收费）",
    _make_schema([FEE[0], FEE[4], FEE[7], FEE[1]]), _press_digital,
    "无版费，适合小批量；印张越多单价优势越弱。",
)
_reg(
    "press_flexo", "瓦楞水墨印刷计价", "印刷", "元",
    "印工 = 版费×色数 + 调机费 + 每张印工×印张（不低于最低收费）",
    _make_schema([FEE[2], FEE[0], FEE[4], FEE[1]]), _press_flexo,
)
_reg(
    "press_label", "标签轮转计价", "印刷", "元",
    "印工 = 版费×色数 + 调机费 + 每平米每色印工×面积×色数（不低于最低收费）",
    _make_schema([FEE[2], FEE[0], FEE[5], FEE[1]]), _press_label,
)
_reg(
    "press_screen", "丝网印刷计价", "印刷", "元",
    "印工 = 版费×色数 + 调机费 + 每件印工×色数×数量（不低于最低收费）",
    _make_schema([FEE[2], FEE[0], FEE[6], FEE[1]]), _press_screen,
    "适合成品加印 LOGO、局部厚墨。",
)
_reg(
    "process_piece", "按件加工", "工艺", "元",
    "工艺费 = 调机费 + 每件单价×数量（不低于最低收费）",
    _make_schema([FEE[0], PRICE[0], FEE[1]]), _process_piece,
)
_reg(
    "process_1000_pieces", "按千件加工", "工艺", "元",
    "工艺费 = 调机费 + 每千件单价×数量/1000（不低于最低收费）",
    _make_schema([FEE[0], PRICE[1], FEE[1]]), _process_1000_pieces,
)
_reg(
    "process_sheet", "按张加工", "工艺", "元",
    "工艺费 = 调机费 + 每张单价×印张（不低于最低收费）",
    _make_schema([FEE[0], PRICE[3], FEE[1]]), _process_sheet,
)
_reg(
    "process_1000_sheets", "按千张加工", "工艺", "元",
    "工艺费 = 调机费 + 每千张单价×印张/1000（不低于最低收费）",
    _make_schema([FEE[0], PRICE[2], FEE[1]]), _process_1000_sheets,
)
_reg(
    "process_m2", "按面积加工", "工艺", "元",
    "工艺费 = 调机费 + 每平米单价×面积（不低于最低收费）",
    _make_schema([FEE[0], PRICE[4], FEE[1]]), _process_m2,
)
_reg(
    "process_order", "按单计价", "工艺", "元",
    "工艺费 = 固定费用（不低于最低收费）",
    _make_schema([PRICE[5], FEE[1]]), _process_order,
)
_reg(
    "process_piece_plate", "按件 + 版费", "工艺", "元",
    "工艺费 = 版费×色数 + 调机费 + 每件单价×色数×数量（不低于最低收费）",
    _make_schema([FEE[2], FEE[0], FEE[6], FEE[1]]), _process_piece_plate,
    "适合烫金、凹凸等需要制版的按件工艺。",
)
_reg(
    "packaging_order", "包装按单 + 按件", "包装", "元",
    "包装费 = 每单固定费 + 每件包装费×数量",
    _make_schema([PRICE[5], PRICE[0]]), _packaging_order,
)
_reg(
    "packaging_piece", "包装按件计价", "包装", "元",
    "包装费 = 每件包装费×数量",
    _make_schema([PRICE[0]]), _packaging_piece,
)
_reg(
    "sample_fixed", "打样固定费", "打样", "元",
    "打样费 = 固定金额",
    _make_schema([PRICE[7]]), _fixed,
)
_reg(
    "stock_piece", "成品胚按件", "成品加印", "元",
    "成品胚费 = 数量 × 每件胚价",
    _make_schema([PRICE[0], FEE[1]]), _stock_piece,
)
_reg(
    "overprint_piece", "成品加印按件 + 版费", "成品加印", "元",
    "加印费 = 版费×色数 + 调机费 + 每件加印费×色数×数量（不低于最低收费）",
    _make_schema([FEE[2], FEE[0], FEE[6], FEE[1]]), _overprint_piece,
)


def list_algorithms() -> List[Dict[str, Any]]:
    out = []
    for a in ALGORITHMS.values():
        out.append(
            {
                "id": a["id"],
                "name": a["name"],
                "category": a["category"],
                "unit": a["unit"],
                "formula": a["formula"],
                "params": a["params"],
                "note": a.get("note", ""),
            }
        )
    return out


def get_algorithm(aid: str) -> Optional[Dict[str, Any]]:
    return ALGORITHMS.get(aid or "")


def calc(aid: str, params: Optional[Dict[str, Any]], ctx: Dict[str, Any]) -> float:
    algo = ALGORITHMS.get(aid or "")
    if not algo:
        return 0.0
    p = {}
    for spec in algo["params"]:
        p[spec["key"]] = _n((params or {}).get(spec["key"]), float(spec.get("default", 0)))
    try:
        return _r2(algo["calc"](p, ctx))
    except Exception:
        return 0.0


def normalize_params(aid: str, params: Optional[Dict[str, Any]]) -> Dict[str, float]:
    algo = ALGORITHMS.get(aid or "")
    if not algo:
        return {}
    out = {}
    for spec in algo["params"]:
        out[spec["key"]] = _n((params or {}).get(spec["key"]), float(spec.get("default", 0)))
    return out
