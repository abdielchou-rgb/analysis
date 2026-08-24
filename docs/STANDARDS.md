# 2hao 报告标准基线（对标顶级投行/咨询/四大）

> **宪法级文档**。本文件定义 2hao 各类报告必须达到的质量基线。
> 任何配置、门禁、模板**不得低于**本文件标准。
> 详细来源：methodology_registry.yaml（对标投行/咨询/四大结构模式）
>
> **制定背景（2026-08-01 审计）**：发现图表标准系统性降级——listed_company
> 有完整 chart_config（21 图/15 表），但 unlisted/industry/earnings 靠硬编码回退
> （4-5 图），且"对标顶级机构"仅存在于注册表（bluebook 目录未实现）。
> 本文件修复此缺陷：先定标，再让代码对齐。

---

## 一、统一基线（三类报告全部适用）

以下四条是硬底线，任何报告类型不得低于：

### 1. 三表完整性（审计级）
- 报告必须基于利润表、资产负债表、现金流量表**三表完整**的数据
- 任一表缺失 → 报告标注「数据缺口」，门禁不得静默通过
- 禁止只保证利润表（历史教训：balance/cashflow 曾仅 3% 覆盖）

### 2. 证据标注（合规级）
- 每个数据点必须有 A/E/F/B 标注：
  - **A** = Actual（实际值，公司披露/年报）
  - **E** = Estimate（估算值，基于模型/假设）
  - **F** = Forecast（预测值，前瞻判断）
  - **B** = Benchmark（基准值，同业/行业对标）
- 每个数据点必须有来源（公司公告/年报/行业研究/Wind 等）
- 无来源、无标注的数据点 → 门禁失败

### 3. 论证链（结构级）
- 每张图必须挂在至少一个分析论点下（图 → 论点 → 结论）
- 禁止图表堆叠在报告末尾
- 核心判断必须有反方论证 + 概率

### 4. 图表密度（呈现级）
- 行业/上市/非上市 ≥ 1 图/页（20 页报告 ≥ 20 图）
- 门禁可执行下限取「每类报告 min_charts」最小值，但不得低于本表

### 5. 全球视野（结构级，2026-08-01 新增）
- 所有报告类型必须包含全球视角，至少覆盖一类：
  - 全球市场空间/全球对标（industry_deep: global_market_sizing/global_competition）
  - 全球估值锚定/海外收入（listed_company: global_peer_comparison/overseas_revenue）
  - 全球对标/出海路径（unlisted_company: global_benchmark/overseas_expansion）
  - 地缘/汇率风险（三框架通用）
- 缺失全球视野 → IronGate global_perspective 检查 warning（非上市数据有限可豁免）
- 对标顶级机构：投行报告必含全球估值坐标系，缺失即不符合机构级标准

---

## 二、分类型标准

| 类型 | 图表下限 | 表格下限 | 最小字数 | 核心论证链 | 关键图型 |
|------|---------|---------|---------|-----------|---------|
| industry_deep | 12 | 4 | 10000 | 市场规模→驱动→格局→机会 | dual_axis/waterfall/radar |
| listed_company | 12 | 4 | 10000 | 核心分歧→财务→估值→风险 | scatter/waterfall/radar |
| unlisted_company | 8 | 3 | 6000 | 商业模式→增长→竞争→估值 | pie/radar/waterfall |
| earnings_notes | 4 | 2 | 4000 | 业绩→驱动→展望 | bar/line |

> **注意**：listed_company 实际 SAC 配置为 min_charts=15（21 模板），
> 本表 12 是**门禁可执行下限**，不是目标值。目标值以 SAC YAML 完整配置为准。

---

## 三、对标来源（顶级机构模式）

### 投行报告结构（A_国际投行）
- 结构模式：`bb_structure_ib`（P1，待实现 `core/bluebook/structure_patterns/`）
- 关键特征：核心分歧驱动、财务模型支撑、估值区间、催化剂时间线
- 图表范式：DCF 敏感性、估值瀑布、同业散点

### 咨询报告结构（C_战略咨询）
- 结构模式：`bb_structure_consulting`（P1，待实现）
- 关键特征：金字塔原理、MECE 分解、市场规模金字塔、五力
- 图表范式：市场规模趋势、价值链、竞争格局

### 四大会计结构（D_四大会计）
- 结构模式：`bb_structure_big4`（P1，待实现）
- 关键特征：三表审计、数据可追溯、合规合规
- 图表范式：三表趋势、比率分析

> 上述 `bluebook/` 目录当前**未实现**。本标准的"对标"以
> methodology_registry.yaml 注册的来源为权威依据，具体模式落地属后续工作。

---

## 四、执行机制（防降级）

### 4.1 配置即标准
- 每种报告类型的 `chart_config` **必须显式定义**在 SAC YAML 中
- `SACLoader.get_chart_config()` 缺配置时**抛错**（fail-fast），不静默回退
- 违反：配置缺失即管线启动失败

### 4.2 门禁对齐标准
- IronGate 的 `min_charts`/`min_tables` **必须从 SAC 读取**，不硬编码
- 违反：Gate 标准与 SAC 不一致 → 回归测试失败

### 4.3 回归测试锁定
- `tests/test_standards_consistency.py` 断言：
  1. 每类报告 SAC 有 chart_config 且 min_charts ≥ 本表下限
  2. `get_chart_config` 缺配置抛错
  3. IronGate min_charts 与 SAC 一致
  4. chart_pipeline 输出 id 与 SAC chart_config id 对齐（无映射层）
  5. 证据标注要求含 A/E/F/B

---

## 五、质量终判（读者定义）

门禁评分是**代理指标**，不是质量标准本身。真正的质量由读者定义：
- 报告末尾加「读者反馈」区块（论证是否完整/图是否支撑结论/是否敢据此决策）
- 反馈进入 LearningLoop，影响后续写作节奏
- 定期（季度）对照顶级机构真实研报做「圆桌对标」，输出差距报告

---

## 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-01 | 建立统一基线与分类型标准，修复图表标准系统性降级 |
