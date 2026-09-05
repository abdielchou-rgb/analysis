# 2hao-analyst 后续优化路线（对标顶级解法）

**版本**：v1.0
**日期**：2026-09-02
**输入**：前序 ultrathink 审计结论 + 六路 web 调研（评测闭环 / 数值可靠 / 预测校准 / 金融多智能体 / 报告引用 / 可靠执行）
**定位**：MASTER_PLAN_20260902 的战略升级层——不重复 WBS，而是回答"**后面该怎么优化才对**"。每条建议标注顶解决出处与 2hao 的差距证据。
**一句话**：把质量的定义从**内部 Gate 自我评分**挪到**外部验证（golden/校准/回测）**；把数值的生成从 **LLM 猜测**挪到**确定性引擎**；把失败从**静默吞掉**变成**显式失败 + fail-closed**。

---

## 一、顶级解法速览（每条：核心做法 → 2hao 差距）

### 1. Eval 栈：golden set + LLM-judge + CI 回归门禁（2026 评测共识）

**顶解**：分层评测。底座 = 确定性检查（schema/正则/工具调用断言），中层 = golden set（**冻结、版本化、取自真实产物、每次事故回流成新用例**，~100-200 条起），上层 = LLM-as-judge（**judge 与 agent 不同模型家族**、钉死 judge 版本、按维度一次一评、随机化顺序、对照人类标注校准 kappa≥0.7）。CI 用 **floor+delta 双门**：总分回退 >1% 或单维回退 >5% 即 block；**安全类 PASS→FAIL 永不允许**；禁止单次运行定论（flake 纪律）；线上采样 1-5% 流量持续校准，离线在线周对账，偏差 >10% 即 golden 过期。

**2hao 差距**：IronGate 是**自评闭环**（评分公式与门槛同一系统内可调），上一轮已实测门槛 0.85→0.80→0.78 三次下调 + 注释漂移。benchmark/golden/ 的 5086 个文件是**风格语料不是真值集**。无独立 judge、无 golden 回归、无人类校准环。**这正是"0.79→0.87 不可信"的根。**

### 2. 数值可靠：structured output ≠ reliable output；data/math/presentation 三层分离

**顶解**：LLM 不能可靠算数（token 概率生成"像的数"），所以——**模型永不计算**：计算交给 function calling / code execution / 确定性引擎（InvoML 范式：data=LLM 抽取、math=runtime 恒算、presentation=LLM 写、数字由 spec 规则保证）；每个抽取数值带 **evidence 字段**（原文引用），value 有值但 evidence 空 = 可检测幻觉；**字段可空**（required 逼模型编造）；schema 只管形状，业务规则事后 Pydantic 校验+≤2 次重试。

**2hao 差距**：compute 引擎是真实数值（好），但**写作层无约束**：锚卡被动（用户诊断正确），更早的 NUM-FIX 猜测式改数字被禁（84f3ecc）——因为它违反"只替换标记、不猜测数字"原则。需要占位符协议 + 数字证据字段 + 写作后数值 post-check。

### 3. 预测校准：LLM 系统性地过度自信（ForecastBench / KalshiBench）

**顶解**：2025 实测——Superforecaster 难度调整 Brier 0.081 仍领先最佳 LLM（GPT-4.5, 0.101）；**所有前沿模型校准误差大**（最佳 ECE≈0.12，推理增强反而更差 ECE≈0.395，多数模型 Brier Skill Score 为负 = 不如直接押 base rate）。有效改进：outcome-RL（RLVR）、RAG+集成+**后验 logistic 校准**、专训小模型。**校准不会随推理 scaling 自动变好，必须显式测、显式校准**。人类+AI 团队化聚合能再提 10-25%。

**2hao 差距**：confidence_at_make（2028 条全覆盖）**从未被校准**；验证用绝对涨跌而非 alpha（已立项 W2，但缺**置信度校准面板 ECE/Brier 与后验重标定**）；预测是"一次性点估计"，无更新型预测。

### 4. 金融多智能体验证：MarketSenseAI "Signal or Noise"（2026 最严实盘验证）

**顶解**：架构 = News/Fundamentals/Dynamics/Macro 四个专家 agent + **synthesis agent** 出五级评级与月度论点，embedding 归因（哪个 agent 驱动信号）。验证方法论是精髓：**信号在观察日 live 生成**（杜绝前视偏差）、双固定 cohort（S&P500 467 股 19 月 / S&P100 94 股 35 月，避免幸存者偏差）、**10,000 次 Monte-Carlo 随机组合做显著性**（strong-buy 组合排 99.7 分位，p=0.003；S&P100 未达显著 → 作者诚实报告）、NNLS 归因 + IC 检验、regime 自适应的 agent 贡献轮动。反面教训：早前夸大的 alpha 在更宽截面/更长周期显著衰减；**"讨论越复杂不代表收益越好"，communication 设计取决于市场**。

