# 图表优先：把"能配图"变成"必须配图"

## 核心问题

当前，图表生成是 **LLM 的"可选行为"**——LLM 决定要不要调 ChartEngine，所以有的报告 4 张图（x_gs.md）、有的 0 张图（ft.md）。

专业机构的报告（摩根士丹利 pitch book、麦肯锡 deck）的标准是 **每页至少一个数据锚点**，图表不是装饰，是分析的核心载体。

需要把管线从：

```
数据 → LLM 写文字 → (可选) 配图
```

改成：

```
数据 → 确定性的图表规划 → 批量生成所有图表 → LLM 围绕图表写文字
```

---

## 设计：ChartPlanner 模块

### 位置

ChartPlanner 插入在 `KnowledgeOrchestrator.build()` 和 `ArgumentEngine` 之间。

```
KnowledgePackage → ChartPlanner → ChartInventory → ArgumentEngine → LLM → StyleCompiler
                                   (确定性的)               (必须引用图表)
```

### 核心逻辑

ChartPlanner 是一个纯规则引擎。输入是 KnowledgePackage 中的数据，输出是一个 ChartInventory（包含所有已生成的图表文件及其元数据）。

```python
@dataclass
class ChartSpec:
    chart_id: str            # "C1", "C2"...
    chart_type: str          # "line", "bar", "waterfall", "tornado", "heatmap", "pie", "scatter", "radar"
    title: str               # "近5年营收趋势"
    data_sources: list[str]  # 触发这张图的数据点ID
    file_name: str           # "revenue_trend_cicc_line.png"
    section_hint: str        # 建议放在哪个章节
    priority: int            # 1=必须, 2=推荐, 3=可选的

@dataclass
class ChartInventory:
    charts: list[ChartSpec]
    total_count: int
    mandatory_count: int
    summary_text: str  # "本报告包含 7 张图表，涵盖营收趋势、估值对标、敏感性分析..."
```

### 触发规则（核心设计）

每条规则是确定的：**如果数据存在，就生成图表。**

| # | 数据条件 | 图表类型 | 优先 | 说明 |
|---|---------|---------|------|------|
| R1 | 任意财务指标有 3+ 期历史数据 | 折线图 `line` | **必须** | 营收、利润、毛利率等时间序列 |
| R2 | 有可比公司数据（5+ 实体） | 柱状图 `bar` | **必须** | PE、PB、EV/EBITDA 估值对标 |
| R3 | 有营收/利润分解（3+ 组件） | 瀑布图 `waterfall` | 推荐 | 收入拆解、利润 bridge |
| R4 | Conviction Matrix 有 WACC | 龙卷风图 `tornado` | **必须** | WACC ±1% 对估值的影响 |
| R5 | Conviction Matrix 有概率分配 | 叠加柱状图 `stacked_bar` | **必须** | Base/Bull/Bear 三种情景对比 |
| R6 | 有行业对标分布数据 | 箱形图 `box` | 推荐 | 该假设在行业分布中的位置 |
| R7 | 有历史 + 预测数据 | 组合图 `line+bar` | **必须** | 实线是历史，虚线是预测 |
| R8 | 有股权结构/股东分析 | 饼图 `pie` | 推荐 | 股东构成、业务占比 |
| R9 | 有多维评分数据（5+ 维度） | 雷达图 `radar` | 可选 | 综合评分、竞争力对比 |
| R10 | 有 ROE 分解数据 | 瀑布图 `waterfall` | **必须** | DuPont 分解 |

**关键设计原则**：R1, R2, R4, R5, R7 打 **必须** 标签——即这些图在任何专业报告中都不应该缺失。LLM 写文字时**必须引用**这些图。

---

## 需要新增的 Chart Types

ChartEngine 目前有 5 种图 (bar/line/pie/pareto/heatmap)。要覆盖投行标准，需要新增：

| 新增类型 | 工程难度 | 典型用途 | 在投行报告中的出现频率 |
|---------|---------|---------|-------------------|
| **瀑布图 (waterfall)** | 中等 (matplotlib 有现成方案) | 营收 Bridge、利润 Bridge、DuPont 分解 | 极高——几乎每份深度报告都有 |
| **龙卷风图 (tornado)** | 中等 | WACC/增长率敏感性分析 | 高——估值章节标配 |
| **箱形图 (box)** | 低 (matplotlib 内置) | 行业分布、假设对标可视化 | 高——Conviction Matrix 的可视化输出 |
| **雷达图 (radar)** | 低 (matplotlib 有 radar chart) | 多维度竞争评分 | 中——适用于行业深度报告 |
| **散点图 (scatter)** | 低 (matplotlib 内置) | 估值 vs 增长矩阵、风险收益图 | 中——麦肯锡风格常用 |
| **K线图 (candlestick)** | 高 (需要 mplfinance 库) | 股价走势 + 技术分析 | 低——当前版本暂不需要 |

**建议新增顺序**：瀑布图 → 龙卷风图 → 箱形图 → 雷达图 → 散点图。K 线图延后。

---

## 与文字生成的集成方式

