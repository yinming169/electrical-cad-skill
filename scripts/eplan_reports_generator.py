#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EPLAN 规范端子图表、封面、目录与成套清单 AutoCAD 2007 (AC1021) DXF 生成器"""
import argparse, json
from pathlib import Path
import ezdxf
from ezdxf.enums import TextEntityAlignment

def _new_doc():
    doc = ezdxf.new("R2007", setup=True)
    doc.header["$INSUNITS"] = 4
    for lname, lw in [("01_细实线", 18), ("02_粗实线", 50), ("07_文字", 18)]:
        if lname not in doc.layers:
            doc.layers.add(lname, color=7, lineweight=lw)
    if "NERIN_ISOCP" not in doc.styles:
        doc.styles.add("NERIN_ISOCP", font="simplex.shx", dxfattribs={"bigfont": "gbcbig.shx", "width": 0.75})
    return doc

def _draw_table(msp, title, headers, widths, rows, origin=(15.0, 276.0), row_h=8.0):
    x0, y_top = origin
    tw = sum(widths)
    t = msp.add_text(title, dxfattribs={"layer": "07_文字", "style": "NERIN_ISOCP", "height": 5.0})
    t.set_placement((x0 + tw / 2.0, y_top + 4.0), align=TextEntityAlignment.MIDDLE_CENTER)
    msp.add_lwpolyline([(10, 10), (410, 10), (410, 287), (10, 287), (10, 10)], dxfattribs={"layer": "02_粗实线"})
    for r_idx, row in enumerate([headers] + rows):
        y1, y2 = y_top - r_idx * row_h, y_top - (r_idx + 1) * row_h
        msp.add_line((x0, y1), (x0 + tw, y1), dxfattribs={"layer": "02_粗实线" if r_idx == 0 else "01_细实线"})
        msp.add_line((x0, y2), (x0 + tw, y2), dxfattribs={"layer": "01_细实线"})
        cx = x0
        for c_idx, w in enumerate(widths):
            msp.add_line((cx, y1), (cx, y2), dxfattribs={"layer": "01_细实线"})
            val = str(row[c_idx]) if c_idx < len(row) else ""
            if val:
                tx = msp.add_text(val, dxfattribs={"layer": "07_文字", "style": "NERIN_ISOCP", "height": 3.0 if r_idx == 0 else 2.6})
                tx.set_placement((cx + w / 2.0, (y1 + y2) / 2.0), align=TextEntityAlignment.MIDDLE_CENTER)
            cx += w
        msp.add_line((x0 + tw, y1), (x0 + tw, y2), dxfattribs={"layer": "01_细实线"})

def generate_terminal_diagram_dxf(spec: dict, out_dxf: Path):
    doc = _new_doc()
    msp = doc.modelspace()
    strip = spec.get("terminal_strip", "-X1")
    terms = spec.get("terminals", [])
    msp.add_lwpolyline([(10, 10), (410, 10), (410, 287), (10, 287), (10, 10)], dxfattribs={"layer": "02_粗实线"})
    title = msp.add_text(f"端子图表 {strip}（EPLAN F13 标准）", dxfattribs={"layer": "07_文字", "style": "NERIN_ISOCP", "height": 5.0})
    title.set_placement((210, 279), align=TextEntityAlignment.MIDDLE_CENTER)
    headers = ["内部目标", "内部线号", "端子号", "端子符号", "外部线号", "外部目标", "电缆/芯线", "功能描述"]
    widths = [55, 30, 22, 24, 30, 60, 75, 94]
    x0, y_top, row_h = 15.0, 270.0, 9.0
    tw = sum(widths)
    msp.add_line((x0, y_top), (x0 + tw, y_top), dxfattribs={"layer": "02_粗实线"})
    msp.add_line((x0, y_top - row_h), (x0 + tw, y_top - row_h), dxfattribs={"layer": "02_粗实线"})
    cx = x0
    for h_txt, w in zip(headers, widths):
        msp.add_line((cx, y_top), (cx, y_top - row_h), dxfattribs={"layer": "01_细实线"})
        t = msp.add_text(h_txt, dxfattribs={"layer": "07_文字", "style": "NERIN_ISOCP", "height": 3.0})
        t.set_placement((cx + w / 2.0, y_top - row_h / 2.0), align=TextEntityAlignment.MIDDLE_CENTER)
        cx += w
    msp.add_line((x0 + tw, y_top), (x0 + tw, y_top - row_h), dxfattribs={"layer": "01_细实线"})
    sym_x = x0 + sum(widths[:3]) + widths[3] / 2.0
    for idx, term in enumerate(terms):
        y1, y2 = y_top - (idx + 1) * row_h, y_top - (idx + 2) * row_h
        yc = (y1 + y2) / 2.0
        msp.add_line((x0, y2), (x0 + tw, y2), dxfattribs={"layer": "01_细实线"})
        vals = [term.get("internal_target", ""), term.get("internal_wire", ""), str(term.get("pin", idx + 1)), "", term.get("external_wire", ""), term.get("external_target", ""), term.get("cable", ""), term.get("desc", "")]
        cx = x0
        for val, w in zip(vals, widths):
            msp.add_line((cx, y1), (cx, y2), dxfattribs={"layer": "01_细实线"})
            if val:
                t = msp.add_text(val, dxfattribs={"layer": "07_文字", "style": "NERIN_ISOCP", "height": 2.5})
                t.set_placement((cx + w / 2.0, yc), align=TextEntityAlignment.MIDDLE_CENTER)
            cx += w
        msp.add_line((x0 + tw, y1), (x0 + tw, y2), dxfattribs={"layer": "01_细实线"})
        msp.add_line((sym_x - 8, yc), (sym_x - 2.2, yc), dxfattribs={"layer": "01_细实线"})
        msp.add_line((sym_x + 2.2, yc), (sym_x + 8, yc), dxfattribs={"layer": "01_细实线"})
        msp.add_circle((sym_x, yc), 2.2, dxfattribs={"layer": "02_粗实线"})
        if term.get("type") == "pe":
            msp.add_line((sym_x - 1.5, yc - 1.5), (sym_x + 1.5, yc + 1.5), dxfattribs={"layer": "01_细实线"})
            msp.add_line((sym_x - 1.5, yc + 1.5), (sym_x + 1.5, yc - 1.5), dxfattribs={"layer": "01_细实线"})
        if term.get("bridge_next"):
            msp.add_line((sym_x, yc - 2.2), (sym_x, yc - row_h + 2.2), dxfattribs={"layer": "02_粗实线"})
    aud = doc.audit()
    out_dxf.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_dxf, encoding="utf-8")
    return {"dxf": str(out_dxf), "dxfversion": doc.dxfversion, "audit_errors": len(aud.errors)}

