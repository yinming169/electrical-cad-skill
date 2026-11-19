# Electrical CAD Skill (`electrical-cad-skill`)

面向 **Claude / DeepSeek / GLM / Kimi / Cursor / Codex** 的电气制图标准 Skill，将自然语言描述、手绘草图照片或图纸扫描件转化为符合现行 **IEC 标准**、**中国国家标准（GB/T）** 与 **EPLAN 样图/符号库基准** 的 CAD 电气图纸（`.dxf` / `.dwg` / `.pdf`）。

## 核心基准
- **最高优先级绘图与符号基准**：严格以配套 EPLAN 样图（顶部 `0~9` 列栅格、底部通栏标题栏、跨页中断箭头、触点映像表、端子排穿透虚线）与 EPLAN 符号库（131 块融合 DXF + 875 符号矢量 JSON，4 mm 模数）为准。
- **现行标准体系**：`GB/T 4728`（IEC 60617）、`GB/T 5094.2-2018`（IEC 81346-2）、`GB/T 6988.1-2024`（IEC 61082-1）、`GB/T 7251.1-2023`（IEC 61439-1）、`GB/T 24275-2019`。
- **双轨制图**：一次配电系统图（`primary`）与 EPLAN 二次控制原理图（`secondary`）严格分流，含塑壳断路器断口与 MNS 抽出式接插件边界硬性修正。

## 多 AI 平台调用方式
- **Claude Code / Cursor / Codex**：克隆本仓库至技能目录，自动识别根目录 `SKILL.md`。
- **DeepSeek / Kimi / GLM / Claude 网页端**：直接复制 `prompts/universal_system_prompt.md` 或附上本仓库链接，输入文字需求或上传图纸照片即可输出符合规范的电气校核与结构化 `circuit_ir.json`。