这是关键设计决策。图表不是事后再配的，而是文字的核心骨架。

### 方式：ChartInventory 作为 Generation Constraint

ChartPlanner 生成 ChartInventory 后，传给 LLM 的 prompt 中增加一个结构化约束段：

```markdown
## 图表清单（你必须引用以下所有 "必须" 图表）

本报告已预生成 7 张图表，存储在 outputs/charts/ 目录下：

| ID | 类型 | 标题 | 必须引用？ |
|----|------|------|-----------|
| C1 | 折线图 | 近5年营收趋势 (2019-2024) | ✅ 必须 |
| C2 | 折线图 | 毛利率与净利率趋势 | ✅ 必须 |
| C3 | 柱状图 | 同行业可比公司 PE 估值对比 | ✅ 必须 |
| C4 | 龙卷风图 | WACC 敏感性分析 | ✅ 必须 |
| C5 | 叠加柱状图 | Conviction Matrix 概率分配 | ✅ 必须 |
| C6 | 瀑布图 | 利润 Bridge 分析 | 推荐 |
| C7 | 箱形图 | 营收CAGR在行业分布中的位置 | 推荐 |

### 引用规范
- 每个 "必须" 图表在正文中至少被引用一次
- 引用格式: ![C1: 近5年营收趋势](outputs/charts/revenue_trend_cicc_line.png)
- 引用的上下文中必须包含对该图表的分析（不只是 "见下图"）
```

这样设计有三个好处：
1. **LLM 没有选择权**——不能跳过必须的图表
2. **LLM 有自由度**——可以决定图表出现的顺序和上下文
3. **可追溯**——每张图的触发条件都是确定的，不会因为 LLM 的随机性而缺失

---

## 落地步骤

### 阶段 1：ChartPlanner 框架（3-4 天）

```python
class ChartPlanner:
    def __init__(self, chart_engine: ChartEngine):
        self.engine = chart_engine
        self.rules = self._register_rules()
    
    def _register_rules(self) -> list[ChartRule]:
        return [
            TimeSeriesRule(priority=1),        # R1: 3+ period → line
            PeerComparisonRule(priority=1),    # R2: 5+ peers → bar
            WaterfallBridgeRule(priority=2),   # R3: bridge data → waterfall
            TornadoSensitivityRule(priority=1),# R4: WACC → tornado
            ConvictionStackRule(priority=1),   # R5: probability → stacked bar
            IndustryDistributionRule(priority=2), # R6: benchmark → box
            ForecastHistoryRule(priority=1),   # R7: actual + forecast → combo
            ... 
        ]
    
    def plan(self, kp: KnowledgePackage) -> ChartInventory:
        specs = []
        for rule in self.rules:
            spec = rule.evaluate(kp)
            if spec:
                # 生成图表文件
                self.engine.generate(spec)
                specs.append(spec)
        return ChartInventory(charts=specs)
```

### 阶段 2：新增 3 个 Chart Types（2-3 天）

瀑布图、龙卷风图、箱形图——这三个覆盖了投行报告 90% 的常见图表需求。

### 阶段 3：集成到 Workflow（1 天）

在 `workflow.run()` 中插入 ChartPlanner 调用：

```python
def run(self, brief):
    kp = self.t0(brief)         # 数据收集
    kp = self.t1(kp)            # KnowledgeOrchestrator
    # ★ NEW：图表规划和生成
    chart_inventory = self.chart_planner.plan(kp)
    kp.chart_inventory = chart_inventory
    # 继续管线
    scaffold = self.t2a(kp)     # ArgumentEngine（知道有哪些图可用）
    report = self.llm(kp, scaffold, chart_inventory)  # LLM 必须引用图表
    report = self.style(report) # StyleCompiler
    return report
```

### 阶段 4：回测报告生产（3-5 天，可选并行）

选择 20 家覆盖不同行业的公司，生成完整报告 + 图表集，然后：
- 盲测：混入真实研报让分析师评
- 回测：6 个月后对比 Conviction Matrix 预测 vs 实际走势
- 产出第一份 **Prediction Audit Report**

---

## 对现有代码的改动范围

| 文件 | 改动 | 规模 |
|------|------|------|
| `core/chart_engine.py` | 新增 waterfall/tornado/box chart 方法 | +150 行 |
| `utils/chart_planner.py` | **新文件**：ChartPlanner + 10 条规则 | +300 行 |
| `core/models.py` | 新增 ChartSpec / ChartInventory dataclass | +30 行 |
| `workflow.py` | 在 KnowledgeOrchestrator 后插入 ChartPlanner | +10 行 |
| LLM prompt template | 增加 ChartInventory 约束段 | +20 行 |

**总计：约 500 行新代码，不修改任何现有逻辑。** 这是纯加法架构，风险极低。

---

## 一句话

> **当前系统的图表问题是"能做但不一定做"。改成"必须做且做完再写文字"——用 10 条确定性规则保证每份报告至少 5 张必须图，把 ChartEngine 的利用率从"LLM 看心情"提到 100%。这事做完，1 号分析师的输出才真正像一份机构级报告。**
