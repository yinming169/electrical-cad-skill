#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoCAD 2018+ 无界面控制台核心 (accoreconsole.exe) 桥接脚本
通过相对路径与命令行参数将生成的 .dxf 转换为 .dwg（仅在安装了 AutoCAD 的 Windows 环境下使用）。
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from path_utils import find_accoreconsole, FRAME_DXF, SYMBOLS_134_DXF


def build_convert_scr(dxf_path: Path, out_dwg: Path) -> str:
    return "\n".join([
        "FILEDIA 0",
        "CMDDIA 0",
        "ATTREQ 0",
        "FONTALT simplex.shx",
        f'_OPEN "{dxf_path}"',
        "ZOOM E",
        f'_SAVEAS 2018 "{out_dwg}"',
        "QUIT Y",
        "",
    ])


def main():
    ap = argparse.ArgumentParser(description="调用本机 AutoCAD accoreconsole.exe 将 DXF 转为 DWG")
    ap.add_argument("--dxf", required=True, help="输入 DXF 文件路径")
    ap.add_argument("--out-dwg", required=True, help="输出 DWG 文件路径")
    ap.add_argument("--accore", default=find_accoreconsole(), help="accoreconsole.exe 路径（可选）")
    args = ap.parse_args()

    accore = Path(args.accore)
    if not accore.exists():
        print(f"未检测到 AutoCAD accoreconsole.exe: {accore}", file=sys.stderr)
        print("提示：可设置环境变量 ACCORECONSOLE 或使用 --accore 指定路径；纯 DXF/PDF 出图无需 AutoCAD。", file=sys.stderr)
        sys.exit(1)

    dxf_path = Path(args.dxf).resolve()
    out_dwg = Path(args.out_dwg).resolve()
    out_dwg.parent.mkdir(parents=True, exist_ok=True)
    scr_path = out_dwg.with_suffix(".scr")
    scr_path.write_text(build_convert_scr(dxf_path, out_dwg), encoding="gbk", errors="ignore")

    cmd = [str(accore), "/s", str(scr_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    print(f"已生成 DWG: {out_dwg}")


if __name__ == "__main__":
    main()
