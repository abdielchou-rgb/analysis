# V51 架构总案（最终版）

> **版本**: V51.0 | **日期**: 2026-07-24  
> **定位**: 1号分析师 · 智能化顶级分析师写作系统  
> **核心理念**: 从"AI 生成报告"转向"人机协作写作——分析师提供判断和数据，系统提供知识编排和写作执行"

---

## 第一部分：架构哲学

### 三条铁律

1. **报告必须像人写的，没有任何 AI 痕迹。** 不标注 AI 参与、不出现内部方法论术语、不暴露"系统是如何工作的"。Style Compiler 和 AI 污染圆桌审计共同保证这一条。

2. **计算层不参与生成，生成层不参与计算。** 计算引擎全部是确定性 Python 代码，零 LLM 参与。行文引擎只能引用计算结果，不能修改。数值门禁检查一致性。这条来自 V30 并保持。

3. **方法论文档是可验证的执行契约，不是可选的 Prompt。** SAC（结构化分析契约）用 YAML 编写，被确定性代码检查是否遵守。LLM 不能绕过 SAC——检查门在 LLM 输出之后，不是之前。

### 版本哲学

**V51 是当前活跃版本。** V30-V34 封存（计算代码已桥接）、V50 封存（架构设计原型已合并）。

方法论升级用 sub-version（V51.1、V51.2），功能增强用 feature flag。架构级变化才升主版本号。

---

## 第二部分：架构骨架（T0 → T1 → T2 → T3）

```
T0 分析师输入接口
│  输入：写作意图 + 素材 + 风格偏好
│  输出：Writing Brief（结构化写作简报）
↓
T1 知识层
│  五个子模块：数据引擎 + 计算引擎 + 方法论体系 + Bluebook + 风格指南
│  输出：Knowledge Package（结构化知识包）
↓
T2 写作引擎
│  三阶段：谋篇 → 行文 → 精修
│  输出：Writing Scaffold → Draft → Final
↓
T3 验证与交付层
│  三个门 + 两个附件 + 导出器
│  输出：正式报告 + 圆桌审计附件 + 版本记录
```

---

## 第三部分：各层详细设计

### T0 分析师输入接口

**三种输入模式**：

| 模式 | 输入形式 | 场景 |
|------|---------|------|
| A（结构化） | "帮我写茅台业绩点评，核心判断是 i茅台直销占比超预期，风格中金" | 分析师明确知道自己的判断 |
| B（素材驱动） | 分析师发来 Excel + 语音笔记："渠道调研数据在这里，我的判断是..." | 有素材但未结构化 |
| C（兜底） | "分析一下贵州茅台" | 不知道要写什么，先做一个全量分析再聚焦 |

**设计原则**：
- 系统主动引导从 C→A，不把 C 作为默认
- 每次交互都是 Writing Brief 的逐步精化，不是跳过
- 每一次确认（Writing Brief / Writing Scaffold / 最终稿）都有"分析师签署"节点

**输出：Writing Brief**

```yaml
asset: "贵州茅台 600519.SH"
report_type: "earnings_notes"    # 非抽象标签，对应特定 SAC
core_thesis:
  direction: "bull"               # bull / bear / neutral
  point: "i茅台直销渠道改革超预期"
  market_consensus: "直销占比45%后趋于稳定"
  our_view: "可突破50%"
  key_variable: "i茅台GMV增速和渠道效率"
  time_window: "12个月"
required_sections:
  - "渠道变化深度分析"
  - "产品结构与价格体系"
  - "盈利预测调整"
  - "估值与情景"
emphasis: ["直销占比", "茅台1935增长", "五粮价差变化"]
style_profile: "cicc"
source_materials: ["channel_deck.xlsx"]
analyst_signature: "待确认"        # 分析师签署节点
```

---

### T1 知识层

**五个子模块**：

#### ① 数据引擎

| 数据源 | 状态 | 用途 |
|--------|------|------|
| akshare 财务数据管线 | ✅ V30 继承 | A 股/港股基础财报 |
| 一致预期（akshare stock_profit_forecast） | ✅ V50 P0 | EPS/营收一致预期 |
| 天眼查（tyc-it CLI，162 工具） | ✅ 非上市企业 | 工商信息/股权穿透/风险/关联方 |
| 行业数据（库存周期/价格指数） | 🔄 V50 P1 | 行业深度分析的供需判断 |
| 业绩会 Transcript | 🔄 V50 P2 | 管理层语气/前瞻信号 |

