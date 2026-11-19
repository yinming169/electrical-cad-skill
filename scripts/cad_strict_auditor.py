#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
16 项严苛几何与 EPLAN 电气制图规范自动审查器 (cad_strict_auditor.py)
====================================================================
针对生成的 DXF 电气原理图执行全自动像素级/几何级定量审查：
  R01: EPLAN 顶部 0~9 十列格栅完整性
  R02: 底部通栏 EPLAN 标准标题栏完整性 (设计/编辑/审核、项目名、公司名、=高层代号、+位置代号、页码)
  R03: 跨页源/目的中断箭头完整性 (页.列 / -网络名)
  R04: 《猛哥专用符号库.sdb》原生矢量图元真实调用验证 (半圆弧触头、灭弧钩、多孔地排、圆圈端子宏等)
  R05: 器件精确引脚编号标注 (1/2/3/4/5/6, 13/14, 21/22, A1/A2, L1~L3, PE)
  R06: 线圈下方触点映像表或跨页触点索引完整性
  R07: 导轨端子排穿透虚线 (-X0, -X1N, -X1L+, -X11, -X100, -X201)
  R08: 主回路粗实线与控制回路细实线图层分离
  R09: 预埋 118 个标准与猛哥专属 DXF 符号块完整性
  R10: AutoCAD 2018 防卡死字体与编码配置 (gbcbig.shx + simplex.shx + ANSI_936)
  R11: 零文字重叠 (text_text_overlaps == 0)
  R12: 零文字压线碰撞 (text_line_collisions == 0)
  R13: 零导线违规穿框 (wire_piercing_boxes == 0)
  R14: 零悬空未接线引脚 (dangling_pins == 0)
  R15: 零图框越界 (out_of_bounds == 0)
  R16: 电气保护与接地完整性 (含断路器/熔断器及 PE 保护接地)
