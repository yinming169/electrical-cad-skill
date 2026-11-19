---
name: electrical-cad-skill
description: 将自然语言描述、手绘草图或电气图纸照片转化为符合现行 IEC 标准（IEC 60617 / IEC 81346-2 / IEC 61082-1 / IEC 61439-1）与国家标准（GB/T 4728 / GB/T 5094.2-2018 / GB/T 6988.1-2024 / GB/T 7251.1-2023 / GB/T 24275-2019）的标准 CAD 电气图纸（.dxf / .dwg / .pdf）。以 EPLAN 样图与 EPLAN 符号库为最高绘图基准，兼容 Claude、DeepSeek、GLM、Kimi、Cursor 及 Codex 直接调用。
---

# 电气制图标准 Skill（IEC / GB + EPLAN 双轨引擎）

## 0. 最高优先级绘图与符号基准（EPLAN 样图 + EPLAN 符号库）
- **绘制方式基准**：所有电气原理图与二次控制图的图面布局、顶部 `0~9` 十列栅格、底部通栏标题栏、跨页中断箭头、线圈下方触点映像表、导轨端子排穿透虚线及器件引脚编号，必须严格参考本仓库提供的 EPLAN 样图（`examples/pdf/EPLAN工业标准自训练样图集_6页全套.pdf`、`examples/pdf/一次与二次双轨规范样图集_6张全套_断路器修正版.pdf`）。
- **图形符号基准**：所有器件图形符号优先且必须调用 EPLAN 符号库（`symbols/mengge_symbol_catalog.json`、`symbols/standard-symbols-IEC-EPLAN-PRIM-MENGGE-134.dxf`）中的原生矢量符号与 4 mm 模数引脚定义，严禁脱离 EPLAN 符号库随意绘制非标图元。

## 1. 强制遵循的现行标准体系
1. 图形符号：`GB/T 4728` 系列（等同 `IEC 60617`）+ EPLAN 4 mm 模数栅格。
2. 项目参照代号（位号）：`GB/T 5094.2-2018`（等同 `IEC 81346-2:2009`，兼容 `IEC 81346-2:2019`）与 `-QF / -KM / -KA / -FR / -SB / -SA / -X: / -PE`。
3. 电气文件编制：`GB/T 6988.1-2024`（对应 `IEC 61082-1:2014`）。
4. 低压成套开关设备和控制设备：`GB/T 7251.1-2023`（等同 `IEC 61439-1:2020`）与 `GB/T 24275-2019`。

## 2. 双轨制图路由
- **轨道 A（电气一次图 `primary`）**：10 kV/6 kV 高压、0.4 kV MNS/GGD、XL-21、变频柜、配电箱、手绘一次草图 → A2 一次系统图框（顶部 3 行柜体表 + 底部 2/6 行对齐负荷表，无 0~9 列号）。
- **轨道 B（电气二次图 `secondary`）**：电机启停/星三角/软起/变频控制、水泵阀门、PLC DI/DO/AI/AO → EPLAN P8 图框（顶部 0~9 十列栅格 + 底部通栏标题栏 + 跨页中断箭头 + 触点映像表）。

## 3. 不可违背的工程与制图铁律
1. **塑壳断路器（MCCB）单线画法**：上端竖线精确终止于灭弧叉号 `×` 中心，断口完全空白断开，斜刀闸从下端出线顶点向左上伸至与 `×` 中心平齐。
2. **抽出式接插件（`︽`/`︾`）边界**：仅限 MNS 低压抽出式抽屉回路；GGD、XL-21、变频柜、壁挂箱等固定式回路严禁画接插件。
3. **标准图形符号**：PT 双圆相交、PE 外切圆三横杠、热元件矩形方波、熔断器开关带熔体框。
4. **核心安全与校核**：CT 二次严禁开路且须一点接地；PT 二次严禁短路（100 V）；TN-S 双电源/母联/ATSE 须为 4P 且配 2 kV·A UPS；电机起动遵循 `Ku = 0.75 + 0.25 * S / P` 判据；低置信度或模糊照片参数一律标 `?` 禁止瞎猜。
5. **零碰撞自审**：每次出图必须通过 16 项严苛审查（0 文字重叠、0 文字压线、0 导线穿框、0 图框越界）。

## 4. 命令行一键调用
```bash
python scripts/electrical_cad_cli.py generate --text "37kW风机星三角起动，变压器容量800kVA，带急停和运行指示" --out output/y_delta.dxf --pdf --audit
python scripts/electrical_cad_cli.py generate --json examples/sample_ir_star_delta.json --out output/from_ir.dxf --pdf --audit
python scripts/electrical_cad_cli.py audit --dxf output/y_delta.dxf --mode secondary
```
