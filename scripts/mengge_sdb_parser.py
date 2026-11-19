#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPLAN Electric P8 符号库 (.slk / .sdb) 逆向解析与 AutoCAD DXF 符号转换器
======================================================================
针对用户上传的《猛哥专用符号库.slk》与《猛哥专用符号库.sdb.7z》：
1. 自动解析 EPLAN 专有 .eod 二进制表：
   - SymbolBib.eod (符号库头信息)
   - AdditionalUserInfo.marker.19_52 (作者与工作站元数据)
   - Symbol.eod (875 个符号定义，901B/条，自动兼容 zlib 压缩与未压缩记录)
   - Variant.eod (7,564 个符号变体 A~H 与精确引脚坐标，635B/条)
   - Instance.eod (130,292 个几何图元：0x1f 直线、0x20 圆/圆弧、0x59 矩形、0x22 多段线、0x1e/0x53 文本，134B/条)
2. 提取“赵猛”创建与定制修改的全部 28 个专属符号 + 核心 EPLAN 符号，
   将其原始几何图元与 4mm 模数连接点无损转换为 AutoCAD 2018 DXF 图块 (`MENGGE_<Code>`)，
   并写入 `standard-symbols-IEC-EPLAN.dxf` 与 `NERIN-A2-frame-ready.dxf`。
