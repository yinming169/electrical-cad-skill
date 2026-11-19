#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
“电气一次图 (铜陵有色设计院 CAD 标准) + 电气二次图 (EPLAN + 猛哥符号库标准)”双轨制图与严苛自审引擎
====================================================================================================
严格遵循用户指令：
1. 【电气一次图】：完全按照上传的 `yes.dxf`、《三期余热发电施工图》、《189.dxf 渣选改造施工图》、《122.dxf 冬瓜山6kV一次系统图》画法：
   - 图框与图签：采用《铜陵有色图签02》（无顶部 0~9 列号，右下角标准工程院会签栏 + 标题栏，图名下方带粗细双下划线 `═══` 及《设计说明》）。
   - 0.4kV MNS 低压配电系统图：顶部三行通栏表头（`开关柜编号` | `开关柜尺寸` | `小室高度:mm`），主母线 `TMY-4(125×8)`，单线回路含干式变压器 (`△/═/Y⏚`)、抽出式断路器双尖角插头 (`︽` + `×` + `︾`)、三圆电流互感器 (`◯─/─#─◯─/─#─◯─/─#`)、单圆测量 CT (`◯─/─#`)、电度表框 `[Wh]` (`6NTPM600`/`AEM96`)、浪涌保护器 (`SPD-T1/50/4P`)、晶闸管动态无功补偿 (`△` 三角电容组)、马达保护器框 `[马达保护器]`、电缆终端倒三角 `▽`、去向方框 (`[BP1]`, `[AL1]`)、底部两行对位表（`设备功率` | `设备名称`）及左下角《能耗监测系统拓扑图》。
   - XL-21 现场动力配电柜一次系统图：外包柜体大矩形框 + 左上角梯形铭牌框 `[AP1]`，顶部中央进线断路器 + 三圆 CT + 电度表 + SPD，内部水平母线引出 10~12 路垂直分支（断路器 `×` + 接触器 + 热继电器 `[` + 底部倒三角电缆头 `▽` + `M31 / WC31 [AC31]`），柜下配双行对位负荷表（功率 + 负荷名称）。
   - 现场变频控制柜 (`BP1/BP2`) 与横向壁挂配电箱 (`AD`) 一次系统图：变频柜内含总塑壳 + 主变频器方框 `[V/f变频器 | 90kW]` + 右侧独立散热风机支路（微断 + 接触器 + 热继电器），柜下配双列表格；横向配电箱左进右出，进出线及支路带 `///` 三相斜线标识与漏电保护圆环。
   - 10kV / 6kV 高压配电一次系统图：顶部高压母线 `TMY-3(80×8)`，左上方五联竖排二次设备小方框（`[PJ] 电力仪表`、`[IOD] 智能操控`、`[MPD] 微机综保`、`[°C] 智能除湿`、`[CW] 无线测温`），手车式真空断路器 (`VBG-12kV`)，双排/三排三圆互感器 (`LZZBJ9-10`)，接地刀闸 (`JN15-12`)，氧化锌避雷器 (`HYSWZ-17/45`) + 带电显示器 (`DXN-10`)，零序 CT (`LXX-Φ100`)，底部 6 行开关柜参数表（`开关柜编号/开关柜名称/设备功率/计算电流/开关柜型号/开关柜尺寸`）。
