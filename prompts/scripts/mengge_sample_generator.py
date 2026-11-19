#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于《猛哥专用符号库.sdb》真实矢量图元的 EPLAN 工业样图生成器与自审自改闭环引擎 (Round 2 修正版)
================================================================================================
针对首轮 16 项严苛审查与视觉检查发现的 5 项缺陷完成全部修正：
  1. 修正元器件左侧标识符 (`-TAG`) 与中文功能描述 (`desc`) 垂直行距为 340 DXF 单位，彻底消除上下行重叠。
  2. 修正 `MENGGE_设备2~5` 与 `MENGGE_电动阀` 顶部圆圈端子的引脚功能名位置，移至端子圆正下方盒内 `(px, py - 580)`，消除压框顶边。
  3. 修正 `MENGGE_地排10/7/5` 的 PE 保护接地虚线走向，统一改为从底部引脚向右 (`x + 1200`) 引出并上引，彻底避开左侧中文名称。
  4. 修正 S3 `-MOV1` 电动阀第 3 引脚 (`COM`) 出线路径：先向上引出顶框 (`y=17200`) 再折向右侧回 N 线，消除水平穿框。
  5. 修正 S5 与 S6 顶部 `-PE` 母线排布高度至 `y=38600`，消除与 `-CU1` 模块右边框及 DO 继电器上引线的交叉。
