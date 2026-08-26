# Brainstorm & Convergence：五大机构合伙人的建议与我自己的思考

## 一、完整脑暴：每个人的建议映射到具体动作

这是从圆桌讨论中提取的**所有可执行的建议**，按角色归类，我不做筛选——先全部摊开。

### 摩根士丹利合伙人（P1）

| 建议 | 具体动作 | 解决什么问题 |
|------|---------|------------|
| A1 | 在 Conviction Matrix 每个假设旁标注数据时效性（"此数据基于2019-2023年模型"） | 信任——client-facing 时的免责 |
| A2 | 接入实时市场 WACC/利率数据校准当前假设 | 数据相关性——用历史数据做当前决策的逻辑漏洞 |
| A3 | 叙事线优化：学会"省略"而非全部展示 | Double-blind——MD 和 junior 的区别在取舍 |
| A4 | Conviction Matrix 输出包含"该假设有多少个样本支持" | 透明度——让使用者自己判断可信度 |

### 麦肯锡全球合伙人（P2）

| 建议 | 具体动作 | 解决什么问题 |
|------|---------|------------|
| B1 | 在每个数据点后加 So What -> Now What 链 | 洞见层——从百分位到可执行判断 |
| B2 | 置信度分级从 3 级扩展到 5 级+归因文本 | 诚实度——标注"为什么我自信/不自信" |
| B3 | 假设敏感性分析（WACC ±1% → 估值变多少） | 分析深度——投行和咨询的标准输出 |
| B4 | 归因分析模块：为什么营收假设处于 P85？ | 分析原创性——不只是报告位置，要解释原因 |

### 中金研究部执行总经理（P3）

| 建议 | 具体动作 | 解决什么问题 |
|------|---------|------------|
| C1 | StyleProfile 增加 writing_dna 可配置层 | 风格识别度——每家券商有自己的表达习惯 |
| C2 | P0 指纹检测集成到合规检查流程 | 合规——在发布前自动检测"AI腔" |
| C3 | 多机构风格 benchmark 库（中金/中信/华泰各一份基线） | 风格差异化——系统的输出不能是平均风格 |
| C4 | 报告 draft 痕迹模拟（不完美的句式、不对称结构） | Double-blind——真实报告不完美 |

### 德勤审计合伙人（P4）

| 建议 | 具体动作 | 解决什么问题 |
|------|---------|------------|
| D1 | 数据血统完整记录：来源文件/MD5/sheet/单元格/提取时间 | 可追溯性——审计的基本要求 |
| D2 | 每条数据带置信度评分 + 评分标准说明 | 可信度——使用者可以判断数据质量 |
| D3 | 模板数据污染自动检测脚本 | 数据质量——防止 batch_extract 读错单元格 |
| D4 | 数据过期检测：超过 6 个月的估值模型自动标记 | 数据新鲜度——静态数据的风险 |

### 讨论中出现的交叉主题（不归属于单个人）

| 建议 | 来自 | 具体动作 |
|------|------|---------|
| E1 | 全组共识 | 输出格式从"数据报告"改为"带有置信度标注的分析报告" |
| E2 | P1+P4 | 数据新鲜度水印：每个假设标注样本期和当前环境差异 |
| E3 | P2+P3 | So What 层可配置化：不同机构要不同的洞见风格 |
| E4 | P2+P4 | 假设敏感度 + 可追溯性合并：每个假设都来自具体文件 |

---

## 二、收敛：我的选择逻辑

**16 个建议不能全部做。** 我的收敛依据是三个条件：

> 1. **跨 stakeholder 穿透力** —— 一个改变是否能同时服务多个角色的核心关切？（不做单点改进）
> 2. **在当前架构上的可执行性** —— 是纯工程问题还是需要新 AI 能力？（优先做工程可解的）
> 3. **对信任曲线的提升斜率** —— 做完之后，是否能改变"不敢发给客户"这个结论？

基于这三个条件，我筛出了 **3 个最高杠杆的建议**。

### 为什么放弃其他 13 个

