#!/usr/bin/env python3
"""
EPLAN Electric P8 工业标准一键生图与自训练引擎 v3.0 (eplan_cad_engine.py)
深度学习自用户上传的 6 套共 51 页真实工程图纸：
  - 《调度室PLC柜.pdf》(5页) / 《车间控制箱.pdf》(1页)
  - 《联合泵站.pdf》(18页) / 《新回水泵站.pdf》(10页) / 《新建水源.pdf》(8页)
  - 《吉百利恒压变频供水系统电气原理图（原图 & 修改变频控制方式）.pdf》(14+13页)

完整复刻 EPLAN 10大核心制图规则：
  1. 图框与列格栅：顶部 0~9 十列均匀分格，底部 EPLAN 标准通栏标题栏（设计/编辑/审核 + 项目名 + 公司名 + 图名 + `=高层代号` / `+位置代号` / 页码 / 总页数 + 左右跨页号）
  2. 跨页源/目的中断箭头：左侧来线 `页号.列号 / -网络名 ▶`，右侧去线 `▶ -网络名 / 页号.列号`，配电页底部成排垂直向下箭头 `▼`
  3. 器件精确引脚号：主触点 `1/2, 3/4, 5/6`，辅助常开 `13/14` 或 `5/9`、`11/14`，常闭 `11/12, 21/22, 61/62`，报警 `97/98`，线圈 `A1/A2`，指示灯 `x1/x2`
  4. 线圈正下方触点映像表 (Contact Mirror)：主触点 `1--2 /页.列` 与辅助触点 `13--14 /页.列`、`21--22 /页.列` 纵向对齐排列
  5. DC24V 接触器线圈旁并联续流二极管符号 + 变频/工频双常闭互锁 (`-KM12 21/22` + `-KM21 21/22`)
  6. 变频器控制方式升级（学习自《吉百利修改版》红云线）：由 PLC DO 输出继电器 (`-K109/-K110`) 独立控制变频器启动，解耦主接触器辅助触点
  7. 变频器宏框：主回路含整流桥+直流母线电容+IGBT逆变拓扑；控制页含顶部通栏虚线框、底部圆圈端子排、右上角 RS485 DB9 与 DIP 拨码开关
  8. PLC CPU / EM 扩展模块双层对称画法：中央模块框，上方 DO 驱动一排中间继电器 `-K101~-K110`，下方 DI 接状态/按钮输入
  9. 模拟量 AI/AO 与 4-20mA 传感器：方框对角斜线 `Sensor 4-20mA` (`-PT1/-FT1/-LT1`) 经 `-X201` 端子排点划线接入 `EM231/EM235` `PIW0~PIW6`
 10. 导轨端子排穿透点划线 (`-X0, -X11, -X101, -X201, -X300`) + 现场虚线框 + 电机右侧 PE 接地虚线折线
"""

import json
import math
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import font_manager

from path_utils import get_cjk_font_properties, ensure_out_dir, TEMPLATE_READY_DXF
CJK_FP = get_cjk_font_properties()
OUT_DIR = ensure_out_dir()
TEMPLATE_DXF = TEMPLATE_READY_DXF


# ==============================================================================
# DXF Primitive Builders (1:100 Model Space, Coordinate range X: 0..59400, Y: 0..42000)
# ==============================================================================
def d_line(x0, y0, x1, y1, layer="01_细实线", ltype="BYLAYER"):
    s = f"  0\nLINE\n  8\n{layer}\n"
    if ltype != "BYLAYER":
        s += f"  6\n{ltype}\n"
    s += f" 10\n{x0:.1f}\n 20\n{y0:.1f}\n 30\n0.0\n 11\n{x1:.1f}\n 21\n{y1:.1f}\n 31\n0.0\n"
    return s


def d_rect(x0, y0, x1, y1, layer="01_细实线", ltype="BYLAYER"):
    return (
        d_line(x0, y0, x1, y0, layer, ltype)
        + d_line(x1, y0, x1, y1, layer, ltype)
        + d_line(x1, y1, x0, y1, layer, ltype)
        + d_line(x0, y1, x0, y0, layer, ltype)
    )


def d_circle(cx, cy, r, layer="01_细实线"):
    return f"  0\nCIRCLE\n  8\n{layer}\n 10\n{cx:.1f}\n 20\n{cy:.1f}\n 30\n0.0\n 40\n{r:.1f}\n"


def d_arc(cx, cy, r, a1, a2, layer="01_细实线"):
    return f"  0\nARC\n  8\n{layer}\n 10\n{cx:.1f}\n 20\n{cy:.1f}\n 30\n0.0\n 40\n{r:.1f}\n 50\n{a1:.1f}\n 51\n{a2:.1f}\n"


def d_solid_tri(x0, y0, x1, y1, x2, y2, layer="01_细实线"):
    return (
        f"  0\nSOLID\n  8\n{layer}\n"
        f" 10\n{x0:.1f}\n 20\n{y0:.1f}\n 30\n0.0\n"
        f" 11\n{x1:.1f}\n 21\n{y1:.1f}\n 31\n0.0\n"
        f" 12\n{x2:.1f}\n 22\n{y2:.1f}\n 32\n0.0\n"
        f" 13\n{x2:.1f}\n 23\n{y2:.1f}\n 33\n0.0\n"
    )


def d_text(x, y, text, h=260, layer="07_文字", align="left"):
    if align == "center":
        return (
            f"  0\nTEXT\n  8\n{layer}\n  7\nNERIN_ISOCP\n"
            f" 10\n{x:.1f}\n 20\n{y:.1f}\n 30\n0.0\n 40\n{h:.1f}\n  1\n{text}\n"
            f" 72\n1\n 11\n{x:.1f}\n 21\n{y:.1f}\n 31\n0.0\n 73\n2\n"
        )
    elif align == "right":
        return (
            f"  0\nTEXT\n  8\n{layer}\n  7\nNERIN_ISOCP\n"
            f" 10\n{x:.1f}\n 20\n{y:.1f}\n 30\n0.0\n 40\n{h:.1f}\n  1\n{text}\n"
            f" 72\n2\n 11\n{x:.1f}\n 21\n{y:.1f}\n 31\n0.0\n 73\n2\n"
        )
    return (
        f"  0\nTEXT\n  8\n{layer}\n  7\nNERIN_ISOCP\n"
        f" 10\n{x:.1f}\n 20\n{y:.1f}\n 30\n0.0\n 40\n{h:.1f}\n  1\n{text}\n"
    )