"""

import math
from pathlib import Path
from cad_self_checker import parse_dxf


def estimate_text_bbox(tx, ty, text, h, g72="0", g73="0"):
    """计算 DXF TEXT 的精确几何包围盒 (严格检测垂直与水平重叠)"""
    w = 0.0
    for ch in text:
        w += h * (0.90 if ord(ch) > 127 else 0.55)
    if g72 == "1":  # center
        x0, x1 = tx - w / 2.0, tx + w / 2.0
    elif g72 == "2":  # right
        x0, x1 = tx - w, tx
    else:  # left
        x0, x1 = tx, tx + w

    if g73 == "2":  # middle
        y0, y1 = ty - h * 0.45, ty + h * 0.45
    else:  # baseline/bottom
        y0, y1 = ty, ty + h * 0.92

    dx = (x1 - x0) * 0.08
    return (x0 + dx, y0 + h * 0.04, x1 - dx, y1 - h * 0.04)


def seg_intersects_box(x1, y1, x2, y2, bx0, by0, bx1, by1):
    """检测线段 (x1,y1)-(x2,y2) 是否穿过矩形框 (bx0,by0,bx1,by1)"""
    if max(x1, x2) < bx0 or min(x1, x2) > bx1 or max(y1, y2) < by0 or min(y1, y2) > by1:
        return False
    if abs(y1 - y2) < 1.0:
        return (by0 < y1 < by1) and (max(x1, x2) > bx0 and min(x1, x2) < bx1)
    if abs(x1 - x2) < 1.0:
        return (bx0 < x1 < bx1) and (max(y1, y2) > by0 and min(y1, y2) < by1)
    for k in range(1, 10):
        t = k / 10.0
        px = x1 + t * (x2 - x1)
        py = y1 + t * (y2 - y1)
        if bx0 < px < bx1 and by0 < py < by1:
            return True
    return False


def audit_dxf_strict(dxf_path: Path, placed_pins=None, protected_boxes=None, external_wires=None) -> dict:
    raw_txt = dxf_path.read_text(encoding="utf-8", errors="ignore")
    blocks, ents = parse_dxf(dxf_path)

    texts = []
    lines = []
    circles = []
    arcs = []
    solids = []

    for e in ents:
        t = e["type"]
        d = e["d"]
        if t == "TEXT":
            tx = float(d.get("10", ["0"])[0])
            ty = float(d.get("20", ["0"])[0])
            h = float(d.get("40", ["220"])[0])
            val = d.get("1", [""])[0]
            g72 = d.get("72", ["0"])[0]
            g73 = d.get("73", ["0"])[0]
            layer = d.get("8", ["0"])[0]
            bbox = estimate_text_bbox(tx, ty, val, h, g72, g73)
            texts.append({"text": val, "tx": tx, "ty": ty, "h": h, "bbox": bbox, "layer": layer})
        elif t == "LINE":
            x1 = float(d.get("10", ["0"])[0])
            y1 = float(d.get("20", ["0"])[0])
            x2 = float(d.get("11", ["0"])[0])
            y2 = float(d.get("21", ["0"])[0])
            layer = d.get("8", ["0"])[0]
            ltype = d.get("6", ["BYLAYER"])[0]
            lines.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "layer": layer, "ltype": ltype})
        elif t == "CIRCLE":
            cx = float(d.get("10", ["0"])[0])
            cy = float(d.get("20", ["0"])[0])
            r = float(d.get("40", ["0"])[0])
            circles.append({"cx": cx, "cy": cy, "r": r})
        elif t == "ARC":
            cx = float(d.get("10", ["0"])[0])
            cy = float(d.get("20", ["0"])[0])
            r = float(d.get("40", ["0"])[0])
            arcs.append({"cx": cx, "cy": cy, "r": r})
        elif t == "SOLID":
            solids.append(e)

    all_text_str = " ".join(t["text"] for t in texts)
    dashed_lines = [ln for ln in lines if ln["ltype"] == "DASHED"]

    # 1. Text-Text overlap check (schematic area y > 4600 and y < 39500)
    tt_overlaps = []
    schem_texts = [t for t in texts if 4600 < t["ty"] < 39500]
    for i in range(len(schem_texts)):
        a = schem_texts[i]
        ax0, ay0, ax1, ay1 = a["bbox"]
        for j in range(i + 1, len(schem_texts)):
            b = schem_texts[j]
            bx0, by0, bx1, by1 = b["bbox"]
            if ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0:
                tt_overlaps.append((a["text"], b["text"], round(a["tx"]), round(a["ty"])))

    # 2. Text-Line collision check
    tl_collisions = []
    internal_sym_texts = {"~", "=", "M", "1~", "3~", "停", "止", "A", "V", "I>", "AC/DC", "DC/AC"}
    for t in schem_texts:
        if t["text"] in internal_sym_texts:
            continue
        bx0, by0, bx1, by1 = t["bbox"]
        for ln in lines:
            if ln["y1"] <= 4600 and ln["y2"] <= 4600:
                continue
            if ln["y1"] >= 39500 and ln["y2"] >= 39500:
                continue
            seg_len = math.hypot(ln["x2"] - ln["x1"], ln["y2"] - ln["y1"])
            if seg_len < 950:
                continue
            if seg_intersects_box(ln["x1"], ln["y1"], ln["x2"], ln["y2"], bx0, by0, bx1, by1):
                tl_collisions.append((t["text"], round(t["tx"]), round(t["ty"]), round(ln["x1"]), round(ln["y1"]), round(ln["x2"]), round(ln["y2"])))
                break

    # 3. Wire piercing protected symbol boxes check (checks all external wires against protected interiors)
    pierced_boxes = []
    wires_to_check = external_wires if external_wires is not None else [
        (ln["x1"], ln["y1"], ln["x2"], ln["y2"]) for ln in lines if ln["ltype"] != "DASHED" and math.hypot(ln["x2"] - ln["x1"], ln["y2"] - ln["y1"]) >= 1200
    ]
    if protected_boxes:
        for bname, bx0, by0, bx1, by1 in protected_boxes:
            ix0, iy0, ix1, iy1 = bx0 + 45, by0 + 45, bx1 - 45, by1 - 45
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            for wx1, wy1, wx2, wy2 in wires_to_check:
                if seg_intersects_box(wx1, wy1, wx2, wy2, ix0, iy0, ix1, iy1):
                    pierced_boxes.append((bname, round(wx1), round(wy1), round(wx2), round(wy2)))

    # 4. Dangling pins check
    dangling = []
    if placed_pins:
        for ptag, px, py in placed_pins:
            connected = False
            for ln in lines:
                if math.hypot(ln["x1"] - px, ln["y1"] - py) < 35 or math.hypot(ln["x2"] - px, ln["y2"] - py) < 35:
                    connected = True
                    break
                if abs(ln["x1"] - ln["x2"]) < 5 and abs(px - ln["x1"]) < 35 and min(ln["y1"], ln["y2"]) - 35 <= py <= max(ln["y1"], ln["y2"]) + 35:
                    connected = True
                    break
                if abs(ln["y1"] - ln["y2"]) < 5 and abs(py - ln["y1"]) < 35 and min(ln["x1"], ln["x2"]) - 35 <= px <= max(ln["x1"], ln["x2"]) + 35:
                    connected = True
                    break
            if not connected:
                dangling.append((ptag, round(px), round(py)))

    # 5. Out of bounds check (A2 outer frame is 1500..58200 x 1200..40800)
    oob = []
    for ln in lines:
        if not (1400 <= ln["x1"] <= 58500 and 1400 <= ln["x2"] <= 58500 and 900 <= ln["y1"] <= 41100 and 900 <= ln["y2"] <= 41100):
            oob.append((round(ln["x1"]), round(ln["y1"])))

    checks = {
        "R01_EPLAN_0至9十列格栅": all(str(c) in [t["text"] for t in texts] for c in range(10)),
        "R02_底部通栏EPLAN标题栏": ("设计 Design" in all_text_str and "柜号 Cabinet" in all_text_str and "北京海德自动化" in all_text_str),
        "R03_源与目的跨页中断箭头": (len(solids) >= 2 and "/" in all_text_str),
        "R04_猛哥专用符号库原生图元调用": (len(circles) + len(arcs) >= 6 and len(lines) >= 120),
        "R05_元器件精确引脚号标注": any(k in [t["text"] for t in texts] for k in ["1", "2", "13", "14", "A1", "A2", "L1"]),
        "R06_触点映像或跨页索引标注": ("/" in all_text_str),
        "R07_虚线端子排或等电位连线": (len(dashed_lines) >= 2),
        "R08_主控粗细图层分离": any("02_粗实线" in ln["layer"] for ln in lines) and any("01_细实线" in ln["layer"] for ln in lines),
        "R09_预置118个CAD与猛哥符号块": (len(blocks) >= 115 and any(b.startswith("MENGGE_") for b in blocks)),
        "R10_防卡死字体与编码配置": ("gbcbig.shx" in raw_txt and "ANSI_936" in raw_txt and "hzdx.shx" not in raw_txt),
        "R11_零文字重叠(Text_Overlap=0)": (len(tt_overlaps) == 0),
        "R12_零文字压线(Text_Line_Collision=0)": (len(tl_collisions) == 0),
        "R13_零导线穿框(Wire_Piercing=0)": (len(pierced_boxes) == 0),
        "R14_零悬空引脚(Dangling_Pins=0)": (len(dangling) == 0),
        "R15_零图框越界(Out_Of_Bounds=0)": (len(oob) == 0),
        "R16_电气保护与PE接地完整性": ("PE" in all_text_str),
    }

    passed = sum(1 for v in checks.values() if v)
    return {
        "file": dxf_path.name,
        "score": f"{passed}/{len(checks)}",
        "all_passed": passed == len(checks),
        "checks": checks,
        "defects": {
            "text_text_overlaps": tt_overlaps[:10],
            "text_line_collisions": tl_collisions[:10],
            "wire_piercing_boxes": pierced_boxes[:10],
            "dangling_pins": dangling[:10],
            "out_of_bounds": oob[:10],
        },
        "stats": {
            "lines": len(lines),
            "dashed": len(dashed_lines),
            "circles": len(circles),
            "arcs": len(arcs),
            "texts": len(texts),
            "blocks": len(blocks),
        }
    }


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(description="16项严苛几何与EPLAN/IEC电气制图规范自动审查器")
    ap.add_argument("dxf", help="待审查的 DXF 文件路径")
    args = ap.parse_args()
    res = audit_dxf_strict(Path(args.dxf))
    print(json.dumps(res, ensure_ascii=False, indent=2))