#### ② 计算引擎（全部确定性 Python 代码）

| 计算模型 | 状态 | 来源 |
|---------|------|------|
| 收入桥（总量→分部级） | ✅ P0 分部级 | V30 L2 + V50 升级 |
| 毛利桥 | ✅ | V30 L2 |
| 费用桥 | ✅ | V30 L2 |
| 利润质量（归母/扣非/现金流三重） | ✅ | V30 L2 |
| 营运资本与现金转换 | ✅ | V30 L2 |
| 现金流联动分析 | ✅ | V30 L2 |
| ROE/ROIC 杜邦分解 | ✅ | V30 L2 |
| 同业对标（≥5 家多维比较） | ✅ P0 | V30 L2 + V50 升级 |
| 三闸门（DuPont+Jones+MScore） | ✅ P0 | 从 V34 迁移 |
| DCF 估值 | ✅ P0 | V30 L2 + V50 完善（WACC/beta 透明） |
| 情景分析（Bull/Base/Bear） | ✅ P0 | V50 新增 |
| 隐含增长率反推 | 🔄 P2 | 当前PE隐含什么增长预期 |

#### ③ 方法论体系（SAC 注册表）

**方法论注册表数据结构**：

```yaml
methodology_registry:
  - id: sac_earnings_notes
    name: 上市公司财报点评
    v24_source: writer_agent public_company 框架
    v50_sac: ✅ active
    priority: P0
    
  - id: sac_industry_deep
    name: 行业深度研究
    v24_source: researcher_agent 11维框架
    v50_sac: ✅ active（融合 Serenity 9步工作流）
    priority: P0
    
  - id: sac_unlisted_company
    name: 非上市企业分析
    v24_source: writer_agent 8层框架
    v50_sac: ✅ active（已重建）
    priority: P0
    
  - id: sac_listed_company
    name: 上市公司深度分析
    v24_source: writer_agent + financial_analyst 整合
    v50_sac: ✅ active
    priority: P0
    
  - id: sac_ipo_analysis
    name: IPO 分析
    v24_source: 四大范式
    v50_sac: 🔄 P1
    priority: P1
    
  - id: sac_event_review
    name: 事件/暴雷复盘
    v24_source: 财经媒体范式
    v50_sac: 🔄 P1
    priority: P1
```

**每个 SAC 的结构**（YAML）：

```yaml
id: sac_industry_deep
name: 行业深度研究
applies_to: ["industry"]

# 谋篇阶段的强制前置工作流（融合 Serenity 9步法）
pre_workflow:
  - step: "需求翻译"        # 把主题转化为系统变化
  - step: "价值链图谱"       # 8层价值链
  - step: "稀缺层定位"       # 找到真正的瓶颈/卡点
  - step: "Bold Call 生成"  # 基于稀缺层而非基于模板

# 行业分析的必须回答维度（11维框架，但报告不暴露这个编号）
required_dimensions:
  - id: "bold_call"
    question: "这个行业当前最重要的超额回报来源是什么？"
    evidence_min: 3
    
  - id: "core_disagreement"
    question: "市场共识是什么？分歧的核心变量在哪？"
    position: "page_2"          # 第二页强制
    
  - id: "profit_pool"
    question: "利润现在在哪？怎么流动？谁的议价权在变？"
    evidence_min: 3
    required_elements: ["产业链", "利润", "毛利率"]
    counter_evidence: true
    
  - id: "competitive_landscape"
    question: "赢家为什么能赢？什么因素能改变这个格局？"
    
  - id: "technology_route"
    question: "技术路线的确定性有多高？"

# 检查清单（行文后验证）
verification:
  min_sources: 8
  min_citations: 6
  counter_evidence_required: true
  forbidden_patterns: ["SAC", "11维", "范式路由", "Writing Scaffold"]
```

#### ④ Bluebook 模式库

从 D:\深度研究报告原始文档 中提取的模式，Phase 1 启动：

```
bluebook/
  index.yaml              # 检索索引（按机构/报告类型/模式类型）
  structure_patterns/     # 每类报告的章节结构模式
  thinking_patterns/      # 推理链模式（高盛怎么论证、麦肯锡怎么展开）
  writing_patterns/       # 写作模式（句法偏好、关键词使用）
  data_patterns/          # 数据模式（图表类型选择、数据呈现方式）
  expression_dna/         # 表达 DNA 库——见下文
```