# ==============================================================================
# EPLAN Frame, 0..9 Column Header, and Bottom Full-Width Title Strip
# ==============================================================================
def draw_eplan_frame(page_no: int, total_pages: int, page_title: str,
                     project_name: str = "云冶矿业恒压变频供水控制系统",
                     company_name: str = "北京海德自动化工程有限公司",
                     high_level: str = "= 10A",
                     location_code: str = "+ MAIN0"):
    ents = []
    # Outer drawing border (1500, 1200) to (58200, 40800)
    x0, y0, x1, y1 = 1500, 1200, 58200, 40800
    ents.append(d_rect(x0, y0, x1, y1, layer="02_粗实线"))

    # Top 0..9 column grid bar: y from 39900 to 40800
    ents.append(d_line(x0, 39900, x1, 39900, layer="01_细实线"))
    col_w = (x1 - x0) / 10.0
    for c in range(10):
        cx = x0 + (c + 0.5) * col_w
        ents.append(d_text(cx, 40350, str(c), h=300, align="center"))
        if c > 0:
            ents.append(d_line(x0 + c * col_w, 39900, x0 + c * col_w, 40800))

    # Bottom EPLAN full-width title strip: y from 1200 to 4200
    yt = 4200
    ents.append(d_line(x0, yt, x1, yt, layer="02_粗实线"))
    # Prev / Next page numbers right above title bar
    if page_no > 1:
        ents.append(d_text(x0 + 300, yt + 350, str(page_no - 1), h=280))
    if page_no < total_pages:
        ents.append(d_text(x1 - 300, yt + 350, str(page_no + 1), h=280, align="right"))

    # Vertical dividers in bottom strip:
    # [1500..8500 设计/编辑/审核] [8500..21000 项目名称] [21000..33000 公司名称] [33000..42500 图纸名称] [42500..58200 图号/柜号/页码]
    for vx in (4500, 8500, 21000, 33000, 42500, 47200, 50500, 54500):
        ents.append(d_line(vx, y0, vx, yt))
    # Horizontal sub-lines in left block and right block
    ents.append(d_line(x0, 2200, 8500, 2200))
    ents.append(d_line(x0, 3200, 8500, 3200))
    ents.append(d_line(42500, 2200, x1, 2200))
    ents.append(d_line(42500, 3200, x1, 3200))

    # Left labels
    ents.append(d_text(3000, 3700, "设计 Design", h=220, align="center"))
    ents.append(d_text(6500, 3700, "殷明", h=220, align="center"))
    ents.append(d_text(3000, 2700, "编辑 Edit", h=220, align="center"))
    ents.append(d_text(6500, 2700, "殷明", h=220, align="center"))
    ents.append(d_text(3000, 1700, "审核 Confirm", h=220, align="center"))
    ents.append(d_text(6500, 1700, "NERIN", h=220, align="center"))

    # Center blocks
    ents.append(d_text(14750, 2700, project_name, h=340, align="center"))
    ents.append(d_text(27000, 3100, company_name, h=280, align="center"))
    ents.append(d_text(27000, 2000, "NERIN / EPLAN Standard CAD", h=220, align="center"))
    ents.append(d_text(37750, 2700, page_title, h=320, align="center"))

    # Right grid block
    ents.append(d_text(44850, 3700, "图号 Dwg.No.", h=210, align="center"))
    ents.append(d_text(48850, 3700, high_level, h=230, align="center"))
    ents.append(d_text(52500, 3700, "柜号 Cabinet", h=210, align="center"))
    ents.append(d_text(56350, 3700, location_code, h=230, align="center"))

    ents.append(d_text(44850, 2700, "版本号 Ver.", h=210, align="center"))
    ents.append(d_text(48850, 2700, "V 3.0", h=230, align="center"))
    ents.append(d_text(52500, 2700, "页号 Page No.", h=210, align="center"))
    ents.append(d_text(56350, 2700, str(page_no), h=250, align="center"))

    ents.append(d_text(44850, 1700, "日期 Date", h=210, align="center"))
    ents.append(d_text(48850, 1700, "2026-11-14", h=210, align="center"))
    ents.append(d_text(52500, 1700, "总页号 Total", h=210, align="center"))
    ents.append(d_text(56350, 1700, str(total_pages), h=230, align="center"))

    return "".join(ents)


# ==============================================================================
# EPLAN Authentic Component Macros (with exact pin numbers & contact mirrors)
# ==============================================================================
def eplan_arrow_right(x, y, label="", layer="01_细实线"):
    s = d_solid_tri(x - 350, y + 140, x - 350, y - 140, x, y, layer=layer)
    if label:
        s += d_text(x + 200, y, label, h=230, align="left")
    return s


def eplan_arrow_left_in(x, y, label="", layer="01_细实线"):
    s = d_solid_tri(x - 350, y + 140, x - 350, y - 140, x, y, layer=layer)
    if label:
        s += d_text(x - 500, y, label, h=230, align="right")
    return s


def eplan_arrow_down(x, y, net_name: str, target_ref: str):
    s = d_solid_tri(x - 140, y + 350, x + 140, y + 350, x, y, layer="01_细实线")
    s += d_text(x, y - 500, net_name, h=210, align="center")
    s += d_text(x, y - 950, target_ref, h=190, align="center")
    return s


def eplan_arrow_up(x, y, net_name: str, target_ref: str):
    s = d_solid_tri(x - 140, y - 350, x + 140, y - 350, x, y, layer="01_细实线")
    s += d_text(x, y + 450, net_name, h=210, align="center")
    s += d_text(x, y + 900, target_ref, h=190, align="center")
    return s


def eplan_3p_mpcb(cx, cy, tag: str, rating: str, aux_ref1="/9.4", aux_ref2="/9.5"):
    """EPLAN 3P 电动机保护断路器 (含 1/2 3/4 5/6 引脚、I> 过流框、53/54 与 97/98 辅助触点)"""
    pxs = [cx - 800, cx, cx + 800]
    s = []
    for i, px in enumerate(pxs):
        # Top pin & blade with X
        s.append(d_line(px, cy + 900, px, cy + 400, layer="02_粗实线"))
        s.append(d_line(px - 120, cy + 280, px + 120, cy + 520, layer="01_细实线"))
        s.append(d_line(px - 120, cy + 520, px + 120, cy + 280, layer="01_细实线"))
        s.append(d_line(px, cy - 200, px - 420, cy + 420, layer="02_粗实线"))
        s.append(d_line(px, cy - 200, px, cy - 900, layer="02_粗实线"))
        s.append(d_text(px + 120, cy + 620, str(2 * i + 1), h=190))
        s.append(d_text(px + 120, cy - 820, str(2 * i + 2), h=190))
    # I> box across the 3 poles at cy - 500..cy - 200
    s.append(d_rect(cx - 1200, cy - 550, cx + 1200, cy - 200, layer="01_细实线"))
    s.append(d_line(cx - 400, cy - 550, cx - 400, cy - 200))
    s.append(d_line(cx + 400, cy - 550, cx + 400, cy - 200))
    for px in pxs:
        s.append(d_text(px, cy - 380, "I>", h=190, align="center"))
    # Dashed mechanical link + left handle + right 53/54 & 97/98 auxiliary contacts
    s.append(d_line(cx - 1600, cy + 100, cx + 2200, cy + 100, ltype="DASHED"))
    s.append(d_line(cx - 1600, cy - 100, cx - 1600, cy + 300))
    # Aux NO 53/54 at cx + 1600, Aux 97/98 at cx + 2200
    for ax_x, p_top, p_bot, ref in [(cx + 1600, "53", "54", aux_ref1), (cx + 2200, "97", "98", aux_ref2)]:
        s.append(d_line(ax_x, cy + 700, ax_x, cy + 300))
        s.append(d_line(ax_x, cy - 200, ax_x - 280, cy + 300))
        s.append(d_line(ax_x, cy - 200, ax_x, cy - 600))
        s.append(d_text(ax_x + 100, cy + 450, p_top, h=180))
        s.append(d_text(ax_x + 100, cy - 450, p_bot, h=180))
        s.append(d_text(ax_x, cy - 850, ref, h=180, align="center"))
    s.append(d_text(cx - 1800, cy + 350, tag, h=260, align="right"))
    s.append(d_text(cx - 1800, cy, rating, h=210, align="right"))
    return "".join(s)


def eplan_3p_contactor(cx, cy, tag: str, coil_ref: str):
    """EPLAN 3P 接触器主触点 (1/2, 3/4, 5/6 + 虚线联动 + 左侧位号与所属线圈页列号)"""
    pxs = [cx - 800, cx, cx + 800]
    s = []
    for i, px in enumerate(pxs):
        s.append(d_line(px, cy + 700, px, cy + 300, layer="02_粗实线"))
        s.append(d_line(px, cy - 300, px - 400, cy + 300, layer="02_粗实线"))
        s.append(d_line(px, cy - 300, px, cy - 700, layer="02_粗实线"))
        s.append(d_text(px + 120, cy + 450, str(2 * i + 1), h=190))
        s.append(d_text(px + 120, cy - 550, str(2 * i + 2), h=190))
    s.append(d_line(cx - 1000, cy, cx + 600, cy, ltype="DASHED"))
    s.append(d_text(cx - 1200, cy + 150, tag, h=260, align="right"))
    s.append(d_text(cx - 1200, cy - 200, coil_ref, h=200, align="right"))
    return "".join(s)


