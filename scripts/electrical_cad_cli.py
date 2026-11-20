#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Electrical CAD Skill 统一命令行入口 (electrical_cad_cli.py)
供 Claude / DeepSeek / GLM / Kimi / Cursor / Codex 及本地工程师直接调用。

子命令:
  1. check-env : 检查符号库、模板、字体与依赖是否完整
  2. generate  : 从自然语言 (--text) 或标准 IR JSON (--json) 一键生成 DXF (+ 可选 PDF 预览 + 自动自审)
  3. audit     : 对指定 DXF 文件执行 16 项严苛几何与 IEC/GB/EPLAN 规范自审
  4. samples   : 一键生成全套一次图 + EPLAN 二次图规范样图集 (DXF + PDF + 自审报告)
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from path_utils import (
    SKILL_ROOT,
    SYMBOLS_134_DXF,
    TEMPLATE_READY_DXF,
    MENGGE_CATALOG_JSON,
    CIRCUIT_PATTERNS_JSON,
    get_cjk_font_properties,
    find_accoreconsole,
    ensure_out_dir,
)


def cmd_check_env(_args):
    fp = get_cjk_font_properties()
    status = {
        "skill_root": str(SKILL_ROOT),
        "template_ready_dxf": TEMPLATE_READY_DXF.exists(),
        "symbols_134_dxf": SYMBOLS_134_DXF.exists(),
        "mengge_catalog_json": MENGGE_CATALOG_JSON.exists(),
        "circuit_patterns_json": CIRCUIT_PATTERNS_JSON.exists(),
        "cjk_font": fp.get_file() or fp.get_name(),
        "accoreconsole_detected": Path(find_accoreconsole()).exists(),
    }
    print(json.dumps(status, ensure_ascii=False, indent=2))
    ok = all([
        status["template_ready_dxf"],
        status["symbols_134_dxf"],
        status["mengge_catalog_json"],
    ])
    sys.exit(0 if ok else 1)