#### ⑤ 风格指南库（V50 新增——从 muxuu 获得的关键启发）

**不仅是一本 styleguide——是机构级别的表达 DNA 库。**

从 D:\深度研究报告原始文档 中提取每个机构的写作特征，量化为可执行的配置文件：

```yaml
# styles/goldman_sachs.yaml
name: "Goldman Sachs"
colors:
  primary: "#051C2C"
  accent: "#009688"
charts:
  preferred_types: ["waterfall", "scatter", "bar_cluster"]
writing:
  conclusion_first: true
  sentence_length_avg: 28
  judgment_density: 2.3_per_100_words  # 每100字判断句数
  signature_terms: ["we believe", "our analysis suggests", "key risk"]
  forbidden_terms: ["arguably", "it is worth noting", "notably"]
  citation_style: "footnote_numbered"
expression_dna:
  source: "D:\\深度研究报告原始文档\\A_国际投行\\高盛"
  sample_size: 15
  extracted_features:
    paragraph_length_distribution: [mean: 4.2_sentences, std: 1.8]
    verb_preference: ["suggest", "indicate", "support", "challenge"]
    hedge_word_frequency: 0.08_per_sentence
```

**执行方式**：T2 行文引擎在写作时读取对应的 style_profile。T3 Turing Gate 检查输出与 style_profile 的偏差。

---

### T2 写作引擎（三阶段）

#### 阶段 1：谋篇——设计论证结构（不写文字）

**输入**: Writing Brief + Knowledge Package  
**输出**: Writing Scaffold（分析师确认）

**工作流程**：

```
1. 判断形态（muxuu 启发）
   → 如果适合 "发现型" 分析（行业/主题），先跑 Serenity 9步工作流
   → 如果适合 "覆盖型" 分析（公司/财报），直接进入 11维/8阶框架

2. 确定反方（反确认偏误设计）
   → 先确定 bear case，再确定 bull case
   → "核心分歧"锁定——市场认为X，我们认为Y

3. 选择结构
   → 根据 report_type + style_profile + Bluebook pattern 选择
   → 11维/8阶作为必须检查清单，不作为目录结构

4. 匹配证据
   → 来自 Knowledge Package 的数据
   → 标记数据缺口（显性化，"待补充"而非编造）

5. 生成 Writing Scaffold
```

**Writing Scaffold 结构**（不再暴露任何方法论标签）：

```json
{
  "report_structure": [
    {
      "section": "核心分歧",                // 第二页，不是第一章
      "claim": "市场认为直销占比45%后趋于稳定，但我们认为可突破50%",
      "counter": "直销占比提升边际递减是合理的——问题在于速度而非方向",
      "evidence": ["2024H1直销占比42%", "i茅台GMV同比+35%"],
      "data_gaps": ["渠道库存精确数据（未公开，以估计值标注）"]
    },
    {
      "section": "i茅台渠道改革的真实影响",
      "claim": "i茅台不仅是渠道——是数据能力和消费者直连",
      "sub_points": [
        "非标产品投放能力提升均价",
        "消费者数据反哺产品规划",
        "渠道管理半径从经销商转向直营"
      ]
    },
    {
      "section": "产品结构升级的空间和边界"
    },
    {
      "section": "估值：当前价格隐含了什么预期",
      "has_alternative_view": true
    }
  ]
}
```

**设计原则**：
- 分析师必须确认 Writing Scaffold 后才能进入行文
- Writing Scaffold 中不出现 "SAC" "11维" "范式" 等内部术语
- "核心分歧"在第二页，不在最后一章

#### 阶段 2：行文——逐节生成

**输入**: Writing Scaffold + Knowledge Package + Style Profile  
**输出**: 初稿

**关键约束**：
1. 逐节生成，每节独立 LLM 调用，上下文锚点连接
2. 判断句→证据的顺序（不是证据罗列→结论）
3. 数据缺口显性化（"此项数据未公开"而不是 LLM 编造）
4. SAC 维度覆盖检查（在行文阶段不暴露 SAC，但后台记录哪些维度已被覆盖）
5. Style Profile 约束（句式、词汇、语气）
6. **报告结构不暴露 11 维/8 阶**（muxuu 启发的核心原则）