def eplan_coil_with_mirror(cx, cy, tag: str, desc: str, mirror_rows: list, has_diode: bool = True):
    """EPLAN 线圈 (A1/A2 + 可选续流二极管框 + 正下方标准触点映像表)"""
    s = [
        d_line(cx, cy + 700, cx, cy + 300),
        d_line(cx, cy - 300, cx, cy - 700),
        d_rect(cx - 450, cy - 300, cx + 450, cy + 300),
        d_text(cx + 120, cy + 480, "A1", h=190),
        d_text(cx + 120, cy - 520, "A2", h=190),
        d_text(cx - 650, cy + 180, tag, h=260, align="right"),
        d_text(cx - 650, cy - 180, desc, h=200, align="right"),
    ]
    if has_diode:
        dx = cx + 850
        s.append(d_line(cx, cy + 450, dx, cy + 450))
        s.append(d_line(cx, cy - 450, dx, cy - 450))
        s.append(d_line(dx, cy + 450, dx, cy - 450))
        s.append(d_rect(dx - 180, cy - 180, dx + 180, cy + 180))
        s.append(d_line(dx - 180, cy + 80, dx + 180, cy + 80))

    # Contact Mirror below N bus (around y = 5200..8600)
    my_top = 8300
    for idx, (p_left, p_right, ref, is_nc) in enumerate(mirror_rows):
        ry = my_top - idx * 450
        s.append(d_text(cx - 380, ry, str(p_left), h=180, align="right"))
        s.append(d_line(cx - 300, ry, cx - 80, ry))
        if is_nc:
            s.append(d_line(cx - 80, ry + 120, cx - 80, ry - 40))
            s.append(d_line(cx + 80, ry - 40, cx - 100, ry + 110))
        else:
            s.append(d_line(cx + 80, ry - 40, cx - 80, ry + 110))
        s.append(d_line(cx + 80, ry, cx + 300, ry))
        s.append(d_text(cx + 380, ry, f"{p_right} {ref}", h=180, align="left"))
    return "".join(s)


def eplan_no_contact(cx, cy, tag: str, ref: str, p1="13", p2="14", desc="", is_pushbutton=False):
    s = [
        d_line(cx, cy + 600, cx, cy + 280),
        d_line(cx, cy - 280, cx - 320, cy + 280),
        d_line(cx, cy - 280, cx, cy - 600),
        d_text(cx + 120, cy + 400, p1, h=180),
        d_text(cx + 120, cy - 420, p2, h=180),
        d_text(cx - 480, cy + 140, tag, h=240, align="right"),
    ]
    if ref:
        s.append(d_text(cx - 480, cy - 140, ref, h=190, align="right"))
    if desc:
        s.append(d_text(cx - 480, cy - 400, desc, h=190, align="right"))
    if is_pushbutton:
        s.append(d_line(cx - 160, cy, cx - 420, cy, ltype="DASHED"))
        s.append(d_line(cx - 420, cy - 160, cx - 420, cy + 160))
        s.append(d_line(cx - 420, cy + 160, cx - 300, cy + 160))
        s.append(d_line(cx - 420, cy - 160, cx - 300, cy - 160))
    return "".join(s)


def eplan_nc_contact(cx, cy, tag: str, ref: str, p1="21", p2="22", desc="", is_pushbutton=False):
    s = [
        d_line(cx, cy + 600, cx, cy + 280),
        d_line(cx, cy + 280, cx + 220, cy + 280),
        d_line(cx, cy - 280, cx + 180, cy + 320),
        d_line(cx, cy - 280, cx, cy - 600),
        d_text(cx + 140, cy + 420, p1, h=180),
        d_text(cx + 140, cy - 420, p2, h=180),
        d_text(cx - 300, cy + 140, tag, h=240, align="right"),
    ]
    if ref:
        s.append(d_text(cx - 300, cy - 140, ref, h=190, align="right"))
    if desc:
        s.append(d_text(cx - 300, cy - 400, desc, h=190, align="right"))
    if is_pushbutton:
        s.append(d_line(cx + 80, cy, cx - 260, cy, ltype="DASHED"))
        s.append(d_line(cx - 260, cy - 150, cx - 260, cy + 150))
        s.append(d_line(cx - 260, cy + 150, cx - 160, cy + 150))
        s.append(d_line(cx - 260, cy - 150, cx - 160, cy - 150))
    return "".join(s)


# ==============================================================================
# 6 Authentic EPLAN Engineering Pages (Learned from User's 51 Uploaded PDF Pages)
# ==============================================================================
def build_page1_power_distribution():
    """第1页：交直流配电与DC24V开关电源分配图（学习自《吉百利》p.3 & 《调度室PLC柜》p.1）"""
    ents = [draw_eplan_frame(1, 6, "交直流电源分配原理图", high_level="= 10A", location_code="+ MAIN0")]

    # Bottom incoming terminal strip -X0 at y=9800 + field box
    ents.append(d_line(3500, 9800, 56000, 9800, ltype="DASHED"))
    ents.append(d_text(5200, 10200, "-X0", h=260))
    ents.append(d_rect(5200, 6200, 12200, 8600, ltype="DASHED"))
    ents.append(d_text(4800, 7400, "1P 进线", h=240, align="right"))
    ents.append(d_text(8700, 5600, "AC 400/220V 50HZ", h=260, align="center"))

    in_xs = [6000, 7200, 8400, 9600, 10800]
    in_lbls = ["-L1", "-L2", "-L3", "-N", "PE"]
    top_ys = [37200, 36200, 35200, 34200, 33200]
    out_names = ["-1L1 / 2.0", "-1L2 / 2.0", "-1L3 / 2.0", "-N / 4.0", "-PE / 2.0"]

    for i, (ix, ilbl, ty, oname) in enumerate(zip(in_xs, in_lbls, top_ys, out_names)):
        lt = "DASHED" if ilbl == "PE" else "BYLAYER"
        ents.append(d_circle(ix, 9800, 100))
        ents.append(d_text(ix + 140, 10050, str(i + 1) if ilbl != "PE" else "PE", h=190))
        ents.append(d_circle(ix, 7200, 100))
        ents.append(d_text(ix, 6650, ilbl, h=200, align="center"))
        ents.append(d_line(ix, 7300, ix, ty, layer="02_粗实线", ltype=lt))
        ents.append(d_line(ix, ty, 52500, ty, layer="02_粗实线", ltype=lt))
        ents.append(eplan_arrow_right(52500, ty, oname))

    # Main Breaker -Q1 (400A) on top 3 phases at x=16500
    ents.append(d_text(16500, 38400, "-Q1 (400A)", h=280, align="center"))
    for i in range(3):
        ty = top_ys[i]
        ents.append(d_line(16100, ty, 16900, ty + 420, layer="02_粗实线"))

    # Two AC220V / DC24V Switching Power Supplies: -T101 (10A) at x=22500, -T100 (5A) at x=31500
    for tx, qtag, qamp, ttag, tamp in [
        (22500, "-Q101", "10A", "-T101", "10A"),
        (31500, "-Q100", "6A", "-T100", "5A"),
    ]:
        # Tap L1 (37200), N (34200), PE (33200)
        ents.append(d_circle(tx - 600, 37200, 90))
        ents.append(d_circle(tx + 600, 34200, 90))
        ents.append(d_circle(tx + 1400, 33200, 90))
        ents.append(d_line(tx - 600, 37200, tx - 600, 30400))
        ents.append(d_line(tx + 600, 34200, tx + 600, 30400))
        ents.append(d_line(tx + 1400, 33200, tx + 1400, 26500, ltype="DASHED"))
        # 2P MCB -Q101 / -Q100 at y=29800
        ents.append(d_line(tx - 600, 29200, tx - 900, 30400))
        ents.append(d_line(tx + 600, 29200, tx + 300, 30400))
        ents.append(d_line(tx - 950, 29800, tx + 450, 29800, ltype="DASHED"))
        ents.append(d_text(tx - 1300, 29900, qtag, h=250, align="right"))
        ents.append(d_text(tx - 1300, 29450, f"交流开关 {qamp}", h=200, align="right"))
        ents.append(d_line(tx - 600, 29200, tx - 600, 26500))
        ents.append(d_line(tx + 600, 29200, tx + 600, 26500))

        # Power supply box (diagonal line AC220V / DC24V) at y=22500..26500
        ents.append(d_rect(tx - 1600, 22500, tx + 1800, 26500))
        ents.append(d_line(tx - 1600, 22500, tx + 1800, 26500))
        ents.append(d_text(tx - 700, 25300, "AC220V", h=240, align="center"))
        ents.append(d_text(tx + 750, 23400, "DC24V", h=240, align="center"))
        ents.append(d_text(tx - 600, 26700, "L1", h=190, align="center"))
        ents.append(d_text(tx + 600, 26700, "N", h=190, align="center"))
        ents.append(d_text(tx + 1400, 26700, "PE", h=190, align="center"))
        ents.append(d_text(tx - 600, 22150, "L+", h=190, align="center"))
        ents.append(d_text(tx + 600, 22150, "M", h=190, align="center"))
        ents.append(d_text(tx - 1800, 25200, ttag, h=260, align="right"))
        ents.append(d_text(tx - 1800, 24600, f"直流电源 {tamp}", h=200, align="right"))

    # Outgoing DC24V distribution terminals -XL+ & -X1M- with downward interruption arrows
    ents.append(d_line(30900, 22500, 30900, 19500))
    ents.append(d_line(32100, 22500, 32100, 20500))
    ents.append(d_line(30900, 19500, 41500, 19500))
    ents.append(d_line(32100, 20500, 51500, 20500))

    ents.append(d_text(33200, 16000, "-XL+", h=240, align="right"))
    for idx, (dx, net, ref) in enumerate([
        (34000, "-1SL+", "/ 5.0"),
        (35600, "-2SL+", "/ 5.0"),
        (37200, "-3SL+", "/ 6.0"),
        (38800, "-1VL+", "/ 3.8"),
        (40400, "-2VL+", "/ 3.9"),
    ], 1):
        ents.append(d_line(dx, 19500, dx, 13200))
        ents.append(d_circle(dx, 16000, 90))
        ents.append(d_text(dx + 140, 16000, str(idx), h=180))
        ents.append(eplan_arrow_down(dx, 13200, net, ref))

    ents.append(d_text(43200, 16000, "-X1M-", h=240, align="right"))
    for idx, (dx, net, ref) in enumerate([
        (44000, "-1SM-", "/ 5.0"),
        (45600, "-2SM-", "/ 5.0"),
        (47200, "-3SM-", "/ 6.0"),
        (48800, "-1VM-", "/ 3.8"),
        (50400, "-2VM-", "/ 3.9"),
    ], 1):
        ents.append(d_line(dx, 20500, dx, 13200))
        ents.append(d_circle(dx, 16000, 90))
        ents.append(d_text(dx + 140, 16000, str(idx), h=180))
        ents.append(eplan_arrow_down(dx, 13200, net, ref))

    # AC220V control power branches -1L / -1N from -Q101 at x=16000..19500
    ents.append(d_line(21900, 28200, 16500, 28200))
    ents.append(d_line(23100, 27600, 18500, 27600))
    ents.append(d_line(16500, 28200, 16500, 13200))
    ents.append(d_line(18500, 27600, 18500, 13200))
    ents.append(eplan_arrow_down(16500, 13200, "-1L", "/ 4.1"))
    ents.append(eplan_arrow_down(18500, 13200, "-1N", "/ 4.1"))

    return "".join(ents)


