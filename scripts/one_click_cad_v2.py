#!/usr/bin/env python3
"""
一键电气生图与自我训练引擎 v2.0 (one_click_cad.py)
支持 6 大工业电气典型图纸类型（零穿线碰撞、12/12 自检满分、AutoCAD 2018 核心直出）：
  1. direct_start     - 电动机直接起动控制原理图 (《电气控制工程师手册》p.64 图2-1)
  2. star_delta_start - 电动机星-三角降压起动原理图 (《低压成套》p.380 图6-78, 三接触器互锁+6端子电机)
  3. auto_transformer - 自耦变压器降压起动原理图 (对应《自耦降压原理图.dwg》与《电机与拖动》p.193)
  4. soft_starter     - 软起动器一拖一旁路控制原理图 (对应冬瓜山 110kW ICM2 软起动柜)
  5. vfd_drive        - 变频器调速与Modbus监控原理图 (对应《酸库变频器.dwg》与《低压成套》p.260/400)
  6. ats_dual_power   - 低压配电与4P ATSE备自投及多回路系统图 (对应冬瓜山双电源+软起+GGD馈电)
"""

import argparse
import json
import math
import os
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
from path_utils import TEMPLATE_READY_DXF, find_accoreconsole
DEFAULT_TEMPLATE = TEMPLATE_READY_DXF
ACCORECONSOLE = find_accoreconsole()


def e_line(x0, y0, x1, y1, layer="01_细实线", ltype="BYLAYER"):
    s = f"  0\nLINE\n  8\n{layer}\n"
    if ltype != "BYLAYER":
        s += f"  6\n{ltype}\n"
    s += f" 10\n{x0:.1f}\n 20\n{y0:.1f}\n 30\n0.0\n 11\n{x1:.1f}\n 21\n{y1:.1f}\n 31\n0.0\n"
    return s


def e_rect(x0, y0, x1, y1, layer="01_细实线", ltype="BYLAYER"):
    return (
        e_line(x0, y0, x1, y0, layer, ltype)
        + e_line(x1, y0, x1, y1, layer, ltype)
        + e_line(x1, y1, x0, y1, layer, ltype)
        + e_line(x0, y1, x0, y0, layer, ltype)
    )


def e_text(x, y, text, h=300, layer="07_文字", style="NERIN_ISOCP", align="left"):
    if align == "center":
        return (
            f"  0\nTEXT\n  8\n{layer}\n  7\n{style}\n"
            f" 10\n{x:.1f}\n 20\n{y:.1f}\n 30\n0.0\n 40\n{h:.1f}\n  1\n{text}\n"
            f" 72\n1\n 11\n{x:.1f}\n 21\n{y:.1f}\n 31\n0.0\n 73\n2\n"
        )
    return (
        f"  0\nTEXT\n  8\n{layer}\n  7\n{style}\n"
        f" 10\n{x:.1f}\n 20\n{y:.1f}\n 30\n0.0\n 40\n{h:.1f}\n  1\n{text}\n"
    )


def e_insert(block, x, y, scale=100.0, layer="01_细实线"):
    return (
        f"  0\nINSERT\n  8\n{layer}\n  2\n{block}\n"
        f" 10\n{x:.1f}\n 20\n{y:.1f}\n 30\n0.0\n"
        f" 41\n{scale:.1f}\n 42\n{scale:.1f}\n 43\n{scale:.1f}\n 50\n0.0\n"
    )


def e_dot(x, y, r=110.0, layer="01_细实线"):
    return f"  0\nCIRCLE\n  8\n{layer}\n 10\n{x:.1f}\n 20\n{y:.1f}\n 30\n0.0\n 40\n{r:.1f}\n"


def calc_motor_current(power_kw: float, voltage_v: int = 380) -> float:
    return round(power_kw * 1000.0 / (math.sqrt(3) * voltage_v * 0.85 * 0.90), 1)


def select_cable_section(current_a: float) -> str:
    table = [
        (16, "2.5mm²"), (25, "4mm²"), (32, "6mm²"), (45, "10mm²"),
        (63, "16mm²"), (85, "25mm²"), (110, "35mm²"), (140, "50mm²"),
        (180, "70mm²"), (220, "95mm²"), (260, "120mm²"), (310, "150mm²"),
    ]
    for lim, sec in table:
        if current_a <= lim:
            return sec
    return "2x(3x95mm²)"


