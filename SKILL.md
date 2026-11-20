---
name: electrical-cad-skill
description: 将自然语言描述、手绘草图或电气图纸照片转化为符合现行 IEC 标准（IEC 60617 / IEC 81346-2 / IEC 61082-1 / IEC 61439-1）与国家标准（GB/T 4728 / GB/T 5094.2-2018 / GB/T 6988.1-2024 / GB/T 7251.1-2023 / GB/T 24275-2019）的标准 CAD 电气图纸（.dxf / .dwg / .pdf）。支持“一次配电系统图 + EPLAN 规范二次原理图”双轨制图，内置 131 个 IEC/EPLAN/一次图融合符号块与 16 项像素级几何碰撞自审，兼容 Claude、DeepSeek、GLM、Kimi、Cursor 及 Codex 直接调用。
---

# 电气制图标准 Skill（IEC / GB + EPLAN 双轨引擎）

本 Skill 用于将**文字需求**、**手绘草图照片**或**既有图纸扫描件**转化为可直接用于工程评审与 AutoCAD / EPLAN 协同的标准化 `.dxf` / `.dwg` / `.pdf` 电气图纸，并自动输出 16 项几何与规范自审报告。

---

## 0. 最高优先级绘图与符号基准（EPLAN 样图 + EPLAN 符号库）

- **绘制方式基准**：所有电气原理图与二次控制图的图面布局、顶部 `0~9` 十列栅格、底部通栏标题栏、跨页中断箭头、线圈下方触点映像表、导轨端子排穿透虚线及器件引脚编号，**必须严格参考本仓库提供的 EPLAN 样图**（`examples/EPLAN工业标准自训练样图集_6页全套.pdf`、`examples/一次与二次双轨规范样图集_6张全套_断路器修正版.pdf`）。
- **图形符号基准**：所有器件图形符号**优先且必须**调用用户提供的 **EPLAN 符号库**（`symbols/mengge_symbol_catalog.json`、`symbols/standard-symbols-IEC-EPLAN-PRIM-MENGGE-134.dxf`、`examples/猛哥专用符号库_30个专属符号图谱.pdf`）中的原生矢量符号与 4 mm 模数引脚定义，严禁脱离 EPLAN 符号库随意绘制非标图元。如用户后续提供新的 EPLAN `.sdb` 符号库，须先用 `scripts/mengge_sdb_parser.py` 解析同步并作为最新符号基准。

---

## 1. 强制遵循的现行标准体系

所有图纸创建与审核**必须**严格符合以下现行国际标准（IEC）与国家标准（GB/T），详见 `references/iec_gb_standards.md`：

1. **图形符号**：`GB/T 4728` 系列（等同采用 `IEC 60617` 数据库）+ EPLAN 4 mm 模数栅格。
2. **项目参照代号（位号）**：`GB/T 5094.2-2018`（等同 `IEC 81346-2:2009`，兼容 `IEC 81346-2:2019`）与院标前缀（`-QF`、`-KM`、`-KA`、`-FR`、`-SB`、`-SA`、`-X:`、`-PE`）。
3. **电气文件与简图编制**：`GB/T 6988.1-2024`（对应 `IEC 61082-1:2014`）。
4. **低压成套开关设备和控制设备**：`GB/T 7251.1-2023`（等同 `IEC 61439-1:2020`）与 `GB/T 24275-2019`。

---

## 2. 核心双轨制图路由（先判定，再出图）

收到文字或照片输入后，先判断图纸属于哪一条轨道，**严禁混用图框与画法**（详见 `references/dual_track_spec.md`）：

| 轨道 | 适用图纸类型 | 基准图框与布局 | 符号基准 |
| :--- | :--- | :--- | :--- |
| **轨道 A：电气一次图** (`primary`) | 10 kV / 6 kV 高压系统图、0.4 kV MNS/GGD 低压配电系统图、XL-21 动力柜、变频柜、壁挂配电箱、手绘一次草图 | A2 工程设计院一次系统图框（右侧会签/标题栏 + 顶部 3 行柜体表 + 底部 2/6 行对齐负荷表，无 0–9 列号） | `symbols/standard-symbols-IEC-EPLAN-PRIM-MENGGE-134.dxf` 中的 `PRIM_*` + `IEC_*` / `GB*` 块 |
| **轨道 B：电气二次图** (`secondary`) | 电机起动/互锁控制原理图、PLC DI/DO/AI/AO 接线图、水泵/阀门控制箱、EPLAN 多页原理图 | **EPLAN Electric P8 工业标准图框**（顶部 `0~9` 十列栅格 + 底部通栏标题栏 + `=高层代号/+位置代号` + 跨页中断箭头 + 触点映像表） | `symbols/standard-symbols-IEC-EPLAN-PRIM-MENGGE-134.dxf` + `symbols/mengge_symbol_catalog.json`（EPLAN 符号库基准） |

---

## 3. 文字 / 照片转 CAD 标准执行流

### 原则
- **直接出图，不卡前置确认**：完成解析、生图、PDF 预览与 16 项自审后一并交付，便于工程师在 CAD 中二次微调。
- **低置信度显式标 `?`**：对于模糊照片、低清扫描件或水印遮挡的参数（如整定电流、电缆截面、线号），**严禁盲目猜测**，在标注末尾加 `?` 并写入 `*_audit_report.json` / `*_自检报告.md`。

### 4 步工作流

1. **解析输入 → 生成标准 IR JSON**
   - 若为**文字需求**：直接调用统一 CLI（自动解析功率、变压器容量、$K_u$ 起动判据、电流、断路器与电缆规格），或先按 `references/circuit_ir_schema.json` 输出结构化 IR JSON。
   - 若为**照片 / 手绘草图 / PDF 截图**：利用当前多模态 AI 的视觉能力先确认方向（0°/90°/180°/270°），过滤水印，按 `references/circuit_ir_schema.json` 提取拓扑、器件位号、型号规格、端子/线号及不确定字段（标 `?`），保存为 `circuit_ir.json`。