**2hao 差距**：预测系统从未做过 **placebo/随机基线显著性**（不是"命中率>随机 5 个点"，而是"在 N 次随机模拟中的分位"）；无 **live-forward cohort** 与 **IC/归因**；framework 有效性（W4.3/S4）只有 Gate 内效度、无"用了它预测是否更准"的外效度。这是"证明自己是真投研"的最短路径。

### 5. 报告引用：STORM/Co-STORM 把每个论断绑到可检索来源

**顶解**：perspective 驱动提问 → 逐论断**输出即带来源链接**；Co-STORM 报告 99% 事实准确率、人类编者评其组织度 +25%；前沿在做**citation precision / human-verified supported rate**（CogGen）这类 claim 级引用质量度量。

**2hao 差距**：有 [注N] + JSON-LD 骨架（P3/S3 接线完成），但无"每数字必带可点击 URL"的强制与 **precision/supported-rate 度量**；来源标注率仍是报告级而非 claim 级。

### 6. 可靠执行：checkpoint ≠ durable；显式失败 + 幂等 + 声明式重试（Temporal/LangGraph）

**顶解**：LangGraph checkpoint 存"数据"不存"执行"（进程死即死）；Temporal 用事件溯源做到**崩溃后精确续跑**、**HITL 可等数天**、**幂等台账**（先记 pending 再执行）、**声明式重试**（按错误类：限流→退避、超长→压缩上下文重试）、saga 补偿、**故障注入测试**（工具成功后才崩溃/审批中重启/checkpoint 过期）。

**2hao 差距**：e2e 单进程 + try/except 静默（ArgumentEngine 失败返回 scaffold=None 而 Gate 照过 = F4）；Gate 在 error 检查集为空时放行（= F2 fail-open）；HITL 审批中断无续跑保障；无故障注入测试。

---

## 二、整合后的四条优化主线（A-D）

### 主线 A — 测量诚实化（治"分数通胀"）

目标：让"0.87"变成可审计、可复现、有外部锚。

| # | 动作 | 要点 | 顶解出处 |
|---|---|---|---|
| A1 | **Gate 语义 fail-closed + 版本化** | iron_gate L527 `_error_scores 为空→True` 改为 block；P0-weighted 记 `judge_ver` + threshold + 公式 hash 入每次运行日志/指纹 | Eval 栈 §1 |
| A2 | **评分公式版本化** | overall_score 语义变化必须 bump `judge_ver`；分数历史表存 (run_id, judge_ver, error_mean, gate_conf)，跨版本比较一律按同 judge_ver | Eval 栈 §1 |
| A3 | **golden 真值集（从语料到真值）** | 从真实交付报告抽 100-200 条带**可机检数值真值**的用例（目标价=compute 输出、关键财务=DB 值）；冻结版本 golden/v2026-09；每次 Gate 事故回流 1 条新用例 | Eval 栈 §1 |
| A4 | **LLM-judge 外评** | 独立 judge（与写作 agent **不同家族**，钉版本）：对 golden 输出按 4 维（正确/完整/幻觉/语气）分维评分；与人类(Marvis)标注样本校准 kappa≥0.7 | Eval 栈 §1 |
| A5 | **CI floor+delta 门禁** | 对 golden 跑：总分回退>1% 或单维>5% → 红；**阈值下调必须附 golden 无回退证据**（堵死"提分靠降门槛"）；单次运行不 gate，2-3 次取均 | Eval 栈 §1 |
| A6 | 线上周对账 | 每周采样生产报告 1-5% → 外部 judge → 与内部 Gate 分差 >10% 即 golden 过期 | Eval 栈 §1 |

### 主线 B — 数值与事实（治"多目标价/锚卡被动/幻觉数字"）

目标：报告里每个数字要么**来自确定性引擎/检索**，要么**带证据可点击**，绝不来自 LLM 猜测。

