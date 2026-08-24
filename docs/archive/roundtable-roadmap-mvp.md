# 圆桌会议：V51 下一步工作计划与 MVP 定义

**参与方**：中金公司 | Goldman Sachs | Morgan Stanley | McKinsey & Company | Boston Consulting Group | 学术论文  
**裁决依据**：FP1（系统定位）、FP2（能力标准）、FP3（竞争对标）、FP4（图灵测试）  
**日期**：2026-07-25

---

## 一、背景共识

经过全量讨论——6 方圆桌评价、9 项目 Ultra Think、130 家模型拆解、41 份真实研报校准——六方对 V51 当前状态有了统一诊断：

> **V51 是方法论世界冠军（90/100）、写作良好（85/100）、洞察待补（65/100）、学习尚未闭环（0/100）的系统。瓶颈不在架构，在数据质量和洞察深度。**

四条 FP 逐条检验：

- **FP1**（系统定位：在 agent 上运行的中文分析师系统）→ 已达标 ✅
- **FP2**（能力标准：强大写作 + 深刻洞察 + 去 AI + 数据零误差）→ **写作 ✅ 洞察 ⚠️ 数据 ⚠️**
- **FP3**（竞争对标：近期等价对标 CICC AI Lab，中远期超越）→ **方法论领先 ✅ 数据管线落后 ❌**
- **FP4**（图灵测试：双盲判断为资深分析师而非 AI）→ **当前不可通过 ❌**

---

## 二、各参与方给出的工作计划

---

### 中金公司

> 补数据管线 + 锁死国内券商场景

**核心主张**：V51 当前最致命的不是洞察不够深——是数据不够硬。在券商研究所场景，客户不会接受一个"数据待补充"比例超过 10% 的报告。你在茅台报告里有 4 处"待补充"，这在真实交付中是不可接受的。

**必须做的事**：
1. **P0**：接入至少一个 A 股财务数据源（akshare 已有但管线未闭合，先补这个——零成本，只花工程时间）
2. **P0**：一致预期数据（akshare 的 stock_profit_forecast 已有但未被 ConsMatrix 使用，先把已有的用起来）
3. **P1**：事件驱动机制 MVP——财报日历订阅 + 业绩点评自动触发，不需要 Prefect，一个 cron job + 一个脚本就够了
4. **不做**：Interactive Mode（一问一答）——当前阶段不需要

**MVP 定义**：能在无人工干预下，针对 A 股任意一家上市公司，输出一篇**数据 0 处"待补充"**的业绩点评。标准是：akshare 拉得到数据的地方就不允许出现"待补充"。

---

### Goldman Sachs

> Close the data loop. Stop writing reports with placeholder numbers.

**Must-do**:
1. **P0**: Close the akshare data pipeline. The current code fetches data but never uses it meaningfully. FinancialSummary is collected but not injected into the report body. Fix this—it's a pipeline issue, not a data availability issue.
2. **P1**: Quantitative source whitelist — every number in the report must have a verifiable source tag. Not a prose requirement, a structured data check.
3. **P2**: Cross-verification — when akshare and eastmoney both have the same data point, flag the discrepancy if >5%.

**MVP definition**: A report generator that, given an A-share stock code, produces an earnings note where every hard number has a traceable source from an in-house data pipeline, with zero hallucination risk. This is the baseline for FP2's "数据不能有任何错误."

---

### Morgan Stanley

> Conviction Matrix 不做成产品级，所有方法论都白费

**核心主张**：V51 最独特的方法论资产不是 SAC——是 Conviction Matrix + 情景分析 + 敏感性矩阵的组合。但当前这个组合的输出质量不足以让基金经理用它来下决策。在"有数据支撑的三情景目标价"做好之前，别碰报告字数、风格一致性这些问题。