| 建议 | 放弃原因 |
|------|---------|
| A2 实时 WACC 校准 | 边际收益递减 —— Layer 4 已接入 akshare，再多一个数据源不改变系统的信任问题。当前瓶颈在"标注", 不在"接入" |
| A3 叙事线优化 | 需要真正的 NLG 能力提升，不是纯工程问题。当前阶段的投入产出比不如其他 3 个 |
| B3 敏感性分析 | 高价值但工程量大，且依赖 So What 层先建好。可以排到第二批 |
| B4 归因分析 | 与 So What 层重叠 —— 归因是 So What 的一种形式，可以合并 |
| C2 P0 合规集成 | 可以快速做但属于防御性功能，不提升系统上限。场景价值：让合规部放心，而非让客户满意 |
| C3 多机构风格 benchmark | 前提是 C1 先完成 —— 没有写作 DNA 框架就无法录风格数据 |
| C4 Draft 痕迹模拟 | 属于"锦上添花"而非"必须"。FP4 要过双盲测试靠的是思想质量而非表面不完美 |
| D3 模板检测脚本 | 是 bug fix 而非功能提升。可以在 batch_extract.py 中加一个 flag 解决 |
| D4 数据过期检测 | 依赖 D1 先完成 —— 没有时间戳就无法检测过期 |

### 我选择的三个

| 优先级 | 建议 | 覆盖的 Stakeholder | 工程性质 | 信任提升 |
|--------|------|-------------------|---------|---------|
| **P0** | 数据血统 + 置信度感知输出 (D1+B2+A4) | P4(审计) + P1(信任) + P2(诚实) | ✅ 纯工程 | 从"查无来历"到"每个数据都可追溯" |
| **P1** | 风格 DNA 可配置化 (C1+A3+E3) | P3(身份) + P1(声音) + P2(风格) | ✅ 纯工程 | 从"平均风格"到"像我们团队写的" |
| **P2** | So What -> Now What 层 (B1+B4+A3) | P2(洞见) + P1(叙事) | ⚠️ 部分需 LLM | 从"告诉客户位置"到"告诉客户怎么办" |

---

## 三、详细方案

### P0：数据血统 + 置信度感知输出

**问题**：P4 说"不可追溯的数据等于不存在"。P1 说"53 个数据点说服力不够"。这两个问题的根因相同——**系统不知道自己的数据从哪里来、有多可信，也不告诉使用者**。

**方案**：

**阶段 1：改造 assumption_db.json（1-2 天）**
每条记录增加血统字段：
```json
{
  "file": "万科A财务预测估值模型.xlsx",
  "company": "万科A",
  "industry": "地产",
  "wacc": 0.08,
  "wacc_provenance": {
    "sheet": "DCF",
    "cell": "G7",
    "label": "加权平均资本成本（WACC）",
    "extracted_at": "2026-07-26T10:30:00",
    "confidence": "high",
    "note": "直接从 DCF sheet 读取"
  },
  "terminal_growth": -0.005,
  "terminal_growth_provenance": {
    "sheet": "DCF",
    "cell": "H58",
    "label": "永续增长率",
    "extracted_at": "2026-07-26T10:30:00",
    "confidence": "low",
    "note": "值为负，可能为模板填充数据"
  }
}
```

**阶段 2：Conviction Matrix 输出改版（1 天）**
当前：
```python
{"base": 0.55, "bull": 0.20, "bear": 0.25, "calibration_log": [...]}
```
改版后：
```python
{
    "base": 0.55,
    "bull": 0.20,
    "bear": 0.25,
    "calibration_log": [...],
    "data_confidence": {
        "level": "medium",
        "sample_size": 53,
        "data_period": "2018-2023",
        "staleness_warning": "数据源为历史估值模型，可能不反映当前利率环境",
        "source": "130家估值模型批量提取 (2026-07)",
    },
    "assumptions": [
        {
            "metric": "revenue_cagr_3y",
            "value": 0.30,
            "percentile": 0.85,
            "judgment": "偏乐观",
            "supporting_data": {
                "industry_distribution": {"mean": 0.20, "p50": 0.18, "p75": 0.25},
                "n_models": 12,
                "data_freshness": "2019-2023",
            },
        }
    ],
}
```