2. **调用统一 CLI 生成 DXF + PDF 预览 + 自动自审**
   ```bash
   # 方式 1：自然语言一键出图（支持直接起动/星三角/自耦/软起/变频/双电源ATSE）
   python scripts/electrical_cad_cli.py generate \
     --text "37kW风机星三角起动，变压器容量800kVA，带急停和运行指示" \
     --out output/y_delta.dxf --pdf --audit

   # 方式 2：基于多模态 AI 解析出的 IR JSON 出图
   python scripts/electrical_cad_cli.py generate \
     --json examples/sample_ir_star_delta.json \
     --out output/from_ir.dxf --pdf --audit

   # 方式 3：生成全套一次+二次双轨规范样图（用于验证或对照 EPLAN 基准）
   python scripts/electrical_cad_cli.py samples --track all --out-dir output/samples

   # 方式 4：对任意已有 DXF 执行 16 项严苛规范自审
   python scripts/electrical_cad_cli.py audit --dxf output/y_delta.dxf --mode secondary
   ```
3. **（可选）调用本机 AutoCAD 2018 控制台核心直出 `.dwg`**
   - 仅限已安装 AutoCAD 的 Windows 环境，通过 `accoreconsole.exe` 无界面执行（禁止 GUI 点击）：
     ```bash
     python scripts/run_acad2018_core.py --dxf output/y_delta.dxf --out-dwg output/y_delta.dwg
     ```
4. **（可选）扩展导入新的 EPLAN `.sdb` 符号库**
   ```bash
   python scripts/mengge_sdb_parser.py --sdb path/to/your_symbols.sdb --out-dir symbols/
   ```

---

## 4. 不可违背的工程与制图铁律

1. **塑壳断路器（MCCB）单线画法**：上端竖线必须精确终止于灭弧叉号 `×` 中心，断口区间完全空白断开，斜刀闸从下端出线顶点 `(x, y_bot)` 向左上伸至 `(x-410, y_top)`，严禁竖线穿通断口或斜刀闸下方悬空。
2. **抽屉接插件（`︽`/`︾`）边界**：仅 **MNS 低压抽出式抽屉回路**允许绘制上下接插件；GGD、XL-21、变频柜、壁挂箱等固定式回路**严禁**绘制接插件。
3. **标准图形符号核验**：电压互感器（PT）必须为双圆相交；保护接地（PE）必须为外切圆包围三横杠；热元件必须为 IEC 矩形方波阶梯；熔断器开关动触刀必须带矩形熔体框。
4. **核心电气安全铁律**：
   - CT 二次侧严禁开路且须一点接地；PT 二次侧严禁短路（额定 100 V）。
   - TN-S 双电源/备自投的进线、母联与 ATSE 均须为 **4P** 开关，PLC 测控配在线式 UPS（典型 2 kV·A）。
   - 电机起动方式遵循 $K_u = 0.75 + 0.25 \cdot S/P$ 判据（$K_u \ge 6$ 允许直起；$4 \le K_u < 6$ 推荐降压起动；$K_u < 4$ 推荐软起/变频）。
   - 电机型号格式为 `Y-112M-4`（功率另标，严禁写成 `Y-112M-4.4`）。
5. **零碰撞自审闭环**：每次出图必须通过 `scripts/cad_strict_auditor.py` 审查，确保 **0 文字重叠、0 文字压线、0 导线穿框、0 图框越界**；若检出冲突，先调整坐标重新生成再交付。

---

## 5. 目录导航

- `references/iec_gb_standards.md` — 现行 IEC / 国标条款与选型校核手册
- `references/dual_track_spec.md` — 一次图 vs EPLAN 二次图双轨制图细则
- `references/circuit_ir_schema.json` — 文字/照片转 CAD 统一中间表示（IR）结构定义
- `symbols/` — 131 块融合符号 DXF、开箱即用 A2 模板与 875 个 EPLAN 符号矢量索引 JSON
- `scripts/` — 跨平台 Python 生图、自审、`.sdb` 解析与 AutoCAD 核心调用脚本
- `examples/` — EPLAN 基准样图 PDF、双轨规范样图 PDF、符号图谱 PDF 及 IR 示例
- `prompts/universal_system_prompt.md` — 供 DeepSeek / Kimi / GLM / Claude 网页端直接复制使用的单文件提示词


## AutoCAD 2007 兼容与无 CAD 开源生图引擎

- **开源 CAD 引擎**：内置集成 GitHub 开源 Python CAD 库 [`mozman/ezdxf`](https://github.com/mozman/ezdxf)（MIT 协议），**任何未安装 AutoCAD 的电脑**只需 Python + `pip install -r requirements.txt` 即可独立生成标准 `.dxf` 图纸。
- **AutoCAD 2007 原生兼容（`R2007` / `AC1021`）**：所有输出图纸与仓库样图均通过 `scripts/dxf_2007_exporter.py` 重建标准 Handle、AcDb 子类标记、UTF-8 编码与 `simplex.shx + gbcbig.shx` 字体样式，并通过 `ezdxf` `doc.audit()` 零错误校验，确保 **AutoCAD 2007 及以上所有版本直接打开无报错、无乱码**。
- **可选开源看图/转换工具**：如需在无 AutoCAD 电脑上可视化查看/编辑 `.dxf`，可配合开源 [`LibreCAD`](https://github.com/LibreCAD/LibreCAD)；如需离线转 `.dwg`，可配合开源 [`LibreDWG`](https://github.com/LibreDWG/libredwg)。