| # | 动作 | 要点 | 顶解出处 |
|---|---|---|---|
| B1 | **占位符协议（从 target_price 推广）** | compute 产 canonical dict → prompt 注入 `{{tp_primary}}` 等**白名单标记** → 后处理**只替换标记、绝不猜数**（吸取 NUM-FIX 教训）→ Gate 断言正文无残留 `{{}}` | data/math/presentation §2 |
| B2 | **Tier 数值分级** | Tier-1（目标价/估值/财务指标/评级）必须 ∈ canonical 或带 [注N]→URL；Tier-2（评论性数字）要求 source token；写作后 post-check：扫描全数字，每个必须命中"canonical ∪ 带注"否则红 | §2 + §5 |
| B3 | **数字证据字段** | claim_citation 扩展：每个 claim 记录 (value, evidence_quote, url, confidence)；evidence 空但有 value → 可检测幻觉，Gate 拦截 | §2 |
| B4 | **schema 可空** | 提取/输出 schema 关键字段 nullable——允许"数据不可得"，不许编造（对齐 FP2a 诚实标注） | §2 |
| B5 | 计算引擎唯一出口 | 复核 compute 是否所有估值只有单一出口（W3.1 聚合 + 明细），杜绝同数多源 | §2 |

### 主线 C — 预测校准升级（治"验证没意义/置信度没校准"）

目标：10-31 首次真实验证就产出**有统计意义**的结果，而非"抛硬币/自证"。

| # | 动作 | 要点 | 顶解出处 |
|---|---|---|---|
| C1 | **校准面板** | 每期验证即算：分桶命中率 vs 声称置信度、**ECE、Brier、Brier Skill Score（对 base-rate）**；写入 observability 新表 `calibration_*` | ForecastBench/KalshiBench §3 |
| C2 | **后验重标定** | 用历史 (claimed, actual) 拟合 logistic，把 confidence_at_make 映射为 calibrated prob；写作时注入校准后置信度 | §3 |
| C3 | **placebo 显著性（MarketSenseAI 式）** | 对每个到期 cohort：构造 N=1000+ 随机方向/随机选股组合，报告系统 hit/alpha 的**分位与 p 值**（替代"高 5 个点"）；区分方向/alpha/目标价三口径 | §4 |
| C4 | **live-forward cohort** | 预测按 made_date 冻结、到期日 live 取数，杜绝前视；资产池与基准 cohort 固定并防幸存者偏差 | §4 |
| C5 | **维度/框架外效度归因** | hit/miss 对 (dimension, framework, 报告关键变量) 做关联/IC——回答"哪个引擎/框架真有用"（framework_effectiveness 从 Gate 内效度→预测外效度） | §4 |
| C6 | **更新型预测** | track_record 支持同一预测的**更新事件**（改判/加注），存时间线——校准对"最新点估计"算 | §3 团队聚合/更新 |

### 主线 D — 执行可靠性（治"静默失败 + fail-open"）

目标：失败必须响亮且可恢复，永远不许"假通过"。

| # | 动作 | 要点 | 顶解出处 |
|---|---|---|---|
| D1 | **节点完成契约** | e2e 启动时声明节点清单 + 每节点必需 evidence key；节点返回 evidence marker；Gate 前校验**全覆盖**，缺失 → ERROR 不是 PASS（ArgumentEngine 即第一案例） | §6 |
| D2 | **fail-closed 全面化** | 所有 Gate/校验：检查集为空/证据缺失 → block；删除 `else True` 兜底 | §6 + Eval §1 |
| D3 | **声明式重试** | 按错误类：LLM 限流→指数退避（已有熔断）；超长→压缩上下文重试；**不可重试错→立刻失败**（不静默 continue） | §6 |
| D4 | **幂等台账** | 副作用（写 DB/导出/发通知）先记 pending 再执行，崩溃后按台账恢复，杜绝重复/丢失 | §6 |
| D5 | **HITL durable** | decision_memo 审批存 data/reviews（已有）→ 补**续跑入口**：审批通过后从 export 节点精确恢复；测试"审批中进程重启" | §6 |
| D6 | **故障注入测试** | 测试套件加：节点抛错→整链显式失败；tool 成功后才崩溃→恢复幂等；error 集为空→block | §6 |

---

## 三、落地路线（P0/P1/P2，工作量含测试）

**P0（本周，修复诚信基线；对应 ultrathink F2/F4/无测试）**

| 任务 | 关联 | 验收 |
|---|---|---|
| A1+A2 Gate fail-closed + judge_ver 版本化 | 修 F2 | 无 error 检查→block；运行日志含 gate 配置 hash |
| D1+D2 节点完成契约 + fail-closed | 修 F4 | ArgumentEngine 缺 evidence → 显式 ERROR |
| B1 target_price 占位符试点（先单数） | W3 补测试 + 用户架构方向 | 正文无残留 `{{}}`；新增 4 红→绿测试（聚合/锚卡单值/Gate 偏离/fallback） |
| A5 初版 golden 真值集 50 条 + CI delta 骨架 | 治分数通胀 | 一次 CI 运行能报"总分/单维 delta" |
| 指纹修正（最终字节 hash，DOCX 解封） | 恢复 DOCX 交付 | DOCX 正常导出且指纹可验 |