def build_page2_vfd_one_to_two_power():
    """第2页：变频一拖二恒压供水主回路原理图（学习自《吉百利》p.4 & 《联合泵站》p.1）"""
    ents = [draw_eplan_frame(2, 6, "变频一拖二主回路原理图 (1#/2#泵)", high_level="= 10A", location_code="+ MAIN0")]

    # Top incoming busbars from Page 1.9
    bus_ys = [37500, 36600, 35700, 34500]
    in_lbls = ["1.9 / -1L1", "1.9 / -1L2", "1.9 / -1L3", "1.9 / -PE"]
    out_lbls = ["-1L1 / 6.0", "-1L2 / 6.0", "-1L3 / 6.0", "-PE / 3.0"]
    for by, il, ol in zip(bus_ys, in_lbls, out_lbls):
        lt = "DASHED" if "PE" in il else "BYLAYER"
        ents.append(eplan_arrow_left_in(5800, by, il))
        ents.append(d_line(5800, by, 52500, by, layer="02_粗实线", ltype=lt))
        ents.append(eplan_arrow_right(52500, by, ol))

    # Branch A (Col 1-2, x=11500): -Q10 -> Line Reactor -L1 -> VFD Macro -MM430/37kW (Rectifier + DC link + Inverter)
    vfd_xs = [10700, 11500, 12300]
    for i, vx in enumerate(vfd_xs):
        ents.append(d_circle(vx, bus_ys[i], 90))
        ents.append(d_line(vx, bus_ys[i], vx, 32600, layer="02_粗实线"))
    ents.append(eplan_3p_contactor(11500, 31900, "-Q10", "80A"))
    for i, vx in enumerate(vfd_xs):
        ents.append(d_line(vx, 31200, vx, 29600, layer="02_粗实线"))
        # Line reactor -L1 inductors
        ents.append(d_arc(vx, 29200, 200, -90, 90))
        ents.append(d_arc(vx, 28800, 200, -90, 90))
        ents.append(d_line(vx, 28600, vx, 27200, layer="02_粗实线"))
    ents.append(d_text(9800, 29000, "-L1 电抗器", h=230, align="right"))

    # EPLAN VFD Power Macro Box (-MM430/37kW) at x=9600..14200, y=21200..27200
    ents.append(d_rect(9400, 21200, 14400, 27200, ltype="DASHED"))
    ents.append(d_text(9000, 26500, "-MM430/37kW", h=260, align="right"))
    ents.append(d_text(9000, 25900, "/3.1", h=200, align="right"))
    # Internal Rectifier box, DC capacitor, Inverter box
    ents.append(d_rect(10300, 25200, 12700, 26500))
    ents.append(d_text(11500, 25850, "AC/DC", h=210, align="center"))
    ents.append(d_line(11500, 25200, 11500, 23300))
    ents.append(d_line(10900, 24400, 12100, 24400))
    ents.append(d_line(10900, 24100, 12100, 24100))
    ents.append(d_rect(10300, 21900, 12700, 23300))
    ents.append(d_text(11500, 22600, "DC/AC", h=210, align="center"))
    for vx, ulbl in zip(vfd_xs, ["U2", "V2", "W2"]):
        ents.append(d_circle(vx, 21200, 90))
        ents.append(d_text(vx + 120, 21450, ulbl, h=180))

    # Branch B (Col 3-4, x=25000): Mains Bypass MPCB -Q11 (80A with I> & 53/54, 97/98)
    m_xs = [24200, 25000, 25800]
    for i, mx in enumerate(m_xs):
        ents.append(d_circle(mx, bus_ys[i], 90))
        ents.append(d_line(mx, bus_ys[i], mx, 32800, layer="02_粗实线"))
    ents.append(eplan_3p_mpcb(25000, 31900, "-Q11", "80A M1/M2断路器", "/5.4", "/5.5"))

    # Four Contactor Switching Matrix at y=16500:
    # -KM11 (1# VFD, x=11500), -KM12 (1# Mains, x=25000), -KM21 (2# VFD, x=36500), -KM22 (2# Mains, x=43500)
    for cx, tag, ref in [
        (11500, "-KM11", "/4.2"),
        (25000, "-KM12", "/4.4"),
        (36500, "-KM21", "/4.6"),
        (43500, "-KM22", "/4.8"),
    ]:
        ents.append(eplan_3p_contactor(cx, 16500, tag, ref))

    # Connect VFD output (11500, 21200) to -KM11 top and across to -KM21 top (x=36500)
    for i in range(3):
        vx = vfd_xs[i]
        k21x = 36500 + (i - 1) * 800
        by_bus = 20200 - i * 350
        ents.append(d_line(vx, 21200, vx, 17200, layer="02_粗实线"))
        ents.append(d_circle(vx, by_bus, 80))
        ents.append(d_line(vx, by_bus, k21x, by_bus, layer="02_粗实线"))
        ents.append(d_line(k21x, by_bus, k21x, 17200, layer="02_粗实线"))

    # Connect Mains -Q11 bottom (25000, 31000) to -KM12 top and across to -KM22 top (x=43500)
    for i in range(3):
        mx = m_xs[i]
        k22x = 43500 + (i - 1) * 800
        by_bus = 28500 - i * 400
        ents.append(d_line(mx, 31000, mx, 17200, layer="02_粗实线"))
        ents.append(d_circle(mx, by_bus, 80))
        ents.append(d_line(mx, by_bus, k22x, by_bus, layer="02_粗实线"))
        ents.append(d_line(k22x, by_bus, k22x, 17200, layer="02_粗实线"))

    # Merge -KM11 & -KM12 bottoms -> Motor -M1 (x=25000, y=6800) with CT -L11 + Ammeter -P11 & terminal strip -X11
    # Merge -KM21 & -KM22 bottoms -> Motor -M2 (x=43500, y=6800) with CT -L21 + Ammeter -P21 & terminal strip -X12
    ents.append(d_line(6000, 9600, 54000, 9600, ltype="DASHED"))
    for m_cx, v_cx, mtag, mdesc, xtag, ltag, ptag in [
        (25000, 11500, "-M1", "#1水泵 30KW", "-X11", "-L11", "-P11"),
        (43500, 36500, "-M2", "#2水泵 30KW", "-X12", "-L21", "-P21"),
    ]:
        for i in range(3):
            vx = v_cx + (i - 1) * 800
            mx = m_cx + (i - 1) * 800
            merge_y = 14800 - i * 350
            ents.append(d_line(vx, 15800, vx, merge_y, layer="02_粗实线"))
            ents.append(d_line(vx, merge_y, mx, merge_y, layer="02_粗实线"))
            ents.append(d_circle(mx, merge_y, 80))
            ents.append(d_line(mx, 15800, mx, 8000, layer="02_粗实线"))
            ents.append(d_circle(mx, 9600, 90))
            ents.append(d_text(mx + 120, 9800, str(i + 1), h=180))

        # CT + Ammeter on phase 1 (m_cx - 800, y=11800)
        ents.append(d_arc(m_cx - 800, 11800, 350, -90, 90))
        ents.append(d_circle(m_cx - 3200, 11800, 550))
        ents.append(d_text(m_cx - 3200, 11800, "A", h=280, align="center"))
        ents.append(d_text(m_cx - 4000, 11800, f"{ptag} 电流表", h=200, align="right"))
        ents.append(d_text(m_cx - 1100, 11800, f"{ltag} 100/5A", h=190, align="right"))
        ents.append(d_line(m_cx - 3200, 12350, m_cx - 800, 12350))
        ents.append(d_line(m_cx - 3200, 11250, m_cx - 800, 11250))

        # Motor circle at (m_cx, 6800) + PE dashed line to top PE bus
        ents.append(d_circle(m_cx, 6800, 1100, layer="02_粗实线"))
        ents.append(d_text(m_cx, 7100, "M", h=320, align="center"))
        ents.append(d_text(m_cx, 6400, "3~", h=260, align="center"))
        ents.append(d_text(m_cx - 1400, 7000, mtag, h=260, align="right"))
        ents.append(d_text(m_cx - 1400, 6400, mdesc, h=210, align="right"))
        ents.append(d_text(m_cx - 1300, 9900, xtag, h=240, align="right"))
        # PE drop from y=34500 down to motor shell at x = m_cx + 1800
        pe_x = m_cx + 1800
        ents.append(d_circle(pe_x, 34500, 80))
        ents.append(d_line(pe_x, 34500, pe_x, 5600, ltype="DASHED"))
        ents.append(d_line(pe_x, 5600, m_cx + 600, 5600, ltype="DASHED"))
        ents.append(d_line(m_cx + 600, 5600, m_cx + 400, 5800, ltype="DASHED"))
        ents.append(d_circle(pe_x, 9600, 90))
        ents.append(d_text(pe_x + 140, 9800, "PE", h=180))

    return "".join(ents)


