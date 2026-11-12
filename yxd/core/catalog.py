# -*- coding: utf-8 -*-
"""基础资料与种子商品。

真实项目里这些数据由后台维护；这里提供一套可直接演示、数值合理的初始数据。
所有价格单位为人民币元；尺寸 mm；重量 g。
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# 全局参数
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS: Dict[str, Any] = {
    "site_name": "印小单",
    "site_slogan": "小批量印刷，在线报价",
    "service_phone": "400-860-9588",
    "warehouse": "杭州中心仓",
    "platform_margin": 0.18,
    "direct_markup": 0.0,
    "default_agent_markup": 0.0,
    "tax_rate": 0.06,
    "overhead_rate": 0.06,
    "loss_rate": 0.05,
    "shipping_base": 10.0,
    "shipping_per_kg": 1.8,
    "free_shipping_over": 3000.0,
    "min_order_total": 300.0,
    "quote_valid_days": 15,
    "delivery_note": "全国统一从杭州中心仓发货，送货上门，含税含运费（满 3000 元免运费）。",
    "quote_note": "本报价含 6% 增值税及标准送货上门费用；报价有效期 15 天，逾期以重新核价为准。",
    "payment_note": "确认订单后支付 50% 定金安排生产，余款发货前结清。",
    # P4：不再内置静态弱密钥。新部署请在 yxd/config.json 里配置 internal_secret
    # （与 ERP 的 pricing.engine.secret 一致）；存量库 settings.integration_key 需按 P4 清理清单
    # 由人工改成强随机值（AI 不执行数据库写操作）。
    "integration_key": "",
}

CATEGORIES: List[Dict[str, Any]] = [
    {"id": "bag", "name": "手提纸袋", "code": "BAG", "parent_id": "", "desc": "牛皮纸 / 白卡 / 铜版，100 个起", "image": "/assets/ui/cat-bag.svg", "sort": 1, "enabled": 1, "pricing_default": "nonstandard"},
    {"id": "box", "name": "纸盒包装", "code": "BOX", "parent_id": "", "desc": "卡盒 / 天地盖 / 飞机盒", "image": "/assets/ui/cat-box.svg", "sort": 2, "enabled": 1, "pricing_default": "nonstandard"},
    {"id": "label", "name": "不干胶标签", "code": "LABEL", "parent_id": "", "desc": "铜版 / 透明 PVC / 牛皮纸", "image": "/assets/ui/cat-label.svg", "sort": 3, "enabled": 1, "pricing_default": "nonstandard"},
    {"id": "carton", "name": "瓦楞纸箱", "code": "CARTON", "parent_id": "", "desc": "三层 / 五层，电商与物流包装", "image": "/assets/ui/cat-carton.svg", "sort": 4, "enabled": 1, "pricing_default": "nonstandard"},
]

# ---------------------------------------------------------------------------
# 上机印张
# ---------------------------------------------------------------------------

SHEETS: List[Dict[str, Any]] = [
    {"id": "sheet-big", "name": "大度 889×1194", "w": 889, "h": 1194, "edge": 8, "grip": 10, "sort": 1, "note": "对开胶印主力印张"},
    {"id": "sheet-std", "name": "正度 787×1092", "w": 787, "h": 1092, "edge": 8, "grip": 10, "sort": 2, "note": "常规书刊/包装"},
    {"id": "sheet-4k", "name": "四开 520×740", "w": 520, "h": 740, "edge": 6, "grip": 8, "sort": 3, "note": "四开机 / 大幅面数码"},
    {"id": "sheet-roll330", "name": "卷筒 330mm", "w": 330, "h": 1000, "edge": 3, "grip": 0, "sort": 4, "note": "标签轮转，宽 330mm"},
    {"id": "sheet-corr", "name": "瓦楞 1200×2400", "w": 1200, "h": 2400, "edge": 15, "grip": 0, "sort": 5, "note": "瓦楞纸板标准板"},
]

# ---------------------------------------------------------------------------
# 设备
# ---------------------------------------------------------------------------

PRESSES: List[Dict[str, Any]] = [
    {
        "id": "press-offset-big", "name": "全开四色胶印机", "type": "offset", "factory_id": "fac-offset",
        "max_w": 900, "max_h": 1200, "sheet_ids": ["sheet-big", "sheet-std"],
        "material_kinds": ["paper", "board"], "colors_max": 4, "days": 3,
        "algorithm_id": "press_offset",
        "params": {"plate_cost": 45, "setup": 180, "per_1000_per_color": 40, "min_charge": 450},
        "note": "大货首选，版费高但千张印工低，500 个以上更划算。", "enabled": 1, "sort": 1,
    },
    {
        "id": "press-offset-4k", "name": "四开四色胶印机", "type": "offset", "factory_id": "fac-offset",
        "max_w": 520, "max_h": 740, "sheet_ids": ["sheet-4k"],
        "material_kinds": ["paper", "board"], "colors_max": 4, "days": 2,
        "algorithm_id": "press_offset",
        "params": {"plate_cost": 35, "setup": 120, "per_1000_per_color": 35, "min_charge": 280},
        "note": "小批量胶印，调机快，300-2000 个区间灵活。", "enabled": 1, "sort": 2,
    },
    {
        "id": "press-digital", "name": "大幅面数码印刷机", "type": "digital", "factory_id": "fac-digital",
        "max_w": 520, "max_h": 740, "sheet_ids": ["sheet-4k"],
        "material_kinds": ["paper", "board"], "colors_max": 4, "days": 1,
        "algorithm_id": "press_digital",
        "params": {"setup": 25, "per_sheet": 2.2, "color_factor": 0.08, "min_charge": 60},
        "note": "无版费，适合 100 个以内小单。", "enabled": 1, "sort": 3,
    },
    {
        "id": "press-label", "name": "标签轮转印刷机", "type": "label", "factory_id": "fac-label",
        "max_w": 330, "max_h": 1000, "sheet_ids": ["sheet-roll330"],
        "material_kinds": ["label"], "colors_max": 4, "days": 2,
        "algorithm_id": "press_label",
        "params": {"plate_cost": 55, "setup": 60, "per_m2_per_color": 0.85, "min_charge": 180},
        "note": "卷筒不干胶专用，含模切排废。", "enabled": 1, "sort": 4,
    },
    {
        "id": "press-flexo", "name": "瓦楞水墨印刷机", "type": "flexo", "factory_id": "fac-flexo",
        "max_w": 2400, "max_h": 1200, "sheet_ids": ["sheet-corr"],
        "material_kinds": ["corrugated"], "colors_max": 2, "days": 2,
        "algorithm_id": "press_flexo",
        "params": {"plate_cost": 70, "setup": 80, "per_sheet": 0.9, "min_charge": 120},
        "note": "纸箱专用，水性油墨，1-2 色。", "enabled": 1, "sort": 5,
    },
    {
        "id": "press-screen", "name": "成品丝印机", "type": "screen", "factory_id": "fac-digital",
        "max_w": 600, "max_h": 900, "sheet_ids": [],
        "material_kinds": ["stock"], "colors_max": 2, "days": 1,
        "algorithm_id": "press_screen",
        "params": {"plate_cost": 40, "setup": 20, "per_piece": 0.06, "min_charge": 60},
        "note": "成品加印 LOGO，无需展开拼版。", "enabled": 1, "sort": 6,
    },
]

# ---------------------------------------------------------------------------
# 报价工厂 / 报价数据源
# 同一商品可以挂多个工厂；每家有独立的价格系数、固定服务费、交期偏移和设备。
# ---------------------------------------------------------------------------

FACTORIES: List[Dict[str, Any]] = [
    {
        "id": "fac-digital", "name": "数码印刷中心", "type": "digital",
        "price_factor": 1.0, "fixed_fee": 0, "lead_days": 0,
        "note": "无版费，适合小批量；单价按张计。",
        "enabled": 1, "sort": 1,
    },
    {
        "id": "fac-offset", "name": "传统胶印厂", "type": "offset",
        "price_factor": 0.94, "fixed_fee": 60, "lead_days": 1,
        "note": "版费/调机费高，千张印工低；数量越大越划算。",
        "enabled": 1, "sort": 2,
    },
    {
        "id": "fac-label", "name": "标签轮转厂", "type": "label",
        "price_factor": 0.90, "fixed_fee": 0, "lead_days": 0,
        "note": "卷筒不干胶专用，按面积/色数计价。",
        "enabled": 1, "sort": 3,
    },
    {
        "id": "fac-flexo", "name": "瓦楞水印厂", "type": "flexo",
        "price_factor": 0.95, "fixed_fee": 0, "lead_days": 0,
        "note": "瓦楞纸箱水墨印刷、开槽、打钉。",
        "enabled": 1, "sort": 4,
    },
]

# ---------------------------------------------------------------------------
# 材料 / 辅料
# ---------------------------------------------------------------------------

PAPER_SHEETS = ["sheet-big", "sheet-std", "sheet-4k"]

MATERIALS: List[Dict[str, Any]] = [
    {
        "id": "mat-kraft120", "name": "牛皮纸 120g", "kind": "paper", "gsm": 120,
        "unit": "g/m²", "sheet_ids": PAPER_SHEETS, "image": "/assets/materials/kraft.svg",
        "color": "#b98a58", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 1.20, "min_charge": 0},
        "note": "原色黄牛皮，质地坚韧，适合环保调性包装。", "enabled": 1, "sort": 1,
    },
    {
        "id": "mat-kraft150", "name": "牛皮纸 150g", "kind": "paper", "gsm": 150,
        "unit": "g/m²", "sheet_ids": PAPER_SHEETS, "image": "/assets/materials/kraft.svg",
        "color": "#b07f4b", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 1.55, "min_charge": 0},
        "note": "更挺括，承重更好，适合服饰、酒水袋。", "enabled": 1, "sort": 2,
    },
    {
        "id": "mat-art250", "name": "白卡纸 250g", "kind": "board", "gsm": 250,
        "unit": "g/m²", "sheet_ids": PAPER_SHEETS, "image": "/assets/materials/white-card.svg",
        "color": "#f4efe4", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 2.25, "min_charge": 0},
        "note": "白度高、挺度好，适合精品袋与卡盒。", "enabled": 1, "sort": 3,
    },
    {
        "id": "mat-art300", "name": "白卡纸 300g", "kind": "board", "gsm": 300,
        "unit": "g/m²", "sheet_ids": PAPER_SHEETS, "image": "/assets/materials/white-card.svg",
        "color": "#f7f2e7", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 2.65, "min_charge": 0},
        "note": "礼盒常用，挺括度与成本平衡。", "enabled": 1, "sort": 4,
    },
    {
        "id": "mat-art350", "name": "白卡纸 350g", "kind": "board", "gsm": 350,
        "unit": "g/m²", "sheet_ids": PAPER_SHEETS, "image": "/assets/materials/white-card.svg",
        "color": "#fbf7ee", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 3.05, "min_charge": 0},
        "note": "高档礼盒与手提袋，手感厚实。", "enabled": 1, "sort": 5,
    },
    {
        "id": "mat-coat200", "name": "铜版纸 200g", "kind": "paper", "gsm": 200,
        "unit": "g/m²", "sheet_ids": PAPER_SHEETS, "image": "/assets/materials/coated.svg",
        "color": "#e8e2d5", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 1.75, "min_charge": 0},
        "note": "表面细腻，色彩还原好，适合彩印。", "enabled": 1, "sort": 6,
    },
    {
        "id": "mat-coat250", "name": "铜版纸 250g", "kind": "paper", "gsm": 250,
        "unit": "g/m²", "sheet_ids": PAPER_SHEETS, "image": "/assets/materials/coated.svg",
        "color": "#efe9dc", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 2.05, "min_charge": 0},
        "note": "性价比高的彩印面材。", "enabled": 1, "sort": 7,
    },
    {
        "id": "mat-special", "name": "特种纸 250g", "kind": "board", "gsm": 250,
        "unit": "g/m²", "sheet_ids": PAPER_SHEETS, "image": "/assets/materials/special.svg",
        "color": "#d9cdb8", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 4.60, "min_charge": 0},
        "note": "纹理纸，适合高客单品牌包装。", "enabled": 1, "sort": 8,
    },
    {
        "id": "mat-greyboard", "name": "灰板纸 1.5mm", "kind": "board", "gsm": 1100,
        "unit": "g/m²", "sheet_ids": PAPER_SHEETS, "image": "/assets/materials/greyboard.svg",
        "color": "#9b9384", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 5.10, "min_charge": 0},
        "note": "精装盒骨架，需裱面纸；本系统按卡盒简化为单层。", "enabled": 1, "sort": 9,
    },
    {
        "id": "mat-corr3", "name": "三层瓦楞纸板", "kind": "corrugated", "gsm": 700,
        "unit": "g/m²", "sheet_ids": ["sheet-corr"], "image": "/assets/materials/corrugated.svg",
        "color": "#c9a06a", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 3.05, "min_charge": 0},
        "note": "B 楞三层，适合 5kg 以内电商包装。", "enabled": 1, "sort": 10,
    },
    {
        "id": "mat-corr5", "name": "五层瓦楞纸板", "kind": "corrugated", "gsm": 1100,
        "unit": "g/m²", "sheet_ids": ["sheet-corr"], "image": "/assets/materials/corrugated5.svg",
        "color": "#b98b52", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 4.35, "min_charge": 0},
        "note": "BC 楞五层，适合重物、长途运输。", "enabled": 1, "sort": 11,
    },
    {
        "id": "mat-label-coat", "name": "铜版不干胶", "kind": "label", "gsm": 80,
        "unit": "g/m²", "sheet_ids": ["sheet-roll330"], "image": "/assets/materials/label.svg",
        "color": "#efe9dc", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 4.20, "min_charge": 0},
        "note": "通用卷筒不干胶，色彩表现好。", "enabled": 1, "sort": 12,
    },
    {
        "id": "mat-label-pvc", "name": "透明 PVC 不干胶", "kind": "label", "gsm": 90,
        "unit": "g/m²", "sheet_ids": ["sheet-roll330"], "image": "/assets/materials/pvc.svg",
        "color": "#dfe8e6", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 7.50, "min_charge": 0},
        "note": "透明底，适合玻璃瓶、化妆品。", "enabled": 1, "sort": 13,
    },
    {
        "id": "mat-label-kraft", "name": "牛皮纸不干胶", "kind": "label", "gsm": 90,
        "unit": "g/m²", "sheet_ids": ["sheet-roll330"], "image": "/assets/materials/label-kraft.svg",
        "color": "#c39a68", "algorithm_id": "material_m2",
        "params": {"price_per_m2": 4.60, "min_charge": 0},
        "note": "自然纹理，适合手作、食品标签。", "enabled": 1, "sort": 14,
    },
    # 辅料
    {
        "id": "aux-rope-paper", "name": "纸绳", "kind": "aux", "gsm": 0,
        "unit": "m", "sheet_ids": [], "image": "/assets/materials/rope-paper.svg",
        "color": "#b98a58", "algorithm_id": "aux_meter",
        "params": {"price_per_meter": 0.06, "min_charge": 0},
        "note": "标配纸绳，轻量环保。", "enabled": 1, "sort": 20,
    },
    {
        "id": "aux-rope-cotton", "name": "棉绳", "kind": "aux", "gsm": 0,
        "unit": "m", "sheet_ids": [], "image": "/assets/materials/rope-cotton.svg",
        "color": "#e6d8bd", "algorithm_id": "aux_meter",
        "params": {"price_per_meter": 0.16, "min_charge": 0},
        "note": "柔软有质感，适合服装、礼品。", "enabled": 1, "sort": 21,
    },
    {
        "id": "aux-rope-nylon", "name": "尼龙绳", "kind": "aux", "gsm": 0,
        "unit": "m", "sheet_ids": [], "image": "/assets/materials/rope-nylon.svg",
        "color": "#d9c9a8", "algorithm_id": "aux_meter",
        "params": {"price_per_meter": 0.10, "min_charge": 0},
        "note": "强度高，适合较重产品。", "enabled": 1, "sort": 22,
    },
    {
        "id": "aux-ribbon", "name": "丝带", "kind": "aux", "gsm": 0,
        "unit": "m", "sheet_ids": [], "image": "/assets/materials/ribbon.svg",
        "color": "#c4552d", "algorithm_id": "aux_meter",
        "params": {"price_per_meter": 0.35, "min_charge": 0},
        "note": "缎面丝带，适合礼盒与高端袋。", "enabled": 1, "sort": 23,
    },
    {
        "id": "aux-magnet", "name": "磁铁扣", "kind": "aux", "gsm": 0,
        "unit": "个", "sheet_ids": [], "image": "/assets/materials/magnet.svg",
        "color": "#6b6b6b", "algorithm_id": "aux_piece",
        "params": {"price_per_piece": 0.22, "min_charge": 0},
        "note": "书型盒/天地盖磁吸闭合，每套 2 个。", "enabled": 1, "sort": 24,
    },
    {
        "id": "aux-eva", "name": "EVA 内衬", "kind": "aux", "gsm": 0,
        "unit": "个", "sheet_ids": [], "image": "/assets/materials/eva.svg",
        "color": "#4b4b45", "algorithm_id": "aux_piece",
        "params": {"price_per_piece": 0.80, "min_charge": 0},
        "note": "按盒型开槽，保护产品。", "enabled": 1, "sort": 25,
    },
]

# ---------------------------------------------------------------------------
# 工艺
# ---------------------------------------------------------------------------

def _m(mid, name, alg, params, days=1, min_qty=0, note=""):
    return {
        "id": mid,
        "name": name,
        "algorithm_id": alg,
        "params": params,
        "days": days,
        "min_qty": min_qty,
        "note": note,
    }


PROCESSES: List[Dict[str, Any]] = [
    {
        "id": "proc-lam-matte", "name": "覆哑膜", "category": "表面处理",
        "description": "在印刷面覆盖一层哑光薄膜，防刮耐磨，呈现低调高级的质感。",
        "image": "/assets/processes/lam.svg",
        "applies_to": ["bag", "cardbox", "tray", "mailer", "sleeve", "sheet"],
        "material_kinds": ["paper", "board"],
        "constraints": {"min_gsm": 100},
        "methods": [
            _m("m-auto", "自动覆膜机", "process_m2", {"setup": 60, "price_per_m2": 1.10, "min_charge": 100}, 1),
        ],
        "enabled": 1, "sort": 1,
    },
    {
        "id": "proc-lam-gloss", "name": "覆光膜", "category": "表面处理",
        "description": "亮光薄膜，色彩更饱和，适合货架陈列与高对比画面。",
        "image": "/assets/processes/lam-gloss.svg",
        "applies_to": ["bag", "cardbox", "tray", "mailer", "sleeve", "sheet"],
        "material_kinds": ["paper", "board"],
        "constraints": {"min_gsm": 100},
        "methods": [
            _m("m-auto", "自动覆膜机", "process_m2", {"setup": 60, "price_per_m2": 1.10, "min_charge": 100}, 1),
        ],
        "enabled": 1, "sort": 2,
    },
    {
        "id": "proc-foil", "name": "烫金 / 烫银", "category": "表面处理",
        "description": "加热金属箔压印到纸面，形成镜面金属效果；可做金、银、玫瑰金。",
        "image": "/assets/processes/foil.svg",
        "applies_to": ["bag", "cardbox", "tray", "mailer", "sleeve", "sheet"],
        "material_kinds": ["paper", "board"],
        "constraints": {"min_gsm": 150},
        "methods": [
            _m("m-flat", "平压烫金", "process_piece_plate", {"plate_cost": 60, "setup": 20, "price_per_piece": 0.030, "min_charge": 80}, 1),
        ],
        "enabled": 1, "sort": 3,
    },
    {
        "id": "proc-die", "name": "模切", "category": "后道加工",
        "description": "按刀模形状冲切展开件，是纸袋、纸盒成型的基础工序；含刀模费。",
        "image": "/assets/processes/die.svg",
        "applies_to": ["bag", "cardbox", "tray", "mailer", "sleeve"],
        "material_kinds": ["paper", "board"],
        "constraints": {},
        "methods": [
            _m("m-die", "自动模切机", "process_1000_sheets", {"setup": 120, "price_per_1000_sheets": 30, "min_charge": 160}, 1),
        ],
        "enabled": 1, "sort": 4,
    },
    {
        "id": "proc-crease", "name": "压痕", "category": "后道加工",
        "description": "在折叠位置压出凹槽，保证盒型折线笔直、不爆色。",
        "image": "/assets/processes/crease.svg",
        "applies_to": ["cardbox", "tray", "mailer", "sleeve"],
        "material_kinds": ["paper", "board"],
        "constraints": {"min_gsm": 200},
        "methods": [
            _m("m-crease", "压痕机", "process_1000_sheets", {"setup": 40, "price_per_1000_sheets": 18, "min_charge": 60}, 1),
        ],
        "enabled": 1, "sort": 5,
    },
    {
        "id": "proc-emboss", "name": "凹凸 / 击凸", "category": "表面处理",
        "description": "用阴阳模压出立体浮雕，无需油墨，适合 LOGO 与纹理。",
        "image": "/assets/processes/emboss.svg",
        "applies_to": ["bag", "cardbox", "tray", "sleeve", "sheet"],
        "material_kinds": ["paper", "board"],
        "constraints": {"min_gsm": 200},
        "methods": [
            _m("m-emboss", "击凸机", "process_piece_plate", {"plate_cost": 50, "setup": 20, "price_per_piece": 0.040, "min_charge": 70}, 1),
        ],
        "enabled": 1, "sort": 6,
    },
    {
        "id": "proc-uv", "name": "局部 UV", "category": "表面处理",
        "description": "在局部图案上叠加高光 UV 油，形成亮面与哑面的对比。",
        "image": "/assets/processes/uv.svg",
        "applies_to": ["bag", "cardbox", "tray", "sleeve", "sheet"],
        "material_kinds": ["paper", "board"],
        "constraints": {"min_gsm": 150},
        "methods": [
            _m("m-uv", "丝网局部 UV", "process_m2", {"setup": 80, "price_per_m2": 4.0, "min_charge": 120}, 1),
        ],
        "enabled": 1, "sort": 7,
    },
    {
        "id": "proc-cut", "name": "裁切", "category": "后道加工",
        "description": "把印刷大张裁切成指定开数，保证成品尺寸精准。",
        "image": "/assets/processes/cut.svg",
        "applies_to": ["bag", "cardbox", "tray", "mailer", "sleeve", "sheet", "label"],
        "material_kinds": ["paper", "board", "label"],
        "constraints": {},
        "methods": [
            _m("m-cut", "切纸机", "process_1000_sheets", {"setup": 0, "price_per_1000_sheets": 10, "min_charge": 30}, 1),
        ],
        "enabled": 1, "sort": 8,
    },
    {
        "id": "proc-glue-bag", "name": "糊袋", "category": "成型",
        "description": "将模切后的袋身粘合成型。小批量手工更省，大批量机器更划算。",
        "image": "/assets/processes/glue.svg",
        "applies_to": ["bag"],
        "material_kinds": ["paper", "board"],
        "constraints": {},
        "methods": [
            _m("m-machine", "机器糊袋", "process_piece", {"setup": 220, "price_per_piece": 0.070, "min_charge": 180}, 2, 300, "300 个以上开机"),
            _m("m-manual", "手工糊袋", "process_piece", {"setup": 0, "price_per_piece": 0.260, "min_charge": 0}, 1, 0, "小批量无需开机费"),
        ],
        "enabled": 1, "sort": 9,
    },
    {
        "id": "proc-handle", "name": "穿绳", "category": "成型",
        "description": "在袋口打孔并穿入提绳，机器与手工两种方式按数量自动比选。",
        "image": "/assets/processes/handle.svg",
        "applies_to": ["bag"],
        "material_kinds": ["paper", "board"],
        "constraints": {},
        "methods": [
            _m("m-machine", "机器穿绳", "process_piece", {"setup": 120, "price_per_piece": 0.040, "min_charge": 80}, 1, 300, "300 个以上开机"),
            _m("m-manual", "手工穿绳", "process_piece", {"setup": 0, "price_per_piece": 0.140, "min_charge": 0}, 1, 0, "小批量无需开机费"),
        ],
        "enabled": 1, "sort": 10,
    },
    {
        "id": "proc-glue-box", "name": "糊盒", "category": "成型",
        "description": "卡盒侧边粘合成型，机器糊盒速度快，小批量手工更灵活。",
        "image": "/assets/processes/glue-box.svg",
        "applies_to": ["cardbox", "mailer", "sleeve", "tray"],
        "material_kinds": ["paper", "board"],
        "constraints": {},
        "methods": [
            _m("m-machine", "机器糊盒", "process_piece", {"setup": 180, "price_per_piece": 0.050, "min_charge": 120}, 2, 300, "300 个以上开机"),
            _m("m-manual", "手工糊盒", "process_piece", {"setup": 0, "price_per_piece": 0.200, "min_charge": 0}, 1, 0, "小批量无需开机费"),
        ],
        "enabled": 1, "sort": 11,
    },
    {
        "id": "proc-window", "name": "开窗 / 贴窗", "category": "后道加工",
        "description": "在盒面开窗并贴 PET 透明片，展示内装产品。",
        "image": "/assets/processes/window.svg",
        "applies_to": ["cardbox", "mailer"],
        "material_kinds": ["paper", "board"],
        "constraints": {"min_gsm": 250},
        "methods": [
            _m("m-window", "开窗贴片", "process_piece", {"setup": 50, "price_per_piece": 0.180, "min_charge": 80}, 1),
        ],
        "enabled": 1, "sort": 12,
    },
    {
        "id": "proc-slot", "name": "开槽", "category": "后道加工",
        "description": "瓦楞纸箱开槽压线，形成上下摇盖。",
        "image": "/assets/processes/slot.svg",
        "applies_to": ["carton"],
        "material_kinds": ["corrugated"],
        "constraints": {},
        "methods": [
            _m("m-slot", "开槽机", "process_1000_sheets", {"setup": 60, "price_per_1000_sheets": 25, "min_charge": 80}, 1),
        ],
        "enabled": 1, "sort": 13,
    },
    {
        "id": "proc-staple", "name": "打钉 / 粘箱", "category": "成型",
        "description": "纸箱接舌打钉或粘合，保证运输强度。",
        "image": "/assets/processes/staple.svg",
        "applies_to": ["carton"],
        "material_kinds": ["corrugated"],
        "constraints": {},
        "methods": [
            _m("m-staple", "打钉", "process_piece", {"setup": 20, "price_per_piece": 0.040, "min_charge": 20}, 1),
        ],
        "enabled": 1, "sort": 14,
    },
    {
        "id": "proc-label-die", "name": "标签模切", "category": "后道加工",
        "description": "按标签形状模切，圆角、异形均可；含刀模费。",
        "image": "/assets/processes/label-die.svg",
        "applies_to": ["label"],
        "material_kinds": ["label"],
        "constraints": {},
        "methods": [
            _m("m-label-die", "标签模切机", "process_1000_pieces", {"setup": 100, "price_per_1000": 40, "min_charge": 120}, 1),
        ],
        "enabled": 1, "sort": 15,
    },
    {
        "id": "proc-label-waste", "name": "排废", "category": "后道加工",
        "description": "去除模切后的边角废料，成卷交付。",
        "image": "/assets/processes/waste.svg",
        "applies_to": ["label"],
        "material_kinds": ["label"],
        "constraints": {},
        "methods": [
            _m("m-waste", "排废机", "process_1000_pieces", {"setup": 0, "price_per_1000": 12, "min_charge": 20}, 1),
        ],
        "enabled": 1, "sort": 16,
    },
    {
        "id": "proc-roll", "name": "卷装", "category": "包装",
        "description": "标签按卷收纳，每卷 500-1000 张，方便贴标机使用。",
        "image": "/assets/processes/roll.svg",
        "applies_to": ["label"],
        "material_kinds": ["label"],
        "constraints": {},
        "methods": [
            _m("m-roll", "卷装机", "process_order", {"price_per_order": 8, "min_charge": 0}, 1),
        ],
        "enabled": 1, "sort": 17,
    },
    {
        "id": "proc-mount", "name": "裱糊", "category": "成型",
        "description": "灰板与面纸对裱，用于精装礼盒；小批量手工裱糊。",
        "image": "/assets/processes/mount.svg",
        "applies_to": ["tray", "sleeve"],
        "material_kinds": ["board"],
        "constraints": {"min_gsm": 200},
        "methods": [
            _m("m-mount", "手工裱糊", "process_m2", {"setup": 40, "price_per_m2": 5.0, "min_charge": 80}, 2),
        ],
        "enabled": 1, "sort": 18,
    },
    {
        "id": "proc-magnet", "name": "装磁铁", "category": "成型",
        "description": "在盒盖内埋入磁铁，形成磁吸闭合。",
        "image": "/assets/processes/magnet.svg",
        "applies_to": ["tray", "sleeve"],
        "material_kinds": ["board"],
        "constraints": {},
        "methods": [
            _m("m-magnet", "手工装磁", "process_piece", {"setup": 20, "price_per_piece": 0.100, "min_charge": 30}, 1),
        ],
        "enabled": 1, "sort": 19,
    },
    {
        "id": "proc-insert", "name": "装内衬", "category": "成型",
        "description": "放置 EVA/纸浆内衬，固定产品。",
        "image": "/assets/processes/insert.svg",
        "applies_to": ["box", "tray", "sleeve"],
        "material_kinds": ["paper", "board"],
        "constraints": {},
        "methods": [
            _m("m-insert", "手工装内衬", "process_piece", {"setup": 0, "price_per_piece": 0.150, "min_charge": 0}, 1),
        ],
        "enabled": 1, "sort": 20,
    },
    {
        "id": "proc-screen-stock", "name": "成品丝印", "category": "成品加印",
        "description": "在已成型纸袋/纸盒上直接丝印 LOGO，无需重新制袋。",
        "image": "/assets/processes/screen.svg",
        "applies_to": ["overprint"],
        "material_kinds": ["stock"],
        "constraints": {},
        "methods": [
            _m("m-screen", "成品丝印", "overprint_piece", {"plate_cost": 40, "setup": 20, "price_per_piece": 0.060, "min_charge": 60}, 1),
        ],
        "enabled": 1, "sort": 21,
    },
    {
        "id": "proc-foil-stock", "name": "成品烫金", "category": "成品加印",
        "description": "在成品表面直接烫金/烫银，适合小批量补印与高端定制。",
        "image": "/assets/processes/foil-stock.svg",
        "applies_to": ["overprint"],
        "material_kinds": ["stock"],
        "constraints": {},
        "methods": [
            _m("m-foil-stock", "成品烫金机", "overprint_piece", {"plate_cost": 80, "setup": 20, "price_per_piece": 0.100, "min_charge": 80}, 1),
        ],
        "enabled": 1, "sort": 22,
    },
    {
        "id": "proc-pack", "name": "装箱打包", "category": "包装",
        "description": "按标准装箱数量入箱、封箱、贴标。",
        "image": "/assets/processes/pack.svg",
        "applies_to": ["bag", "cardbox", "tray", "mailer", "sleeve", "carton", "label", "overprint"],
        "material_kinds": ["paper", "board", "corrugated", "label", "stock"],
        "constraints": {},
        "methods": [
            _m("m-pack", "手工装箱", "process_order", {"price_per_order": 6, "min_charge": 0}, 0),
        ],
        "enabled": 1, "sort": 23,
    },
]

# ---------------------------------------------------------------------------
# 包装方式
# ---------------------------------------------------------------------------

PACKAGINGS: List[Dict[str, Any]] = [
    {
        "id": "pkg-standard", "name": "标准出口纸箱", "description": "五层加强纸箱 + 气泡膜护角，适合常规运输。",
        "image": "/assets/processes/pack.svg",
        "carton_qty": 100, "carton_weight_kg": 0.6,
        "carton_size": [600, 400, 400],
        "algorithm_id": "packaging_order",
        "params": {"price_per_order": 8, "price_per_piece": 0.12},
        "enabled": 1, "sort": 1,
    },
    {
        "id": "pkg-strengthen", "name": "加强包装", "description": "加厚纸箱 + 珍珠棉 + 护角，适合高客单礼盒。",
        "image": "/assets/processes/pack-strong.svg",
        "carton_qty": 50, "carton_weight_kg": 0.9,
        "carton_size": [650, 450, 450],
        "algorithm_id": "packaging_order",
        "params": {"price_per_order": 15, "price_per_piece": 0.22},
        "enabled": 1, "sort": 2,
    },
    {
        "id": "pkg-pallet", "name": "整托包装", "description": "托盘 + 缠绕膜，适合 3000 个以上整批交付。",
        "image": "/assets/processes/pack-pallet.svg",
        "carton_qty": 1000, "carton_weight_kg": 12,
        "carton_size": [1200, 1000, 1100],
        "algorithm_id": "packaging_order",
        "params": {"price_per_order": 80, "price_per_piece": 0.08},
        "enabled": 1, "sort": 3,
    },
]

# ---------------------------------------------------------------------------
# 商品
# ---------------------------------------------------------------------------

def _preset(name, L, W, H):
    return {"name": name, "dims": {"L": L, "W": W, "H": H}}


def _spec(label, value):
    return {"label": label, "value": value}


def _faq(q, a):
    return {"q": q, "a": a}


PRODUCTS: List[Dict[str, Any]] = [
    {
        "id": "bag-kraft",
        "kind": "custom",
        "category": "bag",
        "name": "牛皮纸手提袋",
        "subtitle": "原色牛皮纸 · 100 个起做 · 可先打样",
        "badge": "热销",
        "description": "进口黄牛皮纸，原色质朴，适合烘焙、咖啡、服饰与伴手礼。机器糊袋与自动穿绳，让小批量也有稳定袋型。",
        "long_desc": "袋身采用 120g/150g 原色牛皮纸，纤维长、耐折度好；袋底加固，承重 5-8kg。标配纸绳，可升级棉绳或尼龙绳。支持单色到四色印刷，也可加覆膜、烫金。",
        "images": ["/assets/products/bag-kraft.svg", "/assets/products/bag-kraft-detail.svg"],
        "image": "/assets/products/bag-kraft.svg",
        "modes": ["sample", "custom"],
        "structure": "bag",
        "dim_fields": [
            {"key": "L", "label": "袋宽", "min": 80, "max": 450, "default": 220},
            {"key": "W", "label": "侧深", "min": 30, "max": 220, "default": 90},
            {"key": "H", "label": "袋高", "min": 120, "max": 550, "default": 300},
        ],
        "formula_params": {"glue": 18, "bottom": 35, "top_fold": 30},
        "bleed": 3,
        "size_presets": [
            _preset("小号 180×80×240", 180, 80, 240),
            _preset("中号 220×90×300", 220, 90, 300),
            _preset("大号 260×110×350", 260, 110, 350),
            _preset("加大 300×120×400", 300, 120, 400),
        ],
        "materials": ["mat-kraft120", "mat-kraft150", "mat-art250"],
        "default_material": "mat-kraft120",
        "aux_groups": [
            {
                "id": "handle", "name": "提绳", "per_unit": 2.2, "unit": "m",
                "options": [
                    {"material_id": "aux-rope-paper", "label": "纸绳（标配）", "default": True},
                    {"material_id": "aux-rope-cotton", "label": "棉绳", "default": False},
                    {"material_id": "aux-rope-nylon", "label": "尼龙绳", "default": False},
                    {"material_id": "aux-ribbon", "label": "丝带", "default": False},
                ],
            }
        ],
        "colors": [0, 1, 2, 3, 4],
        "default_colors": 2,
        "processes": {
            "required": ["proc-die", "proc-glue-bag", "proc-handle"],
            "optional": ["proc-lam-matte", "proc-lam-gloss", "proc-foil", "proc-uv"],
            "groups": [],
        },
        "packagings": ["pkg-standard", "pkg-strengthen"],
        "default_packaging": "pkg-standard",
        "quantity": {"min": 100, "max": 20000, "step": 50, "presets": [100, 300, 500, 1000, 3000]},
        "sample": {"enabled": True, "min": 1, "max": 10, "presets": [1, 3, 5, 10], "fee": 180, "lead_days": 3},
        "production": {
            "press_ids": ["press-offset-big", "press-offset-4k", "press-digital"],
            "sheet_ids": [],
            "objective": "cost",
            "loss_rate": 0.05,
        },
        "lead_days": 6,
        "pricing": {"agent_markup": 0.28},
        "highlights": ["100 个起做，3 天出样", "机器糊袋，袋型挺括", "纸绳/棉绳/尼龙绳可选", "含送货上门"],
        "specs": [
            _spec("起订量", "100 个"),
            _spec("常规交期", "5-7 个工作日"),
            _spec("承重", "5-8kg"),
            _spec("提绳", "纸绳标配，可升级"),
            _spec("印刷", "1-4 色"),
            _spec("打样", "1-10 个，3 天"),
        ],
        "faq": [
            _faq("100 个也能做吗？", "可以。100 个起做，系统会按小批量自动选择更省的手工糊袋与数码/四开印刷方案。"),
            _faq("可以先打样吗？", "可以，1-10 个均可打样，打样费在下大货后可按规则抵扣。"),
            _faq("报价含运费吗？", "含标准送货上门运费；满 3000 元免运费，偏远地区另议。"),
        ],
        "audience": ["烘焙 / 咖啡", "服饰 / 买手店", "伴手礼 / 婚庆", "品牌活动"],
        "status": "active",
        "sort": 1,
    },
    {
        "id": "bag-art",
        "kind": "custom",
        "category": "bag",
        "name": "白卡纸手提袋",
        "subtitle": "白卡纸 · 色彩还原好 · 可覆膜烫金",
        "badge": "品牌首选",
        "description": "高白度白卡纸袋，适合彩印品牌画面。可覆哑膜、烫金、局部 UV，做出精品店质感。",
        "long_desc": "250g/300g 白卡纸，纸面平整，色彩饱和。标配纸绳，可升级棉绳/丝带。袋底加固，适合服装、美妆、礼品。",
        "images": ["/assets/products/bag-art.svg", "/assets/products/bag-art-detail.svg"],
        "image": "/assets/products/bag-art.svg",
        "modes": ["sample", "custom"],
        "structure": "bag",
        "dim_fields": [
            {"key": "L", "label": "袋宽", "min": 100, "max": 450, "default": 240},
            {"key": "W", "label": "侧深", "min": 40, "max": 220, "default": 100},
            {"key": "H", "label": "袋高", "min": 150, "max": 550, "default": 320},
        ],
        "formula_params": {"glue": 18, "bottom": 40, "top_fold": 30},
        "bleed": 3,
        "size_presets": [
            _preset("小号 200×90×260", 200, 90, 260),
            _preset("中号 240×100×320", 240, 100, 320),
            _preset("大号 280×110×360", 280, 110, 360),
            _preset("加大 320×120×420", 320, 120, 420),
        ],
        "materials": ["mat-art250", "mat-art300", "mat-art350", "mat-special"],
        "default_material": "mat-art300",
        "aux_groups": [
            {
                "id": "handle", "name": "提绳", "per_unit": 2.2, "unit": "m",
                "options": [
                    {"material_id": "aux-rope-paper", "label": "纸绳（标配）", "default": True},
                    {"material_id": "aux-rope-cotton", "label": "棉绳", "default": False},
                    {"material_id": "aux-rope-nylon", "label": "尼龙绳", "default": False},
                    {"material_id": "aux-ribbon", "label": "丝带", "default": False},
                ],
            }
        ],
        "colors": [1, 2, 3, 4],
        "default_colors": 4,
        "processes": {
            "required": ["proc-die", "proc-glue-bag", "proc-handle"],
            "optional": ["proc-lam-matte", "proc-lam-gloss", "proc-foil", "proc-uv", "proc-emboss"],
            "groups": [],
        },
        "packagings": ["pkg-standard", "pkg-strengthen"],
        "default_packaging": "pkg-standard",
        "quantity": {"min": 100, "max": 20000, "step": 50, "presets": [100, 300, 500, 1000, 3000]},
        "sample": {"enabled": True, "min": 1, "max": 10, "presets": [1, 3, 5, 10], "fee": 200, "lead_days": 3},
        "production": {"press_ids": ["press-offset-big", "press-offset-4k", "press-digital"], "sheet_ids": [], "objective": "cost", "loss_rate": 0.05},
        "lead_days": 6,
        "pricing": {"agent_markup": 0.30},
        "highlights": ["白卡纸色彩还原好", "覆膜 / 烫金 / UV 可选", "100 个起做", "3 天出样"],
        "specs": [
            _spec("起订量", "100 个"),
            _spec("常规交期", "5-7 个工作日"),
            _spec("纸张", "250-350g 白卡"),
            _spec("印刷", "1-4 色"),
            _spec("表面", "光膜 / 哑膜 / 烫金 / UV"),
        ],
        "faq": [
            _faq("覆膜和 UV 怎么选？", "覆膜适合整面保护和手感提升；局部 UV 适合突出 LOGO 或图案，建议搭配哑膜使用。"),
            _faq("能先看颜色吗？", "可以打样 1-10 个，确认颜色与工艺后再下大货。"),
        ],
        "audience": ["美妆 / 护肤", "服装 / 饰品", "品牌礼品", "展会活动"],
        "status": "active",
        "sort": 2,
    },
    {
        "id": "box-lidbase",
        "kind": "custom",
        "category": "box",
        "name": "天地盖礼盒",
        "subtitle": "盖 + 底两件套 · 可裱糊 / 磁吸 · 200 个起",
        "badge": "礼盒",
        "description": "经典天地盖结构，盖底分离，开合有仪式感。适合茶叶、香氛、饰品、月饼等礼盒。",
        "long_desc": "白卡纸或特种纸天地盖，盖底各一片，模切后手工糊盒。可加覆膜、烫金、凹凸，升级磁吸与 EVA 内衬。",
        "images": ["/assets/products/box-lidbase.svg", "/assets/products/box-lidbase-detail.svg"],
        "image": "/assets/products/box-lidbase.svg",
        "modes": ["sample", "custom"],
        "structure": "tray",
        "dim_fields": [
            {"key": "L", "label": "盒长", "min": 80, "max": 450, "default": 240},
            {"key": "W", "label": "盒宽", "min": 60, "max": 350, "default": 180},
            {"key": "H", "label": "盒高", "min": 25, "max": 200, "default": 70},
        ],
        "formula_params": {"margin": 8},
        "bleed": 3,
        "size_presets": [
            _preset("小号 160×120×50", 160, 120, 50),
            _preset("中号 240×180×70", 240, 180, 70),
            _preset("大号 300×220×90", 300, 220, 90),
            _preset("加大 360×260×110", 360, 260, 110),
        ],
        "materials": ["mat-art300", "mat-art350", "mat-special"],
        "default_material": "mat-art350",
        "aux_groups": [
            {
                "id": "magnet", "name": "磁吸扣", "per_unit": 2, "unit": "个", "optional": True,
                "options": [
                    {"material_id": None, "label": "不需要", "default": True},
                    {"material_id": "aux-magnet", "label": "加磁铁扣（2 个）", "default": False},
                ],
            },
            {
                "id": "insert", "name": "内衬", "per_unit": 1, "unit": "个", "optional": True,
                "options": [
                    {"material_id": None, "label": "不需要", "default": True},
                    {"material_id": "aux-eva", "label": "EVA 内衬", "default": False},
                ],
            },
        ],
        "colors": [0, 1, 2, 3, 4],
        "default_colors": 2,
        "processes": {
            "required": ["proc-die", "proc-crease", "proc-glue-box"],
            "optional": ["proc-lam-matte", "proc-lam-gloss", "proc-foil", "proc-emboss", "proc-uv", "proc-magnet", "proc-insert"],
            "groups": [],
        },
        "packagings": ["pkg-standard", "pkg-strengthen"],
        "default_packaging": "pkg-strengthen",
        "quantity": {"min": 200, "max": 10000, "step": 50, "presets": [200, 500, 1000, 3000]},
        "sample": {"enabled": True, "min": 1, "max": 5, "presets": [1, 3, 5], "fee": 220, "lead_days": 4},
        "production": {"press_ids": ["press-offset-big", "press-offset-4k", "press-digital"], "sheet_ids": [], "objective": "cost", "loss_rate": 0.05},
        "lead_days": 7,
        "pricing": {"agent_markup": 0.30},
        "highlights": ["盖底两件套", "可加磁吸与内衬", "200 个起做", "4 天出样"],
        "specs": [
            _spec("起订量", "200 套"),
            _spec("常规交期", "6-8 个工作日"),
            _spec("结构", "天地盖（盖+底）"),
            _spec("纸张", "300-350g 白卡 / 特种纸"),
            _spec("可选", "覆膜 / 烫金 / 凹凸 / 磁吸 / 内衬"),
        ],
        "faq": [
            _faq("一套包含什么？", "一套 = 一个盒盖 + 一个盒底，系统按 2 片坯料计算展开与拼版。"),
            _faq("磁吸和内衬要另外加钱吗？", "是，按实际选用计入工艺与辅料费，报价明细会单独列出。"),
        ],
        "audience": ["茶叶 / 香氛", "珠宝 / 饰品", "月饼 / 食品", "企业礼赠"],
        "status": "active",
        "sort": 3,
    },
    {
        "id": "box-mailer",
        "kind": "custom",
        "category": "box",
        "name": "飞机盒",
        "subtitle": "电商包装 · 免胶带成型 · 100 个起",
        "badge": "电商",
        "description": "一体成型飞机盒，折起即可使用，无需胶带。适合电商发货、服饰、数码配件。",
        "long_desc": "白卡或瓦楞面纸飞机盒，插舌结构，展开即成型。支持双面印刷与覆膜，小批量 100 个起。",
        "images": ["/assets/products/box-mailer.svg", "/assets/products/box-mailer-detail.svg"],
        "image": "/assets/products/box-mailer.svg",
        "modes": ["sample", "custom"],
        "structure": "mailer",
        "dim_fields": [
            {"key": "L", "label": "盒长", "min": 100, "max": 500, "default": 260},
            {"key": "W", "label": "盒宽", "min": 60, "max": 350, "default": 180},
            {"key": "H", "label": "盒高", "min": 20, "max": 200, "default": 80},
        ],
        "formula_params": {"glue": 18, "flap": 15},
        "bleed": 3,
        "size_presets": [
            _preset("小号 200×140×60", 200, 140, 60),
            _preset("中号 260×180×80", 260, 180, 80),
            _preset("大号 320×220×100", 320, 220, 100),
            _preset("加大 400×280×120", 400, 280, 120),
        ],
        "materials": ["mat-art250", "mat-art300"],
        "default_material": "mat-art300",
        "aux_groups": [],
        "colors": [1, 2, 3, 4],
        "default_colors": 2,
        "processes": {
            "required": ["proc-die", "proc-crease", "proc-glue-box"],
            "optional": ["proc-lam-matte", "proc-lam-gloss", "proc-foil"],
            "groups": [],
        },
        "packagings": ["pkg-standard", "pkg-strengthen"],
        "default_packaging": "pkg-standard",
        "quantity": {"min": 100, "max": 20000, "step": 50, "presets": [100, 300, 500, 1000, 3000]},
        "sample": {"enabled": True, "min": 1, "max": 10, "presets": [1, 3, 5, 10], "fee": 160, "lead_days": 3},
        "production": {"press_ids": ["press-offset-big", "press-offset-4k", "press-digital"], "sheet_ids": [], "objective": "cost", "loss_rate": 0.05},
        "lead_days": 5,
        "pricing": {"agent_markup": 0.28},
        "highlights": ["一体成型，免胶带", "100 个起做", "双面印刷可选", "3 天出样"],
        "specs": [
            _spec("起订量", "100 个"),
            _spec("常规交期", "4-6 个工作日"),
            _spec("结构", "飞机盒 / 插舌"),
            _spec("纸张", "250-300g 白卡 / 三层瓦楞"),
        ],
        "faq": [
            _faq("需要自己折吗？", "出厂为模切压痕平板，折起即可成型，无需胶带。"),
            _faq("能印内面吗？", "可以，报价按双面印刷计算；请在下单备注中说明。"),
        ],
        "audience": ["电商发货", "服饰", "数码配件", "美妆"],
        "status": "active",
        "sort": 4,
    },
    {
        "id": "box-card",
        "kind": "custom",
        "category": "box",
        "name": "插舌卡盒",
        "subtitle": "经典卡盒 · 可开窗 · 200 个起",
        "badge": "",
        "description": "插舌卡盒结构，展开即成型，适合食品、日化、文具等中小型包装。",
        "long_desc": "白卡纸插舌盒，上下插舌，无需胶水即可闭合。可加开窗、覆膜、烫金，200 个起做。",
        "images": ["/assets/products/box-card.svg", "/assets/products/box-card-detail.svg"],
        "image": "/assets/products/box-card.svg",
        "modes": ["sample", "custom"],
        "structure": "cardbox",
        "dim_fields": [
            {"key": "L", "label": "盒长", "min": 50, "max": 400, "default": 160},
            {"key": "W", "label": "盒宽", "min": 30, "max": 300, "default": 100},
            {"key": "H", "label": "盒高", "min": 20, "max": 250, "default": 60},
        ],
        "formula_params": {"glue": 18, "flap": 15},
        "bleed": 3,
        "size_presets": [
            _preset("小号 100×70×40", 100, 70, 40),
            _preset("中号 160×100×60", 160, 100, 60),
            _preset("大号 220×150×80", 220, 150, 80),
            _preset("加大 300×200×100", 300, 200, 100),
        ],
        "materials": ["mat-art250", "mat-art300", "mat-art350", "mat-special"],
        "default_material": "mat-art300",
        "aux_groups": [],
        "colors": [0, 1, 2, 3, 4],
        "default_colors": 2,
        "processes": {
            "required": ["proc-die", "proc-crease", "proc-glue-box"],
            "optional": ["proc-lam-matte", "proc-lam-gloss", "proc-foil", "proc-uv", "proc-window"],
            "groups": [],
        },
        "packagings": ["pkg-standard", "pkg-strengthen"],
        "default_packaging": "pkg-standard",
        "quantity": {"min": 200, "max": 30000, "step": 100, "presets": [200, 500, 1000, 3000, 5000]},
        "sample": {"enabled": True, "min": 1, "max": 10, "presets": [1, 3, 5, 10], "fee": 150, "lead_days": 3},
        "production": {"press_ids": ["press-offset-big", "press-offset-4k", "press-digital"], "sheet_ids": [], "objective": "cost", "loss_rate": 0.05},
        "lead_days": 5,
        "pricing": {"agent_markup": 0.28},
        "highlights": ["200 个起做", "可开窗展示", "上下插舌免胶", "3 天出样"],
        "specs": [
            _spec("起订量", "200 个"),
            _spec("常规交期", "4-6 个工作日"),
            _spec("结构", "插舌卡盒"),
            _spec("纸张", "250-350g 白卡 / 特种纸"),
        ],
        "faq": [
            _faq("开窗会影响承重吗？", "会略有影响，建议开窗面积不超过盒面 40%，并搭配覆膜增强挺度。"),
        ],
        "audience": ["食品", "日化", "文具", "小型礼盒"],
        "status": "active",
        "sort": 5,
    },
    {
        "id": "label-coated",
        "kind": "custom",
        "category": "label",
        "name": "铜版纸不干胶",
        "subtitle": "卷筒标签 · 500 张起 · 圆角/异形可模切",
        "badge": "常用",
        "description": "通用铜版不干胶，色彩还原好，适合瓶贴、食品标签、物流标签。",
        "long_desc": "卷筒铜版不干胶，表面细腻，适合四色印刷。可模切圆角、异形，排废后成卷交付。",
        "images": ["/assets/products/label-coated.svg", "/assets/products/label-coated-detail.svg"],
        "image": "/assets/products/label-coated.svg",
        "modes": ["sample", "custom"],
        "structure": "label",
        "dim_fields": [
            {"key": "L", "label": "标签宽", "min": 20, "max": 300, "default": 80},
            {"key": "W", "label": "标签高", "min": 20, "max": 300, "default": 50},
            {"key": "H", "label": "单张数量", "min": 1, "max": 1, "default": 1, "hidden": True},
        ],
        "formula_params": {},
        "bleed": 2,
        "size_presets": [
            _preset("小号 50×30", 50, 30, 1),
            _preset("中号 80×50", 80, 50, 1),
            _preset("大号 100×70", 100, 70, 1),
            _preset("异形 60×60", 60, 60, 1),
        ],
        "materials": ["mat-label-coat", "mat-label-pvc", "mat-label-kraft"],
        "default_material": "mat-label-coat",
        "aux_groups": [],
        "colors": [1, 2, 3, 4],
        "default_colors": 3,
        "processes": {
            "required": ["proc-label-die", "proc-label-waste", "proc-roll"],
            "optional": ["proc-lam-matte", "proc-lam-gloss", "proc-foil"],
            "groups": [],
        },
        "packagings": ["pkg-standard"],
        "default_packaging": "pkg-standard",
        "quantity": {"min": 500, "max": 100000, "step": 500, "presets": [500, 1000, 3000, 5000, 10000]},
        "sample": {"enabled": True, "min": 1, "max": 20, "presets": [1, 5, 10, 20], "fee": 80, "lead_days": 2},
        "production": {"press_ids": ["press-label"], "sheet_ids": [], "objective": "cost", "loss_rate": 0.04},
        "lead_days": 4,
        "pricing": {"agent_markup": 0.25},
        "highlights": ["500 张起做", "圆角/异形模切", "卷装交付", "2 天出样"],
        "specs": [
            _spec("起订量", "500 张"),
            _spec("常规交期", "3-5 个工作日"),
            _spec("材料", "铜版 / 透明 PVC / 牛皮纸"),
            _spec("印刷", "1-4 色"),
            _spec("交付", "卷装，500-1000 张/卷"),
        ],
        "faq": [
            _faq("可以贴曲面瓶身吗？", "建议选透明 PVC 或可移胶材料；下单时备注曲面贴标需求。"),
            _faq("有刀模费吗？", "标准圆角/矩形含在模切费内；异形刀模另计，报价会自动包含。"),
        ],
        "audience": ["食品饮料", "化妆品", "日化", "物流标签"],
        "status": "active",
        "sort": 6,
    },
    {
        "id": "carton-3l",
        "kind": "custom",
        "category": "carton",
        "name": "三层瓦楞纸箱",
        "subtitle": "电商发货 · 100 个起 · 可印 1-2 色",
        "badge": "物流",
        "description": "三层 B 楞纸箱，轻量抗压，适合 5kg 以内电商发货与仓储周转。",
        "long_desc": "三层瓦楞纸板，0201 标准开槽箱。可印 1-2 色 LOGO 与水印，100 个起做，杭州仓发货。",
        "images": ["/assets/products/carton-3l.svg", "/assets/products/carton-3l-detail.svg"],
        "image": "/assets/products/carton-3l.svg",
        "modes": ["sample", "custom"],
        "structure": "carton",
        "dim_fields": [
            {"key": "L", "label": "外长", "min": 150, "max": 1000, "default": 400},
            {"key": "W", "label": "外宽", "min": 100, "max": 800, "default": 300},
            {"key": "H", "label": "外高", "min": 80, "max": 800, "default": 200},
        ],
        "formula_params": {"lap": 40, "trim": 10},
        "bleed": 0,
        "size_presets": [
            _preset("小号 300×200×150", 300, 200, 150),
            _preset("中号 400×300×200", 400, 300, 200),
            _preset("大号 500×350×250", 500, 350, 250),
            _preset("加大 600×400×300", 600, 400, 300),
        ],
        "materials": ["mat-corr3", "mat-corr5"],
        "default_material": "mat-corr3",
        "aux_groups": [],
        "colors": [0, 1, 2],
        "default_colors": 1,
        "processes": {
            "required": ["proc-slot", "proc-staple", "proc-pack"],
            "optional": [],
            "groups": [],
        },
        "packagings": ["pkg-standard"],
        "default_packaging": "pkg-standard",
        "quantity": {"min": 100, "max": 20000, "step": 50, "presets": [100, 300, 500, 1000, 3000]},
        "sample": {"enabled": True, "min": 1, "max": 5, "presets": [1, 3, 5], "fee": 100, "lead_days": 3},
        "production": {"press_ids": ["press-flexo"], "sheet_ids": [], "objective": "cost", "loss_rate": 0.05},
        "lead_days": 5,
        "pricing": {"agent_markup": 0.25},
        "highlights": ["100 个起做", "1-2 色印刷", "标准开槽箱", "杭州仓发货"],
        "specs": [
            _spec("起订量", "100 个"),
            _spec("常规交期", "4-6 个工作日"),
            _spec("材质", "三层 B 楞 / 五层 BC 楞"),
            _spec("印刷", "1-2 色水性印刷"),
        ],
        "faq": [
            _faq("尺寸怎么量？", "量外径：长 × 宽 × 高。内装物建议四周留 5-10mm 余量。"),
            _faq("能印彩色图案吗？", "瓦楞水墨印刷适合 1-2 色线条/LOGO；复杂彩印建议先贴不干胶标签。"),
        ],
        "audience": ["电商发货", "仓储周转", "搬家收纳", "工厂出货"],
        "status": "active",
        "sort": 7,
    },
    {
        "id": "stock-bag-kraft",
        "kind": "overprint",
        "category": "bag",
        "name": "现货牛皮纸袋 · LOGO 加印",
        "subtitle": "现货胚袋 · 100 个起 · 丝印/烫金 3 天出货",
        "badge": "现货加印",
        "description": "220×90×300mm 现货牛皮纸袋，无需重新制袋，直接加印 LOGO。适合急单、活动、小批量试销。",
        "long_desc": "现货胚袋已成型，可丝印 1-2 色或成品烫金。100 个起做，3 天出货，单件成本比全定制低 30%-50%。",
        "images": ["/assets/products/stock-bag-kraft.svg", "/assets/products/stock-bag-kraft-detail.svg"],
        "image": "/assets/products/stock-bag-kraft.svg",
        "modes": ["overprint"],
        "stock": {
            "name": "现货牛皮纸袋 220×90×300mm",
            "dims": {"L": 220, "W": 90, "H": 300},
            "blank_price": 1.85,
            "stock_qty": 2400,
            "lead_days": 3,
            "image": "/assets/products/stock-bag-kraft.svg",
        },
        "overprint_methods": [
            {"id": "screen", "name": "丝印 LOGO", "process_id": "proc-screen-stock", "max_colors": 2, "description": "单色/双色丝印，墨层厚实，适合文字与简单图形。"},
            {"id": "foil", "name": "成品烫金", "process_id": "proc-foil-stock", "max_colors": 1, "description": "金/银/玫瑰金，适合小面积 LOGO 与线条。"},
        ],
        "colors": [1, 2],
        "default_colors": 1,
        "processes": {"required": [], "optional": [], "groups": []},
        "packagings": ["pkg-standard", "pkg-strengthen"],
        "default_packaging": "pkg-standard",
        "quantity": {"min": 100, "max": 2000, "step": 50, "presets": [100, 300, 500, 1000]},
        "sample": {"enabled": False, "min": 1, "max": 5, "presets": [1, 3, 5], "fee": 0, "lead_days": 3},
        "lead_days": 3,
        "pricing": {"agent_markup": 0.35},
        "highlights": ["现货胚袋，无需制袋", "100 个起做", "3 天出货", "单件成本更低"],
        "specs": [
            _spec("现货规格", "220×90×300mm"),
            _spec("起订量", "100 个"),
            _spec("交期", "3 个工作日"),
            _spec("工艺", "丝印 1-2 色 / 成品烫金"),
            _spec("库存", "杭州仓现货"),
        ],
        "faq": [
            _faq("和全定制有什么区别？", "现货加印使用已成型胚袋，只加印 LOGO，省去制袋与糊袋环节，交期更快、成本更低。"),
            _faq("能改尺寸吗？", "现货规格固定；如需改尺寸请选择全定制纸袋。"),
        ],
        "audience": ["急单", "活动物料", "小批量试销", "门店开业"],
        "status": "active",
        "sort": 8,
    },
    {
        "id": "stock-bag-white",
        "kind": "overprint",
        "category": "bag",
        "name": "现货白卡纸袋 · 烫金",
        "subtitle": "现货白卡胚袋 · 200 个起 · 烫金/丝印",
        "badge": "现货加印",
        "description": "250×100×320mm 现货白卡纸袋，适合美妆、服饰、珠宝品牌快速补印。",
        "long_desc": "白卡纸现货胚袋，表面平整，适合成品烫金与丝印。200 个起做，3-4 天出货。",
        "images": ["/assets/products/stock-bag-white.svg", "/assets/products/stock-bag-white-detail.svg"],
        "image": "/assets/products/stock-bag-white.svg",
        "modes": ["overprint"],
        "stock": {
            "name": "现货白卡纸袋 250×100×320mm",
            "dims": {"L": 250, "W": 100, "H": 320},
            "blank_price": 2.45,
            "stock_qty": 1600,
            "lead_days": 3,
            "image": "/assets/products/stock-bag-white.svg",
        },
        "overprint_methods": [
            {"id": "foil", "name": "成品烫金", "process_id": "proc-foil-stock", "max_colors": 1, "description": "金属质感，适合 LOGO 与品牌字样。"},
            {"id": "screen", "name": "丝印 LOGO", "process_id": "proc-screen-stock", "max_colors": 2, "description": "实色丝印，适合大面积单色图形。"},
        ],
        "colors": [1, 2],
        "default_colors": 1,
        "processes": {"required": [], "optional": [], "groups": []},
        "packagings": ["pkg-standard", "pkg-strengthen"],
        "default_packaging": "pkg-strengthen",
        "quantity": {"min": 200, "max": 1500, "step": 50, "presets": [200, 500, 1000]},
        "sample": {"enabled": False, "min": 1, "max": 5, "presets": [1, 3, 5], "fee": 0, "lead_days": 3},
        "lead_days": 4,
        "pricing": {"agent_markup": 0.35},
        "highlights": ["白卡现货胚袋", "200 个起做", "烫金 / 丝印", "3-4 天出货"],
        "specs": [
            _spec("现货规格", "250×100×320mm"),
            _spec("起订量", "200 个"),
            _spec("交期", "3-4 个工作日"),
            _spec("工艺", "成品烫金 / 丝印"),
        ],
        "faq": [
            _faq("现货数量有限吗？", "是，库存实时扣减；大批量建议选择全定制。"),
        ],
        "audience": ["美妆", "服饰", "珠宝", "快闪活动"],
        "status": "active",
        "sort": 9,
    },
]

# ---------------------------------------------------------------------------
# 用户
# ---------------------------------------------------------------------------

# P4：独立站点已下线，内部接口由 ERP 网关注入 viewer + HMAC 鉴权，
# 不再需要 yxd 自己的 admin/agent 账号，也不再 seed 任何硬编码弱口令。
# 存量库中的 users 记录需按 P4 清理清单由人工删除（AI 不执行数据库写操作）。
DEFAULT_USERS = []


# 现有商品默认都是非标计价；标准价商品由后台新建。
for _p in PRODUCTS:
    _p.setdefault("pricing_mode", "nonstandard")
    if _p.get("pricing_mode") != "standard":
        if _p.get("category") == "label":
            _p.setdefault("source_ids", ["fac-label"])
        elif _p.get("category") == "carton":
            _p.setdefault("source_ids", ["fac-flexo"])
        elif _p.get("kind") == "overprint":
            _p.setdefault("source_ids", ["fac-digital"])
        else:
            _p.setdefault("source_ids", ["fac-digital", "fac-offset"])
    _p.setdefault("logistics", {
        "mode": "home", "provider": "统一配送", "warehouse": "杭州中心仓",
        "base_fee": 10.0, "per_kg": 1.8, "free_over": 3000.0,
        "lead_days": 1, "included": True,
        "note": "全国送货上门，满 3000 元免运费，偏远地区另议。",
    })
    # 不做单独的“打样”模式：所有非标商品只有一个起订量，数量即规格。
    if _p.get("kind") != "overprint":
        _p["modes"] = ["custom"]
    _p.pop("sample", None)
    _p["specs"] = [s for s in (_p.get("specs") or []) if "打样" not in (s.get("label", "") + s.get("value", ""))]
    _p["faq"] = [f for f in (_p.get("faq") or []) if "打样" not in (f.get("q", "") + f.get("a", ""))]
    _p["highlights"] = [h for h in (_p.get("highlights") or []) if "打样" not in h]
    _p["subtitle"] = str(_p.get("subtitle") or "").replace(" · 可先打样", "").replace(" · 可打样", "")

# 一个标准定价演示商品：对应商品中心/ERP 里已有固定价格的标品。
PRODUCTS.append({
    "id": "std-kraft-bag-50",
    "pricing_mode": "standard",
    "kind": "standard",
    "category": "bag",
    "name": "现货牛皮纸袋 50 个装",
    "sku": "STD-BAG-50",
    "subtitle": "现货 50 个/包 · 固定价格 · 48 小时发",
    "badge": "标品",
    "description": "220×90×300mm 牛皮纸袋，50 个一包，现货固定价。适合门店补货、活动急用，不需要按尺寸重新计价。",
    "long_desc": "标准定价商品：价格与规格由商品中心/ERP 维护，本工具只补充类目、图片和展示信息。",
    "images": ["/assets/products/bag-kraft.svg"],
    "image": "/assets/products/bag-kraft.svg",
    "modes": ["standard"],
    "standard_price": 68.0,
    "unit": "包",
    "quantity": {"min": 1, "max": 9999, "step": 1, "presets": [1, 5, 10, 20]},
    "lead_days": 2,
    "logistics": {"mode": "home", "provider": "统一配送", "warehouse": "杭州中心仓", "base_fee": 10.0, "per_kg": 1.8, "free_over": 3000.0, "lead_days": 1, "included": True, "note": "全国送货上门，固定价格含标准运费。"},
    "pricing": {"agent_markup": 0},
    "highlights": ["固定价格", "50 个/包", "48 小时发"],
    "specs": [
        {"label": "规格", "value": "220×90×300mm"},
        {"label": "包装", "value": "50 个/包"},
        {"label": "计价", "value": "¥68 / 包"},
        {"label": "交期", "value": "2 个工作日"},
    ],
    "faq": [
        {"q": "可以改尺寸吗？", "a": "标准品尺寸固定；改尺寸请新建非标计价商品。"},
    ],
    "audience": ["门店补货", "活动急用"],
    "status": "active",
    "sort": 10,
})


# ---------------------------------------------------------------------------
# 工厂级价格表：每家工厂拥有自己的材料/工艺/设备/包装价格，而不是全局价乘系数。
# 这里从全局基础价生成一套可编辑的初始价格；后台「报价工厂 → 价格表」可逐项修改。
# ---------------------------------------------------------------------------

def _factory_price_params(params: Dict[str, Any], mult: float) -> Dict[str, Any]:
    out = {}
    for k, v in (params or {}).items():
        if isinstance(v, (int, float)) and any(t in k for t in ("price", "plate", "setup", "min_charge", "per_")):
            out[k] = round(float(v) * mult, 2)
        else:
            out[k] = copy.deepcopy(v)
    return out


FACTORY_PRICE_MULT = {
    "digital": {"material": 1.04, "process": 1.05, "press": 1.00, "packaging": 1.00},
    "offset": {"material": 0.94, "process": 0.90, "press": 1.15, "packaging": 0.96},
    "label": {"material": 1.00, "process": 1.00, "press": 1.00, "packaging": 1.00},
    "flexo": {"material": 0.98, "process": 0.95, "press": 0.98, "packaging": 0.98},
}

for _f in FACTORIES:
    _m = FACTORY_PRICE_MULT.get(_f.get("type"), FACTORY_PRICE_MULT["digital"])
    _f["price_factor"] = 1.0
    _f["fixed_fee"] = 0
    _f["prices"] = {
        "materials": {
            _x["id"]: {"algorithm_id": _x.get("algorithm_id"), "params": _factory_price_params(_x.get("params"), _m["material"])}
            for _x in MATERIALS if _x.get("enabled", 1)
        },
        "processes": {
            _x["id"]: {"methods": [
                {
                    "id": _md.get("id"), "name": _md.get("name"), "algorithm_id": _md.get("algorithm_id"),
                    "params": _factory_price_params(_md.get("params"), _m["process"]),
                    "days": _md.get("days"), "min_qty": _md.get("min_qty", 0), "note": _md.get("note", ""),
                } for _md in _x.get("methods", [])
            ]}
            for _x in PROCESSES if _x.get("enabled", 1)
        },
        "presses": {
            _x["id"]: {"algorithm_id": _x.get("algorithm_id"), "params": _factory_price_params(_x.get("params"), _m["press"])}
            for _x in PRESSES if _x.get("enabled", 1)
        },
        "packagings": {
            _x["id"]: {"algorithm_id": _x.get("algorithm_id"), "params": _factory_price_params(_x.get("params"), _m["packaging"])}
            for _x in PACKAGINGS if _x.get("enabled", 1)
        },
    }