**P1（1 个月，让分数可信、数字可查）**

| 任务 | 关联 | 验收 |
|---|---|---|
| A3+A4 golden 扩到 150-200 条 + LLM-judge（异家族、钉版、人校准 kappa） | — | judge 与人类一致率 ≥80%；每周外评周报 |
| B2+B3 全数字 Tier 分级 + evidence 字段 | claim_citation 现有骨架 | 任一报告每数字命中 canonical∪带注 |
| C1+C2 校准面板 + 后验重标定 | W6.1 升级 | ECE/Brier/BSS 可画；confidence 有 calibrated 版 |
| C4+C5 cohort 定义 + 归因 | W2 完成基础上 | 10-31 到期池有 cohort 与随机基线 |
| D5 HITL durable | — | 审批中断后可从 export 恢复 |
| W1.2 backfill 存量目标价（提级，硬期限依赖） | MASTER_PLAN 更新 | 2028 条覆盖率 0.25%→>90%（或标 unverifiable） |

**P2（季度，让系统可证明"有 alpha"）**

| 任务 | 关联 | 验收 |
|---|---|---|
| C3 placebo/蒙特卡洛显著性 + IC | MarketSenseAI 式 | 每月业绩报含"分位 + p 值"，而非裸命中率 |
| C6 更新型预测 + 校准对最新点估计 | — | track_record 含事件时间线 |
| 专家+synthesis agent + 归因（A/B 先行） | MarketSenseAI 架构 | 与现单路径 A/B：无显著提升则不上 |
| 工程化评估：LangGraph/Temporal | — | 评估报告 + 试点单条长任务迁移 |
| 产品化（Web 真实出报告 + 批量） | MASTER_PLAN W8 | Web 提交→真实报告→下载 |

---

## 四、反模式清单（顶级文献明确的坑）

1. **别再把降阈值当提分**——分数提升只认 golden delta 与外部 judge。
2. **judge 不许自评自家**（self-preference bias）；judge 版本钉死，漂移即查。
3. **多 agent ≠ 更准**（MarketSenseAI 系研究：communication 复杂度不保证收益，regime 依赖）——一切新架构先 A/B。
4. **structured output 保证形状不保证真值**——schema 通过 ≠ 数值对，数值靠引擎/证据。
5. **占位符绝不走回"程序猜数字改"**（NUM-FIX 前车之鉴）——只替换 LLM 显式发的标记。
6. **校准不会随模型变大自动变好**（KalshiBench：推理增强反而更差）——必须显式测、显式校准。
7. **度量不能 self-referential**——内部 Gate 只能当快速过滤器，质量定义在外部。

---

## 五、10-31 硬期限对齐

MASTER_PLAN 的 W1(契约)/W2(alpha 判据)/W6(口径) 完成后，叠加本路线 C1-C5：**首次真实验证（10-31）交付物升级为**：命中率三口径 + ECE/Brier 校准 + **1000 次随机模拟的 alpha 分位与 p 值** + 维度归因——一份"系统相对市场是否有 alpha、置信度是否诚实、哪个引擎在贡献"的可信业绩报告。这比"方向命中率 55%"有说服力一个量级。

---

## 参考来源

- Eval 栈：Nearform "how to build evals for reliable agents"；FutureAGI "LLM Testing in 2026"；Claude API Evaluation (golden/regression)；The Prompt Bench Evals & Testing
- 数值可靠：The Neural Base "Financial: number accuracy"；Zylos "Structured Output in LLMs 2026"；Towards Data Science "Your LLM Can Return Perfect JSON and Still Be Wrong"；InvoML (data/math/presentation)
- 预测校准：ForecastBench (Good Judgment/quantified-uncertainty)；KalshiBench (HF paper 2512.16030)；arXiv 2505.17989 (outcome-based RL)
- 金融多智能体：arXiv 2604.17327 "Signal or Noise in Multi-Agent LLM-based Stock Recommendations?"；MarketSenseAI 2.0 (Fatouros/Metaxas)
- 报告引用：STORM/Co-STORM (stanford-oval)；CogGen (arXiv 2604.17072)
- 可靠执行：Temporal "LangGraph Plugin adds Durable Execution"；Grid Dynamics case；agent state persistence patterns