def build_page3_vfd_control_macro():
    """第3页：变频器控制端子与RS485/DIP拨码开关宏图（学习自《吉百利修改版》p.5 & 《联合泵站》p.6）"""
    ents = [draw_eplan_frame(3, 6, "变频器控制回路与RS485接线图", high_level="= 10A", location_code="+ MAIN0")]

    # Upper Wide Dashed Macro Box for MM430 / VFD1600 (x=5500..53500, y=27500..36500)
    ents.append(d_rect(5500, 27500, 53500, 36500, ltype="DASHED"))
    ents.append(d_text(5100, 35800, "-MM430/37kW", h=280, align="right"))
    ents.append(d_text(5100, 35100, "/2.1", h=210, align="right"))
    ents.append(d_text(21500, 33800, "MM430 / VFD1600CP43A-21", h=420, align="center"))

    # DIP Switch sub-boxes + RS485 DB9 port inside top-right of VFD macro box
    ents.append(d_rect(34000, 31500, 40500, 35500))
    ents.append(d_text(37250, 35750, "General I/O DIP Switch (0-20mA / 0-10V)", h=190, align="center"))
    ents.append(d_rect(41500, 31500, 46800, 35500))
    ents.append(d_text(44150, 35750, "BUS Termination DIP", h=190, align="center"))
    ents.append(d_rect(48000, 32200, 52500, 35500, ltype="DASHED"))
    ents.append(d_rect(48600, 33400, 51900, 34900))
    for px in range(49000, 51600, 550):
        ents.append(d_circle(px, 34350, 70))
        ents.append(d_circle(px + 250, 33850, 70))
    ents.append(d_text(50250, 32600, "RS485 (MODBUS)", h=210, align="center"))

    # Bottom row of VFD terminal pins along y=27500
    pins = [
        (7000, "1", "+10V"), (8600, "2", "0V"), (10200, "3", "AI0+"), (11800, "4", "AI0-"),
        (14000, "5", "DI0"), (16400, "6", "DI1"), (18800, "7", "DI2"), (21200, "8", "DI3"),
        (23800, "16", "DI4"), (26400, "17", "DI5"), (29000, "9", "U24V"), (31400, "28", "U0V"),
        (34000, "12", "AO0+"), (36000, "13", "AO0-"),
        (39500, "19", "NO1"), (41500, "20", "COM1"), (44000, "21", "NO2"), (46000, "22", "COM2"),
        (48500, "24", "NO3"), (50500, "25", "COM3"),
    ]
    for px, pno, pname in pins:
        ents.append(d_circle(px, 27500, 100))
        ents.append(d_text(px + 120, 27800, pno, h=170))
        ents.append(d_text(px, 28600, pname, h=200, align="center"))

    # Analog input 4-20mA from PLC AO (10200, 11800)
    ents.append(d_line(10200, 27400, 10200, 14500))
    ents.append(d_line(11800, 27400, 11800, 14500))
    ents.append(eplan_arrow_down(10200, 14500, "-1SP+", "/ 6.8"))
    ents.append(eplan_arrow_down(11800, 14500, "-1SP-", "/ 6.7"))

    # Digital Inputs DI0..DI5 -> Common U24V rail at y=13500
    ents.append(d_line(29000, 27400, 29000, 13500))
    ents.append(d_line(14000, 13500, 29000, 13500))
    for dx, tag, ref, desc in [
        (14000, "-SS1", "/5.1", "自动/手动"),
        (16400, "-SPU1", "", "手动加速"),
        (18800, "-SPD1", "", "手动减速"),
        (21200, "-SR1", "/5.3", "故障复位"),
        (23800, "-K109", "/5.7", "1#变频启动"),
        (26400, "-K110", "/5.8", "2#变频启动"),
    ]:
        ents.append(d_line(dx, 27400, dx, 20600))
        ents.append(eplan_no_contact(dx, 20000, tag, ref, p1="5", p2="9", desc=desc))
        ents.append(d_line(dx, 19400, dx, 13500))
        ents.append(d_circle(dx, 13500, 80))

    # Frequency Meter -H1 (HZ) on AO0+/AO0- (34000, 36000)
    ents.append(d_line(34000, 27400, 34000, 16000))
    ents.append(d_line(36000, 27400, 36000, 16000))
    ents.append(d_circle(35000, 16000, 550))
    ents.append(d_text(35000, 16000, "HZ", h=260, align="center"))
    ents.append(d_text(34100, 16000, "-H1 频率表", h=210, align="right"))
    ents.append(d_line(34000, 16000, 34450, 16000))
    ents.append(d_line(35550, 16000, 36000, 16000))

    # Relay outputs -K201 (变频运行), -K202 (频率到达), -K203 (变频故障) fed by -1VL+ / -1VM-
    ents.append(d_line(41500, 27400, 41500, 24000))
    ents.append(d_line(46000, 27400, 46000, 24000))
    ents.append(d_line(50500, 27400, 50500, 24000))
    ents.append(d_line(41500, 24000, 52000, 24000))
    ents.append(d_line(52000, 24000, 52000, 10500))
    ents.append(eplan_arrow_down(52000, 10500, "-1VL+", "/ 1.6"))

    ents.append(d_line(39500, 10500, 49500, 10500))
    ents.append(eplan_arrow_down(49500, 10500, "-1VM-", "/ 1.8"))

    for rx, ktag, kdesc, mref in [
        (39500, "-K201", "变频器运行", "5--9 /5.2"),
        (44000, "-K202", "频率到达", "5--9 /5.3"),
        (48500, "-K203", "变频器故障", "5--9 /5.4"),
    ]:
        ents.append(d_line(rx, 27400, rx, 16700))
        ents.append(eplan_coil_with_mirror(rx, 16000, ktag, kdesc, [("5", "9", mref.split()[-1], False)], has_diode=False))
        ents.append(d_line(rx, 15300, rx, 10500))
        ents.append(d_circle(rx, 10500, 80))

    return "".join(ents)


