#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台路径解析与中文字体自动探测模块 (path_utils.py)
彻底消除任何本地 D 盘路径或特定 Linux 容器硬编码路径，确保在 Windows / macOS / Linux 下开箱即用。
"""

import os
import shutil
from pathlib import Path
from matplotlib import font_manager

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
SYMBOLS_DIR = SKILL_ROOT / "symbols"
REFERENCES_DIR = SKILL_ROOT / "references"
EXAMPLES_DIR = SKILL_ROOT / "examples"
DEFAULT_OUT_DIR = SKILL_ROOT / "output"

TEMPLATE_READY_DXF = SYMBOLS_DIR / "NERIN-A2-frame-ready.dxf"
FRAME_DXF = SYMBOLS_DIR / "NERIN-A2-frame.dxf"
SYMBOLS_134_DXF = SYMBOLS_DIR / "standard-symbols-IEC-EPLAN-PRIM-MENGGE-134.dxf"
MENGGE_CATALOG_JSON = SYMBOLS_DIR / "mengge_symbol_catalog.json"
CIRCUIT_PATTERNS_JSON = SYMBOLS_DIR / "electrical_circuit_patterns.json"


def get_cjk_font_properties() -> font_manager.FontProperties:
    """自动探测当前系统的中文字体（Linux / Windows / macOS），找不到时安全回退至默认无衬线字体。"""
    candidate_paths = [
        # Linux (Noto / WenQuanYi / Droid)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        # Windows
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for fp in candidate_paths:
        if os.path.isfile(fp):
            return font_manager.FontProperties(fname=fp)

    # 尝试按字体家族名称在 matplotlib 已安装字体中匹配
    for family in ["Noto Sans CJK SC", "Microsoft YaHei", "SimHei", "PingFang SC", "WenQuanYi Micro Hei"]:
        try:
            matched = font_manager.findfont(font_manager.FontProperties(family=family), fallback_to_default=False)
            if matched and os.path.isfile(matched):
                return font_manager.FontProperties(fname=matched)
        except Exception:
            continue

    return font_manager.FontProperties()


def find_accoreconsole() -> str:
    """自动查找 Windows 本机 AutoCAD accoreconsole.exe，支持通过环境变量 ACCORECONSOLE 覆盖。"""
    env_path = os.environ.get("ACCORECONSOLE")
    if env_path and os.path.isfile(env_path):
        return env_path

    which_path = shutil.which("accoreconsole.exe")
    if which_path:
        return which_path

    for ver in ["2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018"]:
        p = rf"C:\Program Files\Autodesk\AutoCAD {ver}\accoreconsole.exe"
        if os.path.isfile(p):
            return p

    return r"C:\Program Files\Autodesk\AutoCAD 2018\accoreconsole.exe"


def ensure_out_dir(out_dir=None) -> Path:
    p = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p