**证据标注**（在 T2 阶段就要做，不是到 T3 才补）：
- 数字后跟随来源类型，不打断阅读
- 不暴露 L1-L7 标签，用自然语言标注：
  - `2024H1 直销占比 42%（年报数据）` ✅
  - `渠道库存约 X 亿元（L5 数据库来源，待交叉验证）` ❌

#### 阶段 3：精修——分类修改引擎

**六种"不对"类型**：

| 类型 | 修改策略 | Phase |
|------|---------|-------|
| 数据错误 | 定位数字→查数据源→替换→来源标注 | P0 |
| 方向错误 | 定位判断句→翻转结论→替换论据→重组织 | P0 |
| 语气/风格 | 定位措辞→用 style_profile 调整→替换 | P0 |
| 逻辑跳跃 | 定位逻辑断裂→生成中间推理→插入 | P1 |
| 结构不当 | 定位段落→移动→调整过渡句 | P1 |
| 遗漏 | 定位相关章节→生成缺失段落→插入 | P1 |

**Phase 0 交互**：分析师从下拉菜单选择类型 + 自由输入修改指令 + 系统定位到文本位置。每次修改记录在版本记录中，确保反馈持久性。

---

### T3 验证与交付层

#### 门 1：方法论门禁（SAC Gate）

- 检查报告是否覆盖了对应 SAC 的全部 required_dimensions
- 检查 evidence 数量和等级分布
- 检查 counter_evidence 的强制要求
- **检查禁止项**：内部方法论术语（"SAC""Writing Scaffold""范式路由"等）和 AI 痕迹
- **实现**：确定性 Python 代码（字符串匹配+正则+NER），不是 LLM 判断
- **阻断条件**：缺少 P0 维度或产生禁止项 → 阻断返回 T2

#### 门 2：Turing Gate

检查报告是否"像人写的"，五项检测：

| 检测项 | 方法 | 阈值 |
|--------|------|------|
| 句式检查 | AI 套话模式匹配（"值得注意的是""不可否认的是"） | ≤2 次 |
| 判断密度 | 每 100 字判断句数（AlphaWise 标准） | ≥1.0 |
| 句式多样性 | 段落结构变化检测 | 连续 3 段同构→告警 |
| 情感节奏 | 全文情感熵（过于平滑→AI 特征） | ≥阈值 |
| 风格偏差 | 与 style_profile 的特征向量距离 | ≤阈值 |

- **实现**：NLP 特征检测，不需要 LLM 判断
- **阻断条件**：不阻断交付，结果传递到圆桌审计作为输入

#### 门 3：版本记录

- 每次生成、每次修改、每次确认 → 不可篡改的版本记录
- 每个判断句的输入来源（L2 计算/分析师输入/LLM 推测）
- 记录 "修改前 → 修改后" 的 diff，建立反馈持久性

#### 图表引擎

从 D:\深度研究报告原始文档 提取的机构图表规范：

```yaml
styles/goldman_sachs.yaml
styles/morgan_stanley.yaml
styles/mckinsey.yaml
styles/cicc.yaml
styles/citic.yaml
```

每个风格包含：色板、字体层级、图表类型偏好、数据-墨水比参数、水印/脚注格式。

图表与数据绑定规则：
- 收入桥 → Waterfall 图（高盛标准配色）
- 毛利率趋势 → Stacked Bar + 趋势线
- 估值矩阵 → Scatter Plot
- 同业对标 → Radar / 多维 Bar
- 供需平衡 → 双轴折线

密度标准：行业深度 ≥ 1.2 张图表/页；公司分析 ≥ 0.8 张图表/页

#### 多格式导出器

默认全量生成所有格式：

| 格式 | 用途 | 技术栈 |
|------|------|--------|
| .md | 初稿/可继续修改的工作版本 | python-markdown |
| .docx | 正式正文 | python-docx + 机构模板 |
| .pptx | 路演稿 | python-pptx + 机构配色 |
| .pdf | 格式锁定版本 | 通过 docx 转换 |
| .html | 可交互版本 | Jinja2 模板 |
| .xlsx | 数据包（财务数据+估值表） | openpyxl |

#### AI 污染圆桌审计（独立附件）

**不阻断交付**，**不进入主报告**，每份报告输出一个独立附件。

