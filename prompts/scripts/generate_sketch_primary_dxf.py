#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据用户手绘草图生成标准 CAD 电气一次系统图 (仅一次图) - 修正版
严格遵循用户指正：
1. 塑壳断路器符号严格采用符号库 `DYDQ0201` / `1107AA` / `QLS1` 标准画法：
   - 上端垂直母线/支路引线精确终止于灭弧符号 `×` 的中心 `(x, y_top)`（绝不穿过 `×` 向下延伸）；
   - `y_top` 与 `y_bot = y_top - 820` 之间为完全断开的断口（无垂直连线）；
   - 斜刀闸动触头从下端垂直引线的顶点 `(x, y_bot)` 出发，向左上斜伸至 `(x - 410, y_top)`；
   - 下端垂直引线精确从斜刀闸根部铰接点 `(x, y_bot)` 向下引出。
2. 彻底移除所有非 MNS 抽屉回路上的接插件 (`∨` / `︽` / `▽`) 符号，保持与手绘草图及固定式开关柜一次系统图完全一致。
"""

import os
import sys
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import primary_and_secondary_cad_engine as eng

from path_utils import ensure_out_dir
OUT_DIR = ensure_out_dir()


def draw_mccb_symbol(x: float, y_top: float, y_bot: float = None, model: str = "", rating: str = "", left_label: str = "", left_h: float = 220) -> str:
    """
    严格按照符号库 DYDQ0201 / 1107AA / QLS1 绘制塑壳断路器单线符号：
    - (x, y_top): 上端进线端点及 `×` 灭弧符号中心
    - (x, y_bot): 下端出线起点及斜刀闸根部铰接点 (默认 y_bot = y_top - 820)
    - 斜刀闸: (x, y_bot) -> (x - 410, y_top)
    - 断口区间 (y_bot, y_top) 内绝无竖线穿过！
    """
    if y_bot is None:
        y_bot = y_top - 820.0
    dx_cross = 140.0
    s = (
        # 灭弧符号 × 中心严格位于上端引线终点 (x, y_top)
        eng.d_line(x - dx_cross, y_top - dx_cross, x + dx_cross, y_top + dx_cross, "02_粗实线")
        + eng.d_line(x - dx_cross, y_top + dx_cross, x + dx_cross, y_top - dx_cross, "02_粗实线")
        # 动触头斜刀闸：从下端引线起点 (x, y_bot) 斜向左上至 (x - 410, y_top)
        + eng.d_line(x, y_bot, x - 410.0, y_top, "02_粗实线")
    )
    if left_label:
        s += eng.d_text(x - 880, 0.5 * (y_top + y_bot) - 60, left_label, h=left_h, align="center")
    ty = y_top - 120
    for txt in [model, rating]:
        if txt:
            s += eng.d_text(x + 260, ty, txt, h=145, align="left")
            ty -= 360
    return s


def d_brace_horizontal(x1, x2, y, depth=650, layer="02_粗实线"):
    """Draw a horizontal curly brace { pointing downwards from (x1, y) to (x2, y)"""
    xm = 0.5 * (x1 + x2)
    ents = []
    ents.append(eng.d_line(x1, y, x1 + 250, y - depth * 0.45, layer))
    ents.append(eng.d_line(x1 + 250, y - depth * 0.45, xm - 300, y - depth * 0.45, layer))
    ents.append(eng.d_line(xm - 300, y - depth * 0.45, xm, y - depth, layer))
    ents.append(eng.d_line(xm, y - depth, xm + 300, y - depth * 0.45, layer))
    ents.append(eng.d_line(xm + 300, y - depth * 0.45, x2 - 250, y - depth * 0.45, layer))
    ents.append(eng.d_line(x2 - 250, y - depth * 0.45, x2, y, layer))
    return "".join(ents)


def build_sketch_primary_system_dxf():
    ents = []
    ents.append(eng.draw_tongling_primary_frame(
        drawing_title="0.4kV低压配电系统一次图",
        drawing_no="TL-DGS-01DL-01",
        project_name="冬瓜山铜矿低压配电工程",
        sub_project="630A双电源进线·3路400A软起·6路馈线系统",
        stage="施工图",
        date_str="2026.11"
    ))

    # =========================================================================
    # 1. 顶部 3 行开关柜表头 (严格对齐下方各功能区 X 坐标)
    # =========================================================================
    ents.append(eng.d_rect(4500, 35500, 56500, 38800, "02_粗实线"))
    ents.append(eng.d_line(4500, 37700, 56500, 37700))
    ents.append(eng.d_line(4500, 36600, 56500, 36600))
    col_splits = [7500, 17500, 23500, 29500, 35500, 46000]
    for vx in col_splits:
        ents.append(eng.d_line(vx, 35500, vx, 38800))

    ents.append(eng.d_text(6000, 38080, "开关柜编号", h=165, align="center"))
    ents.append(eng.d_text(6000, 36980, "开关柜尺寸", h=165, align="center"))
    ents.append(eng.d_text(6000, 35880, "柜体型号", h=165, align="center"))

    cab_headers = [
        (12500, "1AA1 (双电源进线柜)", "宽×深×高:800×1000×2000", "GKD (固定式)"),
        (20500, "1AA2 (1#软起动柜)", "宽×深×高:800×800×2200", "GKD (固定式)"),
        (26500, "1AA3 (2#软起动柜)", "宽×深×高:800×800×2200", "GKD (固定式)"),
        (32500, "1AA4 (3#软起动柜)", "宽×深×高:800×800×2200", "GKD (固定式)"),
        (40750, "1AA5 (1#馈线电源柜)", "宽×深×高:800×1000×2200", "GGD (固定式)"),
        (51250, "1AA6 (2#馈线电源柜)", "宽×深×高:800×1000×2200", "GGD (固定式)"),
    ]
    for cx, c_no, c_dim, c_type in cab_headers:
        ents.append(eng.d_text(cx, 38080, c_no, h=165, align="center"))
        ents.append(eng.d_text(cx, 36980, c_dim, h=145, align="center"))
        ents.append(eng.d_text(cx, 35880, c_type, h=150, align="center"))

    # =========================================================================
    # 2. 左侧：双电源进线切换单元 (2路 630A 塑壳断路器 -> 汇合下引 -> 右折上引至 TMY)
    #    绝无任何抽屉接插件！断路器上引线停在 y_top=29600，下引线始于 y_bot=28780
    # =========================================================================
    x_in1 = 9200
    x_in2 = 13200
    x_mid = 11200
    x_riser = 16200
    y_bus = 31800
    y_cb_top = 29600
    y_cb_bot = 28780

    for idx_in, (xin, in_lbl, qf_name) in enumerate([
        (x_in1, "I路主电源进线(AC380V)", "QF1"),
        (x_in2, "II路备用电源进线(AC380V)", "QF2")
    ]):
        # 上段进线垂直线：从 34200 精确停在断路器上触点 y_cb_top=29600 (无任何接插件!)
        ents.append(eng.d_line(xin, 34200, xin, y_cb_top, "02_粗实线"))
        ents.append(eng.d_text(xin, 34550, in_lbl, h=150, align="center"))
        ents.append(eng.d_text(xin + 220, 32600, "ZR-YJV-0.6/1kV", h=130))
        ents.append(eng.d_text(xin + 220, 32050, "2(3×185+2×95)", h=130))

        # 标准塑壳断路器符号 (DYDQ0201 / 1107AA): 上触点 × 在 29600，下触点铰接在 28780
        amp_txt = "630A" if idx_in == 0 else "630A"
        amp_h = 260 if idx_in == 0 else 210
        ents.append(draw_mccb_symbol(xin, y_cb_top, y_cb_bot, f"{qf_name}:KFM3X-630S", "In=630A", left_label=amp_txt, left_h=amp_h))

        # 下段垂直线：精确从断路器斜刀闸根部 y_cb_bot=28780 向下连至汇流桥 26200
        ents.append(eng.d_line(xin, y_cb_bot, xin, 26200, "02_粗实线"))

    # 双电源切换水平汇流桥 (x=9200..13200, y=26200)
    ents.append(eng.d_line(x_in1, 26200, x_in2, 26200, "02_粗实线"))
    ents.append(eng.d_circle(x_mid, 26200, 75, "02_粗实线"))
    ents.append(eng.d_text(x_mid, 26550, "CAP3-630/3 双电源切换", h=145, align="center"))

    # 从汇流桥中点 (x_mid=11200, y=26200) 向下引至底部水平折线 (y=19200)
    ents.append(eng.d_line(x_mid, 26200, x_mid, 19200, "02_粗实线"))
    ents.append(eng.prim_ct3(x_mid, 24000, "BH-0.66 800/5"))
    ents.append(eng.d_rect(x_mid - 1750, 22100, x_mid - 650, 22750))
    ents.append(eng.d_text(x_mid - 1200, 22320, "Wh", h=150, align="center"))
    ents.append(eng.d_text(x_mid - 1200, 21700, "多功能表", h=135, align="center"))
    ents.append(eng.d_rect(x_mid - 1750, 20300, x_mid - 450, 20950))
    ents.append(eng.d_text(x_mid - 1100, 20520, "JGM510D-2", h=135, align="center"))
    ents.append(eng.d_line(x_mid - 450, 20625, x_mid, 20625))

    # 底部水平折线 (x_mid=11200 -> x_riser=16200, y=19200) 及向上引至主母线 TMY (y=31800)
    ents.append(eng.d_line(x_mid, 19200, x_riser, 19200, "02_粗实线"))
    ents.append(eng.d_line(x_riser, 19200, x_riser, y_bus, "02_粗实线"))
    ents.append(eng.d_circle(x_riser, y_bus, 80, "02_粗实线"))
    ents.append(eng.d_text(x_riser - 350, 25500, "母线上引铜排", h=145, align="right"))

    # =========================================================================
    # 3. 顶部水平主母线 TMY (x=16200..54800, y=31800)
    # =========================================================================
    ents.append(eng.d_line(x_riser, y_bus, 54800, y_bus, "02_粗实线"))
    ents.append(eng.d_line(x_riser, y_bus + 55, 54800, y_bus + 55, "02_粗实线"))
    ents.append(eng.d_text(26500, y_bus + 420, "TMY  [主母线: TMY-4(60×5)+1×(30×5)]", h=230, align="center"))

    # =========================================================================
    # 4. 中部：3 路 400A 软起动器 (RQ) 电动机控制支路 (1AA2 ~ 1AA4)
    #    严格还原草图：TMY 下引 -> 400A 塑壳断路器 -> [RQ] 方框 -> (M) 电动机圆圈 (无接插件!)
    # =========================================================================
    rq_branches = [
        (20500, "400",  "QF3:KFM3X-400S", "In=400A", "1RQ", "ICM2-110-AS(110kW)", "旁路:KFC3-330", "WP1", "M1", "110kW", "1#矿山主排水泵电机"),
        (26500, "400",  "QF4:KFM3X-400S", "In=400A", "2RQ", "ICM2-110-AS(110kW)", "旁路:KFC3-330", "WP2", "M2", "110kW", "2#矿山主排水泵电机"),
        (32500, "400A", "QF5:KFM3X-400S", "In=400A", "3RQ", "ICM2-110-AS(110kW)", "旁路:KFC3-330", "WP3", "M3", "110kW", "3#矿山主排水泵(备用)"),
    ]

    for bx, sketch_amp, qf_lbl, in_lbl, rq_code, rq_model, bp_lbl, wp_no, m_code, m_kw, m_name in rq_branches:
        # 从主母线 TMY (31800) 垂直引下，精确停在断路器上触点 y_cb_top=29600
        ents.append(eng.d_circle(bx, y_bus, 75, "02_粗实线"))
        ents.append(eng.d_line(bx, y_bus, bx, y_cb_top, "02_粗实线"))

        # 标准塑壳断路器符号 (DYDQ0201 / 1107AA): 上触点 × 在 29600，下触点铰接在 28780
        ents.append(draw_mccb_symbol(bx, y_cb_top, y_cb_bot, qf_lbl, in_lbl, left_label=sketch_amp, left_h=210))

        # 从断路器下触点 (28780) 垂直引至 [RQ] 软起动器顶部 (24800)
        ents.append(eng.d_line(bx, y_cb_bot, bx, 24800, "02_粗实线"))
        ents.append(eng.prim_ct3(bx, 26800, "BH-0.66 400/5"))

        # [RQ] 软起动器矩形框 (x=bx-1200..bx+1200, y=22400..24800)
        ents.append(eng.d_rect(bx - 1200, 22400, bx + 1200, 24800, "02_粗实线"))
        ents.append(eng.d_line(bx - 1200, 23400, bx + 1200, 23400))
        ents.append(eng.d_text(bx, 23950, f"RQ ({rq_code}软起动器)", h=180, align="center"))
        ents.append(eng.d_text(bx, 22780, rq_model, h=140, align="center"))
        ents.append(eng.d_text(bx + 1350, 23600, bp_lbl, h=135, align="left"))

        # 从 [RQ] 底部 (22400) 垂直引至电动机圆圈顶部 (18200) —— 无任何接插件！
        ents.append(eng.d_line(bx, 22400, bx, 18200, "02_粗实线"))
        ents.append(eng.d_text(bx + 220, 20400, f"{wp_no} ZR-YJV-0.6/1kV", h=130))
        ents.append(eng.d_text(bx + 220, 19850, "3×120+2×70", h=130))

        # 电动机圆圈 (M) centered at (bx, 17350), radius=850 (y=16500..18200)
        ents.append(eng.d_circle(bx, 17350, 850, "02_粗实线"))
        ents.append(eng.d_text(bx, 17180, "M", h=320, align="center"))
        ents.append(eng.d_text(bx - 1300, 17200, m_code, h=165, align="center"))

    # =========================================================================
    # 5. 右侧：6 路馈线塑壳断路器支路 + 大括号标注“其它电源柜” (1AA5 ~ 1AA6)
    #    严格还原草图右侧：TMY 下引 -> 标准塑壳断路器 -> 馈出竖线 -> 大括号 { “其它电源柜” (无接插件!)
    # =========================================================================
    feeder_branches = [
        (37250, "QF6",  "KFM3X-250S", "In=160A", "200/5", "WP4", "ZR-YJV 3×70+2×35", "55kW", "1#其它电源柜"),
        (40750, "QF7",  "KFM3X-250S", "In=160A", "200/5", "WP5", "ZR-YJV 3×70+2×35", "55kW", "2#其它电源柜"),
        (44250, "QF8",  "KFM3X-100S", "In=100A", "",      "WP6", "ZR-YJV 3×35+2×16", "37kW", "3#其它电源柜"),
        (47750, "QF9",  "KFM3X-100S", "In=100A", "",      "WP7", "ZR-YJV 3×35+2×16", "37kW", "4#其它电源柜"),
        (51250, "QF10", "KFM3X-100S", "In=63A",  "",      "WP8", "ZR-YJV 4×25+1×16", "22kW", "5#其它电源柜"),
        (54750, "QF11", "KFM3X-100S", "In=63A",  "",      "WP9", "ZR-YJV 4×25+1×16", "备用", "6#其它电源柜(备)"),
    ]

    for fx, qf_no, qf_mod, qf_in, ct_str, wp_code, cab_spec, f_kw, f_dest in feeder_branches:
        # 从主母线 TMY (31800) 垂直引下，精确停在塑壳断路器上触点 y_cb_top=29600 (无任何接插件!)
        ents.append(eng.d_circle(fx, y_bus, 75, "02_粗实线"))
        ents.append(eng.d_line(fx, y_bus, fx, y_cb_top, "02_粗实线"))

        # 标准塑壳断路器符号 (DYDQ0201 / 1107AA)
        ents.append(draw_mccb_symbol(fx, y_cb_top, y_cb_bot, f"{qf_no}:{qf_mod}", qf_in))

        # 从断路器下触点 (28780) 垂直引下至 y=20600 (无任何接插件!)
        ents.append(eng.d_line(fx, y_cb_bot, fx, 20600, "02_粗实线"))
        if ct_str:
            ct_y = 26800 if qf_no == "QF6" else 25300
            ents.append(eng.prim_ct1(fx, ct_y, ct_str))

        ents.append(eng.d_text(fx + 180, 21800, wp_code, h=130))
        ents.append(eng.d_text(fx + 180, 21250, cab_spec, h=120))

    # Horizontal curly brace { under the 6 feeder branches (x=36800..55200, y=19600) + “其它电源柜”
    ents.append(d_brace_horizontal(36800, 55200, 19600, depth=650, layer="02_粗实线"))
    ents.append(eng.d_text(46000, 17650, "其它电源柜", h=340, align="center"))
    ents.append(eng.d_text(46000, 16900, "(由1AA5、1AA6两台GGD固定式低压馈线柜分6路馈出至现场各分配电柜)", h=150, align="center"))

    # =========================================================================
    # 6. 底部 PE 接地母排与 2 行全对齐负荷表 (x=4500..56500, y=12600..14800)
    # =========================================================================
    ents.append(eng.d_line(7500, 15500, 34500, 15500, ltype="DASHED"))
    ents.append(eng.d_text(9200, 15720, "PE接地铜排 TMY-50×5", h=150))

    ents.append(eng.d_rect(4500, 12600, 56500, 14800, "02_粗实线"))
    ents.append(eng.d_line(4500, 13700, 56500, 13700))

    btm_splits = [7500, 17500, 23500, 29500, 35500, 39000, 42500, 46000, 49500, 53000]
    for vx in btm_splits:
        ents.append(eng.d_line(vx, 12600, vx, 14800))

    ents.append(eng.d_text(6000, 14080, "设备功率", h=165, align="center"))
    ents.append(eng.d_text(6000, 12980, "设备名称", h=165, align="center"))

    ents.append(eng.d_text(12500, 14080, "In=630A (双电源)", h=155, align="center"))
    ents.append(eng.d_text(12500, 12980, "I/II路进线及双电源切换", h=150, align="center"))

    for bx, _, _, _, _, _, _, _, _, m_kw, m_name in rq_branches:
        ents.append(eng.d_text(bx, 14080, m_kw, h=160, align="center"))
        ents.append(eng.d_text(bx, 12980, m_name, h=145, align="center"))

    for fx, _, _, _, _, _, _, f_kw, f_dest in feeder_branches:
        ents.append(eng.d_text(fx, 14080, f_kw, h=150, align="center"))
        ents.append(eng.d_text(fx, 12980, f_dest, h=130, align="center"))

    # =========================================================================
    # 7. 图名双横线与设计说明 (铜陵有色设计院一次图标准规范)
    # =========================================================================
    ents.append(eng.d_text(28500, 9460, "0.4kV低压配电系统一次图 (手绘草图标准转化)", h=280, align="center"))
    ents.append(eng.d_line(23800, 9200, 33200, 9200, layer="02_粗实线"))
    ents.append(eng.d_line(23800, 9070, 33200, 9070, layer="01_细实线"))

    notes = [
        "设计说明（依据手绘草图及冬瓜山铜矿配电项目技术规范编制）：",
        "1. 进线单元（1AA1）：采用两路 630A 塑壳断路器（KFM3X-630S/3300，固定式无接插件）进线，经双电源切换装置（CAP3-630/3）汇流后上引至水平主母线 TMY；",
        "2. 主母线（TMY）：水平主母排采用 TMY-4(60×5)+1×(30×5)，贯穿软起动柜（1AA2~1AA4）及低压馈线电源柜（1AA5~1AA6）；",
        "3. 软起动支路（3路）：每路配置 400A 塑壳断路器（KFM3X-400S/3300）、软起动器 RQ（ICM2-110-AS，配旁路接触器 KFC3-330），驱动 3 台 110kW 水泵电机（M1~M3）；",
        "4. 其它电源柜馈线（6路）：由主母线分出 6 路固定式塑壳断路器（2×160A + 2×100A + 2×63A），分别馈出至现场 1#~6# 其它电源柜。"
    ]
    for idx, line in enumerate(notes):
        ents.append(eng.d_text(4500, 7400 - idx * 780, line, h=155))

    return "".join(ents)


if __name__ == "__main__":
    dxf_name = "手绘草图转化_0.4kV双电源630A与3路400A软起及6路馈线一次系统图.dxf"
    dxf_path = OUT_DIR / dxf_name
    png_path = OUT_DIR / (dxf_path.stem + ".png")
    pdf_path = OUT_DIR / (dxf_path.stem + ".pdf")

    dxf_str = build_sketch_primary_system_dxf()
    eng.save_dxf_page(dxf_str, dxf_path)

    res = eng.audit_dxf_strict(dxf_path)
    overlaps = res["defects"]["text_text_overlaps"]
    collisions = res["defects"]["text_line_collisions"]
    print(f"[AUDIT] {dxf_name} | overlaps={len(overlaps)} | collisions={len(collisions)} | blocks={res['stats']['blocks']}")
    if overlaps:
        print("   OVERLAPS:", overlaps[:10])
    if collisions:
        print("   COLLISIONS:", collisions[:10])

    fig, ax = plt.subplots(figsize=(16.54, 11.69))
    eng.render_eplan_page(dxf_path, ax)
    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    fig.savefig(str(png_path), dpi=180)
    with PdfPages(pdf_path) as pdf:
        pdf.savefig(fig)
    plt.close(fig)

    # Also render a zoomed-in verification image of QF1 (630A), QF3 (400A), and QF6 (160A)
    fig2, axes = plt.subplots(1, 3, figsize=(15, 6))
    regions = [
        ("Fixed QF1 (630A): 标准塑壳+无接插件", (7500, 11500), (26000, 34800)),
        ("Fixed QF3 (400A): 标准塑壳+无接插件", (19000, 23000), (22000, 32500)),
        ("Fixed QF6 (160A): 标准塑壳+无接插件", (35800, 39800), (20000, 32500)),
    ]
    for ax_z, (title, xlim, ylim) in zip(axes, regions):
        eng.render_eplan_page(dxf_path, ax_z)
        ax_z.set_xlim(*xlim)
        ax_z.set_ylim(*ylim)
        ax_z.set_aspect("equal")
        ax_z.set_title(title, fontproperties=eng.CJK_FP, fontsize=11)
    plt.tight_layout()
    zoom_path = str(OUT_DIR / "fixed_cb_zoom.png")
    fig2.savefig(zoom_path, dpi=150)
    plt.close(fig2)
    print("Saved PNG, PDF, and zoom:", png_path, pdf_path, zoom_path)