**工作量**：2-3 天。纯 Python 工程，不涉及模型。

---

### P1：风格 DNA 可配置化

**问题**：P3 说系统写得太像"其他人"了——不是不好，是没有识别度。P1 说 MD 和 junior 的区别在取舍——但当前系统没有"声音选择"。

**方案**：

在现有的 StyleProfile（管理图表配色/排版）中增加 writing_dna 层：

```yaml
# 机构风格 DNA profile 示例：中金标准版
writing_dna:
  # 判断词倾向
  judgment_verbs:
    primary: "我们认为"        # 中金偏好
    secondary: "我们判断"
    frequency: 0.7            # 每段出现的概率
  
  # 句子长度偏好
  sentence_length:
    target_mean: 35           # 中金报告的字数习惯
    variance: 0.15
  
  # 第一人称使用
  first_person:
    we_frequency: 0.8         # "我们"的使用频率
    passive_allowed: false
  
  # P0 容忍度
  p0_tolerance: 0.0           # 中金合规要求：零容忍
  
  # 段首模式
  paragraph_start:
    preferred: ["我们认为", "从基本面看", "综合来看"]
    avoid: ["值得注意的是", "综上所述"]
  
  # 数据引用格式
  data_citation:
    style: "inline"           # 中金习惯：在正文中引用 "据 Wind 数据"
    template: "据{source}数据，{value}"
  
  # 不确定性表述
  uncertainty:
    preferred: ["我们预计", "大概率"]
    avoid: ["可能", "不排除"]  # 中金上级偏好更确定的表述
  
  # 省略倾向
  omission:
    low_confidence_threshold: 0.3  # 置信度低于 30% 的数据不展示
    max_metrics_per_section: 5     # 每节不超过 5 个指标（模拟 MD 的选择力）
```

**使用方式**：
```python
# 在 workflow 中
brief.style_profile = "cicc_standard"  # 加载中金风格
# 或在命令行
--style cicc_standard
```

**工作量**：3-5 天。需要：
1. 设计 writing_dna schema
2. 修改 StyleProfile dataclass
3. 写一个 StyleCompiler 的 writing_dna 执行器（在生成报告时应用规则）
4. 为 3-5 家机构创建初始 profile
5. 不需要模型——全部是硬编码规则 + 字符串替换

**为什么这是 P1 不是 P2**：因为它解决了一个比 So What 层更基础的问题——**在过双盲测试之前，先确保系统有自己的声音。** P3 的评分从 5/10 跳到 7/10 只需要这一个改变。

---

### P2：So What -> Now What 层

**问题**：P2 说当前输出可以告诉你"这个假设在 P85"，但不告诉你这意味着什么。在投行和咨询语境下，一个发现如果没有 So What 和 Now What，就等于没有发现。

**方案**：

在 Conviction Matrix 和 Argument Engine 之间插入一个 InsightCompiler 模块：

```python
class InsightCompiler:
    """将数据信号转化为可执行的判断"""
    
    def compile(self, conviction: ConvictionMatrix, 
                benchmark_results: list[BenchmarkResult],
                kp: KnowledgePackage) -> list[Insight]:
        insights = []
        
        # 规则 1: 如果营收假设偏保守且 beta 偏高 -> 市场低估风险
        if conviction.revenue_assumption == "conservative" and conviction.beta > 1.2:
            insights.append(Insight(
                type="risk_mispricing",
                signal="营收假设偏保守 + 高风险 Beta",
                so_what="市场可能高估了公司的周期性风险",
                now_what="建议检查市场定价是否已充分反映保守预期",
                confidence="medium",
                data_support=[benchmark_results[0], benchmark_results[3]]
            ))
        
        # 规则 2: 如果 WACC 显著高于行业 -> 需要解释资本成本溢价
        if conviction.wacc_percentile > 0.75:
            insights.append(Insight(type="capital_cost_gap", ...))
        
        # 规则 3: 如果一致预期偏离度大 -> 这是一个 alpha 信号
        if conviction.consensus_gap > 0.15:
            insights.append(Insight(type="consensus_divergence", ...))
        
        return insights
```