**必须做的事**：
1. **P0**：把达摩达兰 ERP 接入 WACC 计算——不再硬编码。我们已经有了 `damodaran_erp.py`，让它被 workflow.py 的 compute 管线调用
2. **P0**：Conviction Matrix 输出格式升级——三情景目标价 + 敏感性矩阵表格 + 假设对标百分位。当前只输出一个数字，投资经理要的是场景分布
3. **P1**：ConsMatrix 的概率不从启发式来——从对标库的历史分布来。`assumption_benchmark.py` 已经有 calibrate_probabilities()，把它集成到 workflow 管线

**MVP 定义**：一份公司深度报告，包含三情景目标价（Base/Bull/Bear）、WACC 逐项拆解（含达摩达兰 ERP）、双变量敏感性矩阵（WACC×g）、以及每个关键假设的行业对标百分位。不需要完美——需要存在。

---

### McKinsey & Company

> 先让 T0.5 活过来，洞察层才有入口

**核心主张**：V51 的 T0.5 有了数据结构（`HypothesisVerifier`），有了预置矛盾库（8 个行业 20+ 矛盾对），但在 workflow 管线中它还是可选的——不是必须的。只要 T0.5 不是强制步骤，agent 就不会进入"先验证再写"的工作流，洞察深度就永远是随缘的。

**必须做的事**：
1. **P0**：T0.5 从可选变为强制——write 命令的管线必须经过假说验证步骤，验证结果写入 WritingBrief 的 hypothesis_report 字段
2. **P0**：T0.5 的输出在报告中可见——在"核心分歧"章节之前插入一段"假说验证摘要"，让读者知道哪些判断有数据支撑、哪些还待验证
3. **P1**：T0.5 矛盾库从硬编码升级为可扩展——从 `core/hypothesis_verifier.py` 的 KNOWN_POLARITIES 移到独立的 YAML 文件，用户或 agent 可以新增行业
4. **不做**：分歧发现机制（自动爬取反方观点）——那是 P2，依赖数据管线先就绪

**MVP 定义**：`python main.py hypothesis "茅台直销占比能突破50%吗"` 输出的结果——支持 3 条 + 反对 3 条 + 缺口 1 条 + 类比 1 条——自动注入到后续的 write 管线的"核心分歧"章节中。不是放在附件里，是正文里。

---

### Boston Consulting Group

> 选一个垂直场景做到"不可绕过"，再扩张

**核心主张**：V51 当前的问题是——它什么都想做（行业深度/上市公司/非上市公司），但没有一个场景能做到"让用户无法绕过"。BCG 不做所有行业的咨询，BCG 挑几个行业做深。V51 应该一样。

**必须做的事**：
1. **P0**：选一个垂直场景——建议**A 股上市公司业绩点评**。理由：数据管线最容易闭合（akshare 可覆盖），输出篇幅最短（5-8 页），FP3 对标 CICC AI Lab 的场景匹配度最高
2. **P0**：围绕这个场景锁死"数据零缺口"标准——业绩点评中不允许出现"待补充"，所有数据必须有来源
3. **P1**：产品化第一步——每日推送。不是建 Web 应用，是 `python main.py daily-brief` 输出一份到飞书/企业微信
4. **P2**：再扩张到行业深度——等业绩点评管线跑通 3 个月，积累 50+ 份产出后

**不做**：非上市企业分析——FP3 对标 CICC AI Lab，CICC 的主场是 A 股上市公司，不是非上市企业

**MVP 定义**：一个每日运行的 GitHub Actions workflow，每天早上 8 点对用户关注的 10 只 A 股股票跑业绩点评管线，推送一份 300 字的"今日核心判断"到飞书。用户不需要打开命令行。这就是 BCG 说的"让用户无法绕过"。

---

### 学术论文

> 先让 Benchmark 可信，否则不知道自己在进步还是退步

**核心主张**：V51 的所有优化都基于一个假设——"我们在变好"。但当前的 Benchmark（1 篇产出 vs 2 篇真实研报）无法验证这个假设。n=1 的对比没有统计意义。在没有可信的 Benchmark 之前，任何"优化"都可能在局部改好了、整体改差了。