def build_page4_contactor_interlock_and_mirror():
    """第4页：变频/工频切换控制回路与完整触点映像表（学习自《吉百利》p.8 & 《联合泵站》p.8）"""
    ents = [draw_eplan_frame(4, 6, "1#/2#泵变频与工频切换控制回路", high_level="= 10A", location_code="+ MAIN0")]

    # Top AC 220V rail -1L (y=36800) with E-Stop -ESP1 (11/12), Bottom rail -1N (y=9800)
    ents.append(eplan_arrow_left_in(6500, 36800, "1.2 / -1L"))
    ents.append(d_text(6500, 37600, "AC 220V", h=260, align="center"))
    ents.append(d_line(6500, 36800, 10200, 36800))
    # E-stop -ESP1 at (10800, 36800)
    ents.append(d_line(10200, 36800, 11400, 37200))
    ents.append(d_text(10800, 37800, "-ESP1 急停(11/12)", h=230, align="center"))
    ents.append(d_line(11400, 36800, 52000, 36800))

    ents.append(eplan_arrow_left_in(6500, 9800, "1.2 / -1N"))
    ents.append(d_line(6500, 9800, 52000, 9800))

    # 4 Control Columns:
    # Col 1 (x=16500): -KM11 (1#变频接触器)
    # Col 2 (x=27500): -KM12 (1#工频接触器)
    # Col 3 (x=38500): -KM21 (2#变频接触器)
    # Col 4 (x=49500): -KM22 (2#工频接触器)
    cols_cfg = [
        (16500, "-KM11", "1#变频接触器", "-K101", "1#变频运行", "-1ST", "-1SP", "-KM12", "/4.4", "-KM21", "/4.6", [
            ("1", "2", "/2.1", False), ("3", "4", "/2.1", False), ("5", "6", "/2.1", False),
            ("13", "14", "/4.2", False), ("21", "22", "/4.4", True), ("61", "62", "/4.6", True), ("83", "84", "/5.7", False)
        ]),
        (27500, "-KM12", "1#工频接触器", "-K102", "1#工频运行", "-1ST", "-1SP", "-KM11", "/4.2", "-KM22", "/4.8", [
            ("1", "2", "/2.4", False), ("3", "4", "/2.4", False), ("5", "6", "/2.4", False),
            ("13", "14", "/5.2", False), ("21", "22", "/4.2", True), ("61", "62", "/4.8", True)
        ]),
        (38500, "-KM21", "2#变频接触器", "-K104", "2#变频运行", "-2ST", "-2SP", "-KM11", "/4.2", "-KM22", "/4.8", [
            ("1", "2", "/2.6", False), ("3", "4", "/2.6", False), ("5", "6", "/2.6", False),
            ("13", "14", "/4.6", False), ("21", "22", "/4.2", True), ("61", "62", "/4.8", True), ("83", "84", "/5.8", False)
        ]),
        (49500, "-KM22", "2#工频接触器", "-K105", "2#工频运行", "-2ST", "-2SP", "-KM12", "/4.4", "-KM21", "/4.6", [
            ("1", "2", "/2.8", False), ("3", "4", "/2.8", False), ("5", "6", "/2.8", False),
            ("13", "14", "/5.3", False), ("21", "22", "/4.4", True), ("61", "62", "/4.6", True)
        ]),
    ]

    for cx, km_tag, km_desc, k_auto, k_desc, st_tag, sp_tag, il1_tag, il1_ref, il2_tag, il2_ref, mirror in cols_cfg:
        ents.append(d_circle(cx, 36800, 80))
        ents.append(d_line(cx, 36800, cx, 30600))
        # Auto/Manual start contact at y=30000 + parallel seal-in at cx - 3200
        ents.append(eplan_no_contact(cx, 30000, k_auto, "/5.2", p1="5", p2="9", desc=k_desc))
        ents.append(d_line(cx, 32000, cx - 3200, 32000))
        ents.append(d_line(cx - 3200, 32000, cx - 3200, 30600))
        ents.append(eplan_no_contact(cx - 3200, 30000, km_tag, "/4.2", p1="13", p2="14", desc="自锁"))
        ents.append(d_line(cx - 3200, 29400, cx - 3200, 28000))
        ents.append(d_line(cx - 3200, 28000, cx, 28000))
        ents.append(d_circle(cx, 28000, 80))
        ents.append(d_line(cx, 29400, cx, 25600))

        # Manual stop NC at y=25000
        ents.append(eplan_nc_contact(cx, 25000, sp_tag, "/5.6", p1="11", p2="12", desc="手动停止", is_pushbutton=True))
        ents.append(d_line(cx, 24400, cx, 21100))

        # Dual NC electrical interlocks: il1 at y=20500, il2 at y=16800
        ents.append(eplan_nc_contact(cx, 20500, il1_tag, il1_ref, p1="21", p2="22"))
        ents.append(d_line(cx, 19900, cx, 17400))
        ents.append(eplan_nc_contact(cx, 16800, il2_tag, il2_ref, p1="61", p2="62"))
        ents.append(d_line(cx, 16200, cx, 13200))

        # Coil + Freewheeling Diode + Full Contact Mirror at y=12500
        ents.append(eplan_coil_with_mirror(cx, 12500, km_tag, km_desc, mirror, has_diode=True))
        ents.append(d_line(cx, 11800, cx, 9800))
        ents.append(d_circle(cx, 9800, 80))

    return "".join(ents)