**关键设计原则**：Insight 不是 LLM 生成的自由文本，而是**规则引擎 + 模板填充**。原因：
1. 可预测性（同样的数据产生同样的 insight）
2. 可追溯性（每个 insight 可以追溯到触发它的规则）
3. 可测试性（可以写 unit test: "当 WACC > 行业 P75 时，是否生成 capital_cost_gap insight？"）

**工作量**：2-3 周。比前两个大，因为需要设计 insight rules 库（初始 15-20 条规则），且需要与 ArgumentEngine 集成。

---

## 四、三个建议的交互逻辑

```
P0: 数据血统 + 置信度
    │
    │ (为每个数据点提供可信度和来源)
    ▼
P2: So What -> Now What
    │
    │ (InsightCompiler 的判别质量取决于输入数据的置信度)
    │  当置信度"low" 时→ So What 应更谨慎
    │  当置信度"high" 时→ So What 可以更确定
    ▼
P1: 风格 DNA
    │
    │ (So What 的输出需要按机构风格调整表达方式)
    │  中金版本: "我们认为该假设偏保守..."
    │  高盛版本: "We view this assumption as conservative..."
    ▼
输出: 可追溯 + 有洞见 + 有身份的机构级报告
```

**这是一个三角验证关系**：没有 P0，P2 的可信度不可验证；没有 P2，P1 的表达缺乏内容支撑；没有 P1，P0 和 P2 的输出没有人味。

---

## 五、执行顺序

| 周次 | 工作 | 依赖 |
|------|------|------|
| Week 1 | P0 阶段 1: 改造 batch_extract.py + assumption_db.json | 无 |
| Week 2 | P0 阶段 2: Conviction Matrix 输出改版 | 阶段 1 |
| Week 3 | P1: 设计 writing_dna schema + 创建 3 个初始 profile | 无（可并行） |
| Week 3-4 | P2: InsightCompiler MVP（10 条核心规则） | P0 阶段 1 |
| Week 5 | P2 + P1 集成：Insight 按机构风格输出 | P1 + P2 |
| Week 6 | 集成测试 + 内部评估 | 全部 |

---

## 六、我的思考过程——为什么这样选

如果你问我怎么想的，上面的推导过程可以总结成一句话：

**我选择的是"每个杠杆至少撬动两个角色"的改变。**

具体来说：

**我放弃了对单个角色最优但对系统边际收益递减的建议。** 比如 P4 的"完整审计框架配套"——如果单独做，审计合伙人会满意，但不影响 P1 和 P2 对系统的评价。而"数据血统 + 置信度感知输出"这个合并项同时服务了 P4（审计）和 P1（信任）和 P2（诚实假设），一个改变撬动三个角色。

**我优先选了工程可解 > AI 可解的。** P2 的 So What 层虽然最有价值，但它部分依赖 LLM，执行不确定。而 P0 和 P1 完全是硬编码规则 + 配置化，写对了就永远对。这三者的组合是：先做确定性的（P0+P1），再做需要判断力的（P2）。

**我对"风格 DNA"的定位可能和 P3 不一样。** P3 把它看作合规和身份的防御性需求。我把它看作 FP4 过双盲测试的攻击性手段。当前系统的问题不是写得不准确——**它写得很好，但好得太平均了。** 真实分析师的水平不在"平均分高"，而在"有自己的偏好和取舍"。风格 DNA 不是表面工程，它是 FP4 的核心基础设施。

**最后，这三件事的顺序本身就是 FP1 的体现。** P0 是对客户说"我知道我知道什么"，P1 是对客户说"我知道我是谁"，P2 是对客户说"我知道你需要什么"。这三层合在一起，才是"客户是人"的真正含义——不是把报告写得像人写的，而是**把输出组织成一个人可以信任、可以依赖、可以做决策的东西**。