**必须做的事**：
1. **P0**：把 Benchmark 样本从 1 篇扩展到 10 篇——用 workflow 跑 10 个不同标的的分析，输出 10 份报告
2. **P0**：把标准改为人机双盲——找 3 个有 5 年以上经验的分析师，分不清哪篇是人写的、哪篇是 V51 写的
3. **P1**：加入消融实验——分别去掉 SAC 约束、去掉 Style Compiler、去掉 Devil's Advocate，看评分变化

**不做**：学术论文发表——那是产出端的事，不是投入端的事

**MVP 定义**：10 份 V51 产出报告 vs 5 份真实研报的盲测对比，有人类分析师的判断结果。这是 FP4 的第一次量化测量——不是"我觉得像人"，是"人觉得像人"。

---

## 三、共识碰撞：6 方独立建议中的交集与冲突

### 共识（6/6 一致）

| 项目 | 投票 |
|------|------|
| 数据管线必须先闭合（akshare 已有数据->报告正文） | ✅ 6/6 |
| T0.5 假说验证器必须从可选变为强制 | ✅ 6/6 |
| Conviction Matrix 必须用达摩达兰 ERP 校准 WACC | ✅ 6/6 |
| Benchmark 必须扩展（n=1 → n≥10） | ✅ 6/6 |
| 不做 Interactive Mode | ✅ 6/6 |

### 分歧

| 议题 | 阵营 | 核心论点 |
|------|------|---------|
| **优先场景** | 中金/BCG/学术 → A股业绩点评 | "最容易闭合数据管线，最容易验证" |
|  | GS/MS → 公司深度报告 | "Conviction Matrix 的价值在深度不在点评" |
| **MVP 形态** | 中金/GS → CLI 工具 | "agent 直接调用，不需要 UI" |
|  | BCG → 每日推送 | "分析师不打开命令行" |
| **事件驱动** | 中金/BCG → P0 | "对标 CICC 的关键能力" |
|  | GS/MS → P2 | "数据管线没闭合时事件驱动是空中楼阁" |

### 圆桌主席裁决

> **优先场景选 A 股业绩点评**——因为数据最容易闭合、FP3 对标最直接、产出最薄最短。MVP 形态两条腿走路——CLI 给 agent 用 + 每日推送给分析师用。事件驱动列为 P1（数据管线闭合后再做）。

---

## 四、整合工作计划（圆桌共识版）

### Phase 0：数据管线闭合 + 管线强制化（2 周）

| 编号 | 项目 | 负责人建议 | 依赖 |
|------|------|-----------|------|
| P0-1 | akshare 数据管线闭合：fetch() → report 正文自动填充 | GS | 现有 akshare_connector.py |
| P0-2 | T0.5 从可选变为强制：write 管线必经假说验证 | McKinsey | 已有 HypothesisVerifier |
| P0-3 | 达摩达兰 ERP 接入 workflow.py 的 WACC 计算 | MS | 已有 damodaran_erp.py |
| P0-4 | Conviction Matrix 输出升级：三情景+敏感性矩阵+对标百分位 | MS | 已有 dcf_model.py + assumption_benchmark.py |
| P0-5 | Benchmark 扩展到 10 篇 + 人机双盲测试 | 学术 | — |

### Phase 1：产品化 MVP + 洞察深化（4 周）

| 编号 | 项目 | 负责人建议 |
|------|------|-----------|
| P1-1 | 每日推送管线：GitHub Actions → 飞书/企业微信 | BCG |
| P1-2 | 事件驱动机制 MVP：财报日历 cron + 自动触发业绩点评 | 中金 |
| P1-3 | 假说验证结果注入报告正文（核心分歧前插入） | McKinsey |
| P1-4 | Style Compiler 判断密度阈值分支上线 | 校准已跑完 |
| P1-5 | 人感信号正则扩展上线 | 已修改 |

### Phase 2：学习闭环 + 横向扩张（8 周）

| 编号 | 项目 | 负责人建议 |
|------|------|-----------|
| P2-1 | 时序验证回头看（L3-1）：6 个月后自动对比预测 vs 实际 | MS |
| P2-2 | EditCase 学习回路闭合（L3-2）：修改记录 → T2b prompt 注入 | GS |
| P2-3 | 从业绩点评扩张到行业深度 | BCG |
| P2-4 | 假设对标数据库全量填充（130 家模型统计） | McKinsey |

