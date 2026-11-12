# -*- coding: utf-8 -*-
"""拼版计算：把含出血的展开件排到指定上机印张上。

考虑咬口、四周咬口边、两种摆放方向；返回一张印张能排几个成品、
用纸张数、成材率。多片结构（如天地盖 = 盖 + 底）按套折算。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List


def _floor(v: float) -> int:
    return int(math.floor(v + 1e-9))


def best_layout(
    piece_w: float,
    piece_h: float,
    sheet_w: float,
    sheet_h: float,
    edge: float = 8,
    grip: float = 10,
    allow_rotate: bool = True,
) -> Dict[str, Any]:
    """返回最佳摆放。piece_w/h 已含出血，单位 mm。"""
    usable_w = max(0.0, sheet_w - 2 * edge)
    usable_h = max(0.0, sheet_h - edge - grip)
    if piece_w <= 0 or piece_h <= 0 or usable_w <= 0 or usable_h <= 0:
        return {"count": 0, "cols": 0, "rows": 0, "rotated": False, "utilization": 0.0}

    candidates = []
    rotations = [(piece_w, piece_h, False)]
    if allow_rotate and abs(piece_w - piece_h) > 1e-9:
        rotations.append((piece_h, piece_w, True))
    for w, h, rotated in rotations:
        cols = _floor(usable_w / w)
        rows = _floor(usable_h / h)
        count = max(0, cols * rows)
        util = (count * piece_w * piece_h) / (sheet_w * sheet_h) if count else 0.0
        candidates.append(
            {
                "count": count,
                "cols": cols,
                "rows": rows,
                "rotated": rotated,
                "piece_w": round(w, 2),
                "piece_h": round(h, 2),
                "utilization": round(util, 4),
            }
        )
    candidates.sort(key=lambda c: (c["count"], c["utilization"]), reverse=True)
    return candidates[0]


def roll_layout(
    piece_w: float,
    piece_h: float,
    roll_w: float,
    edge: float = 3,
) -> Dict[str, Any]:
    """卷筒材料：计算沿卷宽一排能排几个，竖向可无限延伸。"""
    usable = max(0.0, roll_w - 2 * edge)
    candidates = []
    for w, h, rotated in ((piece_w, piece_h, False), (piece_h, piece_w, True)):
        cols = _floor(usable / w)
        if cols <= 0:
            continue
        candidates.append(
            {
                "count_across": cols,
                "piece_w": round(w, 2),
                "piece_h": round(h, 2),
                "rotated": rotated,
                "utilization": round((cols * w) / roll_w, 4),
            }
        )
    if not candidates:
        return {"count_across": 0, "piece_w": piece_w, "piece_h": piece_h, "rotated": False, "utilization": 0}
    candidates.sort(key=lambda c: (c["count_across"], c["utilization"]), reverse=True)
    return candidates[0]


def sheets_needed(qty: int, units_per_sheet: int, loss_rate: float = 0.05) -> int:
    if qty <= 0 or units_per_sheet <= 0:
        return 0
    if qty <= units_per_sheet:
        return 1
    return max(1, int(math.ceil((qty / float(units_per_sheet)) * (1 + max(0.0, loss_rate)) - 1e-9)))


def make_plan(
    unfold: Dict[str, Any],
    sheet: Dict[str, Any],
    press: Dict[str, Any],
    qty: int,
    loss_rate: float,
) -> Dict[str, Any]:
    """生成一个「机型 + 印张」拼版方案。"""
    layout = best_layout(
        unfold["piece_w"],
        unfold["piece_h"],
        sheet["w"],
        sheet["h"],
        edge=float(sheet.get("edge", 8)),
        grip=float(sheet.get("grip", 10)),
        allow_rotate=bool(sheet.get("allow_rotate", True)),
    )
    ppu = max(1, int(unfold.get("pieces_per_unit", 1)))
    units_per_sheet = layout["count"] // ppu
    sheets = sheets_needed(qty, units_per_sheet, loss_rate)
    sheet_area = float(sheet["w"]) * float(sheet["h"]) / 1_000_000.0
    unit_area = float(unfold.get("unit_area_m2") or 0)
    used_area = units_per_sheet * unit_area
    design_util = used_area / sheet_area if sheet_area else 0
    return {
        "press_id": press["id"],
        "press_name": press["name"],
        "press_type": press.get("type", "offset"),
        "sheet_id": sheet["id"],
        "sheet_name": sheet["name"],
        "sheet_w": sheet["w"],
        "sheet_h": sheet["h"],
        "sheet_area_m2": round(sheet_area, 4),
        "piece_w": unfold["piece_w"],
        "piece_h": unfold["piece_h"],
        "cols": layout["cols"],
        "rows": layout["rows"],
        "blanks_per_sheet": layout["count"],
        "pieces_per_unit": ppu,
        "units_per_sheet": units_per_sheet,
        "rotated": layout["rotated"],
        "sheets": sheets,
        "utilization": round(design_util, 4),
        "material_area_m2": round(sheets * sheet_area, 2),
        "lead_days": int(press.get("days", 2)),
        "waste_sheets": max(0, sheets - int(math.ceil(qty / float(max(1, units_per_sheet))))),
    }


def label_plan(
    unfold: Dict[str, Any],
    roll: Dict[str, Any],
    press: Dict[str, Any],
    qty: int,
    loss_rate: float,
) -> Dict[str, Any]:
    """卷筒标签方案：按卷宽排列，材料按面积计。"""
    layout = roll_layout(
        unfold["piece_w"],
        unfold["piece_h"],
        roll["w"],
        edge=float(roll.get("edge", 3)),
    )
    across = max(1, layout["count_across"])
    piece_area = unfold["piece_w"] * unfold["piece_h"] / 1_000_000.0
    material_area = qty * piece_area * (1 + max(0.0, loss_rate))
    length_m = (qty / float(across)) * unfold["piece_h"] / 1000.0 * (1 + max(0.0, loss_rate))
    return {
        "press_id": press["id"],
        "press_name": press["name"],
        "press_type": "label",
        "sheet_id": roll["id"],
        "sheet_name": roll["name"],
        "sheet_w": roll["w"],
        "sheet_h": roll["h"],
        "sheet_area_m2": round(roll["w"] * roll["h"] / 1_000_000.0, 4),
        "piece_w": unfold["piece_w"],
        "piece_h": unfold["piece_h"],
        "cols": across,
        "rows": 0,
        "blanks_per_sheet": across,
        "pieces_per_unit": 1,
        "units_per_sheet": across,
        "rotated": layout["rotated"],
        "sheets": 0,
        "material_area_m2": round(material_area, 2),
        "roll_length_m": round(length_m, 2),
        "utilization": layout["utilization"],
        "lead_days": int(press.get("days", 2)),
        "label_roll": True,
    }