**六位虚拟评审**：

| 评审 | 打分范围 | 审查重点 |
|------|---------|---------|
| 合规审查官 | 0-100 | 措辞、免责声明、数据可追溯 |
| 资深卖方分析师 | 0-100 | Bold Call 锐利度、论证扎实度 |
| 买方研究员 | 0-100 | 值不值得花 20 分钟读 |
| AI 审计师 | 0-100 | AI 腔、过度平滑、句式多样性 |
| 反方辩护人 | 0-100 | 最薄弱环节、空头攻击点 |
| 文体学家 | 0-100 | 语言力度、读者体验、节奏 |

**测试用例库**（V50-P1 建设）：

```
tests/
  functional/
    known-cases/        # 5+ 标杆案例的还原度测试
    edge-cases/         # 5+ 非典型场景的合理性测试
  style/
    voice-checks/       # 10+ 风格一致性测试
    contamination/      # AI 痕迹检测测试
```

每个测试用例定义：输入 → 预期输出特征 → 通过条件。

---

## 第四部分：与 muxuu 生态的融合点

| muxuu 能力 | V50 融合方式 | 状态 |
|-----------|------------|------|
| Serenity 9步工作流 | T2 谋篇阶段的"发现引擎"——先跑工作流找稀缺层，再用框架覆盖完整性 | ✅ P0 整合 |
| 证据阶梯 3级+NeedsChecking | T1 证据标记增加"待核实"独立状态标签 | ✅ P0 整合 |
| 风格指南 + 中文表达规范 | T1 新增风格指南库模块，从 D:\深度研究报告原始文档 提取 | ✅ P0 启动 |
| 表达 DNA 调研方法 | T1 Bluebook 中建立 expression_dna/ 目录，用 6 维度调研法提取机构特征 | 🔄 P1 |
| 反确认偏误（bear先写） | T2 谋篇先确定 bear case，核心分歧在第二页 | ✅ P0 调整 |
| Phase 4 验证体系 | T3 建立测试用例库（功能测试+风格测试） | 🔄 P1 |
| 输出契约（禁内部黑话） | T3 方法论门禁增加禁止项检查 | ✅ P0 |
| 版本纪律（架构级才升主版） | V50 是唯一活跃版本，sub-version 标记方法论升级 | ✅ 已决定 |

---

## 第五部分：Phase 0 交付标准（10 项）

1. ✅ T0 可以接收类型 A 的写作指令，输出 Writing Brief（含"分析师签署"节点）
2. ✅ T0 有退化为类型 C 的兜底路径（给定股票代码，不阻塞用户）
3. ✅ T1 已接入至少一个一致预期数据源（akshare stock_profit_forecast）
4. ✅ T1 方法论体系包含 ≥4 个 SAC（财报点评/行业深度/非上市企业/上市公司深度）
5. ✅ T1 风格指南库至少有 3 个机构配置文件（高盛/中金/中信——从 D:\ 提取基础色板和段落结构）
6. ✅ T2 谋篇引擎融合 Serenity 9步工作流（发现引擎）+ 11维/8阶框架（覆盖引擎）
7. ✅ T2 谋篇先确定 bear case，核心分歧锁定在第二页
8. ✅ T2 行文引擎逐节生成，不暴露内部方法论标签，证据自然标注
9. ✅ T2 精修引擎 Phase 0（下拉菜单选择修改类型 + 定位 + 执行）
10. ✅ T3 方法论门禁 + Turing Gate + 图表引擎 + 六格式导出 + 圆桌审计附件

---

## 关于版本号的最终声明

**V50 是唯一的活跃版本。** 不再需要 V24、V30、V31、V32、V33、V34、V48。

物理归档方案：
- `1号分析师_V24.0/` → 移入 `_archive/` 目录，只读，作方法论文档的历史参考
- `1号分析师_V30/` → 数据管线和计算代码迁移到 V50 T1 后归档
- `1号分析师_V31-V34/` → 三闸门和导出器迁移后归档
- `1号分析师_V48/` → Web 看板（暂不纳入 V50 P0 范围）单独评估

V50 的版本号策略：
- 架构级变化 → V51、V52（预计 6-12 个月一次）
- 方法论升级 → V50.1、V50.2（SAC 新增/升级、风格库扩展）
- 功能增强 → feature flag（不消耗版本号）