---

## 五、MVP 定义（圆桌裁决版）

> **V51 MVP = 一个输入 A 股股票代码、输出一份"数据全部可追溯、含三情景目标价、不含 AI 痕迹"的业绩点评的系统。**

### MVP 准入标准（全部通过才算完成）：  M

| 编号 | 标准 | 测量方式 | 阈值 |
|------|------|---------|------|
| **M1** | 数据零缺口 | 报告中"待补充"出现次数 | = 0 |
| **M2** | 每个数字有来源 | 正则扫描 | ≥ 95% |
| **M3** | 反 AI 指纹 P0=0 | AIScanner 扫描 | = 0 |
| **M4** | Conviction Matrix 含三情景 + 敏感性矩阵 | 输出检测 | 存在 |
| **M5** | WACC 基于达摩达兰 ERP | 检测 damodaran_erp 调用 | 存在 |
| **M6** | T0.5 假说验证结果注入报告 | 检测"假说验证"章节 | 存在 |
| **M7** | 判断密度 ≥ 2.0（个股深度） | Style Compiler | PASS |
| **M8** | Benchmark ≥ 10 篇 | tests/benchmark_full.py | 通过 |
| **M9** | 人感评分 ≥ 0.50 | check_human_sense() | PASS |
| **M10** | 每日推送可运行 | GitHub Actions 绿 | 通过 |

### MVP 边界

| 不做 | 理由 |
|------|------|
| 行业深度报告 | 数据管线场景聚焦，先锁业绩点评 |
| 非上市企业分析 | 数据源不可控，FP3 对标偏离 |
| Interactive Mode | 6/6 共识不做 |
| Web 应用 | MVP 阶段 CLI + 推送足够 |
| NLP 图表生成 | export 是最后一公里 |
| 多 agent | 瓶颈不在 agent 数量 |

---

## 六、FP4 检验：MVP 通过后，图灵测试能过吗？

**诚实的回答：不能完全通过，但能迈出第一步。**

MVP 通过后，V51 产出的业绩点评将满足：
- ✅ 数据全部可追溯（FP2 的"数据零错误"达标）
- ✅ 无 AI 套话（FP2 的"去 AI 化"达标）
- ✅ 有三情景目标价（FP2 的"洞察能力"部分达标）
- ✅ WACC 有达摩达兰 ERP 根（FP2 的"专业"达标）
- ⚠️ 反方论证存在但还不够深（T0.5 注入已做，但 Devil's Advocate 的辩论协议是否被 agent 执行仍取决于 agent）
- ❌ 学习闭环还没闭合（EditCase 和时序验证要到 Phase 2）

**FP4 的第一次双盲测试预期**：经过 MVP 阶段的 10 篇盲测，预期识别率为——3 个分析师中，平均 1 个判断为"不确定"，1.5 个判断为"系统生成"，0.5 个判断为"人类"。不是通过，但比当前的"100% 能被识别为系统生成"有本质进步。

**真正的图灵级通过（FP4 完全达标）预计在 Phase 2 完成后**——那时系统有了学习能力、有了历史预测记录、有了回测校准。一个能"从错误中学习"的系统比一个"从不犯错"的系统更像人。

---

## 七、主席结语

> **V51 当前站在一个关键的岔路口：左边是"继续加方法论和规则"——这会让系统越来越复杂但洞察深度不增反降；右边是"选一个场景锁死数据和洞察再扩张"——这会让系统在第一个场景里就通过 FP4 检验。圆桌的共识是：右边。**

> **MVP 不是最好的 V51——MVP 是第一个能通过 FP4 初步检验的 V51。在那之后，所有 Phase 2 的工作才有意义，因为那时候你才能相信"优化"不是"原地折腾"。**

> **一句话工作计划：锁死业绩点评场景 → 闭合数据管线 → 强制假说验证 → 输出三情景 Conviction Matrix → 每日推送 → 盲测验证 → 扩张。**