def render_dxf_to_pdf(dxf_path: Path, pdf_path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from eplan_cad_engine import render_eplan_page

    with PdfPages(pdf_path) as pdf:
        fig, ax = plt.subplots(figsize=(16.54, 11.69), dpi=150)  # A3/A2 landscape ratio
        render_eplan_page(dxf_path, ax)
        ax.axis("off")
        plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
        pdf.savefig(fig)
        plt.close(fig)


def cmd_generate(args):
    import one_click_cad_v2 as occ
    from cad_self_checker import audit_dxf
    from cad_strict_auditor import audit_dxf_strict

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.json:
        ir = json.loads(Path(args.json).read_text(encoding="utf-8"))
        # 补齐缺省工程计算字段
        if "rated_current_a" not in ir and "power_kw" in ir:
            ir["rated_current_a"] = occ.calc_motor_current(float(ir["power_kw"]), int(ir.get("voltage_v", 380)))
        if "breaker_a" not in ir and "rated_current_a" in ir:
            ie = float(ir["rated_current_a"])
            ir["breaker_a"] = next((b for b in [16, 25, 32, 40, 63, 100, 160, 250, 400, 630] if b >= ie * 1.25), 630)
        if "cable" not in ir and "rated_current_a" in ir:
            ir["cable"] = f"YJV-3x{occ.select_cable_section(float(ir['rated_current_a']))}+1xPE"
        if "ku" not in ir and "power_kw" in ir:
            p_kw = max(float(ir["power_kw"]), 0.1)
            s_kva = float(ir.get("transformer_kva", 1000))
            ku = round(0.75 + 0.25 * (s_kva / p_kw), 2)
            ir["ku"] = ku
            ir["ku_advice"] = (
                "Ku>=6 允许直起" if ku >= 6.0
                else ("4<=Ku<6 推荐降压起动" if ku >= 4.0 else "Ku<4 推荐软起/变频")
            )
        ir.setdefault("drawing_no", "IEC-E-01")
    elif args.text:
        ir = occ.parse_text_to_ir(args.text, dno=args.drawing_no)
    else:
        print("错误：必须提供 --text 或 --json 参数。", file=sys.stderr)
        sys.exit(2)

    ctype = ir.get("circuit_type", "direct_start")
    if ctype == "sketch_dual_source_primary":
        import generate_sketch_primary_dxf as gsp
        from eplan_cad_engine import save_dxf_page
        ents = gsp.build_sketch_primary_system_dxf()
        save_dxf_page(ents, out_path)
    else:
        ents = occ.render_ir_to_entities(ir)
        occ.write_dxf(ents, TEMPLATE_READY_DXF, out_path)

    from dxf_2007_exporter import rebuild_to_autocad_2007
    export_info = rebuild_to_autocad_2007(out_path, out_path, dxf_version=getattr(args, "dxf_version", "R2007"))
    result = {
        "dxf_path": str(out_path),
        "dxf_version": export_info["dxfversion"],
        "ezdxf_audit_errors": export_info["audit_errors"],
        "ir": ir,
    }

    if args.pdf:
        pdf_path = out_path.with_suffix(".pdf")
        render_dxf_to_pdf(out_path, pdf_path)
        result["pdf_path"] = str(pdf_path)

    if args.audit:
        basic_audit = audit_dxf(out_path)
        strict_audit = audit_dxf_strict(out_path)
        audit_report = {
            "dxf": str(out_path),
            "basic_12_checks": basic_audit,
            "strict_16_checks": strict_audit,
        }
        report_path = out_path.with_name(out_path.stem + "_audit_report.json")
        report_path.write_text(json.dumps(audit_report, ensure_ascii=False, indent=2), encoding="utf-8")
        result["audit_report_path"] = str(report_path)
        result["strict_score"] = strict_audit.get("score")
        result["text_text_overlaps"] = len(strict_audit.get("defects", {}).get("text_text_overlaps", []))
        result["text_line_collisions"] = len(strict_audit.get("defects", {}).get("text_line_collisions", []))

    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_audit(args):
    from cad_strict_auditor import audit_dxf_strict
    from cad_self_checker import audit_dxf

    dxf_path = Path(args.dxf).resolve()
    if not dxf_path.exists():
        print(f"错误：找不到 DXF 文件 {dxf_path}", file=sys.stderr)
        sys.exit(2)

    report = {
        "dxf": str(dxf_path),
        "mode": args.mode,
        "strict_16_checks": audit_dxf_strict(dxf_path),
        "basic_12_checks": audit_dxf(dxf_path),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_samples(args):
    out_dir = ensure_out_dir(args.out_dir)
    import eplan_cad_engine as ece
    import primary_and_secondary_cad_engine_v2 as ps2
    from cad_strict_auditor import audit_dxf_strict

    generated = []
    if args.track in ("primary", "all"):
        for fname, builder in [
            ("P1_10kV高压配电一次系统图.dxf", ps2.build_p1_10kv_hv_primary_system),
            ("P2_0.4kV低压MNS配电系统图.dxf", ps2.build_p2_lv_mns_primary_system),
            ("P3_XL21现场动力配电柜一次系统图.dxf", ps2.build_p3_xl21_power_cabinet_primary),
            ("P4_变频柜与防腐配电箱一次系统图.dxf", ps2.build_p4_vfd_cabinet_and_horizontal_box_primary),
        ]:
            b = builder()
            if isinstance(b, tuple):
                ents, pins, boxes, wires = b
            else:
                ents = b.build_dxf_str() if hasattr(b, "build_dxf_str") else "".join(b.ents)
                pins = getattr(b, "placed_pins", None)
                boxes = getattr(b, "protected_boxes", None)
                wires = getattr(b, "external_wires", None)
            out_p = out_dir / fname
            ece.save_dxf_page(ents, out_p)
            from dxf_2007_exporter import rebuild_to_autocad_2007
            rebuild_to_autocad_2007(out_p, out_p, dxf_version="R2007")
            rep = audit_dxf_strict(out_p, placed_pins=pins, protected_boxes=boxes, external_wires=wires)
            generated.append({
                "file": str(out_p),
                "track": "primary",
                "tt_overlaps": len(rep["defects"]["text_text_overlaps"]),
                "tl_collisions": len(rep["defects"]["text_line_collisions"]),
            })

    if args.track in ("secondary", "all"):
        import mengge_sample_generator as msg
        for fname, builder in [
            ("S3_车间控制箱电动阀与电磁阀原理图_EPLAN.dxf", msg.build_s3_workshop_valve_control),
            ("S4_水源泵站主接触器切换与触点映像图_EPLAN.dxf", msg.build_s4_contactor_interlock_and_mirror),
            ("S5_PLC_CPU314C数字量DI_DO扩展图_EPLAN.dxf", msg.build_s5_plc_cpu_di_do_with_mengge),
        ]:
            b = builder()
            if isinstance(b, tuple):
                ents, pins, boxes, wires = b
            else:
                ents = b.build_dxf_str() if hasattr(b, "build_dxf_str") else "".join(b.ents)
                pins = getattr(b, "placed_pins", None)
                boxes = getattr(b, "protected_boxes", None)
                wires = getattr(b, "external_wires", None)
            out_p = out_dir / fname
            ece.save_dxf_page(ents, out_p)
            from dxf_2007_exporter import rebuild_to_autocad_2007
            rebuild_to_autocad_2007(out_p, out_p, dxf_version="R2007")
            rep = audit_dxf_strict(out_p, placed_pins=pins, protected_boxes=boxes, external_wires=wires)
            generated.append({
                "file": str(out_p),
                "track": "secondary",
                "score": rep["score"],
                "tt_overlaps": len(rep["defects"]["text_text_overlaps"]),
                "tl_collisions": len(rep["defects"]["text_line_collisions"]),
            })

    print(json.dumps({"out_dir": str(out_dir), "generated": generated}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        prog="electrical_cad_cli",
        description="IEC / GB + EPLAN 双轨电气制图与 16 项规范自审统一 CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_env = sub.add_parser("check-env", help="检查符号库、模板、中文字体与环境状态")
    p_env.set_defaults(func=cmd_check_env)

    p_gen = sub.add_parser("generate", help="从自然语言或 IR JSON 一键生成 DXF (+ PDF 预览 + 自审)")
    p_gen.add_argument("--text", type=str, help="自然语言电气需求描述")
    p_gen.add_argument("--json", type=str, help="标准 ElectricalCircuitIR JSON 文件路径")
    p_gen.add_argument("--out", type=str, required=True, help="输出 DXF 文件路径")
    p_gen.add_argument("--drawing-no", type=str, default="IEC-E-01", help="图号")
    p_gen.add_argument("--pdf", action="store_true", help="同时输出高清 PDF 预览图")
    p_gen.add_argument("--audit", action="store_true", help="出图后自动执行 16 项规范与碰撞自审")
    p_gen.add_argument("--dxf-version", default="R2007", choices=["R12", "R2000", "R2007", "R2010", "R2018"], help="输出 DXF 版本，默认 R2007 (AutoCAD 2007 / AC1021)")
    p_gen.set_defaults(func=cmd_generate)

    p_aud = sub.add_parser("audit", help="对指定 DXF 执行 16 项严苛几何与规范自审")
    p_aud.add_argument("--dxf", type=str, required=True, help="待审 DXF 文件路径")
    p_aud.add_argument("--mode", choices=["primary", "secondary"], default="secondary", help="审查模式")
    p_aud.set_defaults(func=cmd_audit)

    p_smp = sub.add_parser("samples", help="生成一次+二次双轨规范参考样图")
    p_smp.add_argument("--track", choices=["primary", "secondary", "all"], default="all")
    p_smp.add_argument("--out-dir", type=str, default="output/samples")
    p_smp.set_defaults(func=cmd_samples)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