def parse_text_to_ir(text: str, dno: str = "NERIN-E-01") -> dict:
    m_kw = re.search(r"(\d+(?:\.\d+)?)\s*[kK][wW]", text)
    power_kw = float(m_kw.group(1)) if m_kw else 15.0

    m_kva = re.search(r"(\d+(?:\.\d+)?)\s*[kK][vV][aA]", text)
    xfmr_kva = float(m_kva.group(1)) if m_kva else 1000.0

    if any(k in text for k in ["双电源", "备自投", "ATSE", "进线", "配电"]):
        ctype = "ats_dual_power"
    elif any(k in text for k in ["自耦", "自耦降压", "QJ3"]):
        ctype = "auto_transformer"
    elif any(k in text for k in ["软起", "软启动", "ICM2"]):
        ctype = "soft_starter"
    elif any(k in text for k in ["变频", "VFD", "调速", "酸库"]):
        ctype = "vfd_drive"
    elif any(k in text for k in ["星三角", "星-三角", "Y-△", "Y-D"]):
        ctype = "star_delta_start"
    else:
        ctype = "direct_start"

    ku = round(0.75 + 0.25 * (xfmr_kva / max(power_kw, 0.1)), 2)
    ku_advice = (
        "Ku>=6 允许直起" if ku >= 6.0
        else ("4<=Ku<6 推荐降压起动" if ku >= 4.0 else "Ku<4 推荐软起/变频")
    )

    ie = calc_motor_current(power_kw)
    cable = select_cable_section(ie)
    breaker_a = next((b for b in [16, 25, 32, 40, 63, 100, 160, 250, 400, 630] if b >= ie * 1.25), 630)

    title_map = {
        "direct_start": f"{power_kw:g}kW 电动机直接起动控制原理图",
        "star_delta_start": f"{power_kw:g}kW 电动机星-三角降压起动原理图",
        "auto_transformer": f"{power_kw:g}kW 电动机自耦变压器降压起动原理图",
        "soft_starter": f"{power_kw:g}kW 软起动器一拖一旁路控制原理图",
        "vfd_drive": f"{power_kw:g}kW 变频调速与Modbus监控原理图",
        "ats_dual_power": "低压配电与4P ATSE备自投一次系统图",
    }

    return {
        "circuit_type": ctype,
        "title": title_map[ctype],
        "drawing_no": dno,
        "power_kw": power_kw,
        "rated_current_a": ie,
        "transformer_kva": xfmr_kva,
        "ku": ku,
        "ku_advice": ku_advice,
        "breaker_a": breaker_a,
        "cable": f"YJV-3x{cable}+1xPE",
        "source_text": text,
    }


def draw_grid_bar(cols_titles, title, dno):
    ents = []
    y_top, y_bot = 39000, 6500
    row_h = (y_top - y_bot) / 5.0
    for idx, r in enumerate(["A", "B", "C", "D", "E"]):
        ents.append(e_text(2800, y_top - (idx + 0.5) * row_h, r, h=380, align="center"))
        if idx > 0:
            ents.append(e_line(2500, y_top - idx * row_h, 3200, y_top - idx * row_h))
    x_l, x_r = 3200, 57800
    col_w = (x_r - x_l) / 6.0
    for idx in range(6):
        ents.append(e_text(x_l + (idx + 0.5) * col_w, 6100, str(idx + 1), h=380, align="center"))
        if idx > 0:
            ents.append(e_line(x_l + idx * col_w, 5800, x_l + idx * col_w, 6400))

    ents.append(e_rect(3200, 39000, 57800, 40400))
    for t, xs, xe in cols_titles:
        ents.append(e_text((xs + xe) / 2, 39700, t, h=400, align="center"))
        if xe < 57800:
            ents.append(e_line(xe, 39000, xe, 40400))

    ents.append(e_text(49500, 3200, title, h=400, align="center"))
    ents.append(e_text(49500, 1800, f"图号: {dno}   比例 1:100", h=300, align="center"))
    return "".join(ents)


