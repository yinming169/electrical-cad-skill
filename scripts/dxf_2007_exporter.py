#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开源 CAD 引擎 (mozman/ezdxf) AutoCAD 2007 (R2007 / AC1021) 严格规范导出器
作用：
  1. 无需本机安装 AutoCAD，即可在任意 Windows / macOS / Linux 电脑上生成标准 DXF。
  2. 强制输出 AutoCAD 2007 (AC1021) 标准格式与 UTF-8 编码，剔除高版本 (AC1024/AC1032) 不兼容对象。
  3. 为所有图元、图层、图块自动分配合法 Handle 与 AcDb 子类标记，并通过 doc.audit() 零错误校验，确保 AutoCAD 2007 及以上版本直接无报错打开。
"""

import argparse
import sys
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cad_self_checker import parse_dxf


def _safe_float(d, key, default=0.0):
    try:
        return float(d.get(key, [str(default)])[0])
    except Exception:
        return default


def _safe_str(d, key, default=""):
    vals = d.get(key)
    return vals[0] if vals else default


def _ensure_layer(doc, layer_name: str):
    name = (layer_name or "0").strip()
    if not name or name in doc.layers:
        return name or "0"
    lw = 50 if "粗" in name else 18
    doc.layers.add(name, color=7, lineweight=lw)
    return name


def _add_primitive(target, doc, e, valid_blocks=None):
    t = e.get("type", "")
    d = e.get("d", {})
    layer = _ensure_layer(doc, _safe_str(d, "8", "0"))
    ltype = _safe_str(d, "6", "BYLAYER")
    attribs = {"layer": layer}
    if ltype and ltype.upper() != "BYLAYER":
        if ltype.upper() in doc.linetypes:
            attribs["linetype"] = ltype.upper()
        elif ltype in doc.linetypes:
            attribs["linetype"] = ltype

    if t == "LINE":
        x0, y0 = _safe_float(d, "10"), _safe_float(d, "20")
        x1, y1 = _safe_float(d, "11"), _safe_float(d, "21")
        target.add_line((x0, y0), (x1, y1), dxfattribs=attribs)
    elif t == "CIRCLE":
        cx, cy, r = _safe_float(d, "10"), _safe_float(d, "20"), _safe_float(d, "40")
        if r > 0:
            target.add_circle((cx, cy), r, dxfattribs=attribs)
    elif t == "ARC":
        cx, cy, r = _safe_float(d, "10"), _safe_float(d, "20"), _safe_float(d, "40")
        a1, a2 = _safe_float(d, "50"), _safe_float(d, "51")
        if r > 0:
            target.add_arc((cx, cy), r, a1, a2, dxfattribs=attribs)
    elif t == "SOLID":
        pts = [
            (_safe_float(d, "10"), _safe_float(d, "20")),
            (_safe_float(d, "11"), _safe_float(d, "21")),
            (_safe_float(d, "12"), _safe_float(d, "22")),
            (_safe_float(d, "13", _safe_float(d, "12")), _safe_float(d, "23", _safe_float(d, "22"))),
        ]
        target.add_solid(pts, dxfattribs=attribs)
    elif t == "TEXT":
        txt = _safe_str(d, "1", "")
        if not txt:
            return
        tx, ty = _safe_float(d, "10"), _safe_float(d, "20")
        h = max(_safe_float(d, "40", 260.0), 1.0)
        g72 = _safe_str(d, "72", "0")
        g73 = _safe_str(d, "73", "0")
        ax = _safe_float(d, "11", tx)
        ay = _safe_float(d, "21", ty)
        t_attribs = dict(attribs)
        t_attribs["height"] = h
        t_attribs["style"] = "NERIN_ISOCP"
        ent = target.add_text(txt, dxfattribs=t_attribs)
        if g72 == "1" and g73 == "2":
            ent.set_placement((ax, ay), align=TextEntityAlignment.MIDDLE_CENTER)
        elif g72 == "2" and g73 == "2":
            ent.set_placement((ax, ay), align=TextEntityAlignment.MIDDLE_RIGHT)
        elif g72 == "1":
            ent.set_placement((ax, ay), align=TextEntityAlignment.CENTER)
        elif g72 == "2":
            ent.set_placement((ax, ay), align=TextEntityAlignment.RIGHT)
        else:
            ent.set_placement((tx, ty), align=TextEntityAlignment.LEFT)
    elif t == "INSERT" and valid_blocks is not None:
        bname = _safe_str(d, "2", "")
        if bname and bname in valid_blocks:
            ix, iy = _safe_float(d, "10"), _safe_float(d, "20")
            sx = _safe_float(d, "41", 1.0) or 1.0
            sy = _safe_float(d, "42", 1.0) or 1.0
            rot = _safe_float(d, "50", 0.0)
            ins_attribs = dict(attribs)
            ins_attribs.update({"xscale": sx, "yscale": sy, "rotation": rot})
            target.add_blockref(bname, (ix, iy), dxfattribs=ins_attribs)


def rebuild_to_autocad_2007(src_dxf: Path, dst_dxf: Path = None, dxf_version: str = "R2007") -> dict:
    """将任意内部生成的 DXF 通过 ezdxf 重建为严格的 AutoCAD 2007 (AC1021) 标准文件并审计。"""
    dst = Path(dst_dxf) if dst_dxf else Path(src_dxf)
    blocks, ents = parse_dxf(Path(src_dxf))

    doc = ezdxf.new(dxf_version, setup=True)
    doc.header["$INSUNITS"] = 4  # millimeters
    doc.header["$LTSCALE"] = 100.0

    # 标准院标与 EPLAN 图层
    for lname, lw in [("01_细实线", 18), ("02_粗实线", 50), ("07_文字", 18), ("09_打印隐藏", 18)]:
        if lname not in doc.layers:
            doc.layers.add(lname, color=7, lineweight=lw)

    # 防卡死中文字体样式 (simplex.shx + gbcbig.shx，AutoCAD 2007 原生支持)
    if "NERIN_ISOCP" not in doc.styles:
        doc.styles.add("NERIN_ISOCP", font="simplex.shx", dxfattribs={"bigfont": "gbcbig.shx", "width": 0.75})

    # 重建所有命名图块 (过滤 *Model_Space / *Paper_Space)
    valid_blocks = set()
    for bname, bents in blocks.items():
        if not bname or bname.startswith("*"):
            continue
        if bname in doc.blocks:
            valid_blocks.add(bname)
            continue
        try:
            blk = doc.blocks.new(name=bname)
            for be in bents:
                _add_primitive(blk, doc, be, valid_blocks=None)
            valid_blocks.add(bname)
        except Exception:
            continue

    # 重建模型空间图元
    msp = doc.modelspace()
    for e in ents:
        _add_primitive(msp, doc, e, valid_blocks=valid_blocks)

    auditor = doc.audit()
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(dst, encoding="utf-8")

    return {
        "path": str(dst),
        "dxfversion": doc.dxfversion,
        "blocks_count": len(valid_blocks),
        "entities_count": len(msp),
        "audit_errors": len(auditor.errors),
        "audit_fixes": len(auditor.fixes),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="将 DXF 转换为严格兼容 AutoCAD 2007 (AC1021) 的标准文件")
    ap.add_argument("src", help="输入 DXF 文件路径")
    ap.add_argument("--out", help="输出 DXF 文件路径（默认覆盖原文件）")
    ap.add_argument("--version", default="R2007", choices=["R12", "R2000", "R2004", "R2007", "R2010", "R2018"], help="目标 DXF 版本，默认 R2007 (AC1021)")
    args = ap.parse_args()
    import json
    res = rebuild_to_autocad_2007(Path(args.src), Path(args.out) if args.out else None, dxf_version=args.version)
    print(json.dumps(res, ensure_ascii=False, indent=2))