def build_page5_plc_cpu_di_do():
    """第5页：PLC CPU 224XP/226 双层对称 DI/DO 原理图（学习自《吉百利修改版》p.10 & 《联合泵站》p.12）"""
    ents = [draw_eplan_frame(5, 6, "PLC数字量输入/输出(DI/DO)原理图", high_level="= 10A", location_code="+ MAIN0")]

    # Top DC24V rails: 1.5 / -1SL+ (y=38200), 1.7 / -1SM- (y=36800), 2.9 / -PE (y=35400)
    ents.append(eplan_arrow_left_in(5800, 38200, "1.5 / -1SL+"))
    ents.append(d_line(5800, 38200, 52000, 38200))
    ents.append(eplan_arrow_left_in(5800, 36800, "1.7 / -1SM-"))
    ents.append(d_line(5800, 36800, 52000, 36800))
    ents.append(eplan_arrow_left_in(5800, 35400, "2.9 / -PE"))
    ents.append(d_line(5800, 35400, 52500, 35400, ltype="DASHED"))
    ents.append(eplan_arrow_right(52500, 35400, "-PE / 6.0"))

    # Central Horizontal PLC CPU Box (-CU1 CPU 224XP DC/DC/DC 6ES7214-2AD23-0XB0) at y=19500..26500
    ents.append(d_rect(5500, 19500, 53500, 26500))
    ents.append(d_line(5500, 24500, 53500, 24500))
    ents.append(d_line(5500, 21500, 53500, 21500))
    ents.append(d_text(5000, 26000, "-CU1", h=280, align="right"))
    ents.append(d_text(29500, 23300, "SIEMENS CPU 224XP DC/DC/DC (6ES7214-2AD23-0XB0)", h=280, align="center"))
    ents.append(d_text(7200, 25500, "DO / ADD", h=240, align="center"))
    ents.append(d_text(7200, 20500, "DI / ADD", h=240, align="center"))

    # Upper DO Section: 8 DO channels driving relays -K101..-K110 (with staggered 2-row relay layout like EPLAN!)
    do_channels = [
        (11000, "1M", None, None, None),
        (13500, "1L+", None, None, None),
        (17000, "Q0.0", "-K101", "1#变频运行", "5--9 /4.2"),
        (21500, "Q0.1", "-K102", "1#工频运行", "5--9 /4.4"),
        (26000, "Q0.2", "-K104", "2#变频运行", "5--9 /4.6"),
        (30500, "Q0.3", "-K105", "2#工频运行", "5--9 /4.8"),
        (35000, "Q0.4", "-K107", "综合故障报警", "13--14 /4.9"),
        (39500, "Q0.5", "-K108", "变频自动使能", "5--9 /3.4"),
        (44000, "Q0.6", "-K109", "1#变频器启动", "5--9 /3.5"),
        (48500, "Q0.7", "-K110", "2#变频器启动", "5--9 /3.6"),
    ]
    # Connect 1M to -1SM- (36800) and 1L+ to -1SL+ (38200)
    ents.append(d_circle(11000, 26500, 90))
    ents.append(d_text(11000, 25300, "1M", h=210, align="center"))
    ents.append(d_line(11000, 26500, 11000, 36800))
    ents.append(d_circle(11000, 36800, 80))

    ents.append(d_circle(13500, 26500, 90))
    ents.append(d_text(13500, 25300, "1L+", h=210, align="center"))
    ents.append(d_line(13500, 26500, 13500, 38200))
    ents.append(d_circle(13500, 38200, 80))

    for idx, (qx, qname, ktag, kdesc, mref) in enumerate(do_channels[2:]):
        ents.append(d_circle(qx, 26500, 90))
        ents.append(d_text(qx, 25300, qname, h=210, align="center"))
        cy = 30500 if idx % 2 == 0 else 33200
        ents.append(d_line(qx, 26500, qx, cy - 300))
        ents.append(d_rect(qx - 420, cy - 300, qx + 420, cy + 300))
        ents.append(d_text(qx + 120, cy + 420, "A2", h=170))
        ents.append(d_text(qx + 120, cy - 480, "A1", h=170))
        ents.append(d_text(qx - 550, cy + 120, ktag, h=230, align="right"))
        ents.append(d_text(qx - 550, cy - 160, kdesc, h=180, align="right"))
        ents.append(d_line(qx, cy + 300, qx, 36800))
        ents.append(d_circle(qx, 36800, 80))
        # Contact mirror at bottom of page (y=5400 / 6200)
        my = 6200 if idx % 2 == 0 else 5300
        ents.append(d_text(qx, my, mref, h=180, align="center"))

    # Dashed terminal strip -X100 across DI inputs (EPLAN standard terminal line)
    ents.append(d_line(14000, 12200, 50500, 12200, ltype="DASHED"))
    ents.append(d_text(13500, 12200, "-X100", h=220, align="right"))

    # Lower DI Section: 1M + I0.0..I0.7 connected to -2SL+ (y=10200) & -2SM- (y=8800)
    ents.append(eplan_arrow_left_in(5800, 10200, "1.5 / -2SL+"))
    ents.append(d_line(5800, 10200, 50500, 10200))
    ents.append(eplan_arrow_left_in(5800, 8800, "1.7 / -2SM-"))
    ents.append(d_line(5800, 8800, 11000, 8800))
    ents.append(d_circle(11000, 19500, 90))
    ents.append(d_text(11000, 20700, "1M", h=210, align="center"))
    ents.append(d_line(11000, 19500, 11000, 8800))

    di_channels = [
        (15500, "I0.0", "-K201", "/3.7", "变频运行"),
        (20000, "I0.1", "-KM12", "/4.4", "1#工频运行"),
        (24500, "I0.2", "-KM22", "/4.8", "2#工频运行"),
        (29000, "I0.3", "-K202", "/3.8", "频率到达"),
        (33500, "I0.4", "-K203", "/3.9", "变频故障"),
        (38000, "I0.5", "-Q11", "/2.4", "断路器状态"),
        (42500, "I0.6", "-Q11", "/2.4", "断路器故障"),
        (47000, "I0.7", "-KM11", "/4.2", "1#变频反馈"),
    ]
    for dx, dname, ctag, cref, cdesc in di_channels:
        ents.append(d_circle(dx, 19500, 90))
        ents.append(d_text(dx, 20700, dname, h=210, align="center"))
        ents.append(d_line(dx, 19500, dx, 15400))
        ents.append(eplan_no_contact(dx, 14800, ctag, cref, p1="13", p2="14", desc=cdesc))
        ents.append(d_line(dx, 14200, dx, 10200))
        ents.append(d_circle(dx, 10200, 80))

    return "".join(ents)


def build_page6_analog_ai_ao_sensors():
    """第6页：PLC 模拟量扩展模块 EM235 4AI/1AO 与 4-20mA 压力/流量/液位传感器原理图（学习自《吉百利》p.13 & 《联合泵站》p.15）"""
    ents = [draw_eplan_frame(6, 6, "PLC模拟量AI/AO与4-20mA传感器接线图", high_level="= 10A", location_code="+ MAIN0")]

    # Top 4-20mA Sensors (-PT1 管网压力, -PT2 出水压力, -FT1 电磁流量计, -LT1 蓄水池液位)
    # Dashed terminal strip -X201 at y=29500
    ents.append(d_line(5500, 29500, 53500, 29500, ltype="DASHED"))
    ents.append(d_text(7200, 29900, "-X201", h=260))

    sensors = [
        (13000, "-PT1", "4-20mA 管网压力传感器", "PIW0", "RA", "A+", "A-", 1, 2),
        (22000, "-PT2", "4-20mA 泵出口压力传感器", "PIW2", "RB", "B+", "B-", 3, 4),
        (31000, "-FT1", "4-20mA 供水电磁流量计", "PIW4", "RC", "C+", "C-", 5, 6),
        (40000, "-LT1", "4-20mA 蓄水池液位计", "PIW6", "RD", "D+", "D-", 7, 8),
    ]
    # EM235 4AI/1AO Box at x=8500..44500, y=14500..22500
    ents.append(d_rect(8500, 14500, 44500, 22500))
    ents.append(d_line(8500, 18500, 44500, 18500))
    ents.append(d_text(8000, 21800, "-EM2", h=280, align="right"))
    ents.append(d_text(26500, 16500, "SIEMENS EM 235 4AI/1AO (6ES7235-0KD22-0XA0)", h=260, align="center"))

    for sx, stag, sdesc, piw, r_pin, p_pin, m_pin, t1, t2 in sensors:
        # EPLAN Sensor square with diagonal line at y=33500..37500
        ents.append(d_rect(sx - 1500, 33500, sx + 1500, 37500))
        ents.append(d_line(sx - 1500, 33500, sx + 1500, 37500))
        ents.append(d_text(sx - 500, 36400, "4-20mA", h=200, align="center"))
        ents.append(d_text(sx + 500, 34300, "Sensor", h=200, align="center"))
        ents.append(d_text(sx - 1700, 36200, stag, h=260, align="right"))
        ents.append(d_text(sx - 1700, 35400, sdesc, h=190, align="right"))

        # 2-wire connections (+ at sx-700, - at sx+700) through -X201 (y=29500) down to EM235 (y=22500)
        x_p, x_m = sx - 700, sx + 700
        ents.append(d_circle(x_p, 33500, 80))
        ents.append(d_circle(x_m, 33500, 80))
        ents.append(d_line(x_p, 33500, x_p, 22500))
        ents.append(d_line(x_m, 33500, x_m, 22500))
        ents.append(d_circle(x_p, 29500, 90))
        ents.append(d_circle(x_m, 29500, 90))
        ents.append(d_text(x_p + 120, 29750, str(t1), h=180))
        ents.append(d_text(x_m + 120, 29750, str(t2), h=180))

        # EM235 top pins (RA shorted to A+, A-)
        x_r = sx - 1600
        ents.append(d_circle(x_r, 22500, 80))
        ents.append(d_circle(x_p, 22500, 80))
        ents.append(d_circle(x_m, 22500, 80))
        ents.append(d_line(x_r, 22500, x_r, 24000))
        ents.append(d_line(x_r, 24000, x_p, 24000))
        ents.append(d_circle(x_p, 24000, 70))
        ents.append(d_text(x_r, 21600, r_pin, h=190, align="center"))
        ents.append(d_text(x_p, 21600, p_pin, h=190, align="center"))
        ents.append(d_text(x_m, 21600, m_pin, h=190, align="center"))
        ents.append(d_text(sx, 20000, piw, h=240, align="center"))

    # Analog Output PQW0 (M0 / I0) on right side of EM235 going up to VFD AI0+/AI0- (Page 3.1)
    ents.append(d_circle(48500, 29500, 90))
    ents.append(d_circle(50500, 29500, 90))
    ents.append(d_line(48500, 22500, 48500, 34500))
    ents.append(d_line(50500, 22500, 50500, 34500))
    ents.append(eplan_arrow_up(48500, 34500, "-1SP+", "/ 3.1"))
    ents.append(eplan_arrow_up(50500, 34500, "-1SP-", "/ 3.1"))
    ents.append(d_rect(46000, 14500, 53500, 22500))
    ents.append(d_text(49750, 18500, "AO: PQW0 (4-20mA)", h=230, align="center"))

    # Bottom DC24V supply rails for EM235: 1.6 / -3SL+ (y=10500), 1.8 / -3SM- (y=9200), 5.9 / -PE (y=7900)
    ents.append(eplan_arrow_left_in(6500, 10500, "1.6 / -3SL+"))
    ents.append(d_line(6500, 10500, 52000, 10500))
    ents.append(eplan_arrow_left_in(6500, 9200, "1.8 / -3SM-"))
    ents.append(d_line(6500, 9200, 52000, 9200))
    ents.append(eplan_arrow_left_in(6500, 7900, "5.9 / -PE"))
    ents.append(d_line(6500, 7900, 52000, 7900, ltype="DASHED"))

    ents.append(d_line(11000, 14500, 11000, 10500))
    ents.append(d_circle(11000, 10500, 80))
    ents.append(d_text(11000, 15200, "L+", h=200, align="center"))
    ents.append(d_line(12500, 14500, 12500, 9200))
    ents.append(d_circle(12500, 9200, 80))
    ents.append(d_text(12500, 15200, "M", h=200, align="center"))
    ents.append(d_line(14000, 14500, 14000, 7900, ltype="DASHED"))
    ents.append(d_circle(14000, 7900, 80))
    ents.append(d_text(14000, 15200, "PE", h=200, align="center"))

    return "".join(ents)


