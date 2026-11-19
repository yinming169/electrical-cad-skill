# Electrical CAD Skill (`electrical-cad-skill`)

一个面向多模态大语言模型（**Claude / DeepSeek / GLM / Kimi / Cursor / Codex / Gemini**）的开源电气制图 Skill，用于将**自然语言描述**、**手绘草图照片**或**电气原理图扫描件**转化为符合现行 **IEC 标准** 与 **中国国家标准（GB/T）** 的标准化 `.dxf` / `.dwg` / `.pdf` CAD 图纸，并内置 16 项几何与规范自动审查闭环。

## 核心特性

- **现行 IEC & 国标合规**：对齐 `GB/T 4728`（IEC 60617）、`GB/T 5094.2-2018`（IEC 81346-2）、`GB/T 6988.1-2024`（IEC 61082-1）、`GB/T 7251.1-2023`（IEC 61439-1）与 `GB/T 24275-2019`。
- **一次图 + EPLAN 二次图双轨架构**：
  - **一次系统图**：支持 10 kV 高压柜、0.4 kV MNS 低压抽屉柜、XL-21 动力柜、变频柜、壁挂箱及手绘一次草图转化（内置断路器断口与 MNS 接插件硬性修正）。
  - **EPLAN 二次原理图**：完整复刻 EPLAN Electric P8 规范（顶部 `0~9` 十列栅格、底部通栏标题栏、跨页中断箭头、线圈下方触点映像表、端子排穿透虚线与 PE 等电位接地）。
- **131 个融合标准 DXF 符号块 + 875 个 EPLAN 矢量符号索引**：开箱即用，支持后续通过 `scripts/mengge_sdb_parser.py` 导入新的 EPLAN `.sdb` 符号库。
- **16 项严苛几何自审**：自动检测文字重叠、文字压线、导线穿框、悬空引脚、图框越界及 AutoCAD 2018 字体防卡死配置。
- **跨平台零硬编码**：纯 Python 相对路径架构，自动探测 Windows / macOS / Linux 中文字体，无需安装 AutoCAD 即可直接生成标准 DXF 与高清 PDF 预览。

## 快速开始

### 1. 环境准备

```bash
git clone https://github.com/<your-username>/electrical-cad-skill.git
cd electrical-cad-skill
pip install -r requirements.txt
python scripts/electrical_cad_cli.py check-env
```

### 2. 命令行一键生图与自审

```bash
# 自然语言转 CAD（DXF + PDF 预览 + 自动自审）
python scripts/electrical_cad_cli.py generate \
  --text "37kW风机星三角起动，变压器容量800kVA，带急停和运行指示" \
  --out output/fan_star_delta.dxf --pdf --audit

# 从 AI 识别出的 IR JSON 生成 CAD
python scripts/electrical_cad_cli.py generate \
  --json examples/sample_ir_star_delta.json \
  --out output/from_ir.dxf --pdf --audit

# 对已有 DXF 进行 16 项规范自审
python scripts/electrical_cad_cli.py audit --dxf output/fan_star_delta.dxf --mode secondary

# 一键生成全套一次+二次规范参考样图
python scripts/electrical_cad_cli.py samples --track all --out-dir output/samples
```

## 在不同 AI 平台上调用本 Skill

| AI 平台 / 工具 | 推荐调用方式 |
| :--- | :--- |
| **Claude Code / Cursor / Codex / OpenClaw** | 直接将本仓库克隆到技能目录（如 `.claude/skills/electrical-cad-skill/`），AI 会自动识别根目录 `SKILL.md` 并调用 `scripts/electrical_cad_cli.py`。 |
| **DeepSeek / Kimi / GLM（智谱清言）网页端** | 1) 复制 `prompts/universal_system_prompt.md` 作为系统提示词或首轮指令；<br>2) 上传草图照片或输入文字需求，让 AI 输出符合 `references/circuit_ir_schema.json` 的 JSON；<br>3) 在本地终端运行 `python scripts/electrical_cad_cli.py generate --json <file.json> --out out.dxf --pdf --audit`。 |
| **支持代码解释器的 AI（如 Claude / ChatGPT / Kimi 代码环境）** | 直接上传本仓库压缩包，告诉 AI“阅读 `SKILL.md` 并执行 `scripts/electrical_cad_cli.py` 根据我的需求出图”。 |

## 目录结构

```text
electrical-cad-skill/
├── SKILL.md                         # 跨 AI 开放标准技能定义（核心入口）
├── README.md                        # 项目说明与多平台接入指南
├── requirements.txt                 # Python 依赖清单
├── prompts/
│   └── universal_system_prompt.md   # DeepSeek/Kimi/GLM/Claude 网页端单文件提示词
├── references/
│   ├── iec_gb_standards.md          # 现行 IEC / 国标强制规范对照
│   ├── dual_track_spec.md           # 一次图 + EPLAN 二次图双轨制图细则
│   └── circuit_ir_schema.json       # 文字/照片转 CAD 统一 IR JSON Schema
├── symbols/
│   ├── standard-symbols-IEC-EPLAN-PRIM-MENGGE-134.dxf
│   ├── NERIN-A2-frame.dxf
│   ├── NERIN-A2-frame-ready.dxf
│   ├── mengge_symbol_catalog.json
│   └── electrical_circuit_patterns.json
├── scripts/
│   ├── electrical_cad_cli.py        # 统一命令行入口
│   ├── path_utils.py                # 跨平台路径与中文字体自动探测
│   ├── one_click_cad_v2.py          # 文字/IR 一键生图引擎
│   ├── eplan_cad_engine.py          # EPLAN 二次图引擎
│   ├── primary_and_secondary_cad_engine_v2.py  # 一次+二次双轨引擎
│   ├── mengge_sample_generator.py   # EPLAN 符号库实战样图生成器
│   ├── generate_sketch_primary_dxf.py # 手绘草图一次系统图引擎
│   ├── cad_strict_auditor.py        # 16 项严苛规范审查器
│   ├── cad_self_checker.py          # DXF 解析与基础碰撞检查
│   ├── mengge_sdb_parser.py         # EPLAN .sdb 符号库解析导入工具
│   └── run_acad2018_core.py         # AutoCAD 2018 accoreconsole 桥接脚本
└── examples/
    ├── sample_ir_star_delta.json
    ├── EPLAN工业标准自训练样图集_6页全套.pdf
    ├── 一次与二次双轨规范样图集_6张全套_断路器修正版.pdf
    └── 猛哥专用符号库_30个专属符号图谱.pdf
```

## 合规与免责声明

- 本仓库**不包含**任何受版权保护的出版教材全文或扫描件，仅保留原创代码、标准符号块、结构化规范摘要与合成参考样图。
- 自动生成的 CAD 图纸供工程设计与评审加速使用；正式施工出图前，仍须由注册电气工程师按现行国家标准及项目设计院规范进行最终人工校审签章。