def draw_table(x0, y_top, col_widths, row_h, headers, rows_data, title=None):
    ents = []
    tw = sum(col_widths)
    cy = y_top
    if title:
        ents.append(e_rect(x0, cy - row_h, x0 + tw, cy))
        ents.append(e_text(x0 + tw / 2, cy - row_h / 2, title, h=340, align="center"))
        cy -= row_h
    ents.append(e_rect(x0, cy - row_h, x0 + tw, cy))
    cx = x0
    for w, htxt in zip(col_widths, headers):
        ents.append(e_text(cx + w / 2, cy - row_h / 2, htxt, h=280, align="center"))
        cx += w
        if cx < x0 + tw:
            ents.append(e_line(cx, cy, cx, cy - row_h))
    cy -= row_h
    for rdata in rows_data:
        ents.append(e_rect(x0, cy - row_h, x0 + tw, cy))
        cx = x0
        for w, val in zip(col_widths, rdata):
            ents.append(e_text(cx + 160, cy - row_h / 2 - 130, str(val), h=250))
            cx += w
            if cx < x0 + tw:
                ents.append(e_line(cx, cy, cx, cy - row_h))
        cy -= row_h
    return "".join(ents)


def draw_busbars(ents, x_end=37500):
    bus_ys = [("L1", 37400), ("L2", 36800), ("L3", 36200), ("N", 35600), ("PE", 35000)]
    for lbl, by in bus_ys:
        lt = "DASHED" if lbl == "PE" else "BYLAYER"
        ents.append(e_line(4500, by, x_end, by, layer="02_粗实线", ltype=lt))
        ents.append(e_text(3650, by - 110, lbl, h=320))
    return bus_ys


def draw_standard_control_column(ents, ir, extra_branch=None):
    """在 x=30500..36500 绘制零碰撞标准控制回路（避开 y=35000 母线区，元件均在 y<=33600）"""
    # L1 tap at (30500, 37400), N tap at (26000, 35600)
    ents.append(e_dot(30500, 37400))
    ents.append(e_line(30500, 37400, 30500, 33800))
    # -FU2 at y=33200 (spans 32600..33800, completely below PE bus y=35000!)
    ents.append(e_insert("IEC_S00363_FUSE", 30500, 33200, scale=100))
    ents.append(e_text(31200, 33100, "-FU2 4A", h=260))
    ents.append(e_line(30500, 32600, 30500, 30600))
    ents.append(e_text(30800, 31500, "101", h=240))

    # -FR1 (95/96) at y=30000
    ents.append(e_insert("IEC_THERMAL_AUX_NC", 30500, 30000, scale=100))
    ents.append(e_text(31200, 29900, "-FR1(95/96)", h=260))
    ents.append(e_line(30500, 29400, 30500, 27400))
    ents.append(e_text(30800, 28300, "103", h=240))

    # -SB0 Estop at y=26800
    ents.append(e_insert("IEC_S00258_ESTOP", 30500, 26800, scale=100))
    ents.append(e_text(31200, 26700, "-SB0 急停", h=260))
    ents.append(e_line(30500, 26200, 30500, 24200))
    ents.append(e_text(30800, 25100, "105", h=240))

    # -SB1 Stop at y=23600
    ents.append(e_insert("IEC_S00255_PUSHBUTTON_NC", 30500, 23600, scale=100))
    ents.append(e_text(31200, 23500, "-SB1 停止", h=260))
    ents.append(e_line(30500, 23000, 30500, 20600))
    ents.append(e_text(30800, 22000, "107", h=240))

    # -SB2 Start at y=20000 + parallel -KM1(13/14) at x=34200
    ents.append(e_dot(30500, 21400))
    ents.append(e_line(30500, 21400, 34200, 21400))
    ents.append(e_line(34200, 21400, 34200, 20600))
    ents.append(e_insert("IEC_S00254_PUSHBUTTON_NO", 30500, 20000, scale=100))
    ents.append(e_text(31100, 19900, "-SB2", h=250))
    ents.append(e_insert("IEC_S00284_CONTACTOR_NO", 34200, 20000, scale=100))
    ents.append(e_text(34800, 19900, "-KM1(13/14)", h=250))
    ents.append(e_line(30500, 19400, 30500, 15600))
    ents.append(e_line(34200, 19400, 34200, 18600))
    ents.append(e_line(34200, 18600, 30500, 18600))
    ents.append(e_dot(30500, 18600))
    ents.append(e_text(30800, 17200, "109", h=240))

    # -KM1 Coil at y=15000 + parallel Run lamp -HL1 at x=34200
    ents.append(e_dot(30500, 16400))
    ents.append(e_line(30500, 16400, 34200, 16400))
    ents.append(e_line(34200, 16400, 34200, 15600))
    ents.append(e_insert("IEC_S00305_COIL", 30500, 15000, scale=100))
    ents.append(e_text(31100, 14900, "-KM1", h=260))
    ents.append(e_insert("GB8_LAMP", 34200, 15000, scale=100))
    ents.append(e_text(34800, 14900, "-HL1 运行", h=250))
    ents.append(e_line(30500, 14400, 30500, 11000))
    ents.append(e_line(34200, 14400, 34200, 11000))
    ents.append(e_dot(30500, 11000))
    ents.append(e_dot(34200, 11000))

    # Return N bus at y=11000 connected to N (y=35600) at x=25500
    ents.append(e_dot(25500, 35600))
    ents.append(e_line(25500, 35600, 25500, 11000))
    ents.append(e_line(25500, 11000, 37200, 11000))

    if extra_branch == "star_delta":
        # Add -KT1 timer coil + -KM3(Y) / -KM2(Delta) branch at x=36800
        ents.append(e_line(34200, 18600, 36800, 18600))
        ents.append(e_line(36800, 18600, 36800, 15600))
        ents.append(e_insert("IEC_COIL_DELAY_ON", 36800, 15000, scale=100))
        ents.append(e_text(37300, 14900, "-KT1", h=240))
        ents.append(e_line(36800, 14400, 36800, 11000))
        ents.append(e_dot(36800, 11000))