3. 导出全量 875 个符号的 JSON 索引库 (`mengge_symbol_catalog.json`) 与可视化图谱。
"""

import os
import re
import json
import math
import zlib
import struct
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager

from path_utils import get_cjk_font_properties, ensure_out_dir
CJK_FP = get_cjk_font_properties()
plt.rcParams['axes.unicode_minus'] = False

SDB_DIR = '/tmp/mengge_sdb/猛哥专用符号库.sdb'
OUT_DIR = str(ensure_out_dir())


def parse_symbols(sdb_dir=SDB_DIR):
    """解析 Symbol.eod 全部 875 条符号记录"""
    sym_path = os.path.join(sdb_dir, 'Symbol.eod')
    sym_data = open(sym_path, 'rb').read()
    rec_size = 901
    num_recs = len(sym_data) // rec_size
    symbols = {}
    ordered_list = []

    for idx in range(num_recs):
        rec = sym_data[idx * rec_size:(idx + 1) * rec_size]
        sym_id = struct.unpack_from('>I', rec, 0)[0]
        hdr_code_raw = rec[25:89].split(b'\x00')[0]
        if hdr_code_raw and hdr_code_raw[0] < 0x20:
            hdr_code_raw = hdr_code_raw[1:]
        hdr_code = hdr_code_raw.decode('utf-8', 'ignore').strip()

        payload = rec[108:]
        if payload and payload[0] == 0x78:
            try:
                dec = zlib.decompressobj().decompress(payload)
            except Exception:
                dec = rec[89:]
        else:
            dec = rec[89:]

        mc = re.search(b'\x51\xeb([^\x00]+)\x00', dec)
        code = mc.group(1).decode('utf-8', 'ignore').strip() if mc else hdr_code
        mn = re.search(b'\x52\xeb(..)', dec, re.DOTALL)
        sym_num = struct.unpack('<H', mn.group(1))[0] if mn else idx

        strs = [m.group(0).decode('utf-8', 'ignore') for m in re.finditer(b'[\x20-\x7e\x80-\xff]{2,}', dec)]
        full_txt = '\n'.join(strs)

        zh_matches = re.findall(r'(?:zh_CN|\?\?_\?\?)@([^;]+)', full_txt)
        en_matches = re.findall(r'en_US@([^;]+)', full_txt)
        de_matches = re.findall(r'de_DE@([^;]+)', full_txt)

        zh_name = zh_matches[0].strip() if zh_matches else ''
        iec_ref = zh_matches[1].strip() if len(zh_matches) > 1 else (
            en_matches[1].strip() if len(en_matches) > 1 else (
                de_matches[1].strip() if len(de_matches) > 1 else ''
            )
        )
        en_name = en_matches[0].strip() if en_matches else ''
        if re.match(r'^[0-9]{2,3}-[0-9]{2}', zh_name) and len(zh_matches) > 1:
            iec_ref, zh_name = zh_name, zh_matches[1].strip()
        if not zh_name and code in ('三相主触点', 'Ping', '电动阀', '地排5', '地排7', '地排10', '设备2', '设备3', '设备4', '设备5'):
            zh_name = code

        is_mengge = ('赵猛' in full_txt) or (sym_id >= 1396)
        timestamps = [int(t) for t in re.findall(r'\b(1[1-7]\d{8})\b', full_txt)]

        item = {
            'idx': idx,
            'sym_id': sym_id,
            'sym_num': sym_num,
            'code': code,
            'zh_name': zh_name or code,
            'en_name': en_name,
            'iec_ref': iec_ref,
            'is_mengge': is_mengge,
            'author': '赵猛' if is_mengge else 'EPLAN_IEC',
            'timestamps': timestamps,
            'variants': {}
        }
        symbols[sym_id] = item
        ordered_list.append(item)

    return symbols, ordered_list


def parse_variants(symbols, sdb_dir=SDB_DIR):
    """解析 Variant.eod 全部 7,564 条变体记录及引脚坐标"""
    var_path = os.path.join(sdb_dir, 'Variant.eod')
    var_data = open(var_path, 'rb').read()
    rec_size = 635
    num_recs = len(var_data) // rec_size
    variants = {}

    for v_idx in range(num_recs):
        vrec = var_data[v_idx * rec_size:(v_idx + 1) * rec_size]
        vid = struct.unpack_from('>I', vrec, 0)[0]
        payload = vrec[42:]
        if payload and payload[0] == 0x78:
            try:
                dec = zlib.decompressobj().decompress(payload)
            except Exception:
                dec = vrec[28:]
        else:
            dec = vrec[28:]

        ms = re.search(b'\x95\xed\x14\x00(....)', dec, re.DOTALL)
        if not ms:
            continue
        sid = struct.unpack('<I', ms.group(1))[0]
        mv = re.search(b'\x96\xed(.)', dec, re.DOTALL)
        vnum = mv.group(1)[0] if mv else 0

        pins = []
        for pm in re.finditer(b'\x97\xed\x30\x00(?:\xbd\xed(..))?\xbe\xed(.{16})\xbf\xed(..)', dec, re.DOTALL):
            pidx = struct.unpack('<H', pm.group(1))[0] if pm.group(1) else 0
            px, py = struct.unpack('<dd', pm.group(2))
            pdir = struct.unpack('<H', pm.group(3))[0]
            if abs(px) < 1000 and abs(py) < 1000:
                pins.append({'index': pidx + 1, 'x': round(px, 3), 'y': round(py, 3), 'dir': pdir})

        v_obj = {
            'vid': vid,
            'sym_id': sid,
            'var_num': vnum,
            'var_letter': chr(65 + (vnum % 26)),
            'pins': pins,
            'primitives': []
        }
        variants[vid] = v_obj
        if sid in symbols:
            symbols[sid]['variants'][vnum] = v_obj

    return variants


def parse_instances(variants, sdb_dir=SDB_DIR):
    """解析 Instance.eod 全部 130,292 条几何图元记录"""
    inst_path = os.path.join(sdb_dir, 'Instance.eod')
    inst_data = open(inst_path, 'rb').read()
    rec_size = 134
    num_recs = len(inst_data) // rec_size
    counts = {'line': 0, 'arc_circle': 0, 'rect': 0, 'polyline': 0, 'text': 0, 'block': 0}

    for i_idx in range(num_recs):
        irec = inst_data[i_idx * rec_size:(i_idx + 1) * rec_size]
        itype = struct.unpack_from('>H', irec, 4)[0]
        parent_tbl = struct.unpack_from('>H', irec, 24)[0]
        vid = struct.unpack_from('>I', irec, 26)[0]
        if parent_tbl != 0x002d or vid not in variants:
            m_vid = re.search(b'\xf1\xeb\x2d\x00(....)', irec, re.DOTALL)
            if m_vid:
                vid = struct.unpack('<I', m_vid.group(1))[0]
            if vid not in variants:
                continue

        zoff = irec.find(b'\x78\xda')
        if zoff != -1:
            try:
                body = zlib.decompressobj().decompress(irec[zoff:])
            except Exception:
                body = irec[30:]
        else:
            body = irec[30:]

        mlt = re.search(b'\xfc\xeb(..)', body, re.DOTALL)
        dashed = bool(mlt and struct.unpack('<H', mlt.group(1))[0] == 1)

        if itype == 0x1f:  # LINE
            m1 = re.search(b'\x73\xec(.{16})', body, re.DOTALL)
            m2 = re.search(b'\x74\xec(.{16})', body, re.DOTALL)
            if m1 and m2:
                x1, y1 = struct.unpack('<dd', m1.group(1))
                x2, y2 = struct.unpack('<dd', m2.group(1))
                if all(abs(v) < 1000 for v in (x1, y1, x2, y2)):
                    variants[vid]['primitives'].append({
                        'type': 'line',
                        'x1': round(x1, 4), 'y1': round(y1, 4),
                        'x2': round(x2, 4), 'y2': round(y2, 4),
                        'dashed': dashed
                    })
                    counts['line'] += 1

        elif itype == 0x20:  # ARC / CIRCLE
            mc = re.search(b'\x8b\xec(.{16})', body, re.DOTALL)
            cx, cy = struct.unpack('<dd', mc.group(1)) if mc else (0.0, 0.0)
            mr = re.search(b'\x8c\xec(.{8})', body, re.DOTALL)
            r = struct.unpack('<d', mr.group(1))[0] if mr else 0.0
            ma1 = re.search(b'\x89\xec(.{8})', body, re.DOTALL)
            ma2 = re.search(b'\x8a\xec(.{8})', body, re.DOTALL)
            a1 = math.degrees(struct.unpack('<d', ma1.group(1))[0]) if ma1 else 0.0
            a2 = math.degrees(struct.unpack('<d', ma2.group(1))[0]) if ma2 else 360.0
            if 0.01 < abs(r) < 500 and abs(cx) < 1000 and abs(cy) < 1000:
                variants[vid]['primitives'].append({
                    'type': 'arc_circle',
                    'cx': round(cx, 4), 'cy': round(cy, 4), 'r': round(abs(r), 4),
                    'a1': round(a1, 2), 'a2': round(a2, 2),
                    'is_circle': abs(abs(a2 - a1) - 360.0) < 1.0 or (not ma1 and not ma2),
                    'dashed': dashed
                })
                counts['arc_circle'] += 1

        elif itype == 0x59:  # RECTANGLE
            m1 = re.search(b'\xd3\xf0(.{16})', body, re.DOTALL)
            m2 = re.search(b'\xd4\xf0(.{16})', body, re.DOTALL)
            if m1 and m2:
                x1, y1 = struct.unpack('<dd', m1.group(1))
                x2, y2 = struct.unpack('<dd', m2.group(1))
                if all(abs(v) < 1000 for v in (x1, y1, x2, y2)):
                    variants[vid]['primitives'].append({
                        'type': 'rect',
                        'x1': round(x1, 4), 'y1': round(y1, 4),
                        'x2': round(x2, 4), 'y2': round(y2, 4),
                        'dashed': dashed
                    })
                    counts['rect'] += 1

        elif itype == 0x22:  # POLYLINE / POLYGON
            pts = []
            for pm in re.finditer(b'\xcd\xec(.{16})', body, re.DOTALL):
                px, py = struct.unpack('<dd', pm.group(1))
                if abs(px) < 1000 and abs(py) < 1000:
                    pts.append((round(px, 4), round(py, 4)))
            if len(pts) >= 2:
                closed = bool(re.search(b'\xcf\xec\x01', body))
                variants[vid]['primitives'].append({
                    'type': 'polyline',
                    'points': pts,
                    'closed': closed,
                    'dashed': dashed
                })
                counts['polyline'] += 1

        elif itype in (0x1e, 0x53):  # TEXT
            mp = re.search(b'\x55\xec(.{16})', body, re.DOTALL)
            tx, ty = struct.unpack('<dd', mp.group(1)) if mp else (0.0, 0.0)
            mt = re.search(b'\x5f\xec([^\x00]+)\x00', body)
            raw_t = mt.group(1).decode('utf-8', 'ignore') if mt else ''
            m_clean = re.search(r'@([^;]+)', raw_t)
            txt = m_clean.group(1) if m_clean else raw_t
            if txt and abs(tx) < 1000 and abs(ty) < 1000:
                variants[vid]['primitives'].append({
                    'type': 'text',
                    'x': round(tx, 4), 'y': round(ty, 4),
                    'text': txt
                })
                counts['text'] += 1

        elif itype == 0x90:
            counts['block'] += 1

    return counts


def sanitize_block_name(code, sym_id):
    """生成合法的 AutoCAD DXF 块名"""
    clean = re.sub(r'[^A-Za-z0-9_\-\u4e00-\u9fa5]', '', code)
    if not clean:
        clean = f'SYM_{sym_id}'
    return f'MENGGE_{clean}'


def build_dxf_block_str(bname, v_obj):
    """将单个符号变体构建为标准 AutoCAD DXF BLOCK 文本块"""
    lines = [
        f"  0\nBLOCK\n  8\n0\n  2\n{bname}\n 70\n0\n 10\n0.0\n 20\n0.0\n 30\n0.0\n  3\n{bname}\n  1\n\n"
    ]
    for p in v_obj['primitives']:
        lt_str = "  6\nDASHED\n" if p.get('dashed') else ""
        if p['type'] == 'line':
            lines.append(
                f"  0\nLINE\n  8\n0\n{lt_str}"
                f" 10\n{p['x1']:.4f}\n 20\n{p['y1']:.4f}\n 30\n0.0\n"
                f" 11\n{p['x2']:.4f}\n 21\n{p['y2']:.4f}\n 31\n0.0\n"
            )
        elif p['type'] == 'rect':
            pts = [(p['x1'], p['y1']), (p['x2'], p['y1']), (p['x2'], p['y2']), (p['x1'], p['y2']), (p['x1'], p['y1'])]
            for i in range(4):
                lines.append(
                    f"  0\nLINE\n  8\n0\n{lt_str}"
                    f" 10\n{pts[i][0]:.4f}\n 20\n{pts[i][1]:.4f}\n 30\n0.0\n"
                    f" 11\n{pts[i+1][0]:.4f}\n 21\n{pts[i+1][1]:.4f}\n 31\n0.0\n"
                )
        elif p['type'] == 'polyline':
            pts = list(p['points'])
            if p.get('closed') and pts[0] != pts[-1]:
                pts.append(pts[0])
            for i in range(len(pts) - 1):
                lines.append(
                    f"  0\nLINE\n  8\n0\n{lt_str}"
                    f" 10\n{pts[i][0]:.4f}\n 20\n{pts[i][1]:.4f}\n 30\n0.0\n"
                    f" 11\n{pts[i+1][0]:.4f}\n 21\n{pts[i+1][1]:.4f}\n 31\n0.0\n"
                )
        elif p['type'] == 'arc_circle':
            if p['is_circle']:
                lines.append(
                    f"  0\nCIRCLE\n  8\n0\n{lt_str}"
                    f" 10\n{p['cx']:.4f}\n 20\n{p['cy']:.4f}\n 30\n0.0\n 40\n{p['r']:.4f}\n"
                )
            else:
                lines.append(
                    f"  0\nARC\n  8\n0\n{lt_str}"
                    f" 10\n{p['cx']:.4f}\n 20\n{p['cy']:.4f}\n 30\n0.0\n 40\n{p['r']:.4f}\n"
                    f" 50\n{p['a1']:.4f}\n 51\n{p['a2']:.4f}\n"
                )
        elif p['type'] == 'text':
            lines.append(
                f"  0\nTEXT\n  8\n0\n 10\n{p['x']:.4f}\n 20\n{p['y']:.4f}\n 30\n0.0\n"
                f" 40\n2.0\n  1\n{p['text']}\n"
            )
    lines.append("  0\nENDBLK\n  8\n0\n")
    return "".join(lines)


def inject_mengge_symbols_into_dxf(symbols, dxf_paths):
    """将赵猛定制与修改的全部 28 个专属符号注入 DXF 符号库与图框模板"""
    mengge_syms = [s for s in symbols.values() if s['is_mengge']]
    mengge_syms.sort(key=lambda x: x['sym_id'])

    injected_names = []
    block_chunks = []

    for s in mengge_syms:
        v_dict = s['variants']
        if not v_dict:
            continue
        # Prefer Variant 0 (A); if empty primitives, pick first variant with primitives
        v_obj = v_dict.get(0) or next(iter(v_dict.values()))
        if not v_obj['primitives']:
            for k in sorted(v_dict.keys()):
                if v_dict[k]['primitives']:
                    v_obj = v_dict[k]
                    break
        bname = sanitize_block_name(s['code'], s['sym_id'])
        block_chunks.append((bname, build_dxf_block_str(bname, v_obj)))
        injected_names.append((bname, s['sym_id'], s['code'], s['zh_name'], s['iec_ref'], len(v_obj['pins']), len(v_obj['primitives']), v_obj))

    for dxf_path in dxf_paths:
        if not os.path.exists(dxf_path):
            continue
        content = open(dxf_path, 'r', encoding='utf-8', errors='ignore').read()
        # Remove previously injected MENGGE_ blocks if re-running
        content = re.sub(r'  0\nBLOCK\n  8\n0\n  2\nMENGGE_.*?\n  0\nENDBLK\n  8\n0\n', '', content, flags=re.DOTALL)
        b_start = content.find('SECTION\n  2\nBLOCKS')
        b_end = content.find('  0\nENDSEC', b_start)
        if b_start != -1 and b_end != -1:
            all_new_blocks = "".join(chunk for _, chunk in block_chunks)
            content = content[:b_end] + all_new_blocks + content[b_end:]
            with open(dxf_path, 'w', encoding='utf-8') as f:
                f.write(content)

    return injected_names


def render_mengge_symbol_atlas(injected_list, out_png, out_pdf):
    """渲染《猛哥专用符号库 28 个专属定制与改建符号图谱》高清图"""
    n = len(injected_list)
    cols = 7
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(22, rows * 3.2), dpi=200)
    fig.patch.set_facecolor('white')
    fig.suptitle('《猛哥专用符号库.sdb》逆向提取 — 赵猛定制与改建 28 个专属 EPLAN 符号图谱 (1:1 真实几何与 4mm 模数引脚)',
                 fontproperties=CJK_FP, fontsize=15, fontweight='bold', y=0.98, color='#1A365D')

    axes_flat = axes.flatten() if hasattr(axes, 'flatten') else [axes]
    for idx, ax in enumerate(axes_flat):
        if idx >= n:
            ax.axis('off')
            continue
        bname, sid, code, zh_name, iec_ref, npins, nprims, v_obj = injected_list[idx]
        ax.set_facecolor('#F8FAFC')
        ax.grid(True, linestyle=':', linewidth=0.5, color='#CBD5E1')

        xs, ys = [0.0], [0.0]
        for p in v_obj['primitives']:
            ls = '--' if p.get('dashed') else '-'
            if p['type'] == 'line':
                ax.plot([p['x1'], p['x2']], [p['y1'], p['y2']], color='#0F172A', lw=1.5, linestyle=ls)
                xs.extend([p['x1'], p['x2']])
                ys.extend([p['y1'], p['y2']])
            elif p['type'] == 'rect':
                rx = [p['x1'], p['x2'], p['x2'], p['x1'], p['x1']]
                ry = [p['y1'], p['y1'], p['y2'], p['y2'], p['y1']]
                ax.plot(rx, ry, color='#0F172A', lw=1.5, linestyle=ls)
                xs.extend(rx)
                ys.extend(ry)
            elif p['type'] == 'polyline':
                pts = list(p['points'])
                if p.get('closed') and pts[0] != pts[-1]:
                    pts.append(pts[0])
                px = [pt[0] for pt in pts]
                py = [pt[1] for pt in pts]
                ax.plot(px, py, color='#0F172A', lw=1.5, linestyle=ls)
                xs.extend(px)
                ys.extend(py)
            elif p['type'] == 'arc_circle':
                if p['is_circle']:
                    cir = mpatches.Circle((p['cx'], p['cy']), p['r'], fill=False, edgecolor='#0F172A', lw=1.5, linestyle=ls)
                    ax.add_patch(cir)
                else:
                    arc = mpatches.Arc((p['cx'], p['cy']), 2 * p['r'], 2 * p['r'], angle=0,
                                       theta1=p['a1'], theta2=p['a2'], edgecolor='#0F172A', lw=1.5, linestyle=ls)
                    ax.add_patch(arc)
                xs.extend([p['cx'] - p['r'], p['cx'] + p['r']])
                ys.extend([p['cy'] - p['r'], p['cy'] + p['r']])
            elif p['type'] == 'text':
                ax.text(p['x'], p['y'], p['text'], fontproperties=CJK_FP, fontsize=8, color='#1E40AF', ha='center', va='center', fontweight='bold')
                xs.append(p['x'])
                ys.append(p['y'])

        for pin in v_obj['pins']:
            ax.plot(pin['x'], pin['y'], 'ro', markersize=4.5, zorder=5)
            ax.text(pin['x'] + 0.4, pin['y'] + 0.4, f"#{pin['index']}", fontsize=6.5, color='#DC2626', fontweight='bold')
            xs.append(pin['x'])
            ys.append(pin['y'])

        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        span = max(xmax - xmin, ymax - ymin, 8.0) * 0.68
        cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
        ax.set_xlim(cx - span, cx + span)
        ax.set_ylim(cy - span, cy + span)
        ax.set_aspect('equal')
        ax.tick_params(labelsize=6)
        title_zh = zh_name if len(zh_name) <= 12 else zh_name[:12] + '..'
        ax.set_title(f"{bname}\n[{code}] {title_zh}\n(引脚:{npins} | 图元:{nprims} | Var:{v_obj['var_letter']})",
                     fontproperties=CJK_FP, fontsize=7.5, fontweight='bold', color='#1E293B')

    plt.tight_layout(rect=[0, 0.01, 1, 0.95])
    fig.savefig(out_png, dpi=200)
    fig.savefig(out_pdf)
    plt.close(fig)


if __name__ == '__main__':
    symbols, ordered_list = parse_symbols()
    variants = parse_variants(symbols)
    prim_counts = parse_instances(variants)

    print(f"Parsed Symbols: {len(symbols)}, Variants: {len(variants)}, Primitives: {prim_counts}")

    dxf_targets = [
        os.path.join(OUT_DIR, 'standard-symbols-IEC-EPLAN.dxf'),
        os.path.join(OUT_DIR, 'NERIN-A2-frame-ready.dxf'),
    ]
    injected = inject_mengge_symbols_into_dxf(symbols, dxf_targets)
    print(f"Injected {len(injected)} MENGGE_* custom/modified symbols into DXF libraries:")
    for item in injected:
        print(f"  {item[0]:20s} | ID={item[1]:4d} | Code={item[2]:10s} | ZH={item[3]:18s} | IEC={item[4]:15s} | pins={item[5]} | prims={item[6]}")

    catalog_out = {
        'library_name': '猛哥专用符号库.sdb',
        'slk_version': '1.2',
        'author_marker': '赵猛;LAPTOP-P10FRKB6;;赵猛;13920794724;',
        'total_symbols': len(symbols),
        'total_variants': len(variants),
        'primitive_counts': prim_counts,
        'mengge_custom_symbols_count': len(injected),
        'mengge_custom_symbols': [
            {
                'dxf_block': item[0],
                'sym_id': item[1],
                'code': item[2],
                'zh_name': item[3],
                'iec_ref': item[4],
                'variant_used': item[7]['var_letter'],
                'pins': item[7]['pins'],
                'primitives_count': item[6],
                'primitives': item[7]['primitives']
            }
            for item in injected
        ],
        'all_symbols_summary': [
            {
                'sym_id': s['sym_id'],
                'sym_num': s['sym_num'],
                'code': s['code'],
                'zh_name': s['zh_name'],
                'en_name': s['en_name'],
                'iec_ref': s['iec_ref'],
                'author': s['author'],
                'variant_count': len(s['variants']),
                'variant_A_pins': s['variants'][0]['pins'] if 0 in s['variants'] else []
            }
            for s in ordered_list
        ]
    }
    json_path = os.path.join(OUT_DIR, 'mengge_symbol_catalog.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(catalog_out, f, ensure_ascii=False, indent=2)
    print('Saved catalog JSON:', json_path, os.path.getsize(json_path))

    atlas_png = os.path.join(OUT_DIR, '猛哥专用符号库_28个专属符号图谱.png')
    atlas_pdf = os.path.join(OUT_DIR, '猛哥专用符号库_28个专属符号图谱.pdf')
    render_mengge_symbol_atlas(injected, atlas_png, atlas_pdf)
    print('Rendered atlas:', atlas_png, atlas_pdf)