2. 【电气二次图】：完全保持 EPLAN Electric P8 生成规范与《猛哥专用符号库.sdb》(`MENGGE_*`) 画法（顶部 0~9 十列格栅 + 底部通栏 EPLAN 标题栏 + 跨页中断箭头 + 线圈下方触点映像表 + 真实 `MENGGE_*` 符号）。
"""

import json
import math
import re
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages

from path_utils import TEMPLATE_READY_DXF, SYMBOLS_134_DXF
from eplan_cad_engine import (
    OUT_DIR, CJK_FP,
    d_line, d_rect, d_circle, d_arc, d_solid_tri, d_text,
    save_dxf_page, render_eplan_page
)
from mengge_sample_generator import (
    build_s3_workshop_valve_control,
    build_s4_contactor_interlock_and_mirror,
    build_s5_plc_cpu_di_do_with_mengge,
)
from cad_strict_auditor import audit_dxf_strict


# ==============================================================================
# 1. 注入 10 个核心《电气一次系统图》标准图块 (PRIM_*) 至 DXF 符号库与模板
# ==============================================================================
def build_primary_dxf_blocks() -> str:
    """构建 10 个源自 yes.dxf / 189.dxf / 122.dxf 的原生电气一次图标准块"""
    blocks = []

    def wrap_blk(name, body):
        return f"  0\nBLOCK\n  8\n0\n  2\n{name}\n 70\n0\n 10\n0.0\n 20\n0.0\n 30\n0.0\n  3\n{name}\n  1\n\n{body}  0\nENDBLK\n  8\n0\n"

    # 1. PRIM_CT3_KK: 三圆电流互感器组 (源自 yes.dxf Block KK: ◯─/─#─◯─/─#─◯─/─#)
    b_kk = (
        d_circle(-700, 0, 210) + d_circle(0, 0, 210) + d_circle(700, 0, 210)
        + d_line(-490, 0, -210, 0) + d_line(210, 0, 490, 0) + d_line(910, 0, 1250, 0)
        + d_line(-410, -140, -290, 140) + d_line(-330, -140, -210, 140)
        + d_line(290, -140, 410, 140) + d_line(370, -140, 490, 140)
        + d_line(990, -140, 1110, 140) + d_line(1070, -140, 1190, 140)
    )
    blocks.append(wrap_blk("PRIM_CT3_KK", b_kk))

    # 2. PRIM_CT1_GHF: 单圆测量/零序互感器 (源自 yes.dxf Block GHF: ◯─//)
    b_ghf = (
        d_circle(0, 0, 210)
        + d_line(210, 0, 620, 0)
        + d_line(320, -140, 440, 140) + d_line(430, -140, 550, 140)
    )
    blocks.append(wrap_blk("PRIM_CT1_GHF", b_ghf))

    # 3. PRIM_DRAWOUT_UP / PRIM_DRAWOUT_DN: 抽出式手车/抽屉柜上下双尖角插头 (源自 yes.dxf Block HG)
    b_hg_up = (
        d_line(-280, -220, 0, 0) + d_line(0, 0, 280, -220)
        + d_line(-280, -420, 0, -200) + d_line(0, -200, 280, -420)
    )
    blocks.append(wrap_blk("PRIM_DRAWOUT_UP", b_hg_up))
    b_hg_dn = (
        d_line(-280, 220, 0, 0) + d_line(0, 0, 280, 220)
        + d_line(-280, 420, 0, 200) + d_line(0, 200, 280, 420)
    )
    blocks.append(wrap_blk("PRIM_DRAWOUT_DN", b_hg_dn))

    # 4. PRIM_CB_DYDQ: 一次单线断路器 (源自 yes.dxf Block DYDQ0201: × 灭弧符号 + 斜刀闸)
    b_cb = (
        d_line(0, 600, 0, 250)
        + d_line(-140, 110, 140, 390) + d_line(-140, 390, 140, 110)
        + d_line(-320, 220, 0, -350)
        + d_line(0, -350, 0, -600)
    )
    blocks.append(wrap_blk("PRIM_CB_DYDQ", b_cb))

    # 5. PRIM_SPD_HFH: 熔断器 + 浪涌保护器/避雷器 + 接地支路 (源自 yes.dxf Block HFH)
    b_spd = (
        d_line(0, 0, 1600, 0)
        + d_rect(300, -140, 750, 140)
        + d_rect(950, -180, 1450, 180)
        + d_line(1450, 0, 1750, 0)
        + d_line(1750, -260, 1750, 260)
        + d_line(1860, -180, 1860, 180)
        + d_line(1970, -100, 1970, 100)
    )
    blocks.append(wrap_blk("PRIM_SPD_HFH", b_spd))

    # 6. PRIM_CABLE_HEAD: 电缆终端头倒三角符号 ▽
    b_ch = d_line(-220, 260, 220, 260) + d_line(-220, 260, 0, -180) + d_line(220, 260, 0, -180)
    blocks.append(wrap_blk("PRIM_CABLE_HEAD", b_ch))

    # 7. PRIM_TRANSFORMER_DYN11: 干式变压器一次符号 (△ / ═ / Y⏚, 源自 yes.dxf 低压配电系统图一)
    b_tr = (
        d_line(0, 1100, -320, 550) + d_line(-320, 550, 320, 550) + d_line(320, 550, 0, 1100)
        + d_line(-420, 220, 420, 220) + d_line(-420, 80, 420, 80)
        + d_line(-280, -200, 0, -520) + d_line(280, -200, 0, -520) + d_line(0, -520, 0, -900)
        + d_line(-750, -520, 0, -520)
        + d_line(-750, -340, -750, -700) + d_line(-860, -420, -860, -620) + d_line(-970, -480, -970, -560)
    )
    blocks.append(wrap_blk("PRIM_TRANSFORMER_DYN11", b_tr))

    # 8. PRIM_CAP_DELTA: 动态无功补偿三角形电容器组符号 (源自 yes.dxf 1AN2/MNS)
    b_cap = (
        d_line(0, 700, -650, -500) + d_line(0, 700, 650, -500) + d_line(-650, -500, 650, -500)
        + d_line(-220, -100, 220, -100) + d_line(-220, -240, 220, -240)
    )
    blocks.append(wrap_blk("PRIM_CAP_DELTA", b_cap))

    # 9. PRIM_THERMAL_REL: 一次系统图热继电器符号 `[`
    b_th = d_line(0, 350, 0, 180) + d_line(0, 180, -220, 180) + d_line(-220, 180, -220, -180) + d_line(-220, -180, 0, -180) + d_line(0, -180, 0, -350)
    blocks.append(wrap_blk("PRIM_THERMAL_REL", b_th))

    # 10. PRIM_HV_ARRESTER: 高压三相氧化锌避雷器符号 (源自 yes.dxf 10kV系统图 HYSWZ-17/45)
    b_arr = (
        d_rect(-160, -320, 160, 320)
        + d_line(0, 320, 0, 600) + d_line(0, -320, 0, -600)
        + d_line(-240, -600, 240, -600) + d_line(-160, -700, 160, -700) + d_line(-80, -800, 80, -800)
    )
    blocks.append(wrap_blk("PRIM_HV_ARRESTER", b_arr))

    return "".join(blocks)


def inject_primary_blocks():
    prim_str = build_primary_dxf_blocks()
    for fname in ["standard-symbols-IEC-EPLAN.dxf", "NERIN-A2-frame-ready.dxf"]:
        p = OUT_DIR / fname
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        txt = re.sub(r"  0\nBLOCK\n  8\n0\n  2\nPRIM_.*?\n  0\nENDBLK\n  8\n0\n", "", txt, flags=re.DOTALL)
        b_start = txt.find("SECTION\n  2\nBLOCKS")
        b_end = txt.find("  0\nENDSEC", b_start)
        if b_start != -1 and b_end != -1:
            txt = txt[:b_end] + prim_str + txt[b_end:]
            p.write_text(txt, encoding="utf-8")


# ==============================================================================
# 2. 铜陵有色设计研究院标准 A2 一次系统图图框与右下角会签图签 (《铜陵有色图签02》)
# ==============================================================================
def draw_tongling_primary_frame(
    drawing_title: str,
    drawing_no: str,
    project_name: str = "三期余热发电及尾矿脱水优化改造项目",
    sub_project: str = "变电所及现场配电",
    stage: str = "施工图",
    date_str: str = "2026.11",
) -> str:
    """
    绘制《yes.dxf / 189.dxf》同款铜陵有色设计研究院标准 A2 图框 (59400 × 42000)：
    - 无顶部 0~9 列格栅（纯正国内甲级设计院一次系统图风格）
    - 外框细线 (1500, 1200)..(58200, 40800)，内框粗实线 (3500, 2200)..(57200, 39800)
    - 右下角完整复刻《铜陵有色图签02》：左侧多专业会签栏（总图/冶炼/选矿/采矿/建筑/化工/暖通/机械/热工/给排水/自控/电气）+
      中部审定/审核/校对/设计栏 + 建设单位（铜陵有色金属集团股份有限公司 金冠铜业分公司）+
      工程名称 + 图名 + 设计院名称（铜陵有色设计研究院有限责任公司 Tongling Nonferrous Design and Research Institute Co.,Ltd.）+
      图号与版本三角标 `△ 0`
    """
    s = []
    # Outer thin border & Inner thick border
    s.append(d_rect(1500, 1200, 58200, 40800, "01_细实线"))
    s.append(d_rect(3500, 2200, 57200, 39800, "02_粗实线"))

    # Bottom-right Title Block & Countersignature Table (x: 24500..57200, y: 2200..5600)
    tx0, tx1, ty0, ty1 = 24500, 57200, 2200, 5600
    s.append(d_rect(tx0, ty0, tx1, ty1, "02_粗实线"))

    # Horizontal rows in title block (5 rows, each 680 high)
    row_ys = [2200 + k * 680 for k in range(1, 5)]
    for ry in row_ys[:4]:
        s.append(d_line(tx0, ry, 38500, ry))

    # Right side horizontal splits (x: 38500..57200)
    s.append(d_line(38500, 3560, 57200, 3560))
    s.append(d_line(38500, 2880, 50500, 2880))
    s.append(d_line(43200, 4240, 48800, 4240))

    # Vertical dividers in Countersignature & Signature block
    v_cols = [25300, 26800, 28300, 29800, 31300, 32800, 34300, 36200, 38500, 43200, 48800, 50500]
    for vx in v_cols[:9]:
        s.append(d_line(vx, ty0, vx, ty1))
    s.append(d_line(43200, ty0, 43200, ty1))
    s.append(d_line(48800, ty0, 48800, ty1))
    s.append(d_line(50500, ty0, 50500, 3560))

    # Labels in Countersignature Table
    s.append(d_text(24900, 4600, "会", 180, align="center"))
    s.append(d_text(24900, 3800, "签", 180, align="center"))
    s.append(d_text(24900, 3000, "栏", 180, align="center"))

    depts_col1 = [("总 图", 5150), ("冶 炼", 4470), ("选 矿", 3790), ("采 矿", 3110), ("专 业", 2430)]
    depts_col2 = [("建 筑", 5150), ("化 工", 4470), ("暖 通", 3790), ("机 械", 3110), ("专 业", 2430)]
    depts_col3 = [("热 工", 5150), ("给排水", 4470), ("自 控", 3790), ("电 气", 3110), ("专 业", 2430)]
    roles_col4 = [("项目负责人", 5150), ("审 定", 4470), ("审 核", 3790), ("校 对", 3110), ("设 计", 2430)]
    for lbl, ly in depts_col1:
        s.append(d_text(26050, ly, lbl, 150, align="center"))
    for lbl, ly in depts_col2:
        s.append(d_text(29050, ly, lbl, 150, align="center"))
    for lbl, ly in depts_col3:
        s.append(d_text(32050, ly, lbl, 150, align="center"))
    for lbl, ly in roles_col4:
        s.append(d_text(35250, ly, lbl, 150, align="center"))
    s.append(d_text(37350, 2430, "殷 明", 165, align="center"))
    s.append(d_text(37350, 3790, "赵 猛", 165, align="center"))

    # Client & Project cells
    s.append(d_text(40850, 4700, "铜陵有色金属集团股份有限公司", 165, align="center"))
    s.append(d_text(40850, 4100, "金冠铜业分公司", 165, align="center"))
    s.append(d_text(46000, 4750, project_name, 160, align="center"))
    s.append(d_text(46000, 3800, sub_project, 165, align="center"))

    # Project metadata cells (x: 38500..48800, y: 2200..3560)
    s.append(d_text(39600, 3120, "项目编号", 150, align="center"))
    s.append(d_text(41900, 3120, "TL1070-2026", 155, align="center"))
    s.append(d_text(39600, 2430, "设计阶段", 150, align="center"))
    s.append(d_text(41900, 2430, stage, 155, align="center"))

    s.append(d_text(44000, 3120, "专业", 145, align="center"))
    s.append(d_text(45200, 3120, "电气", 155, align="center"))
    s.append(d_text(46400, 3120, "比例", 145, align="center"))
    s.append(d_text(47800, 3120, "1:100", 150, align="center"))

    s.append(d_text(44000, 2430, "图幅", 145, align="center"))
    s.append(d_text(45200, 2430, "A2", 155, align="center"))
    s.append(d_text(46400, 2430, "日期", 145, align="center"))
    s.append(d_text(47800, 2430, date_str, 150, align="center"))

    # Drawing Title & Design Institute Name
    s.append(d_text(53000, 4750, "铜陵有色设计研究院有限责任公司", 195, align="center"))
    s.append(d_text(53000, 4300, "Tongling Nonferrous Design and Research Institute Co.,Ltd.", 120, align="center"))
    s.append(d_text(51200, 3800, drawing_title, 220, align="center"))

    s.append(d_text(49650, 2750, "图号", 160, align="center"))
    s.append(d_text(53300, 2750, drawing_no, 185, align="center"))

    # Revision Triangle `△ 0` at bottom right (56300, 2500)
    s.append(d_line(55850, 2400, 56650, 2400))
    s.append(d_line(55850, 2400, 56250, 3100))
    s.append(d_line(56650, 2400, 56250, 3100))
    s.append(d_text(56250, 2520, "0", 165, align="center"))

    return "".join(s)


def draw_double_underlined_title(x: float, y: float, title: str, width: float = 6800) -> str:
    """绘制一次系统图底部标志性的双下划线图名（上粗下细）"""
    hw = width / 2.0
    return (
        d_text(x, y + 260, title, h=280, align="center")
        + d_line(x - hw, y, x + hw, y, layer="02_粗实线")
        + d_line(x - hw, y - 130, x + hw, y - 130, layer="01_细实线")
    )


def prim_ct3(x: float, y: float, ratio_str: str = "1000/5") -> str:
    """绘制 yes.dxf / 189.dxf 标志性三圆电流互感器 (◯─/─#─◯─/─#─◯─/─#)"""
    r = 210
    s = (
        d_circle(x - 620, y, r)
        + d_circle(x, y, r)
        + d_circle(x + 620, y, r)
        + d_line(x - 410, y, x - 210, y)
        + d_line(x + 210, y, x + 410, y)
        + d_line(x + 830, y, x + 1150, y)
        + d_line(x - 350, y - 140, x - 250, y + 140)
        + d_line(x + 270, y - 140, x + 370, y + 140)
        + d_line(x + 920, y - 140, x + 1020, y + 140)
        + d_line(x + 1000, y - 140, x + 1100, y + 140)
    )
    if ratio_str:
        s += d_text(x + 1280, y - 90, ratio_str, h=165, align="left")
    return s


def prim_ct1(x: float, y: float, ratio_str: str = "3000/5") -> str:
    """绘制单圆测量/零序互感器 (◯─//)"""
    s = (
        d_circle(x, y, 200)
        + d_line(x + 200, y, x + 580, y)
        + d_line(x + 310, y - 130, x + 410, y + 130)
        + d_line(x + 410, y - 130, x + 510, y + 130)
    )
    if ratio_str:
        s += d_text(x + 680, y - 80, ratio_str, h=165, align="left")
    return s


def prim_drawout_up(x: float, y: float) -> str:
    """绘制手车/抽屉式上插头双尖角 ︽"""
    return (
        d_line(x - 240, y - 180, x, y) + d_line(x, y, x + 240, y - 180)
        + d_line(x - 240, y - 340, x, y - 160) + d_line(x, y - 160, x + 240, y - 340)
    )


def prim_drawout_dn(x: float, y: float) -> str:
    """绘制手车/抽屉式下插头双尖角 ︾"""
    return (
        d_line(x - 240, y + 180, x, y) + d_line(x, y, x + 240, y + 180)
        + d_line(x - 240, y + 340, x, y + 160) + d_line(x, y + 160, x + 240, y + 340)
    )


def prim_cb(x: float, y: float, model: str = "", rating: str = "", set1: str = "", set2: str = "") -> str:
    """绘制一次单线断路器 (严格按 DYDQ0201 / 1107AA / QLS1 标准：上触点 × 居中于 (x, y)，下铰接点在 (x, y-820)，斜刀闸 (x, y-820)->(x-410, y))"""
    y_top = y
    y_bot = y - 820.0
    s = (
        d_line(x - 140, y_top - 140, x + 140, y_top + 140, layer="02_粗实线")
        + d_line(x - 140, y_top + 140, x + 140, y_top - 140, layer="02_粗实线")
        + d_line(x, y_bot, x - 410, y_top, layer="02_粗实线")
    )
    ty = y_top - 100
    for txt in [model, rating, set1, set2]:
        if txt:
            s += d_text(x + 280, ty, txt, h=155, align="left")
            ty -= 280
    return s


def prim_cable_head(x: float, y: float, w_no: str = "", spec1: str = "", spec2: str = "") -> str:
    """绘制电缆终端倒三角 ▽ 及右侧回路号与电缆规格"""
    s = (
        d_line(x - 180, y + 220, x + 180, y + 220)
        + d_line(x - 180, y + 220, x, y - 140)
        + d_line(x + 180, y + 220, x, y - 140)
    )
    ty = y + 220
    for txt in [w_no, spec1, spec2]:
        if txt:
            s += d_text(x + 260, ty, txt, h=150, align="left")
            ty -= 260
    return s


# ==============================================================================
# P1: 10kV 高压配电系统一次图 (复刻自 yes.dxf《硫酸10kV高配所Ⅱ段母线新增开关柜系统图》& 122.dxf)
# ==============================================================================
def build_p1_10kv_hv_primary_system():
    ents = [draw_tongling_primary_frame("10kV高压配电系统图", "TL1070-201DL-02", sub_project="硫酸10kV高配所改造")]

    # Left half: 10kV KYN28A-12 Switchgear Primary System Diagram (3 Columns: AH2, AH1, AH3)
    # Top 10kV Busbar WBM (y=36200, x=7500..31500)
    ents.append(d_line(7500, 36200, 31500, 36200, layer="02_粗实线"))
    ents.append(d_text(7500, 36600, "10kV, II段 TMY-3(80×8), 1250A, 与原高压柜拼接", h=210, align="left"))
    ents.append(d_text(31200, 36600, "II段母线", h=200, align="right"))

    hv_cols = [
        (11500, "AH2", "余热发电三期1#变压器柜", "1250kVA", "72A", "KYN28A-12", "800×1500×2300",
         "PST645UX(变压器)", "VBG-12kV (DC220V)", "630A-31.5kA", "LZZBJ9-10, 150/5", "0.5/10P20, 15/20VA",
         "WG1", "ZR-YJV-8.7/10kV", "3×95", False),
        (19500, "AH1", "余热发电三期并网接入柜", "10.5kV 10MW", "607.3A", "KYN28A-12", "800×1500×2300",
         "PA150-D(光纤差动)", "VBG-12kV (DC220V)", "1250A-31.5kA", "LZZBJ9-10, 1200/5", "0.5/10P20/10P20",
         "WG2", "ZR-YJV-8.7/10kV", "3×(3×185)", True),
        (27500, "AH3", "冬瓜山-1000m泵房馈线柜", "2000kVA", "115.5A", "KYN28A-12", "800×1500×2300",
         "PST642U(线路保护)", "VBG-12kV (DC220V)", "1250A-31.5kA", "LZZBJ9-10, 300/5", "0.5/10P10, 15/20VA",
         "WG3", "ZR-YJV22-8.7/10kV", "3×120", False),
    ]

    for cx, c_no, c_name, c_pwr, c_cur, c_model, c_dim, mpd_str, vcb1, vcb2, ct1, ct2, w_no, c_spec1, c_spec2, has_pt in hv_cols:
        # Bus drop to upper draw-out plug (36200 -> 30400)
        ents.append(d_line(cx, 36200, cx, 30400, layer="02_粗实线"))
        ents.append(d_circle(cx, 36200, 75, layer="02_粗实线"))

        # 5-stacked secondary instrument boxes on left of vertical drop (y=35200 down to 31600)
        sec_boxes = [
            ("PJ", "电力仪表: APM520", 35000),
            ("IOD", "智能操控: ASD500", 34150),
            ("MPD", f"微机综保: {mpd_str}", 33300),
            ("°C", "智能除湿: EXN-CS600", 32450),
            ("CW", "无线测温: EXN27-RW6", 31600),
        ]
        for code, b_lbl, by in sec_boxes:
            ents.append(d_rect(cx - 1050, by - 320, cx - 250, by + 320))
            ents.append(d_line(cx - 250, by, cx, by))
            ents.append(d_text(cx - 650, by - 90, code, h=155, align="center"))
            ents.append(d_text(cx + 220, by - 90, b_lbl, h=150, align="left"))

        # Draw-out Vacuum Circuit Breaker VBG-12kV (y=30400..27400)
        ents.append(prim_drawout_up(cx, 30400))
        ents.append(d_line(cx, 30050, cx, 29300, layer="02_粗实线"))
        ents.append(prim_cb(cx, 29000, vcb1, vcb2))
        ents.append(d_line(cx, 28700, cx, 27750, layer="02_粗实线"))
        ents.append(prim_drawout_dn(cx, 27400))

        # 2-row 3-circle CT group (y=26000 & y=25200)
        ents.append(d_line(cx, 27400, cx, 21200, layer="02_粗实线"))
        ents.append(prim_ct3(cx, 26000, ""))
        ents.append(prim_ct3(cx, 25100, ""))
        ents.append(d_text(cx + 1280, 25850, ct1, h=150, align="left"))
        ents.append(d_text(cx + 1280, 25000, ct2, h=145, align="left"))

        # Left branch at y=23600: Earthing Switch JN15-12/31.5
        ents.append(d_line(cx - 1500, 23600, cx + 1400, 23600))
        ents.append(d_line(cx - 1500, 23600, cx - 1500, 23000))
        ents.append(d_line(cx - 1750, 22400, cx - 1500, 23000))
        ents.append(d_line(cx - 1500, 22400, cx - 1500, 21600))
        ents.append(d_line(cx - 1780, 21600, cx - 1220, 21600))
        ents.append(d_line(cx - 1680, 21450, cx - 1320, 21450))
        ents.append(d_text(cx - 1500, 20950, "JN15-12/31.5", h=145, align="center"))

        # Right branch at y=23600: Oxide Surge Arrester HYSWZ-17/45 + DXN-10
        ents.append(d_line(cx + 1400, 23600, cx + 1400, 22900))
        ents.append(d_rect(cx + 1240, 22000, cx + 1560, 22900))
        ents.append(d_line(cx + 1400, 22000, cx + 1400, 21600))
        ents.append(d_line(cx + 1160, 21600, cx + 1640, 21600))
        ents.append(d_line(cx + 1240, 21450, cx + 1560, 21450))
        ents.append(d_text(cx + 1720, 22350, "HYSWZ-17/45", h=145, align="left"))
        ents.append(d_text(cx + 420, 20950, "DXN-10", h=145, align="center"))

        # Optional Voltage Transformer JDZX9-10 for AH1
        if has_pt:
            ents.append(d_line(cx - 650, 23600, cx - 650, 22800))
            ents.append(d_rect(cx - 780, 22100, cx - 520, 22800))
            ents.append(d_text(cx - 880, 21700, "XRNP-12/0.5A", h=135, align="center"))
            ents.append(d_circle(cx - 650, 21150, 240))
            ents.append(d_text(cx - 650, 21050, "V", h=160, align="center"))
            ents.append(d_text(cx - 650, 20350, "JDZX9-10", h=140, align="center"))

        # Zero-sequence CT LXX-Φ100 + Cable head at bottom (y=19800 & y=18400)
        ents.append(d_line(cx, 21200, cx, 17400, layer="02_粗实线"))
        ents.append(d_circle(cx, 19800, 210))
        ents.append(d_text(cx + 320, 19700, "LXX-Φ100 50/1A", h=150, align="left"))
        ents.append(prim_cable_head(cx, 18400, w_no, c_spec1, c_spec2))

    # Bottom 6-Row Parameter Table for 10kV Switchgear (x=4800..31500, y=9600..16200)
    tx0, tx1, ty0, ty1 = 4800, 31500, 9600, 16200
    ents.append(d_rect(tx0, ty0, tx1, ty1, "02_粗实线"))
    col_xs = [4800, 8800, 15500, 23500, 31500]
    for vx in col_xs[1:-1]:
        ents.append(d_line(vx, ty0, vx, ty1))
    row_titles = [
        ("开关柜编号", [c[1] for c in hv_cols]),
        ("开关柜名称", [c[2] for c in hv_cols]),
        ("设备功率", [c[3] for c in hv_cols]),
        ("计算电流", [c[4] for c in hv_cols]),
        ("开关柜型号", [c[5] for c in hv_cols]),
        ("开关柜尺寸", [c[6] for c in hv_cols]),
    ]
    for r_idx, (r_title, r_vals) in enumerate(row_titles):
        ry_top = ty1 - r_idx * 1100
        ry_bot = ry_top - 1100
        if r_idx > 0:
            ents.append(d_line(tx0, ry_top, tx1, ry_top))
        ymid = (ry_top + ry_bot) / 2.0 - 90
        ents.append(d_text(6800, ymid, r_title, h=175, align="center"))
        for c_idx, val in enumerate(r_vals):
            cx_cell = (col_xs[c_idx + 1] + col_xs[c_idx + 2]) / 2.0
            ents.append(d_text(cx_cell, ymid, val, h=170, align="center"))

    ents.append(draw_double_underlined_title(18150, 8100, "硫酸10kV高配所Ⅱ段母线新增开关柜系统图", 8800))

    # Right half: 10kV Substation Switchgear Arrangement Plan & Technical Notes (as in yes.dxf High-Voltage sheet!)
    ents.append(d_rect(34500, 18500, 55500, 35500, "02_粗实线"))
    ents.append(d_text(45000, 33800, "10kV高压配电室母线桥与开关柜排列平面布置图", h=230, align="center"))
    # Top row of cabinets (I段: +AA01..+AK10)
    for k in range(10):
        bx0 = 36500 + k * 1700
        ents.append(d_rect(bx0, 29500, bx0 + 1700, 32200))
        lbl = "Ⅰ段母线" if k == 0 else (f"+AK0{k}" if k < 10 else "+AK10")
        ents.append(d_text(bx0 + 850, 30700, lbl, h=150, align="center"))
    # Bottom row of cabinets (II段: AH1, AH2, AH3, +AK14..+AK20)
    bot_names = ["Ⅱ段母线", "AH1(新)", "AH2(新)", "AH3(新)", "+AK22", "+AK21", "+AK20", "+AK19", "+AK18", "+AK16"]
    for k, bname in enumerate(bot_names):
        bx0 = 36500 + k * 1700
        ents.append(d_rect(bx0, 22200, bx0 + 1700, 24900))
        ents.append(d_text(bx0 + 850, 23400, bname, h=145, align="center"))
    # Busbar bridge on right
    ents.append(d_rect(51800, 24900, 53500, 29500, ltype="DASHED"))
    ents.append(d_text(52650, 27100, "母线桥", h=170, align="center"))
    ents.append(draw_double_underlined_title(45000, 17000, "10kV高配所新增及改造开关柜平面布置图", 8200))

    # Design Notes at bottom right above title block (y=9600..15200)
    notes = [
        "设计说明：",
        "1. 10kV高配所Ⅱ段母线新增AH1并网接入柜、AH2余热发电1#变压器柜及AH3冬瓜山泵房馈线柜，柜型为KYN28A-12；",
        "2. 主母线采用TMY-3(80×8)铜母排，额定电流1250A，由开关柜成套厂随柜配供并与原母线可靠拼接；",
        "3. 微机综合保护装置采用PA150-D光纤差动及PST645UX变压器保护，操作电源DC220V引自站内直流屏；",
        "4. 高压柜内配置APM520多功能电力仪表、ASD500智能操控装置、EXN-CS600智能除湿及EXN27-RW6无线测温装置。",
    ]
    for idx, line in enumerate(notes):
        ents.append(d_text(34500, 15000 - idx * 820, line, h=180 if idx == 0 else 160, align="left"))

    return "".join(ents), [], [(f"HV_TABLE", 4800, 9600, 31500, 16200)], []


# ==============================================================================
# P2: 0.4kV 低压配电系统图 (复刻自 yes.dxf《低压配电系统图（一）、（二）、（三）》)
# ==============================================================================
def build_p2_lv_mns_primary_system():
    ents = [draw_tongling_primary_frame("低压配电系统图（一）", "TL1070-201DL-03-1", sub_project="余热发电厂房变电所")]

    # Top 3-Row Switchgear Header Table (x=8500..54500, y=34200..37500)
    # Columns: LabelCol(8500..12500), TM1(12500..20500), 1AN1/MNS(20500..27500), 1AN2/MNS(27500..34500), 1AN3/MNS(34500..41000), 1AN4/MNS(41000..54500: 3 drawers)
    hx0, hx1, hy0, hy1 = 8500, 54500, 34200, 37500
    ents.append(d_rect(hx0, hy0, hx1, hy1, "02_粗实线"))
    ents.append(d_line(hx0, 36400, hx1, 36400))
    ents.append(d_line(hx0, 35300, hx1, 35300))

    h_cols = [8500, 12500, 20500, 27500, 34500, 41000, 54500]
    for vx in h_cols[1:-1]:
        ents.append(d_line(vx, hy0, vx, hy1))
    # Subdivide 1AN4/MNS into 3 drawer columns in Row 3 (41000, 45500, 50000, 54500)
    ents.append(d_line(45500, hy0, 45500, 35300))
    ents.append(d_line(50000, hy0, 50000, 35300))

    ents.append(d_text(10500, 36750, "开关柜编号", h=165, align="center"))
    ents.append(d_text(10500, 35650, "开关柜尺寸", h=165, align="center"))
    ents.append(d_text(10500, 34550, "小室高度:mm", h=165, align="center"))

    cab_headers = [
        (16500, "TM1", "宽×深×高:2000×1500×2200", "—"),
        (24000, "1AN1/MNS", "宽×深×高:800×1000×2200", "1800"),
        (31000, "1AN2/MNS", "宽×深×高:800×1000×2200", "1800"),
        (37750, "1AN3/MNS", "宽×深×高:800×1000×2200", "1800"),
    ]
    for cx, cno, cdim, ch in cab_headers:
        ents.append(d_text(cx, 36750, cno, h=165, align="center"))
        ents.append(d_text(cx, 35650, cdim, h=150, align="center"))
        ents.append(d_text(cx, 34550, ch, h=160, align="center"))

    ents.append(d_text(47750, 36750, "1AN4/MNS (馈线及水泵抽屉柜)", h=165, align="center"))
    ents.append(d_text(47750, 35650, "宽×深×高:800×1000×2200", h=150, align="center"))
    for dcx, dh in [(43250, "600"), (47750, "400"), (52250, "200")]:
        ents.append(d_text(dcx, 34550, dh, h=160, align="center"))

    # Horizontal Main Busbar at y=31800 (x=22000..54500)
    ents.append(d_line(22000, 31800, 54500, 31800, layer="02_粗实线"))
    ents.append(d_text(27500, 32150, "TMY-4(125×8)", h=190, align="center"))

    # 1. Column TM1 (x=15500): 10kV cable -> SCB18-1250/10 Dyn11 Dry-Type Transformer -> Copper busbar to 1AN1/MNS
    ents.append(d_line(15500, 33600, 15500, 27500, layer="02_粗实线"))
    ents.append(d_text(15800, 33000, "高压引至硫酸10kV配电所Ⅰ段", h=150))
    ents.append(d_text(15800, 32350, "ZR-YJV-8.7/10kV 3×95", h=150))
    ents.append(prim_cable_head(15500, 29800))
    # Transformer Dyn11 symbol at (15500, 25800)
    ents.append(d_line(15500, 27500, 15180, 26900, layer="02_粗实线"))
    ents.append(d_line(15180, 26900, 15820, 26900, layer="02_粗实线"))
    ents.append(d_line(15820, 26900, 15500, 27500, layer="02_粗实线"))
    ents.append(d_line(15050, 26450, 15950, 26450, layer="02_粗实线"))
    ents.append(d_line(15050, 26250, 15950, 26250, layer="02_粗实线"))
    ents.append(d_line(15220, 25900, 15500, 25550, layer="02_粗实线"))
    ents.append(d_line(15780, 25900, 15500, 25550, layer="02_粗实线"))
    ents.append(d_line(15500, 25550, 15500, 20200, layer="02_粗实线"))
    # Neutral ground on transformer
    ents.append(d_line(14600, 25550, 15500, 25550))
    ents.append(d_line(14600, 25300, 14600, 25800))
    ents.append(d_line(14450, 25400, 14450, 25700))
    ents.append(d_text(16150, 26800, "SCB18-1250/10", h=155))
    ents.append(d_text(16150, 26200, "Dyn11 10/0.4kV", h=155))
    # Busbar link from transformer bottom (15500, 20200) -> right to (20200, 20200) -> up to (20200, 31800) -> right to 1AN1 (24000, 31800)
    ents.append(d_line(15500, 20200, 20200, 20200, layer="02_粗实线"))
    ents.append(d_line(20200, 20200, 20200, 31800, layer="02_粗实线"))
    ents.append(d_line(20200, 31800, 24000, 31800, layer="02_粗实线"))

    # 2. Column 1AN1/MNS (x=24000): Incoming ACB CAU25N2/3 2500A
    ents.append(d_line(24000, 31800, 24000, 19200, layer="02_粗实线"))
    ents.append(d_rect(24300, 30800, 24950, 31400))
    ents.append(d_text(24625, 30980, "Wh", h=155, align="center"))
    ents.append(d_text(24300, 30350, "6NTPM600", h=145))
    ents.append(prim_drawout_up(24000, 29200))
    ents.append(prim_cb(24000, 27500, "CAU25N2/3 2500A 3P3", "In=2500A", "Iset1=1600A, 24s", "Iset2=8000A, 0.4s"))
    ents.append(prim_ct3(24000, 24200, "3000/5"))
    ents.append(prim_ct1(24000, 23100, "3000/5"))
    ents.append(prim_drawout_dn(24000, 21800))
    # SPD branch at y=20600
    ents.append(d_line(24000, 20600, 26200, 20600))
    ents.append(d_rect(24500, 20450, 25000, 20750))
    ents.append(d_rect(25250, 20420, 25850, 20780))
    ents.append(d_text(24500, 20950, "SPD-T1/50/4P", h=145))
    ents.append(d_line(24000, 19200, 27500, 19200, layer="02_粗实线"))
    ents.append(d_line(27500, 19200, 27500, 31800, layer="02_粗实线"))

    # 3. Column 1AN2/MNS (x=31000): 300kvar Dynamic Reactive Power Compensation
    ents.append(d_line(31000, 31800, 31000, 20500, layer="02_粗实线"))
    ents.append(d_circle(31000, 31800, 75, layer="02_粗实线"))
    ents.append(d_rect(31300, 30800, 31950, 31400))
    ents.append(d_text(31625, 30980, "Wh", h=155, align="center"))
    ents.append(d_rect(32600, 30800, 33250, 31400))
    ents.append(d_text(32925, 30980, "K", h=155, align="center"))
    ents.append(d_text(31300, 30350, "6NTPM600 / 控制器", h=145))
    ents.append(prim_cb(31000, 28800, "成套确定"))
    ents.append(prim_ct3(31000, 26800, ""))
    # Thyristor + Delta Capacitor Bank
    ents.append(d_rect(30650, 23800, 31350, 24500))
    ents.append(d_line(30650, 23800, 31350, 24500))
    ents.append(d_text(31550, 24000, "晶闸管", h=155))
    ents.append(d_line(31000, 20500, 30100, 18900, layer="02_粗实线"))
    ents.append(d_line(31000, 20500, 31900, 18900, layer="02_粗实线"))
    ents.append(d_line(30100, 18900, 31900, 18900, layer="02_粗实线"))
    ents.append(d_text(31000, 18250, "YTQ-0.4/300-KL", h=150, align="center"))

    # 4. Column 1AN3/MNS (x=37750): Bus Tie Cabinet + Low-Voltage Bus Bridge to 2AN3
    ents.append(d_line(37750, 31800, 37750, 20500, layer="02_粗实线"))
    ents.append(d_circle(37750, 31800, 75, layer="02_粗实线"))
    ents.append(prim_drawout_up(37750, 29200))
    ents.append(prim_cb(37750, 27500, "CAU25N2/3 2500A 3P3", "In=2500A", "Iset1=1600A, 24s", "Iset2=8000A, 0.4s"))
    ents.append(prim_ct3(37750, 24200, "3000/5"))
    ents.append(prim_drawout_dn(37750, 21800))
    ents.append(d_line(37750, 20500, 40500, 20500, layer="02_粗实线"))
    ents.append(d_line(40500, 20500, 40500, 38800, layer="02_粗实线"))
    ents.append(d_text(40500, 39150, "低压母线桥 去2AN3", h=165, align="center"))

    # 5. Column 1AN4/MNS (3 Feeder / Motor Drawer Columns at x=43250, 47750, 52250)
    feeders = [
        (43250, "CAU16H/3 1000A", "In=1000A", "1000/5", "WP11", "ZR-YJV-0.6/1kV", "2(3×150+2×70)", "余热发电", False),
        (47750, "CM3-250M/3300", "In=180A", "250/5", "WP12", "ZR-YJV-0.6/1kV", "3×95+2×50", "BP1变频柜", False),
        (52250, "CMU100L/3 电动机", "In=80A", "100/5", "WP31", "ZR-YJV-0.6/1kV", "3×25+1×16", "1#除盐水泵", True),
    ]
    for fx, f_cb, f_in, f_ct, f_wno, f_sp1, f_sp2, f_load, is_motor in feeders:
        ents.append(d_line(fx, 31800, fx, 17500, layer="02_粗实线"))
        ents.append(d_circle(fx, 31800, 75, layer="02_粗实线"))
        ents.append(prim_drawout_up(fx, 29200))
        ents.append(prim_cb(fx, 27500, f_cb, f_in))
        if is_motor:
            # Motor protector box [马达保护器] + CT as in yes.dxf 1AN6/MNS
            ents.append(d_circle(fx, 24200, 210))
            ents.append(d_rect(fx + 350, 23900, fx + 2150, 24500))
            ents.append(d_text(fx + 1250, 24080, "马达保护器", h=150, align="center"))
            ents.append(d_text(fx + 1250, 23450, "马保配套MT", h=140, align="center"))
        else:
            ents.append(prim_ct3(fx, 24200, f_ct))
        ents.append(prim_drawout_dn(fx, 21800))
        ents.append(prim_cable_head(fx, 19200, f_wno, f_sp1, f_sp2))
        ents.append(d_rect(fx - 1100, 16800, fx + 1100, 17500))
        ents.append(d_text(fx, 17020, f_load, h=155, align="center"))

    # Grounding busbar TMY-50x5 & GPAS-800 above bottom table (y=15600)
    ents.append(d_line(8200, 15600, 22500, 15600, ltype="DASHED"))
    ents.append(d_text(9800, 15800, "TMY-50×5 接地母排", h=155))
    ents.append(d_rect(22500, 15250, 23600, 15950))
    ents.append(d_text(23850, 15480, "地电位反击抑制器: GPAS-800", h=150))

    # Bottom 2-Row Aligned Load Table (x=8500..54500, y=12600..14800)
    ents.append(d_rect(8500, 12600, 54500, 14800, "02_粗实线"))
    ents.append(d_line(8500, 13700, 54500, 13700))
    for vx in [12500, 20500, 27500, 34500, 41000, 45500, 50000]:
        ents.append(d_line(vx, 12600, vx, 14800))

    ents.append(d_text(10500, 14080, "设备功率", h=165, align="center"))
    ents.append(d_text(10500, 12980, "设备名称", h=165, align="center"))
    bot_cells = [
        (16500, "1250kVA", "1#变压器"),
        (24000, "600kW", "1#电源进线"),
        (31000, "补偿容量300kvar", "动态无功补偿"),
        (37750, "—", "母线联络柜"),
        (43250, "250kW", "余热发电主用电"),
        (47750, "75kW", "给料泵变频柜BP1"),
        (52250, "30kW", "1#除盐水泵"),
    ]
    for cx, pwr, name in bot_cells:
        ents.append(d_text(cx, 14080, pwr, h=155, align="center"))
        ents.append(d_text(cx, 12980, name, h=155, align="center"))

    # Bottom-left Energy Monitoring System Topology Diagram (as in yes.dxf 低压配电系统图一!)
    ents.append(d_rect(6800, 8800, 10800, 9900))
    ents.append(d_text(8800, 9200, "能耗监测主机", h=165, align="center"))
    ents.append(d_line(8800, 9900, 8800, 10600))
    ents.append(d_text(8800, 10750, "至电力监控系统后台", h=155, align="center"))
    ents.append(d_line(8800, 8800, 8800, 7400))
    ents.append(d_text(9100, 8000, "RS485", h=150))
    ents.append(d_line(5500, 7400, 12100, 7400))
    for bx, bcode, bname in [(5800, "AEM96", "多功能电表"), (8800, "K", "无功补偿控制器"), (11800, "°C", "变压器温控器")]:
        ents.append(d_line(bx, 7400, bx, 6700))
        ents.append(d_rect(bx - 900, 5800, bx + 900, 6700))
        ents.append(d_text(bx, 6100, bcode, h=155, align="center"))
        ents.append(d_text(bx, 5250, bname, h=145, align="center"))
    ents.append(draw_double_underlined_title(8800, 4300, "能耗监测系统拓扑图", 5200))

    # Design Notes in center-left bottom (x=15500, y=6800..11600)
    notes = [
        "设计说明：",
        "1. 低压配电系统采用单母线分段接线，进线及母联断路器均可手动、自动投切；正常运行时两进线及母联仅允许两台同时合闸；",
        "2. 变电所采用电力能耗管理系统，末端带RS485接口的多功能电表、无功控制器、温控器经通讯总线上传至监控主机；",
        "3. 断路器除注明外均为3极，额定极限短路分断能力Icu≥50kA；小室高度≤400mm为抽屉式，≥600mm为固定分隔式；",
        "4. 干式变压器与低压MNS柜并排布置，带IP20外壳（颜色RAL-7035），二次侧采用铜母排桥连接至1AN1进线柜。",
    ]
    for idx, line in enumerate(notes):
        ents.append(d_text(15500, 11400 - idx * 800, line, h=170 if idx == 0 else 155, align="left"))

    return "".join(ents), [], [], []


# ==============================================================================
# P3: XL-21 现场动力配电柜 AP1 一次系统图 (复刻自 189.dxf《现场动力配电柜系统图（一）》)
# ==============================================================================
def build_p3_xl21_power_cabinet_primary():
    ents = [draw_tongling_primary_frame("现场动力配电柜系统图（一）", "TLA2214-02DL-04-1", sub_project="压滤厂房及渣选车间")]

    # Outer Cabinet Box (x=6500..53500, y=17500..31500)
    ents.append(d_rect(6500, 17500, 53500, 31500, "01_细实线"))

    # Top-left Trapezoid Tag [AP1] & Specs (x=12000, y=29200)
    ents.append(d_line(11000, 29000, 14200, 29000, "02_粗实线"))
    ents.append(d_line(11400, 29650, 13800, 29650))
    ents.append(d_line(11400, 29000, 11600, 29650))
    ents.append(d_line(13800, 29000, 13600, 29650))
    ents.append(d_text(12600, 29180, "AP1", h=185, align="center"))
    ents.append(d_text(12600, 28350, "Pc=230kW", h=165, align="center"))
    ents.append(d_text(12600, 27650, "XL-21型动力配电柜", h=165, align="center"))
    ents.append(d_text(12600, 26950, "参考尺寸：宽×深×高:800×400×1800", h=155, align="center"))

    # Top Center Incoming Supply at x=30000 (y=36200 down to 25200)
    ents.append(d_line(30000, 36200, 30000, 25200, layer="02_粗实线"))
    ents.append(d_text(30400, 35300, "电源引自龙门吊变电所", h=165))
    ents.append(d_text(30400, 34600, "ZR-YJV-0.6/1kV", h=160))
    ents.append(d_text(30400, 33900, "2(3×150+2×70)", h=160))
    ents.append(prim_cable_head(30000, 32300))

    # Repeat Grounding branch on left of incoming line at y=30600
    ents.append(d_line(27800, 30600, 30000, 30600, ltype="DASHED"))
    ents.append(d_line(27800, 30600, 27800, 29700, ltype="DASHED"))
    ents.append(d_line(27450, 29700, 28150, 29700))
    ents.append(d_line(27580, 29520, 28020, 29520))
    ents.append(d_text(27800, 28950, "重复接地", h=155, align="center"))

    # Main Incoming MCCB CM3-630L/3300 + CT 750/5 + Meter AEM96 + SPD
    ents.append(prim_cb(30000, 29800, "CM3-630L/3300", "In=630A"))
    ents.append(prim_ct3(30000, 28000, "750/5"))
    ents.append(d_rect(30350, 26500, 30950, 27100))
    ents.append(d_text(30650, 26680, "Wh", h=150, align="center"))
    ents.append(d_text(31150, 26680, "AEM96", h=155))
    # SPD branch at y=25900
    ents.append(d_line(30000, 25900, 33800, 25900))
    ents.append(d_rect(31200, 25740, 31900, 26060))
    ents.append(d_rect(32300, 25700, 33100, 26100))
    ents.append(d_text(32100, 26250, "SPD-T1/4P", h=150, align="center"))

    # Horizontal Main Busbar inside AP1 cabinet at y=25200 (x=9000..51500)
    ents.append(d_line(9000, 25200, 51500, 25200, layer="02_粗实线"))

    # 10 Vertical Outgoing Branches (8 Motor DOL starters + 2 Power Feeders)
    branches = [
        (9500, "CM3-63M/33002", "In=63A", "65A", "40~55A", "WP31", "4×16", "M31", "AC31", "22kW", "返回搅拌槽", True),
        (14100, "CM3-63M/33002", "In=63A", "65A", "40~55A", "WP32", "4×16", "M32", "AC32", "22kW", "2#给料搅拌槽", True),
        (18700, "CM3-63M/33002", "In=63A", "65A", "40~55A", "WP33", "4×16", "M33", "AC33", "22kW", "3#给料搅拌槽", True),
        (23300, "CM3-63M/33002", "In=32A", "32A", "21~29A", "WP34", "4×6", "M34", "AC34", "11kW", "管道冲洗泵(主1)", True),
        (27900, "CM3-63M/33002", "In=32A", "32A", "21~29A", "WP35", "4×6", "M35", "AC35", "11kW", "管道冲洗泵(主2)", True),
        (32500, "CM3-63M/33002", "In=50A", "50A", "33~47A", "WP37", "4×10", "M37", "AC37", "18.5kW", "滤布冲洗泵(主1)", True),
        (37100, "CM3-63M/33002", "In=50A", "50A", "33~47A", "WP38", "4×10", "M38", "AC38", "18.5kW", "滤布冲洗泵(主2)", True),
        (41700, "CM3-63M/33002", "In=50A", "50A", "33~47A", "WP39", "4×10", "M39", "AC39", "18.5kW", "滤布冲洗泵(备)", True),
        (46300, "CM3-250M/3300", "In=125A", "", "", "WP51", "3×50+2×25", "", "2#压滤机", "56kW", "2#压滤机主电源", False),
        (50900, "CM3-250M/3300", "In=250A", "", "", "WP53", "3×150+2×70", "", "AP2", "100kW", "AP2动力配电柜", False),
    ]

    for bx, cb_m, cb_in, km_in, fr_in, w_no, c_spec, m_no, box_no, pwr, lname, is_m in branches:
        ents.append(d_line(bx, 25200, bx, 13800, layer="02_粗实线"))
        ents.append(d_circle(bx, 25200, 70, layer="02_粗实线"))
        ents.append(prim_cb(bx, 23200, cb_m, cb_in))
        if is_m:
            # Contactor blade + Thermal overload `[` symbol
            ents.append(d_line(bx - 240, 20900, bx, 20300))
            ents.append(d_text(bx + 220, 20550, km_in, h=150))
            ents.append(d_line(bx, 19200, bx - 240, 19200))
            ents.append(d_line(bx - 240, 19200, bx - 240, 18500))
            ents.append(d_line(bx - 240, 18500, bx, 18500))
            ents.append(d_text(bx + 220, 18750, fr_in, h=150))

        ents.append(prim_cable_head(bx, 15800, w_no, "ZR-YJV-0.6/1kV", c_spec))
        if is_m:
            ents.append(d_text(bx - 280, 13500, m_no, h=150, align="right"))
            ents.append(d_rect(bx + 200, 13350, bx + 1150, 13900))
            ents.append(d_text(bx + 675, 13500, box_no, h=145, align="center"))
        else:
            ents.append(d_rect(bx - 800, 13300, bx + 800, 13950))
            ents.append(d_text(bx, 13500, box_no, h=155, align="center"))

    # Bottom 2-Row Aligned Load Table (x=7200..53200, y=9800..12200)
    ents.append(d_rect(7200, 9800, 53200, 12200, "02_粗实线"))
    ents.append(d_line(7200, 11000, 53200, 11000))
    for k in range(1, 10):
        vx = 7200 + k * 4600
        ents.append(d_line(vx, 9800, vx, 12200))
    for idx, b_item in enumerate(branches):
        cx_cell = 7200 + idx * 4600 + 2300
        ents.append(d_text(cx_cell, 11450, b_item[9], h=160, align="center"))
        ents.append(d_text(cx_cell, 10250, b_item[10], h=150, align="center"))

    ents.append(draw_double_underlined_title(30200, 8200, "现场动力配电柜AP1系统图", 6800))

    notes = [
        "设计说明：",
        "1. 在压滤厂房现场新增两台XL-21型动力配电柜AP1、AP2，给压滤机及周边搅拌槽、冲洗泵低压设备供电；",
        "2. AP1电源引自龙门吊变电所，进线电缆沿厂房电缆沟及桥架敷设，出线电缆由桥架引下穿钢管至各现场控制箱及电机；",
        "3. 现场配电柜及操作箱均采用304不锈钢防腐材质，防护等级不低于IP54。",
    ]
    for idx, line in enumerate(notes):
        ents.append(d_text(7200, 7000 - idx * 780, line, h=170 if idx == 0 else 155, align="left"))

    return "".join(ents), [], [], []


# ==============================================================================
# P4: 现场变频控制柜 BP1/BP2 与横向防腐配电箱 AD 一次系统图 (复刻自 189.dxf & yes.dxf)
# ==============================================================================
def build_p4_vfd_cabinet_and_horizontal_box_primary():
    ents = [draw_tongling_primary_frame("现场新增配电箱柜系统图", "TLA2214-01DL-03", sub_project="给料输送及浓缩工段")]

    # Left & Center: BP1 (Main) and BP2 (Standby) 75kW VFD Cabinets (at x=12500 and x=26500)
    vfd_cabs = [
        (12500, "BP1", "给料输送泵变频柜(主用)", "WB1", "M1", "AC1", "WB1.1", "M1.1", "给料输送泵(主用)", "现场变频控制柜BP1系统图"),
        (26500, "BP2", "给料输送泵变频柜(备用)", "WB2", "M2", "AC2", "WB2.1", "M2.1", "给料输送泵(备用)", "现场变频控制柜BP2系统图"),
    ]
    for cx, bp_tag, bp_desc, wb_main, m_main, ac_main, wb_fan, m_fan, load_desc, sys_title in vfd_cabs:
        # Cabinet enclosure box (cx-3500..cx+5800, y=19500..31200)
        ents.append(d_rect(cx - 3500, 19500, cx + 5800, 31200))

        # Top-right tag inside cabinet
        ents.append(d_rect(cx + 2200, 29800, cx + 4200, 30500, "02_粗实线"))
        ents.append(d_text(cx + 3200, 30000, bp_tag, h=180, align="center"))
        ents.append(d_text(cx + 3200, 29200, "Pc=75kW", h=160, align="center"))
        ents.append(d_text(cx + 3200, 28500, bp_desc, h=155, align="center"))
        ents.append(d_text(cx + 3200, 27800, "宽×深×高:800×600×1800", h=145, align="center"))
        ents.append(d_text(cx + 3200, 27100, "防护等级IP54", h=145, align="center"))

        # Incoming cable from top (split around VFD box y=20600..23000)
        ents.append(d_line(cx - 1200, 35200, cx - 1200, 28800, layer="02_粗实线"))
        ents.append(d_line(cx - 1200, 27980, cx - 1200, 23000, layer="02_粗实线"))
        ents.append(d_line(cx - 1200, 20600, cx - 1200, 15000, layer="02_粗实线"))
        ents.append(d_text(cx - 900, 34400, "电源引自水泵房改造抽屉柜", h=155))
        ents.append(d_text(cx - 900, 33700, "ZR-YJV-0.6/1kV 3×95+2×50", h=150))
        ents.append(prim_cable_head(cx - 1200, 32000))

        # Main MCCB CM3-250M/3300 In=180A at y=28800
        ents.append(prim_cb(cx - 1200, 28800, "CM3-250M/3300", "In=180A"))

        # VFD Box [V/f变频器 | 90kW] at (cx - 1200, 21800)
        ents.append(d_rect(cx - 2100, 20600, cx - 300, 23000, "02_粗实线"))
        ents.append(d_line(cx - 2100, 21800, cx - 300, 21800))
        ents.append(d_text(cx - 1200, 22200, "V/f变频器", h=160, align="center"))
        ents.append(d_text(cx - 1200, 21000, "90kW", h=160, align="center"))

        # Branch to Cooling Fan at y=26200 -> right to cx + 1800 -> down to 15000
        fan_x = cx + 1800
        ents.append(d_line(cx - 1200, 26200, fan_x, 26200))
        ents.append(d_circle(cx - 1200, 26200, 65))
        ents.append(d_line(fan_x, 26200, fan_x, 15000))
        ents.append(prim_cb(fan_x, 24800, "CH3N-63/3P", "In=16A"))
        ents.append(d_line(fan_x - 200, 22600, fan_x, 22000))
        ents.append(d_text(fan_x + 220, 22200, "9A", h=150))
        ents.append(d_line(fan_x, 21100, fan_x - 200, 21100))
        ents.append(d_line(fan_x - 200, 21100, fan_x - 200, 20500))
        ents.append(d_line(fan_x - 200, 20500, fan_x, 20500))
        ents.append(d_text(fan_x + 220, 20700, "1~1.6A", h=150))

        # Outgoing cables below cabinet
        ents.append(prim_cable_head(cx - 1200, 17800, wb_main, "ZR-YJV-0.6/1kV", "3×95+1×50"))
        ents.append(d_text(cx - 1450, 14800, m_main, h=155, align="right"))
        ents.append(d_rect(cx - 950, 14650, cx - 100, 15200))
        ents.append(d_text(cx - 525, 14800, ac_main, h=145, align="center"))

        ents.append(prim_cable_head(fan_x, 17800, wb_fan, "ZR-YJV-0.6/1kV", "4×2.5"))
        ents.append(d_text(fan_x, 14800, m_fan, h=155, align="center"))

        # 2x2 Load Table below each VFD cabinet (y=10800..13200)
        ents.append(d_rect(cx - 2800, 10800, cx + 3800, 13200, "02_粗实线"))
        ents.append(d_line(cx - 2800, 12000, cx + 3800, 12000))
        ents.append(d_line(cx + 500, 10800, cx + 500, 13200))
        ents.append(d_text(cx - 1150, 12450, "75kW", h=160, align="center"))
        ents.append(d_text(cx + 2150, 12450, "0.37kW", h=160, align="center"))
        ents.append(d_text(cx - 1150, 11250, load_desc, h=155, align="center"))
        ents.append(d_text(cx + 2150, 11250, "变频电机风扇", h=155, align="center"))

        ents.append(draw_double_underlined_title(cx + 500, 9200, sys_title, 6200))

    # Right Side: Horizontal Wall-Mounted Distribution Box AD (`浓缩现场配电箱系统图` from 189.dxf!)
    # Box at x=38500..49500, y=16500..26800
    ents.append(d_rect(38500, 16500, 49500, 26800))
    ents.append(d_rect(39500, 25300, 41500, 26000, "02_粗实线"))
    ents.append(d_text(40500, 25500, "AD", h=180, align="center"))
    ents.append(d_text(40500, 24600, "Pc=33kW, JXF型", h=155, align="center"))
    ents.append(d_text(39200, 19800, "注：", h=150))
    ents.append(d_text(39200, 19100, "1. 箱体采用聚碳酸酯材质；", h=145))
    ents.append(d_text(39200, 18400, "2. 防护等级IP54，距地1.5m明装。", h=145))

    # Incoming line from left into AD box at y=21800
    ents.append(d_line(34200, 21800, 44200, 21800, layer="02_粗实线"))
    ents.append(d_text(34400, 22700, "电源引自水泵房改造抽屉柜", h=150))
    ents.append(d_text(34400, 22050, "ZR-YJV-3×50+2×25", h=150))
    # Horizontal main breaker CM3-250M/3300 In=140A at (42200, 21800)
    ents.append(d_line(41800, 21800, 42400, 21500, layer="02_粗实线"))
    ents.append(d_line(42300, 21680, 42500, 21920))
    ents.append(d_line(42300, 21920, 42500, 21680))
    ents.append(d_text(41800, 22150, "CM3-250M/3300 In=140A", h=145, align="center"))

    # Vertical distribution busbar inside AD box at x=44200 (y=17500..25800)
    ents.append(d_line(44200, 17500, 44200, 25800, layer="02_粗实线"))

    ad_branches = [
        (25800, "CM3-63M/3300 In=63A", "WD1 ZR-YJV-1kV-5×16-SC50", "AK1给料搅拌桶控制箱 22kW"),
        (24100, "CM3-63M/3300 In=40A", "WD2 ZR-YJV-1kV-5×6-SC32", "AK2液下泵控制箱 11kW"),
        (22400, "CM3-63M/3300 In=63A", "WD3", "备用"),
        (20700, "CM3-63M/3300 In=40A", "WD4", "备用"),
        (19000, "CM3-63M/3300 In=40A", "WD5", "备用"),
        (17500, "CH3H-16A/2P+30mA", "WD6", "现场检修插座回路"),
    ]
    for by, b_cb, b_cable, b_dest in ad_branches:
        ents.append(d_line(44200, by, 52500, by))
        # 3-phase slash marks `///` on horizontal branch (authentic 189.dxf / yes.dxf style!)
        for k in range(3):
            sx = 44600 + k * 140
            ents.append(d_line(sx - 70, by - 140, sx + 70, by + 140))
        # Horizontal breaker symbol `×` + blade
        ents.append(d_line(46500, by - 220, 47100, by))
        ents.append(d_line(47000, by - 110, 47200, by + 110))
        ents.append(d_line(47000, by + 110, 47200, by - 110))
        ents.append(d_text(46800, by + 200, b_cb, h=140, align="center"))
        ents.append(d_text(49800, by + 160, b_cable, h=140, align="left"))
        ents.append(d_text(52700, by - 80, b_dest, h=145, align="left"))

    ents.append(draw_double_underlined_title(44000, 14800, "浓缩现场配电箱AD系统图", 6200))

    return "".join(ents), [], [], []


if __name__ == "__main__":
    inject_primary_blocks()

    # Build 4 Primary System Diagrams (Tongling Design Institute CAD style) + 2 Coordinated EPLAN Secondary Schematics (EPLAN + MengGe style)
    primary_pages = [
        ("一次规范样图_P1_10kV高压配电系统图.dxf", build_p1_10kv_hv_primary_system),
        ("一次规范样图_P2_低压MNS受电与电容及抽屉柜系统图.dxf", build_p2_lv_mns_primary_system),
        ("一次规范样图_P3_XL21现场动力配电柜AP1系统图.dxf", build_p3_xl21_power_cabinet_primary),
        ("一次规范样图_P4_现场变频柜BP1_BP2与防腐配电箱AD系统图.dxf", build_p4_vfd_cabinet_and_horizontal_box_primary),
    ]
    secondary_pages = [
        ("二次规范样图_S1_车间控制箱电动阀与电磁阀控制图_EPLAN标准.dxf", build_s3_workshop_valve_control),
        ("二次规范样图_S2_水源泵站接触器切换与触点映像图_EPLAN标准.dxf", build_s4_contactor_interlock_and_mirror),
    ]

    pdf_out = OUT_DIR / "一次与二次双轨规范样图集_6张全套.pdf"
    with PdfPages(pdf_out) as pdf:
        for fname, p_fn in primary_pages:
            dxf_str, pins, boxes, wires = p_fn()
            dxf_path = OUT_DIR / fname
            save_dxf_page(dxf_str, dxf_path)
            res = audit_dxf_strict(dxf_path, placed_pins=pins, protected_boxes=boxes, external_wires=wires)
            # Check primary specific rules (R11 text overlap, R12 text-line collision, R15 out-of-bounds, R09 128 blocks, R10 font)
            print(f"[PRIMARY]   {fname:52s} | overlaps={len(res['defects']['text_text_overlaps'])} | collisions={len(res['defects']['text_line_collisions'])} | blocks={res['stats']['blocks']}")
            if res["defects"]["text_text_overlaps"]:
                print("   OVERLAPS:", res["defects"]["text_text_overlaps"][:5])
            if res["defects"]["text_line_collisions"]:
                print("   COLLISIONS:", res["defects"]["text_line_collisions"][:5])

            fig, ax = plt.subplots(figsize=(16.54, 11.69))
            render_eplan_page(dxf_path, ax)
            plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
            fig.savefig(str(OUT_DIR / (dxf_path.stem + ".png")), dpi=150)
            pdf.savefig(fig)
            plt.close(fig)

        for fname, s_fn in secondary_pages:
            b = s_fn()
            dxf_path = OUT_DIR / fname
            save_dxf_page(b.build_dxf_str(), dxf_path)
            res = audit_dxf_strict(dxf_path, placed_pins=b.placed_pins, protected_boxes=b.protected_boxes, external_wires=b.external_wires)
            print(f"[SECONDARY] {fname:52s} | score={res['score']} | passed={res['all_passed']} | blocks={res['stats']['blocks']}")

            fig, ax = plt.subplots(figsize=(16.54, 11.69))
            render_eplan_page(dxf_path, ax)
            plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
            fig.savefig(str(OUT_DIR / (dxf_path.stem + ".png")), dpi=150)
            pdf.savefig(fig)
            plt.close(fig)

    print("Saved Dual-Mode PDF:", pdf_out)