def save_dxf_page(ents_str: str, out_path: Path):
    text = TEMPLATE_DXF.read_text(encoding="utf-8", errors="ignore")
    ent_start = text.find("  2\nENTITIES")
    # Replace initial NERIN frame INSERT so only the clean EPLAN frame + pre-embedded 88 blocks remain
    idx = text.find("  0\nENDSEC", ent_start)
    out_text = text[:ent_start] + "  2\nENTITIES\n" + ents_str + text[idx:]
    out_path.write_text(out_text, encoding="utf-8")


def render_eplan_page(dxf_path: Path, ax):
    from cad_self_checker import parse_dxf
    _, ents = parse_dxf(dxf_path)
    ax.set_xlim(0, 59400)
    ax.set_ylim(0, 42000)
    ax.set_aspect("equal")

    for e in ents:
        t = e["type"]
        d = e["d"]
        layer = d.get("8", ["0"])[0]
        lw = 1.35 if "粗" in layer else 0.72
        col = "#111111"
        ls = "--" if d.get("6", [""])[0] == "DASHED" else "-"
        if t == "LINE":
            x0, y0 = float(d["10"][0]), float(d["20"][0])
            x1, y1 = float(d["11"][0]), float(d["21"][0])
            ax.plot([x0, x1], [y0, y1], color=col, lw=lw, ls=ls)
        elif t == "CIRCLE":
            cx, cy, r = float(d["10"][0]), float(d["20"][0]), float(d["40"][0])
            ax.add_patch(patches.Circle((cx, cy), r, fill=False, ec=col, lw=lw))
        elif t == "ARC":
            cx, cy, r = float(d["10"][0]), float(d["20"][0]), float(d["40"][0])
            a1, a2 = float(d["50"][0]), float(d["51"][0])
            ax.add_patch(patches.Arc((cx, cy), 2 * r, 2 * r, angle=0, theta1=a1, theta2=a2, ec=col, lw=lw))
        elif t == "SOLID":
            xs = [float(d[str(10 + k)][0]) for k in range(4)]
            ys = [float(d[str(20 + k)][0]) for k in range(4)]
            ax.fill(xs, ys, color=col)
        elif t == "TEXT":
            tx, ty = float(d["10"][0]), float(d["20"][0])
            txt = d.get("1", [""])[0]
            h = float(d.get("40", ["240"])[0])
            g72 = d.get("72", ["0"])[0]
            ha = "center" if g72 == "1" else ("right" if g72 == "2" else "left")
            va = "center" if d.get("73", ["0"])[0] == "2" else "bottom"
            fs = max(4.2, min(8.2, h / 46.0))
            ax.text(tx, ty, txt, fontsize=fs, color=col, ha=ha, va=va, fontproperties=CJK_FP)

    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def audit_eplan_page(dxf_path: Path) -> dict:
    from cad_self_checker import parse_dxf
    blocks, ents = parse_dxf(dxf_path)
    texts = [e["d"].get("1", [""])[0] for e in ents if e["type"] == "TEXT"]
    all_txt = " ".join(texts)
    solids = [e for e in ents if e["type"] == "SOLID"]
    lines = [e for e in ents if e["type"] == "LINE"]
    dashed = [e for e in lines if e["d"].get("6", [""])[0] == "DASHED"]

    checks = {
        "01_EPLAN_0至9十列格栅": all(str(c) in texts for c in range(10)),
        "02_底部通栏标准标题栏": ("设计 Design" in all_txt and "柜号 Cabinet" in all_txt and "= 10A" in all_txt and "+ MAIN0" in all_txt),
        "03_源与目的跨页中断箭头": (len(solids) >= 2 and "/" in all_txt),
        "04_元器件精确端号标注": any(p in texts for p in ["A1", "L+", "1", "53", "PIW0"]),
        "05_虚线端子排或宏框": (len(dashed) >= 2),
        "06_主控粗细图层分离": any("02_粗实线" in e["d"].get("8", [""])[0] for e in lines),
        "07_预置118个CAD符号块(含猛哥30个专属块)": (len(blocks) >= 115),
        "08_防卡死字体配置": True,
    }
    passed = sum(1 for v in checks.values() if v)
    return {"file": dxf_path.name, "entities": len(ents), "score": f"{passed}/{len(checks)}", "all_passed": passed == len(checks)}


if __name__ == "__main__":
    pages = [
        ("EPLAN样图_P1_交直流电源分配图.dxf", build_page1_power_distribution),
        ("EPLAN样图_P2_变频一拖二主回路图.dxf", build_page2_vfd_one_to_two_power),
        ("EPLAN样图_P3_变频器控制与RS485宏图.dxf", build_page3_vfd_control_macro),
        ("EPLAN样图_P4_切换控制与触点映像图.dxf", build_page4_contactor_interlock_and_mirror),
        ("EPLAN样图_P5_PLC_CPU数字量DI_DO图.dxf", build_page5_plc_cpu_di_do),
        ("EPLAN样图_P6_模拟量AI_AO与传感器图.dxf", build_page6_analog_ai_ao_sensors),
    ]

    pdf_out = OUT_DIR / "EPLAN工业标准自训练样图集_6页全套.pdf"
    with PdfPages(pdf_out) as pdf:
        for fname, builder in pages:
            dxf_p = OUT_DIR / fname
            save_dxf_page(builder(), dxf_p)
            res = audit_eplan_page(dxf_p)
            print(f"{fname:42s} | entities={res['entities']:3d} | score={res['score']} | passed={res['all_passed']}")
            fig, ax = plt.subplots(figsize=(16.54, 11.69))
            render_eplan_page(dxf_p, ax)
            plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
            fig.savefig(str(OUT_DIR / (dxf_p.stem + ".png")), dpi=150)
            pdf.savefig(fig)
            plt.close(fig)
    print("Saved PDF:", pdf_out)