def generate_report_dxf(rtype: str, data: dict, out_dxf: Path):
    if rtype == "terminal":
        return generate_terminal_diagram_dxf(data, out_dxf)
    doc = _new_doc()
    msp = doc.modelspace()
    presets = {
        "toc": ("目录（EPLAN F06）", ["页码", "页类型", "页描述", "日期", "编辑者"], [35, 75, 160, 60, 60]),
        "parts": ("部件列表（EPLAN F01）", ["序号", "标识符", "名称", "规格型号", "技术参数", "品牌", "位置"], [22, 48, 65, 85, 85, 45, 40]),
        "bom": ("部件汇总表（EPLAN F02）", ["序号", "标识符", "名称", "规格型号", "技术参数", "数量", "单位", "品牌", "备注"], [20, 42, 58, 72, 72, 22, 20, 40, 44]),
        "cabinet": ("箱柜设备清单（EPLAN F18）", ["序号", "设备标识符", "型号", "规格"], [35, 95, 130, 130]),
        "cable": ("电缆总览（EPLAN F10）", ["电缆代号", "从", "至", "描述", "电缆型号", "ø", "长度(m)", "连接数", "线径(mm²)"], [38, 46, 46, 68, 68, 22, 34, 32, 36]),
        "wires": ("线号统计表（EPLAN F27）", ["线号名称", "数量"], [200, 190]),
    }
    if rtype == "cover":
        fields = [("公司/客户", data.get("client", "")), ("项目名称", data.get("project_name", "")), ("项目描述", data.get("project_desc", "")), ("图号", data.get("drawing_no", "")), ("设计/负责人", data.get("designer", "")), ("制造商", data.get("manufacturer", "")), ("安装地点", data.get("location", "")), ("日期/审核/页数", f"{data.get('date', '')} | {data.get('reviewer', '')} | 共{data.get('pages', '')}页")]
        _draw_table(msp, "电气工程项目封面（EPLAN F26）", ["项目属性", "内容"], [110, 280], fields, row_h=14.0)
    else:
        title, headers, widths = presets[rtype]
        _draw_table(msp, title, headers, widths, data.get("rows", []))
    aud = doc.audit()
    out_dxf.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_dxf, encoding="utf-8")
    return {"dxf": str(out_dxf), "dxfversion": doc.dxfversion, "audit_errors": len(aud.errors)}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", required=True, choices=["cover", "toc", "parts", "bom", "cabinet", "cable", "wires", "terminal"])
    ap.add_argument("--json", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    print(json.dumps(generate_report_dxf(args.type, json.loads(Path(args.json).read_text(encoding="utf-8")), Path(args.out)), ensure_ascii=False, indent=2))