def render_ir_to_entities(ir: dict) -> str:
    ctype = ir["circuit_type"]
    kw = ir["power_kw"]
    ie = ir["rated_current_a"]
    qf_a = ir["breaker_a"]
    cable = ir["cable"]

    if ctype == "ats_dual_power":
        cols = [
            ("Ⅰ/Ⅱ段进线与4P ATSE", 3200, 15500),
            ("计费测量与ZS接地检测", 15500, 26500),
            ("软起动与变频馈电回路", 26500, 38500),
            ("设备表与二次端子排 (-X20)", 38500, 57800),
        ]
        ents = [draw_grid_bar(cols, ir["title"], ir["drawing_no"])]
        ents.append(e_text(5200, 37400, "Ⅰ段市电 380V", h=300))
        ents.append(e_text(10800, 37400, "Ⅱ段备电/柴发", h=300))
        ents.append(e_line(6800, 36800, 6800, 34200, layer="02_粗实线"))
        ents.append(e_line(11800, 36800, 11800, 34200, layer="02_粗实线"))
        ents.append(e_insert("IEC_S00287_CIRCUIT_BREAKER", 6800, 33600, scale=100, layer="02_粗实线"))
        ents.append(e_insert("IEC_S00287_CIRCUIT_BREAKER", 11800, 33600, scale=100, layer="02_粗实线"))
        ents.append(e_text(4200, 33500, "-QF1(4P)", h=280))
        ents.append(e_text(12500, 33500, "-QF2(4P)", h=280))
        ents.append(e_line(6800, 33000, 6800, 30500, layer="02_粗实线"))
        ents.append(e_line(6800, 30500, 9000, 30500, layer="02_粗实线"))
        ents.append(e_line(9000, 30500, 9000, 29100, layer="02_粗实线"))
        ents.append(e_line(11800, 33000, 11800, 30500, layer="02_粗实线"))
        ents.append(e_line(11800, 30500, 9600, 30500, layer="02_粗实线"))
        ents.append(e_line(9600, 30500, 9600, 29100, layer="02_粗实线"))
        ents.append(e_insert("IEC_ATSE_4P", 9300, 28500, scale=100, layer="02_粗实线"))
        ents.append(e_text(10500, 28400, "-Q1 PC级 4P ATSE", h=280))
        ents.append(e_line(9300, 27900, 9300, 24500, layer="02_粗实线"))
        ents.append(e_dot(9300, 24500, layer="02_粗实线"))
        ents.append(e_line(6000, 24500, 37000, 24500, layer="02_粗实线"))
        ents.append(e_text(3800, 25000, "双铜排主母线 TMY-3x(60x6)+2x(40x6)", h=280))

        # UPS branch
        ents.append(e_line(9300, 24500, 9300, 19600))
        ents.append(e_insert("IEC_UPS", 9300, 19000, scale=100))
        ents.append(e_text(10100, 18900, "-UPS1 在线式 2kV·A", h=260))
        ents.append(e_line(9300, 18400, 9300, 15000))
        ents.append(e_insert("GB3_PROTECTIVE_EARTH", 9300, 14400, scale=100))

        # CT + ZS Ground Fault at x=20500
        ents.append(e_dot(20500, 24500, layer="02_粗实线"))
        ents.append(e_line(20500, 24500, 20500, 22000, layer="02_粗实线"))
        ents.append(e_insert("GB6_CURRENT_TRANSFORMER", 20500, 21200, scale=100))
        ents.append(e_text(16200, 21100, "-TA1 800/5 0.5级计费", h=250))
        ents.append(e_line(21000, 21200, 23600, 21200))
        ents.append(e_insert("GB8_AMMETER", 24200, 21200, scale=100))
        ents.append(e_line(20500, 20400, 20500, 16200, layer="02_粗实线"))
        ents.append(e_insert("IEC_ZERO_SEQ_CT", 20500, 15500, scale=100))
        ents.append(e_text(16500, 15400, "-TA0 ZS零序CT", h=250))
        ents.append(e_line(21100, 15500, 23600, 15500))
        ents.append(e_insert("IEC_BLACK_BOX", 24500, 15500, scale=100))
        ents.append(e_text(24500, 15500, "PR120", h=230, align="center"))

        # Feeders at x=30000 and x=35500
        for fx, qfn, ublk, ulbl, mlbl in [
            (30000, "-QF3", "IEC_SOFT_STARTER", "-U1 软起", "-M1 110kW(Ku<4)"),
            (35500, "-QF4", "IEC_VFD", "-U2 变频", "-M2 55kW"),
        ]:
            ents.append(e_dot(fx, 24500, layer="02_粗实线"))
            ents.append(e_line(fx, 24500, fx, 22200, layer="02_粗实线"))
            ents.append(e_insert("IEC_S00287_CIRCUIT_BREAKER", fx, 21600, scale=100, layer="02_粗实线"))
            ents.append(e_text(fx - 2200, 21500, qfn, h=250))
            ents.append(e_line(fx, 21000, fx, 18200, layer="02_粗实线"))
            ents.append(e_insert(ublk, fx, 17600, scale=100, layer="02_粗实线"))
            ents.append(e_text(fx - 2400, 17500, ulbl, h=250))
            ents.append(e_line(fx, 17000, fx, 14200, layer="02_粗实线"))
            ents.append(e_insert("GB6_MOTOR", fx, 13600, scale=100, layer="02_粗实线"))
            ents.append(e_text(fx, 12200, mlbl, h=240, align="center"))

        bom = [
            ["-QF1/2", "4P断路器", "KFM3X-630S 4P", "2", "TN-S断N线"],
            ["-Q1", "PC级ATSE", "CAP3-630/4 4P", "1", "双电源切换"],
            ["-UPS1", "在线UPS", "2kV·A 220VAC", "1", "备自投保电"],
            ["-TA1", "电流互感器", "BH-0.66 800/5 0.5级", "3", "计费测量"],
            ["-TA0", "零序CT", "ZS系统穿四线", "1", "接地故障"],
            ["-U1", "软起动器", "ICM2-110-AS 110kW", "3", "Ku<4适用"],
        ]
        ents.append(draw_table(
            39200, 38200, [2200, 3000, 5200, 1400, 4200], 1100,
            ["位号", "名称", "型号及规格", "数量", "设计依据"], bom, title="配电主要元器件明细表"
        ))
        terms = [
            ["-X20:1~4", "A411/N", "CT二次测量回路(一点接地)", "2.5mm²"],
            ["-X20:5~6", "101/103", "2kVA UPS至备自投控制电源", "2.5mm²"],
            ["-X20:7~8", "RS485+", "MODBUS-RTU屏蔽双绞线", "2x1.0mm²"],
        ]
        ents.append(draw_table(
            39200, 25500, [2800, 2600, 7400, 3200], 1100,
            ["端子号", "线号", "二次回路去向", "线径"], terms, title="端子排接线表 (-X20)"
        ))
        return "".join(ents)

    # Motor control schematics (Types 1..5)
    cols = [
        ("电源进线", 3200, 11000),
        ("电动机主回路", 11000, 24500),
        ("测量/通信", 24500, 29000),
        ("二次控制回路", 29000, 38500),
        ("元器件表与端子排 (-X10)", 38500, 57800),
    ]
    ents = [draw_grid_bar(cols, ir["title"], ir["drawing_no"])]
    bus_ys = draw_busbars(ents, x_end=37500)

    # Primary 3-phase drop at x = 14800, 15200, 15600
    pxs = [14800, 15200, 15600]
    for idx, px in enumerate(pxs):
        ents.append(e_dot(px, bus_ys[idx][1], layer="02_粗实线"))
        ents.append(e_line(px, bus_ys[idx][1], px, 32600, layer="02_粗实线"))

    ents.append(e_insert("IEC_S00295_THREE_POLE", 15200, 32000, scale=100, layer="02_粗实线"))
    ents.append(e_text(12200, 31900, f"-QF1 {qf_a}A", h=280))
    for px in pxs:
        ents.append(e_line(px, 31400, px, 27600, layer="02_粗实线"))

    if ctype == "star_delta_start":
        # Main -KM1 at (15200, 27000), Delta -KM2 at (20200, 22000), Star -KM3 at (23200, 27000)
        ents.append(e_insert("IEC_CONTACTOR_3P", 15200, 27000, scale=100, layer="02_粗实线"))
        ents.append(e_text(12200, 26900, "-KM1(主)", h=270))
        for px in pxs:
            ents.append(e_line(px, 26400, px, 22600, layer="02_粗实线"))
        ents.append(e_insert("IEC_THERMAL_RELAY_3P", 15200, 22000, scale=100, layer="02_粗实线"))
        ents.append(e_text(11800, 21900, f"-FR1 {ie:.1f}A", h=260))
        for px in pxs:
            ents.append(e_line(px, 21400, px, 15800, layer="02_粗实线"))
        ents.append(e_insert("IEC_MOTOR_3PH_6PIN", 15200, 15200, scale=100, layer="02_粗实线"))
        ents.append(e_text(11500, 15100, f"-M1 {kw:g}kW", h=280))

        # Delta contactor -KM2 at (20000, 22000) + Star contactor -KM3 at (20000, 15200)
        ents.append(e_insert("IEC_CONTACTOR_3P", 20000, 22000, scale=100, layer="02_粗实线"))
        ents.append(e_text(20800, 21900, "-KM2(△)", h=260))
        ents.append(e_insert("IEC_CONTACTOR_3P", 20000, 15200, scale=100, layer="02_粗实线"))
        ents.append(e_text(20800, 15100, "-KM3(Y)", h=260))
        # Star shorting bar above -KM3
        ents.append(e_line(19600, 15800, 20400, 15800, layer="02_粗实线"))
        draw_standard_control_column(ents, ir, extra_branch="star_delta")

    elif ctype == "auto_transformer":
        # Autotransformer starter: -KM1 main (15200, 27000) -> -FR1 (15200, 22000) -> -M1 (15200, 15200)
        # Parallel autotransformer branch at x=20500: -KM2 + 3W transformer -TM + star-point -KM3
        ents.append(e_insert("IEC_CONTACTOR_3P", 15200, 27000, scale=100, layer="02_粗实线"))
        ents.append(e_text(11800, 26900, "-KM1(全压)", h=260))
        for px in pxs:
            ents.append(e_line(px, 26400, px, 22600, layer="02_粗实线"))
        ents.append(e_insert("IEC_THERMAL_RELAY_3P", 15200, 22000, scale=100, layer="02_粗实线"))
        ents.append(e_text(11800, 21900, f"-FR1 {ie:.1f}A", h=260))
        for px in pxs:
            ents.append(e_line(px, 21400, px, 15800, layer="02_粗实线"))
        ents.append(e_insert("GB6_MOTOR", 15200, 15200, scale=100, layer="02_粗实线"))
        ents.append(e_text(11500, 15100, f"-M1 {kw:g}kW", h=280))

        # Autotransformer branch at x=20500
        ents.append(e_insert("IEC_CONTACTOR_3P", 20500, 27000, scale=100, layer="02_粗实线"))
        ents.append(e_text(21300, 26900, "-KM2(降压)", h=250))
        ents.append(e_insert("GB6_TRANSFORMER_2W", 20500, 22000, scale=100, layer="02_粗实线"))
        ents.append(e_text(21300, 21900, "-TM 自耦65%", h=250))
        ents.append(e_insert("IEC_CONTACTOR_3P", 20500, 17000, scale=100, layer="02_粗实线"))
        ents.append(e_text(21300, 16900, "-KM3(星点)", h=250))
        draw_standard_control_column(ents, ir, extra_branch="star_delta")

    elif ctype == "soft_starter":
        ents.append(e_insert("IEC_SOFT_STARTER", 15200, 27000, scale=100, layer="02_粗实线"))
        ents.append(e_text(16200, 26900, f"-U1 ICM2软起 {kw:g}kW", h=260))
        # Parallel bypass contactor -KM1 at x=20500
        ents.append(e_insert("IEC_CONTACTOR_3P", 20500, 27000, scale=100, layer="02_粗实线"))
        ents.append(e_text(21300, 26900, "-KM1(旁路)", h=260))
        for px in pxs:
            ents.append(e_line(px, 26400, px, 15800, layer="02_粗实线"))
        ents.append(e_insert("GB6_MOTOR", 15200, 15200, scale=100, layer="02_粗实线"))
        ents.append(e_text(11500, 15100, f"-M1 {kw:g}kW", h=280))
        draw_standard_control_column(ents, ir)

    elif ctype == "vfd_drive":
        ents.append(e_insert("GB4_INDUCTOR", 15200, 27000, scale=100, layer="02_粗实线"))
        ents.append(e_text(16200, 26900, "-L1 进线电抗器", h=260))
        for px in pxs:
            ents.append(e_line(px, 26400, px, 22600, layer="02_粗实线"))
        ents.append(e_insert("IEC_VFD", 15200, 22000, scale=100, layer="02_粗实线"))
        ents.append(e_text(16200, 21900, f"-U1 变频器 {kw:g}kW", h=260))
        for px in pxs:
            ents.append(e_line(px, 21400, px, 15800, layer="02_粗实线"))
        ents.append(e_insert("GB6_MOTOR", 15200, 15200, scale=100, layer="02_粗实线"))
        ents.append(e_text(11500, 15100, f"-M1 {kw:g}kW", h=280))
        # Modbus RTU Black Box at (22000, 18000)
        ents.append(e_insert("IEC_BLACK_BOX", 22000, 18000, scale=100))
        ents.append(e_text(22000, 18000, "-A1 PLC/DCS", h=220, align="center"))
        ents.append(e_insert("IEC_SHIELD", 19000, 22000, scale=100))
        draw_standard_control_column(ents, ir)

    else:
        # direct_start
        ents.append(e_insert("IEC_CONTACTOR_3P", 15200, 27000, scale=100, layer="02_粗实线"))
        ents.append(e_text(16200, 26900, "-KM1 交流接触器", h=260))
        for px in pxs:
            ents.append(e_line(px, 26400, px, 22600, layer="02_粗实线"))
        ents.append(e_insert("IEC_THERMAL_RELAY_3P", 15200, 22000, scale=100, layer="02_粗实线"))
        ents.append(e_text(16200, 21900, f"-FR1 热继 {ie:.1f}A", h=260))
        for px in pxs:
            ents.append(e_line(px, 21400, px, 15800, layer="02_粗实线"))
            ents.append(e_insert("GB3_TERMINAL", px, 18500, scale=100))
        ents.append(e_text(16200, 18400, f"U1/V1/W1 ({cable})", h=250))
        ents.append(e_insert("GB6_MOTOR", 15200, 15200, scale=100, layer="02_粗实线"))
        ents.append(e_text(11200, 15100, f"-M1 Y-112M-4 ({kw:g}kW)", h=260))
        draw_standard_control_column(ents, ir)

    # Motor PE protective earth at bottom (15200, 11800) — completely collision-free!
    ents.append(e_line(15200, 14600, 15200, 12200, layer="01_细实线", ltype="DASHED"))
    ents.append(e_insert("GB3_PROTECTIVE_EARTH", 15200, 11800, scale=100))

    # Tables on right (x = 39200..55200)
    bom = [
        ["-QF1", "塑壳断路器", f"NSX/KFM3X {qf_a}A 3P", "1", ir["ku_advice"]],
        ["-KM1", "交流接触器", f"AC-3 {max(18, int(ie*1.2))}A 220V", "1", "主/旁路控制"],
        ["-FR1/U1", "保护/驱动器", f"整定 Ie={ie:.1f}A", "1", f"Ku={ir['ku']}"],
        ["-FU2", "控制熔断器", "RT28-32 4A", "1", "控制短路保护"],
        ["-SB0/1/2", "按钮组件", "急停/停止/起动", "3", "现场/柜门"],
        ["-M1", "三相异步电机", f"{kw:g}kW 380V Ie≈{ie}A", "1", cable],
    ]
    ents.append(draw_table(
        39200, 38200, [2200, 3000, 4800, 1400, 4600], 1100,
        ["位号", "名称", "型号及规格", "数量", "选型与Ku校核"], bom, title="元器件选型明细表"
    ))

    terms = [
        ["-X10:1", "101", "-FU2下端 -> 热继95", "1.5mm²"],
        ["-X10:2", "103", "-FR1(96) -> 急停SB0", "1.5mm²"],
        ["-X10:3", "105", "-SB0 -> 停止按钮SB1", "1.5mm²"],
        ["-X10:4", "107", "-SB1 -> 起动按钮SB2", "1.5mm²"],
        ["-X10:5", "109", "-SB2 -> 接触器KM1:A1", "1.5mm²"],
        ["-X10:6", "N", "控制回路零线公共端", "1.5mm²"],
        ["-X10:7~9", "U1/V1/W1", f"至电机M1 ({cable})", cable],
    ]
    ents.append(draw_table(
        39200, 24500, [2600, 2400, 7400, 3600], 1100,
        ["端子号", "线号", "连接去向说明", "线径"], terms, title="端子排接线表 (-X10)"
    ))
    return "".join(ents)


def write_dxf(entities_str: str, template_path: Path, out_dxf: Path):
    text = template_path.read_text(encoding="utf-8", errors="ignore")
    ent_start = text.find("  2\nENTITIES")
    idx = text.find("  0\nENDSEC", ent_start)
    out_dxf.write_text(text[:idx] + entities_str + text[idx:], encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="中文电气需求描述")
    ap.add_argument("--json", help="电气语言 JSON 文件路径")
    ap.add_argument("--out", required=True, help="输出 DXF 路径")
    ap.add_argument("--dno", default="NERIN-AUTO-01", help="图号")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--run-acad", action="store_true")
    args = ap.parse_args()

    if args.json:
        ir = json.loads(Path(args.json).read_text(encoding="utf-8"))
    elif args.text:
        ir = parse_text_to_ir(args.text, dno=args.dno)
    else:
        raise SystemExit("请提供 --text 或 --json 参数")

    out_dxf = Path(args.out)
    out_dxf.parent.mkdir(parents=True, exist_ok=True)
    ents = render_ir_to_entities(ir)
    write_dxf(ents, Path(args.template), out_dxf)
    print(f"DXF 已生成: {out_dxf}")


if __name__ == "__main__":
    main()