"""

import json
import math
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from eplan_cad_engine import (
    OUT_DIR, CJK_FP,
    d_line, d_rect, d_circle, d_arc, d_solid_tri, d_text,
    draw_eplan_frame, eplan_arrow_left_in, eplan_arrow_right, eplan_arrow_down,
    save_dxf_page, render_eplan_page
)
from cad_strict_auditor import audit_dxf_strict

from path_utils import MENGGE_CATALOG_JSON
CATALOG_PATH = MENGGE_CATALOG_JSON
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
MENGGE_SYMS = {s["dxf_block"]: s for s in CATALOG["mengge_custom_symbols"]}


class MengGeSchematicBuilder:
    """支持直接实例化《猛哥专用符号库.sdb》真实矢量图元并自动记录引脚、保护框与外部导线的绘图器"""

    def __init__(self, page_no: int, total_pages: int, title: str, high_level="= 云冶矿业", location_code="+ 调度室PLC柜", project_name="云冶矿业供水自动化控制系统"):
        self.ents = [draw_eplan_frame(page_no, total_pages, title, high_level=high_level, location_code=location_code, project_name=project_name)]
        self.placed_pins = []
        self.protected_boxes = []
        self.external_wires = []

    def add(self, dxf_str: str):
        self.ents.append(dxf_str)

    def wire(self, x0, y0, x1, y1, thick=False, dashed=False, is_internal=False):
        layer = "02_粗实线" if thick else "01_细实线"
        ltype = "DASHED" if dashed else "BYLAYER"
        self.ents.append(d_line(x0, y0, x1, y1, layer=layer, ltype=ltype))
        if not is_internal and not dashed:
            self.external_wires.append((x0, y0, x1, y1))

    def node(self, x, y):
        self.ents.append(d_circle(x, y, 85, layer="02_粗实线"))

    def box(self, name, x0, y0, x1, y1, thick=False, dashed=False, protect=True):
        layer = "02_粗实线" if thick else "01_细实线"
        ltype = "DASHED" if dashed else "BYLAYER"
        self.ents.append(d_rect(x0, y0, x1, y1, layer=layer, ltype=ltype))
        if protect and not dashed:
            self.protected_boxes.append((name, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

    def label(self, x, y, text, h=220, align="left"):
        self.ents.append(d_text(x, y, str(text), h=h, align=align))

    def place_mengge_symbol(
        self,
        block_name: str,
        x: float,
        y: float,
        scale: float = 150.0,
        tag: str = "",
        desc: str = "",
        cross_ref: str = "",
        pin_labels: dict = None,
        thick: bool = False,
        track_pins: list = None,
        protect_box: bool = False,
        tag_offset_x: float = None,
        tag_offset_y: float = 220.0,
    ) -> dict:
        """
        在 (x, y) 处按比例 `scale` (默认 1mm = 150 DXF 单位) 精确绘制《猛哥专用符号库.sdb》中的矢量图元，
        并返回各引脚的绝对坐标字典 `{pin_index: (px, py)}`。
        """
        sym = MENGGE_SYMS[block_name]
        layer = "02_粗实线" if thick else "01_细实线"
        xs, ys = [], []
        is_top_circle_macro = block_name in ("MENGGE_设备2", "MENGGE_设备3", "MENGGE_设备4", "MENGGE_设备5", "MENGGE_电动阀")

        for p in sym["primitives"]:
            lt = "DASHED" if p.get("dashed") else "BYLAYER"
            ptype = p["type"]
            if ptype == "line":
                x1, y1 = x + p["x1"] * scale, y + p["y1"] * scale
                x2, y2 = x + p["x2"] * scale, y + p["y2"] * scale
                self.ents.append(d_line(x1, y1, x2, y2, layer=layer, ltype=lt))
                xs.extend([x1, x2])
                ys.extend([y1, y2])
            elif ptype == "rect":
                x1, y1 = x + p["x1"] * scale, y + p["y1"] * scale
                x2, y2 = x + p["x2"] * scale, y + p["y2"] * scale
                self.ents.append(d_rect(x1, y1, x2, y2, layer=layer, ltype=lt))
                xs.extend([x1, x2])
                ys.extend([y1, y2])
                if protect_box and not p.get("dashed"):
                    # For top-entry macro boxes (where pins are at y+2.0mm inside top edge y+4.0mm),
                    # protect the box body below y+2.0mm so top entry wires to y+2.0mm are legal
                    ymax_prot = (y + 2.0 * scale) if is_top_circle_macro else ((y + 11.0 * scale) if block_name == "MENGGE_Ping" else max(y1, y2))
                    self.protected_boxes.append((f"{block_name}:{tag}", min(x1, x2), min(y1, y2), max(x1, x2), ymax_prot))
            elif ptype == "polyline":
                pts = [(x + pt[0] * scale, y + pt[1] * scale) for pt in p["points"]]
                if p.get("closed") and pts[0] != pts[-1]:
                    pts.append(pts[0])
                for i in range(len(pts) - 1):
                    self.ents.append(d_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], layer=layer, ltype=lt))
                for pt in pts:
                    xs.append(pt[0])
                    ys.append(pt[1])
            elif ptype == "arc_circle":
                cx, cy = x + p["cx"] * scale, y + p["cy"] * scale
                r = p["r"] * scale
                if p["is_circle"]:
                    self.ents.append(d_circle(cx, cy, r, layer=layer))
                else:
                    self.ents.append(d_arc(cx, cy, r, p["a1"], p["a2"], layer=layer))
                xs.extend([cx - r, cx + r])
                ys.extend([cy - r, cy + r])
            elif ptype == "text":
                tx, ty = x + p["x"] * scale, y + p["y"] * scale
                self.ents.append(d_text(tx, ty, p["text"], h=190, align="center"))

        pin_coords = {}
        for pin in sym["pins"]:
            idx = pin["index"]
            px = x + pin["x"] * scale
            py = y + pin["y"] * scale
            pin_coords[idx] = (px, py)
            xs.append(px)
            ys.append(py)
            if track_pins is None or idx in track_pins:
                self.placed_pins.append((f"{tag or block_name}#{idx}", px, py))

        # Place Pin Labels cleanly
        if pin_labels:
            for idx, plabel in pin_labels.items():
                if idx in pin_coords:
                    px, py = pin_coords[idx]
                    if is_top_circle_macro:
                        # Place inside macro box below the R=0.75mm terminal circle (at y = py - 680)
                        self.ents.append(d_text(px, py - 680, str(plabel), h=160, align="center"))
                    elif block_name == "MENGGE_Ping":
                        # Place above top border (y + 12*scale + 160)
                        self.ents.append(d_text(px + 180, y + 12.0 * scale + 150, str(plabel), h=160, align="left"))
                    else:
                        dy = 150 if py >= y else -290
                        self.ents.append(d_text(px + 180, py + dy, str(plabel), h=160, align="left"))

        # Place Device Tag, Cross-ref & Description strictly to the left of bounding box with generous 340-unit line spacing
        xmin = min(xs) if xs else x - 600
        tx_left = (x + tag_offset_x) if tag_offset_x is not None else (xmin - 250)
        cur_y = y + tag_offset_y
        if tag:
            self.ents.append(d_text(tx_left, cur_y, tag, h=220, align="right"))
            cur_y -= 340
        if cross_ref:
            self.ents.append(d_text(tx_left, cur_y, cross_ref, h=175, align="right"))
            cur_y -= 300
        if desc:
            self.ents.append(d_text(tx_left, cur_y, desc, h=175, align="right"))

        return pin_coords

    def build_dxf_str(self) -> str:
        return "".join(self.ents)


# ==============================================================================
# S1: 调度室 PLC 柜交直流电源分配、整流模块 (MENGGE_G22) 与等电位接地铜排 (MENGGE_地排10/7)
# ==============================================================================
def build_s1_plc_power_and_grounding():
    b = MengGeSchematicBuilder(
        1, 6,
        "交直流电源分配、整流模块与等电位接地系统图",
        high_level="= 云冶矿业",
        location_code="+ 调度室PLC柜",
    )

    ys_bus = [38200, 37000, 35800, 34600, 33400]
    names_bus = ["L1", "L2", "L3", "N", "PE"]
    for idx, (yb, nb) in enumerate(zip(ys_bus, names_bus)):
        is_pe = (nb == "PE")
        b.wire(6500, yb, 53500, yb, thick=not is_pe, dashed=is_pe)
        b.label(6100, yb - 90, f"AC380V/{nb}" if idx == 0 else nb, h=210, align="right")
        b.add(eplan_arrow_right(53500, yb, f"-1{nb} / 2.0"))

    q1_pins = b.place_mengge_symbol(
        "MENGGE_FA4", 8000, 30000, scale=150.0,
        tag="-Q1", desc="总进线4P 32A",
        pin_labels={1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8"},
        thick=True
    )
    for p_idx, bus_y in [(1, 38200), (3, 37000), (5, 35800), (7, 34600)]:
        px, py = q1_pins[p_idx]
        b.wire(px, py, px, bus_y, thick=True)
        b.node(px, bus_y)

    b.wire(6500, 24500, 14000, 24500, dashed=True)
    b.label(6200, 24500, "-X0", h=220, align="right")
    for idx, p_bot in enumerate([2, 4, 6, 8], start=1):
        px, py = q1_pins[p_bot]
        tx_pins = b.place_mengge_symbol("MENGGE_X2", px, 24500, scale=150.0, pin_labels={1: str(idx)})
        b.wire(px, py, tx_pins[1][0], tx_pins[1][1], thick=True)
        b.wire(tx_pins[2][0], tx_pins[2][1], px, 21500, thick=True)
    b.label(9800, 20600, "引自配电室 AC380V/220V 进线", h=210, align="center")

    # Branch 1 (Col 3): 2P Breaker MENGGE_FA2 (-Q2 10A) + Switching Power Supply MENGGE_G22 (-T101 AC220V/DC24V 5A)
    q2_pins = b.place_mengge_symbol(
        "MENGGE_FA2", 18500, 30000, scale=150.0,
        tag="-Q2", desc="控制电源 10A",
        pin_labels={1: "1", 2: "2", 3: "3", 4: "4"}
    )
    b.wire(q2_pins[1][0], q2_pins[1][1], q2_pins[1][0], 38200)
    b.node(q2_pins[1][0], 38200)
    b.wire(q2_pins[3][0], q2_pins[3][1], q2_pins[3][0], 34600)
    b.node(q2_pins[3][0], 34600)

    g1_pins = b.place_mengge_symbol(
        "MENGGE_G22", 18500, 23500, scale=150.0,
        tag="-T101", desc="DC24V/5A电源",
        pin_labels={1: "L", 3: "N", 2: "L+", 4: "M"},
        protect_box=True
    )
    b.wire(q2_pins[2][0], q2_pins[2][1], g1_pins[1][0], g1_pins[1][1])
    b.wire(q2_pins[4][0], q2_pins[4][1], g1_pins[3][0], g1_pins[3][1])

    xf1_pins = b.place_mengge_symbol(
        "MENGGE_XF", 18500, 18500, scale=150.0,
        tag="-XF1", desc="4A熔断器端子",
        pin_labels={1: "1", 2: "2"}
    )
    b.wire(g1_pins[2][0], g1_pins[2][1], xf1_pins[1][0], xf1_pins[1][1])
    b.wire(xf1_pins[2][0], xf1_pins[2][1], 18500, 14500)
    b.add(eplan_arrow_down(18500, 14500, "-1SL+", "/ 5.0"))

    xm1_pins = b.place_mengge_symbol("MENGGE_X2", 20900, 18500, scale=150.0, tag="-X1M", pin_labels={1: "1"})
    b.wire(g1_pins[4][0], g1_pins[4][1], xm1_pins[1][0], xm1_pins[1][1])
    b.wire(xm1_pins[2][0], xm1_pins[2][1], 20900, 14500)
    b.add(eplan_arrow_down(20900, 14500, "-1SM-", "/ 5.0"))

    # Branch 2 (Col 5): 2P Breaker MENGGE_FA2 (-Q3 6A) + Switching Power Supply MENGGE_G22 (-T102) + Switch MENGGE_Ping (-W1)
    q3_pins = b.place_mengge_symbol(
        "MENGGE_FA2", 28000, 30000, scale=150.0,
        tag="-Q3", desc="仪表电源 6A",
        pin_labels={1: "1", 2: "2", 3: "3", 4: "4"}
    )
    b.wire(q3_pins[1][0], q3_pins[1][1], q3_pins[1][0], 37000)
    b.node(q3_pins[1][0], 37000)
    b.wire(q3_pins[3][0], q3_pins[3][1], q3_pins[3][0], 34600)
    b.node(q3_pins[3][0], 34600)

    g2_pins = b.place_mengge_symbol(
        "MENGGE_G22", 28000, 23500, scale=150.0,
        tag="-T102", desc="DC24V仪表电源",
        pin_labels={1: "L", 3: "N", 2: "2L+", 4: "2M"},
        protect_box=True
    )
    b.wire(q3_pins[2][0], q3_pins[2][1], g2_pins[1][0], g2_pins[1][1])
    b.wire(q3_pins[4][0], q3_pins[4][1], g2_pins[3][0], g2_pins[3][1])

    w1_pins = b.place_mengge_symbol(
        "MENGGE_Ping", 29200, 14500, scale=150.0,
        tag="-W1", desc="工业交换机24V",
        pin_labels={1: "24V+", 2: "24V-"},
        protect_box=True
    )
    b.wire(g2_pins[2][0], g2_pins[2][1], w1_pins[1][0], w1_pins[1][1])
    b.wire(g2_pins[4][0], g2_pins[4][1], w1_pins[2][0], w1_pins[2][1])

    # Branch 3 (Col 7): 1P Breaker MENGGE_FA1 (-Q4 6A) + Fan MENGGE_M2AIR (-M1) + Lamp MENGGE_EH2 (-EH1)
    q4_pins = b.place_mengge_symbol(
        "MENGGE_FA1", 37500, 30000, scale=150.0,
        tag="-Q4", desc="柜内照明风扇6A",
        pin_labels={1: "1", 2: "2"}
    )
    b.wire(q4_pins[1][0], q4_pins[1][1], 37500, 35800)
    b.node(37500, 35800)
    b.wire(q4_pins[2][0], q4_pins[2][1], 37500, 26500)
    b.wire(37500, 26500, 42500, 26500)
    b.node(37500, 26500)

    fan_pins = b.place_mengge_symbol(
        "MENGGE_M2AIR", 37500, 22000, scale=150.0,
        tag="-M1", desc="柜顶散热风机",
        pin_labels={1: "L", 2: "N"}
    )
    b.wire(37500, 26500, fan_pins[1][0], fan_pins[1][1])
    b.wire(fan_pins[2][0], fan_pins[2][1], 37500, 17500)

    eh_pins = b.place_mengge_symbol(
        "MENGGE_EH2", 42500, 22000, scale=150.0,
        tag="-EH1", desc="柜内照明荧光灯",
        pin_labels={1: "L", 2: "N"}
    )
    b.wire(42500, 26500, eh_pins[1][0], eh_pins[1][1])
    b.wire(eh_pins[2][0], eh_pins[2][1], 42500, 17500)
    b.wire(37500, 17500, 44500, 17500)
    b.node(42500, 17500)
    b.wire(44500, 17500, 44500, 34600)
    b.node(44500, 34600)

    # Branch 4 (Col 8-9): Main Grounding Busbar MENGGE_地排10 (-PE1) & Instrument Ground Bar MENGGE_地排7 (-PE2)
    # Route PE wires to the RIGHT of each busbar so left-side text labels are 100% clear!
    pe1_pins = b.place_mengge_symbol(
        "MENGGE_地排10", 48000, 16500, scale=150.0,
        tag="-PE1", desc="主接地铜排(10孔)",
        protect_box=True
    )
    b.wire(pe1_pins[1][0], pe1_pins[1][1], 48000, 12500, dashed=True)
    b.wire(48000, 12500, 49200, 12500, dashed=True)
    b.wire(49200, 12500, 49200, 33400, dashed=True)
    b.node(49200, 33400)

    pe2_pins = b.place_mengge_symbol(
        "MENGGE_地排7", 52500, 16500, scale=150.0,
        tag="-PE2", desc="屏蔽接地排(7孔)",
        protect_box=True
    )
    b.wire(pe2_pins[1][0], pe2_pins[1][1], 52500, 12500, dashed=True)
    b.wire(49200, 12500, 52500, 12500, dashed=True)
    b.node(49200, 12500)

    return b


# ==============================================================================
# S2: 冬瓜山/新回水泵站软起动一拖二及旁路主回路原理图 (采用 MENGGE_FA3 / MENGGE_三相主触点 / MENGGE_M2W / MENGGE_地排5)
# ==============================================================================
def build_s2_soft_starter_one_to_two_power():
    b = MengGeSchematicBuilder(
        2, 6,
        "75kW水泵软起动一拖二及旁路主回路原理图",
        high_level="= 云冶矿业",
        location_code="+ 新回水泵站",
    )

    for yb, name in [(38200, "1L1"), (37000, "1L2"), (35800, "1L3"), (34600, "PE")]:
        is_pe = (name == "PE")
        b.add(eplan_arrow_left_in(6000, yb, f"1.9 / -{name}"))
        b.wire(6000, yb, 52500, yb, thick=not is_pe, dashed=is_pe)
        b.add(eplan_arrow_right(52500, yb, f"-{name} / 3.0"))

    q10_pins = b.place_mengge_symbol(
        "MENGGE_FA3", 10500, 31500, scale=150.0,
        tag="-Q10", desc="软起支路160A",
        pin_labels={1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6"},
        thick=True
    )
    for p_top, bus_y in [(1, 38200), (3, 37000), (5, 35800)]:
        px, py = q10_pins[p_top]
        b.wire(px, py, px, bus_y, thick=True)
        b.node(px, bus_y)

    b.box("-SFR01", 9300, 24500, 14100, 28500, thick=True, protect=True)
    b.label(9000, 27200, "-SFR01", h=230, align="right")
    b.label(9000, 26200, "75kW软起动器", h=180, align="right")
    b.label(11700, 26500, "3~ THYRISTOR", h=190, align="center")
    for p_bot, top_lbl, bot_lbl in [(2, "1L1", "2T1"), (4, "3L2", "4T2"), (6, "5L3", "6T3")]:
        px, py = q10_pins[p_bot]
        b.wire(px, py, px, 28500, thick=True)
        b.label(px + 150, 28650, top_lbl, h=155)
        b.label(px + 150, 24050, bot_lbl, h=155)

    sfr_bus_ys = [22200, 21400, 20600]
    for idx, p_bot in enumerate([2, 4, 6]):
        px = q10_pins[p_bot][0]
        by = sfr_bus_ys[idx]
        b.wire(px, 24500, px, by, thick=True)
        b.wire(px, by, 30500 + idx * 1200, by, thick=True)
        b.node(px, by)

    pumps = [
        (1, 11700, 19300, "-Q11", "-KM11", "/4.2", "-KM12", "/4.4", "-X11", "-M1", "1#回水泵 75kW"),
        (2, 31700, 39300, "-Q21", "-KM21", "/4.6", "-KM22", "/4.8", "-X21", "-M2", "2#回水泵 75kW"),
    ]
    for pno, x_sfr_c, x_byp_left, q_tag, km_sfr, ref_sfr, km_byp, ref_byp, x_term, m_tag, m_desc in pumps:
        qb_pins = b.place_mengge_symbol(
            "MENGGE_FA3", x_byp_left, 31500, scale=150.0,
            tag=q_tag, desc=f"{pno}#工频旁路160A",
            pin_labels={1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6"},
            thick=True
        )
        for p_top, bus_y in [(1, 38200), (3, 37000), (5, 35800)]:
            px, py = qb_pins[p_top]
            b.wire(px, py, px, bus_y, thick=True)
            b.node(px, bus_y)

        kms_pins = b.place_mengge_symbol(
            "MENGGE_三相主触点", x_sfr_c, 17500, scale=150.0,
            tag=km_sfr, cross_ref=ref_sfr, desc=f"{pno}#软起接触器",
            pin_labels={1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6"},
            thick=True
        )
        for idx, p_top in enumerate([1, 3, 5]):
            px, py = kms_pins[p_top]
            b.wire(px, py, px, sfr_bus_ys[idx], thick=True)

        kmb_pins = b.place_mengge_symbol(
            "MENGGE_三相主触点", x_byp_left + 1200, 17500, scale=150.0,
            tag=km_byp, cross_ref=ref_byp, desc=f"{pno}#旁路接触器",
            pin_labels={1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6"},
            thick=True
        )
        for p_qb, p_km in [(2, 1), (4, 3), (6, 5)]:
            b.wire(qb_pins[p_qb][0], qb_pins[p_qb][1], kmb_pins[p_km][0], kmb_pins[p_km][1], thick=True)

        merge_ys = [15600, 15000, 14400]
        for idx, p_bot in enumerate([2, 4, 6]):
            sx, sy = kms_pins[p_bot]
            bx, by_pin = kmb_pins[p_bot]
            my = merge_ys[idx]
            b.wire(sx, sy, sx, my, thick=True)
            b.wire(sx, my, bx, my, thick=True)
            b.node(bx, my)

        b.wire(x_byp_left - 800, 12600, x_byp_left + 3600, 12600, dashed=True)
        b.label(x_byp_left - 1000, 12600, x_term, h=210, align="right")
        term_xs = [kmb_pins[2][0], kmb_pins[4][0], kmb_pins[6][0]]
        for idx, tx in enumerate(term_xs):
            tp = b.place_mengge_symbol("MENGGE_X2", tx, 12600, scale=150.0, pin_labels={1: f"U{pno}" if idx == 0 else (f"V{pno}" if idx == 1 else f"W{pno}")})
            b.wire(tx, merge_ys[idx], tp[1][0], tp[1][1], thick=True)

        mpins = b.place_mengge_symbol(
            "MENGGE_M2W", x_byp_left, 8200, scale=150.0,
            tag=m_tag, desc=m_desc,
            pin_labels={1: "U1", 2: "W1", 3: "PE"},
            thick=True
        )
        b.wire(term_xs[0], 12300, mpins[1][0], mpins[1][1], thick=True)
        b.wire(term_xs[1], 12300, term_xs[1], 9100, thick=True)
        b.wire(term_xs[2], 12300, mpins[2][0], mpins[2][1], thick=True)
        pe_x = x_byp_left + 3600
        b.wire(mpins[3][0], mpins[3][1], pe_x, mpins[3][1], dashed=True)
        b.wire(pe_x, mpins[3][1], pe_x, 34600, dashed=True)
        b.node(pe_x, 34600)

    # Right side local grounding bar MENGGE_地排5 (-PE_M) — route PE wire to RIGHT (50700) so left text is 100% clear!
    pem_pins = b.place_mengge_symbol(
        "MENGGE_地排5", 49500, 14000, scale=150.0,
        tag="-PE_M", desc="泵站就地接地排",
        protect_box=True
    )
    b.wire(pem_pins[1][0], pem_pins[1][1], 49500, 11000, dashed=True)
    b.wire(49500, 11000, 50700, 11000, dashed=True)
    b.wire(50700, 11000, 50700, 34600, dashed=True)
    b.node(50700, 34600)

    return b


# ==============================================================================
# S3: 车间控制箱电动阀门 (MENGGE_电动阀) 与电磁阀 (MENGGE_Y1) 控制原理图 (含 MENGGE_XZKG-1 转换开关)
# ==============================================================================
def build_s3_workshop_valve_control():
    b = MengGeSchematicBuilder(
        3, 6,
        "车间控制箱电动阀与电磁阀控制回路原理图",
        high_level="= 云冶矿业",
        location_code="+ 车间控制箱",
    )

    b.add(eplan_arrow_left_in(6000, 38000, "1.3 / -L220"))
    b.wire(6000, 38000, 52000, 38000, thick=True)
    b.add(eplan_arrow_right(52000, 38000, "-L220 / 4.0"))

    b.add(eplan_arrow_left_in(6000, 10500, "1.3 / -N220"))
    b.wire(6000, 10500, 52000, 10500)
    b.add(eplan_arrow_right(52000, 10500, "-N220 / 4.0"))

    sa1_pins = b.place_mengge_symbol(
        "MENGGE_XZKG-1", 10500, 33500, scale=150.0,
        tag="-SA1", desc="就地/远控转换",
        pin_labels={1: "1", 2: "2", 3: "3", 4: "4"},
        tag_offset_x=-2200
    )
    b.wire(sa1_pins[1][0], sa1_pins[1][1], sa1_pins[1][0], 38000)
    b.node(sa1_pins[1][0], 38000)
    b.wire(sa1_pins[3][0], sa1_pins[3][1], sa1_pins[3][0], 38000)
    b.node(sa1_pins[3][0], 38000)

    sb1_pins = b.place_mengge_symbol(
        "MENGGE_SSD", 10500, 28000, scale=150.0,
        tag="-SB1", desc="就地开阀按钮",
        pin_labels={1: "13", 2: "14"},
        tag_offset_x=-1450
    )
    b.wire(sa1_pins[2][0], sa1_pins[2][1], sb1_pins[1][0], sb1_pins[1][1])

    k301_pins = b.place_mengge_symbol(
        "MENGGE_S", 12900, 28000, scale=150.0,
        tag="-K301", cross_ref="/5.5", desc="远控开阀",
        pin_labels={1: "13", 2: "14"}
    )
    b.wire(sa1_pins[4][0], sa1_pins[4][1], k301_pins[1][0], k301_pins[1][1])
    b.wire(k301_pins[2][0], k301_pins[2][1], 12900, 26200)
    b.wire(12900, 26200, 10500, 26200)
    b.node(10500, 26200)

    sq1_pins = b.place_mengge_symbol(
        "MENGGE_O", 10500, 23500, scale=150.0,
        tag="-SQ1", desc="开到位限位",
        pin_labels={1: "11", 2: "12"}
    )
    b.wire(sb1_pins[2][0], sb1_pins[2][1], sq1_pins[1][0], sq1_pins[1][1])

    il1_pins = b.place_mengge_symbol(
        "MENGGE_O", 10500, 19500, scale=150.0,
        tag="-KM32", cross_ref="/3.4", desc="关阀互锁",
        pin_labels={1: "21", 2: "22"}
    )
    b.wire(sq1_pins[2][0], sq1_pins[2][1], il1_pins[1][0], il1_pins[1][1])

    km31_pins = b.place_mengge_symbol(
        "MENGGE_KM", 10500, 14500, scale=150.0,
        tag="-KM31", desc="电动阀开接触器",
        pin_labels={1: "A1", 2: "A2"},
        protect_box=True
    )
    b.wire(il1_pins[2][0], il1_pins[2][1], km31_pins[1][0], km31_pins[1][1])
    b.wire(km31_pins[2][0], km31_pins[2][1], 10500, 10500)
    b.node(10500, 10500)
    b.label(10500, 8800, "13--14 /3.7", h=175, align="center")
    b.label(10500, 8000, "21--22 /3.4", h=175, align="center")

    # Branch 2 (x=20500): Close Valve Branch
    sb2_pins = b.place_mengge_symbol(
        "MENGGE_SSD", 20500, 28000, scale=150.0,
        tag="-SB2", desc="就地关阀按钮",
        pin_labels={1: "13", 2: "14"},
        tag_offset_x=-1450
    )
    b.wire(20500, 38000, sb2_pins[1][0], sb2_pins[1][1])
    b.node(20500, 38000)

    sq2_pins = b.place_mengge_symbol(
        "MENGGE_O", 20500, 23500, scale=150.0,
        tag="-SQ2", desc="关到位限位",
        pin_labels={1: "11", 2: "12"}
    )
    b.wire(sb2_pins[2][0], sb2_pins[2][1], sq2_pins[1][0], sq2_pins[1][1])

    il2_pins = b.place_mengge_symbol(
        "MENGGE_O", 20500, 19500, scale=150.0,
        tag="-KM31", cross_ref="/3.2", desc="开阀互锁",
        pin_labels={1: "21", 2: "22"}
    )
    b.wire(sq2_pins[2][0], sq2_pins[2][1], il2_pins[1][0], il2_pins[1][1])

    km32_pins = b.place_mengge_symbol(
        "MENGGE_KM", 20500, 14500, scale=150.0,
        tag="-KM32", desc="电动阀关接触器",
        pin_labels={1: "A1", 2: "A2"},
        protect_box=True
    )
    b.wire(il2_pins[2][0], il2_pins[2][1], km32_pins[1][0], km32_pins[1][1])
    b.wire(km32_pins[2][0], km32_pins[2][1], 20500, 10500)
    b.node(20500, 10500)
    b.label(20500, 8800, "13--14 /3.8", h=175, align="center")
    b.label(20500, 8000, "21--22 /3.2", h=175, align="center")

    # Branch 3 (x=29500): Solenoid Valve MENGGE_Y1 (-YV1)
    k303_pins = b.place_mengge_symbol(
        "MENGGE_S", 29500, 28000, scale=150.0,
        tag="-K303", cross_ref="/5.6", desc="电磁阀启动",
        pin_labels={1: "13", 2: "14"}
    )
    b.wire(29500, 38000, k303_pins[1][0], k303_pins[1][1])
    b.node(29500, 38000)

    yv1_pins = b.place_mengge_symbol(
        "MENGGE_Y1", 29500, 14500, scale=150.0,
        tag="-YV1", desc="主管电磁阀",
        pin_labels={1: "A1", 2: "A2"},
        protect_box=True
    )
    b.wire(k303_pins[2][0], k303_pins[2][1], yv1_pins[1][0], yv1_pins[1][1])
    b.wire(yv1_pins[2][0], yv1_pins[2][1], 29500, 10500)
    b.node(29500, 10500)

    # Branch 4 (x=36500): Valve Fault Relay MENGGE_KA (-KA1) & Indicator Lamp MENGGE_H (-HL1)
    st_pins = b.place_mengge_symbol(
        "MENGGE_S", 36500, 28000, scale=150.0,
        tag="-ST1", desc="过矩报警触点",
        pin_labels={1: "97", 2: "98"}
    )
    b.wire(36500, 38000, st_pins[1][0], st_pins[1][1])
    b.node(36500, 38000)

    ka1_pins = b.place_mengge_symbol(
        "MENGGE_KA", 36500, 21000, scale=150.0,
        tag="-KA1", desc="过矩故障继电器",
        pin_labels={1: "A1", 2: "A2"},
        protect_box=True
    )
    b.wire(st_pins[2][0], st_pins[2][1], ka1_pins[1][0], ka1_pins[1][1])

    hl1_pins = b.place_mengge_symbol(
        "MENGGE_H", 36500, 14500, scale=150.0,
        tag="-HL1", desc="阀门故障红灯",
        pin_labels={1: "x1", 2: "x2"}
    )
    b.wire(ka1_pins[2][0], ka1_pins[2][1], hl1_pins[1][0], hl1_pins[1][1])
    b.wire(hl1_pins[2][0], hl1_pins[2][1], 36500, 10500)
    b.node(36500, 10500)

    # Branch 5 (x=44500..48100): Motorized Valve Actuator Macro MENGGE_电动阀 (-MOV1)
    mov_pins = b.place_mengge_symbol(
        "MENGGE_电动阀", 44500, 15500, scale=150.0,
        tag="-MOV1", desc="电动蝶阀 DN300",
        pin_labels={1: "OPEN", 2: "CLOSE", 3: "COM"},
        protect_box=True
    )
    km31_no = b.place_mengge_symbol(
        "MENGGE_S", 44500, 28000, scale=150.0,
        tag="-KM31", cross_ref="/3.2", desc="开阀触点",
        pin_labels={1: "13", 2: "14"}
    )
    b.wire(44500, 38000, km31_no[1][0], km31_no[1][1])
    b.node(44500, 38000)
    b.wire(km31_no[2][0], km31_no[2][1], mov_pins[1][0], mov_pins[1][1])

    km32_no = b.place_mengge_symbol(
        "MENGGE_S", 48100, 28000, scale=150.0,
        tag="-KM32", cross_ref="/3.4", desc="关阀触点",
        pin_labels={1: "13", 2: "14"}
    )
    b.wire(48100, 38000, km32_no[1][0], km32_no[1][1])
    b.node(48100, 38000)
    b.wire(km32_no[2][0], km32_no[2][1], 48100, 23000)
    b.wire(48100, 23000, 45700, 23000)
    b.wire(45700, 23000, mov_pins[2][0], mov_pins[2][1])

    # Route mov_pins[3] (48100, 15800) UP through top border to y=21200, then right to x=50500 and down to N (10500)
    b.wire(mov_pins[3][0], mov_pins[3][1], 48100, 21200)
    b.wire(48100, 21200, 50500, 21200)
    b.wire(50500, 21200, 50500, 10500)
    b.node(50500, 10500)

    b.wire(43200, 20000, 51200, 20000, dashed=True)
    b.label(42900, 20000, "-X301", h=200, align="right")
    b.wire(43200, 9200, 51200, 9200, dashed=True)
    b.label(42900, 9200, "PE", h=200, align="right")

    return b


# ==============================================================================
# S4: 水源泵站主接触器切换、双常闭互锁与完整触点映像表原理图 (MENGGE_S / MENGGE_O / MENGGE_KM / MENGGE_H)
# ==============================================================================
def build_s4_contactor_interlock_and_mirror():
    b = MengGeSchematicBuilder(
        4, 6,
        "1#/2#水泵软起与旁路接触器切换及触点映像图",
        high_level="= 云冶矿业",
        location_code="+ 新回水泵站",
    )

    b.add(eplan_arrow_left_in(6000, 38000, "3.9 / -L220"))
    b.wire(6000, 38000, 52000, 38000, thick=True)
    b.add(eplan_arrow_right(52000, 38000, "-L220 / 5.0"))

    b.add(eplan_arrow_left_in(6000, 11200, "3.9 / -N220"))
    b.wire(6000, 11200, 52000, 11200)
    b.add(eplan_arrow_right(52000, 11200, "-N220 / 5.0"))

    branches = [
        (12500, "-KM11", "1#软起接触器", "-K101", "/5.2", "-1SP1", "-KM12", "/4.4", "-KM21", "/4.6", "-HR1", "/2.2"),
        (24000, "-KM12", "1#旁路接触器", "-K102", "/5.3", "-1SP2", "-KM11", "/4.2", "-KM22", "/4.8", "-HR2", "/2.3"),
        (35500, "-KM21", "2#软起接触器", "-K103", "/5.4", "-2SP1", "-KM22", "/4.8", "-KM11", "/4.2", "-HR3", "/2.6"),
        (47000, "-KM22", "2#旁路接触器", "-K104", "/5.5", "-2SP2", "-KM21", "/4.6", "-KM12", "/4.4", "-HR4", "/2.7"),
    ]

    for cx, km_tag, km_desc, k_tag, k_ref, sp_tag, il1_tag, il1_ref, il2_tag, il2_ref, hr_tag, main_ref in branches:
        k_pins = b.place_mengge_symbol(
            "MENGGE_S", cx, 33000, scale=150.0,
            tag=k_tag, cross_ref=k_ref, desc="PLC自动启动",
            pin_labels={1: "13", 2: "14"}
        )
        b.wire(cx, 38000, k_pins[1][0], k_pins[1][1])
        b.node(cx, 38000)

        sh_pins = b.place_mengge_symbol(
            "MENGGE_S", cx + 3200, 33000, scale=150.0,
            tag=km_tag, cross_ref="/4.2",
            pin_labels={1: "13", 2: "14"}
        )
        b.wire(cx, 35500, cx + 3200, 35500)
        b.node(cx, 35500)
        b.wire(cx + 3200, 35500, sh_pins[1][0], sh_pins[1][1])
        b.wire(sh_pins[2][0], sh_pins[2][1], cx + 3200, 30500)
        b.wire(cx + 3200, 30500, cx, 30500)
        b.node(cx, 30500)

        sp_pins = b.place_mengge_symbol(
            "MENGGE_O", cx, 28000, scale=150.0,
            tag=sp_tag, desc="停止按钮",
            pin_labels={1: "11", 2: "12"}
        )
        b.wire(k_pins[2][0], k_pins[2][1], sp_pins[1][0], sp_pins[1][1])

        p_il1 = b.place_mengge_symbol(
            "MENGGE_O", cx, 24000, scale=150.0,
            tag=il1_tag, cross_ref=il1_ref,
            pin_labels={1: "21", 2: "22"}
        )
        b.wire(sp_pins[2][0], sp_pins[2][1], p_il1[1][0], p_il1[1][1])

        p_il2 = b.place_mengge_symbol(
            "MENGGE_O", cx, 20000, scale=150.0,
            tag=il2_tag, cross_ref=il2_ref,
            pin_labels={1: "61", 2: "62"}
        )
        b.wire(p_il1[2][0], p_il1[2][1], p_il2[1][0], p_il2[1][1])

        km_pins = b.place_mengge_symbol(
            "MENGGE_KM", cx, 15000, scale=150.0,
            tag=km_tag, desc=km_desc,
            pin_labels={1: "A1", 2: "A2"},
            protect_box=True
        )
        b.wire(p_il2[2][0], p_il2[2][1], km_pins[1][0], km_pins[1][1])
        b.wire(km_pins[2][0], km_pins[2][1], cx, 11200)
        b.node(cx, 11200)

        hr_pins = b.place_mengge_symbol(
            "MENGGE_H", cx + 3200, 15000, scale=150.0,
            tag=hr_tag,
            pin_labels={1: "x1", 2: "x2"},
            tag_offset_x=-420
        )
        b.wire(cx, 17500, cx + 3200, 17500)
        b.node(cx, 17500)
        b.wire(cx + 3200, 17500, hr_pins[1][0], hr_pins[1][1])
        b.wire(hr_pins[2][0], hr_pins[2][1], cx + 3200, 11200)
        b.node(cx + 3200, 11200)

        mirror_rows = [
            ("NO", "1", "2", main_ref, 9500),
            ("NO", "3", "4", main_ref, 8700),
            ("NO", "5", "6", main_ref, 7900),
            ("NO", "13", "14", "/4.2", 7100),
            ("NC", "21", "22", il1_ref, 6300),
            ("NC", "61", "62", il2_ref, 5500),
        ]
        for mtype, mp1, mp2, mref, my in mirror_rows:
            b.label(cx - 500, my - 70, mp1, h=145, align="right")
            b.wire(cx - 420, my, cx - 150, my, is_internal=True)
            if mtype == "NO":
                b.wire(cx - 150, my, cx + 120, my + 160, is_internal=True)
            else:
                b.wire(cx + 150, my, cx + 150, my + 180, is_internal=True)
                b.wire(cx - 150, my, cx + 180, my + 150, is_internal=True)
            b.wire(cx + 150, my, cx + 420, my, is_internal=True)
            b.label(cx + 500, my - 70, f"{mp2} {mref}", h=145, align="left")

    b.wire(6000, 4900, 52000, 4900, dashed=True)
    b.wire(6000, 4750, 52000, 4750, dashed=True)
    b.label(5800, 4800, "PE", h=180, align="right")

    return b


# ==============================================================================
# S5: 调度室 PLC CPU314C 数字量 DI/DO 扩展与熔断器隔离端子 (MENGGE_K / MENGGE_XF / MENGGE_S / MENGGE_X2 / MENGGE_地排5)
# ==============================================================================
def build_s5_plc_cpu_di_do_with_mengge():
    b = MengGeSchematicBuilder(
        5, 6,
        "调度室PLC数字量DI/DO与熔断器隔离端子原理图",
        high_level="= 云冶矿业",
        location_code="+ 调度室PLC柜",
    )

    # Top rails: -PE at top (38600), -1SL+ (37600), -1SM- (36600) so DO relay coils connect straight to -1SM- without crossing -PE!
    b.add(eplan_arrow_left_in(6000, 38600, "1.9 / -PE"))
    b.wire(6000, 38600, 52500, 38600, dashed=True)
    b.add(eplan_arrow_right(52500, 38600, "-PE / 6.0"))

    b.add(eplan_arrow_left_in(6000, 37600, "1.3 / -1SL+"))
    b.wire(6000, 37600, 51000, 37600)
    b.add(eplan_arrow_left_in(6000, 36600, "1.3 / -1SM-"))
    b.wire(6000, 36600, 51000, 36600)

    # Central PLC CPU Box (-CU1 SIEMENS CPU 314C-2PN/DP) at x=6000..47500, y=21000..26500
    b.box("-CU1", 6000, 21000, 47500, 26500, thick=True, protect=True)
    b.wire(6000, 24800, 47500, 24800, is_internal=True)
    b.wire(6000, 22700, 47500, 22700, is_internal=True)
    b.label(5600, 25500, "-CU1", h=260, align="right")
    b.label(26750, 23600, "SIEMENS SIMATIC S7-300 CPU 314C-2PN/DP (6ES7314-6EH04-0AB0)", h=250, align="center")
    b.label(8000, 25400, "DO 24VDC", h=210, align="center")
    b.label(8000, 21600, "DI 24VDC", h=210, align="center")

    do_list = [
        (13500, "Q0.0", "-XF1", "-K101", "1#软起启动", "13--14 /4.2"),
        (19500, "Q0.1", "-XF2", "-K102", "1#旁路切换", "13--14 /4.4"),
        (25500, "Q0.2", "-XF3", "-K103", "2#软起启动", "13--14 /4.6"),
        (31500, "Q0.3", "-XF4", "-K104", "2#旁路切换", "13--14 /4.8"),
        (37500, "Q0.4", "-XF5", "-K301", "远控开电动阀", "13--14 /3.2"),
        (43500, "Q0.5", "-XF6", "-K303", "主管电磁阀", "13--14 /3.6"),
    ]
    for qx, qpin, xftag, ktag, kdesc, mref in do_list:
        b.label(qx, 25300, qpin, h=190, align="center")
        xf_pins = b.place_mengge_symbol("MENGGE_XF", qx, 29800, scale=150.0, tag=xftag)
        b.wire(qx, 26500, xf_pins[2][0], xf_pins[2][1])

        k_pins = b.place_mengge_symbol(
            "MENGGE_K", qx, 33600, scale=150.0,
            tag=ktag, desc=kdesc,
            pin_labels={1: "A2", 2: "A1"},
            protect_box=True
        )
        b.wire(xf_pins[1][0], xf_pins[1][1], k_pins[2][0], k_pins[2][1])
        b.wire(k_pins[1][0], k_pins[1][1], qx, 36600)
        b.node(qx, 36600)
        b.label(qx, 5600, mref, h=175, align="center")

    b.wire(6000, 9200, 46500, 9200)
    b.add(eplan_arrow_left_in(6000, 9200, "1.3 / -2SL+"))
    b.wire(11000, 12800, 46500, 12800, dashed=True)
    b.label(10600, 12800, "-X100", h=210, align="right")

    di_list = [
        (13500, "I0.0", "-KM11", "/4.2", "1#软起运行", "1"),
        (19500, "I0.1", "-KM12", "/4.4", "1#旁路运行", "2"),
        (25500, "I0.2", "-KM21", "/4.6", "2#软起运行", "3"),
        (31500, "I0.3", "-KM22", "/4.8", "2#旁路运行", "4"),
        (37500, "I0.4", "-SQ1", "/3.2", "电动阀开到位", "5"),
        (43500, "I0.5", "-KA1", "/3.7", "电动阀故障", "6"),
    ]
    for dx, dpin, ctag, cref, cdesc, tno in di_list:
        b.label(dx, 21500, dpin, h=190, align="center")
        c_pins = b.place_mengge_symbol(
            "MENGGE_S", dx, 17200, scale=150.0,
            tag=ctag, cross_ref=cref, desc=cdesc,
            pin_labels={1: "13", 2: "14"}
        )
        b.wire(dx, 21000, c_pins[1][0], c_pins[1][1])
        x_pins = b.place_mengge_symbol("MENGGE_X2", dx, 12800, scale=150.0, pin_labels={1: tno})
        b.wire(c_pins[2][0], c_pins[2][1], x_pins[1][0], x_pins[1][1])
        b.wire(x_pins[2][0], x_pins[2][1], dx, 9200)
        b.node(dx, 9200)

    # Right side PLC Grounding Busbar MENGGE_地排5 (-PE_PLC) — route PE wire to RIGHT (52000) so left text is 100% clear!
    pe_plc = b.place_mengge_symbol(
        "MENGGE_地排5", 50500, 15000, scale=150.0,
        tag="-PE_PLC", desc="PLC机架接地排",
        protect_box=True
    )
    b.wire(pe_plc[1][0], pe_plc[1][1], 50500, 12000, dashed=True)
    b.wire(50500, 12000, 51800, 12000, dashed=True)
    b.wire(51800, 12000, 51800, 38600, dashed=True)
    b.node(51800, 38600)

    return b


# ==============================================================================
# S6: 现场仪表设备宏 (MENGGE_设备2/3/4/5) 与 PLC 模拟量 AI/AO 接线原理图 (模式同调度室PLC柜 P5)
# ==============================================================================
def build_s6_field_instruments_and_analog_io():
    b = MengGeSchematicBuilder(
        6, 6,
        "现场仪表设备(2~5连接点)与模拟量AI/AO接线原理图",
        high_level="= 云冶矿业",
        location_code="+ 调度室PLC柜",
    )

    # Top PE rail at y=38600 across full width (above -CU1_AI box at y=31000..36800!)
    b.add(eplan_arrow_left_in(6000, 38600, "5.9 / -PE"))
    b.wire(6000, 38600, 53000, 38600, dashed=True)
    b.add(eplan_arrow_right(53000, 38600, "-PE / 1.9"))

    # Top PLC Analog Input/Output Module Box (-CU1 AI5/AO2) at x=6500..46500, y=31000..36800
    b.box("-CU1_AI", 6500, 31000, 46500, 36800, thick=True, protect=True)
    b.wire(6500, 33600, 46500, 33600, is_internal=True)
    b.label(6100, 35600, "-CU1", h=260, align="right")
    b.label(26500, 34900, "SIEMENS CPU 314C INTEGRATED AI5 / AO2 (4-20mA 模拟量采集与调节通道)", h=240, align="center")

    # Intermediate Terminal Strip -X201 at y=24500
    b.wire(6500, 24500, 46500, 24500, dashed=True)
    b.label(6100, 24500, "-X201", h=220, align="right")

    # 1. MENGGE_设备2 (-LT1 两线制超声波液位计)
    u2_pins = b.place_mengge_symbol(
        "MENGGE_设备2", 9500, 14000, scale=150.0,
        tag="-LT1", desc="超声波液位计",
        pin_labels={1: "I+", 2: "I-"},
        protect_box=True
    )
    for idx, pno in enumerate([1, 2], start=1):
        px, py = u2_pins[pno]
        tp = b.place_mengge_symbol("MENGGE_X2", px, 24500, scale=150.0, pin_labels={1: str(idx)})
        b.wire(px, py, tp[2][0], tp[2][1])
        b.wire(tp[1][0], tp[1][1], px, 31000)
        b.label(px, 31800, "PIW752+" if pno == 1 else "PIW752-", h=165, align="center")

    # 2. MENGGE_设备3 (-PT1 三线制管网压力变送器)
    u3_pins = b.place_mengge_symbol(
        "MENGGE_设备3", 18000, 14000, scale=150.0,
        tag="-PT1", desc="管网压力变送器",
        pin_labels={1: "24V", 2: "SIG", 3: "0V"},
        protect_box=True
    )
    for pno, lbl, tno in [(1, "2L+", "3"), (2, "PIW754+", "4"), (3, "MANA", "5")]:
        px, py = u3_pins[pno]
        tp = b.place_mengge_symbol("MENGGE_X2", px, 24500, scale=150.0, pin_labels={1: tno})
        b.wire(px, py, tp[2][0], tp[2][1])
        b.wire(tp[1][0], tp[1][1], px, 31000)
        b.label(px, 31800, lbl, h=160, align="center")

    # 3. MENGGE_设备4 (-FT1 四线制电磁流量计)
    u4_pins = b.place_mengge_symbol(
        "MENGGE_设备4", 27500, 14000, scale=150.0,
        tag="-FT1", desc="四线制电磁流量计",
        pin_labels={1: "L+", 2: "M", 3: "I+", 4: "I-"},
        protect_box=True
    )
    for pno, lbl, tno in [(1, "2L+", "6"), (2, "2M", "7"), (3, "PIW756+", "8"), (4, "PIW756-", "9")]:
        px, py = u4_pins[pno]
        tp = b.place_mengge_symbol("MENGGE_X2", px, 24500, scale=150.0, pin_labels={1: tno})
        b.wire(px, py, tp[2][0], tp[2][1])
        b.wire(tp[1][0], tp[1][1], px, 31000)
        b.label(px, 31800, lbl, h=155, align="center")

    # 4. MENGGE_设备5 (-AT1 五端子多参数水质分析仪)
    u5_pins = b.place_mengge_symbol(
        "MENGGE_设备5", 38500, 14000, scale=150.0,
        tag="-AT1", desc="五端子水质分析仪",
        pin_labels={1: "L+", 2: "M", 3: "pH+", 4: "Tb+", 5: "COM"},
        protect_box=True
    )
    for pno, lbl, tno in [(1, "2L+", "10"), (2, "2M", "11"), (3, "PIW758+", "12"), (4, "PIW760+", "13"), (5, "MANA", "14")]:
        px, py = u5_pins[pno]
        tp = b.place_mengge_symbol("MENGGE_X2", px, 24500, scale=150.0, pin_labels={1: tno})
        b.wire(px, py, tp[2][0], tp[2][1])
        b.wire(tp[1][0], tp[1][1], px, 31000)
        b.label(px, 31800, lbl, h=150, align="center")

    # Right side Shield Grounding Busbar MENGGE_地排7 (-PE_AI) — route PE wire to RIGHT (52200) so left text is 100% clear!
    pe_ai = b.place_mengge_symbol(
        "MENGGE_地排7", 51000, 14000, scale=150.0,
        tag="-PE_AI", desc="模拟量屏蔽接地排",
        protect_box=True
    )
    b.wire(pe_ai[1][0], pe_ai[1][1], 51000, 11000, dashed=True)
    b.wire(51000, 11000, 52200, 11000, dashed=True)
    b.wire(52200, 11000, 52200, 38600, dashed=True)
    b.node(52200, 38600)

    return b


if __name__ == "__main__":
    suite = [
        ("猛哥规范样图_S1_调度室PLC柜交直流配电与接地系统图.dxf", build_s1_plc_power_and_grounding),
        ("猛哥规范样图_S2_新回水泵站软起动一拖二及旁路主回路图.dxf", build_s2_soft_starter_one_to_two_power),
        ("猛哥规范样图_S3_车间控制箱电动阀与电磁阀控制原理图.dxf", build_s3_workshop_valve_control),
        ("猛哥规范样图_S4_水源泵站主接触器切换与触点映像原理图.dxf", build_s4_contactor_interlock_and_mirror),
        ("猛哥规范样图_S5_调度室PLC_CPU314C数字量DI_DO扩展图.dxf", build_s5_plc_cpu_di_do_with_mengge),
        ("猛哥规范样图_S6_现场仪表设备宏与模拟量AI_AO接线图.dxf", build_s6_field_instruments_and_analog_io),
    ]

    pdf_out = OUT_DIR / "猛哥符号库实战样图集_6张全套_自审修正版.pdf"
    audit_results = []
    with PdfPages(pdf_out) as pdf:
        for fname, builder_fn in suite:
            b = builder_fn()
            dxf_path = OUT_DIR / fname
            save_dxf_page(b.build_dxf_str(), dxf_path)
            res = audit_dxf_strict(
                dxf_path,
                placed_pins=b.placed_pins,
                protected_boxes=b.protected_boxes,
                external_wires=b.external_wires
            )
            audit_results.append(res)
            print(f"{fname:48s} | score={res['score']} | passed={res['all_passed']}")
            if not res["all_passed"]:
                for k, v in res["checks"].items():
                    if not v:
                        print(f"    FAILED CHECK: {k}")
                for dk, dv in res["defects"].items():
                    if dv:
                        print(f"    DEFECT {dk} ({len(dv)}): {dv[:5]}")

            fig, ax = plt.subplots(figsize=(16.54, 11.69))
            render_eplan_page(dxf_path, ax)
            plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
            fig.savefig(str(OUT_DIR / (dxf_path.stem + ".png")), dpi=150)
            pdf.savefig(fig)
            plt.close(fig)

    (OUT_DIR / "mengge_strict_audit_report.json").write_text(
        json.dumps(audit_results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Saved PDF:", pdf_out)
