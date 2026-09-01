# 2hao 双模架构 + 多模块并行：理解与顶级解法对照

**日期**：2026-09-01
**性质**：概念澄清 + 业界对标（非工程交付）

---

## 一、双模架构（训练模式 vs 性能模式）——我的理解

### 1.1 它是"执行者切换"，不是"两种产品"

我的理解：**性能模式与训练模式是同一个引擎的两个驾驶位**，切换的是"谁来当执行者"以及"执行者以什么身份进管线"。

| 维度 | 性能模式（Performance，默认） | 训练模式（Training，可选） |
|---|---|---|
| 执行者 | 管线本身（`scheduler.py`/`main.py` 黑盒跑 E2EOrchestratorV2） | Claude/Agent 作为 SAC 框架的直接执行者 |
| Agent 角色 | 调度员（只负责选择方法、调入口、兜底回流） | 白盒操作员（逐步调用各模块，可观察每步） |
| 数据采集 | `data_collector` 自动多源 | Agent 直接调 `data_collector` |
| 计算 | `compute_engine` 自动跑 | Agent 直接调 `compute_engine` 并看结果 |
| 写作 | `section_writer` 自动 | Agent 直接调 `section_writer` |
| 校验 | IronGate 自动 | Agent 直接调 IronGate |
| 适用 | 批量/标准化，要稳定产出 | 单份深度/个性化，要过程透明、可干预 |
| 成本特征 | token 省（早停/缓存） | token 高（多轮可见） |

**本质是同一个"组织分工"的两种编排**：数据、计算、写作、校验这些模块是共享的（就像同一套流水线设备），变的只是"操作员是自动控制系统还是人"。

### 1.2 为什么 2hao 需要这个设计？（与单模式对比）

- **单一自动管线的问题**：黑盒，失败时不知道哪步错、错了为什么；用户没法介入，深度报告容易"结构对但没答对题"（FP0 要解决的）
- **纯 Agent 直接写的问题**：无纪律，容易跳过 Gate、编造数据、不溯源（FP2a/FP7d 要防的）
- **双模的价值**：性能模式保"可靠与成本"（过门禁、早停省 token），训练模式保"深度与可干预"（白盒、可观察、可纠偏）——**两个模式共享门禁与数据纪律**，这是 2hao 设计的精髓

### 1.3 我看到的边界与风险

1. **边界容易破**：性能模式"只调度不写"与训练模式"直接写"之间，Agent 很容易借"方法选择"（R1 补充）滑进"直接写"。宪法用 FP7d（兜底必须回流管线）+ R28（Agent 对事实负责但不写正文）画线——这条线是整套设计的承重墙
2. **路由是门面**：审计发现 `task_router` 只被 report_generator 调用，scheduler 主链路不路由——双模在文档里清晰、在代码里没完全接上
3. **模式切换的成本未量化**：训练模式的"白盒观察"价值没有指标证明（没有"训练模式产出的报告质量 vs 性能模式"的对照实验）

---

## 二、多模块并行运行的逻辑——我的理解

### 2.1 2hao 的并行是怎么设计的

E2EOrchestratorV2 的 23 节点图（`agent_graph.py`）是自研的 DAG 执行器：

```
preflight → biz_macro → data_feeds
                                  ↘
data ─→ enrich ─→ scarcity / cross_validate / argument / compute / charts
                                  ↘                      ↘          ↘
                                    write_sections → style → assemble → template → validate → critic → compliance → export_docx
```

关键机制（审计确认）：
- **拓扑排序 + 分层并行**：无依赖节点同一批跑（`agent_graph.py` 真实实现）
- **节点契约校验**：每节点 `output_contract` 检查输出类型，error 级阻断
- **写改循环**：validate 失败 → 带 gate_feedback + 状态锚点重跑（STALL/CIRCUIT-BREAK/语义早停/best-so-far 保稿/checkpoint 断点续跑）
- **并行不是线程级**：目前主要是"阶段流水线"（上一个阶段的输出是下一个阶段的输入）+ 同层扇出（多个 section 并行写）

### 2.2 我的理解：2hao 的并行是"三个层次"

1. **流水线（pipeline parallelism）**：data→enrich→compute→write→gate→export，这是串行主链，每阶段吞吐由上一阶段输出决定
2. **扇出（data parallelism / fan-out）**：同一阶段内并行——多个 section 并行写、多个数据源并行采、多张图并行出（commit cde89fe 已做 process-pool 并行渲染）
3. **写改循环（iterative refinement）**：不是并行，是"串行重试+选择性重写"——validate 失败后带反馈重写失败段（rewrite_indices 局部重写），是质量收敛的关键

**设计意图**：把"一次生成的赌博"变成"迭代收敛的工程"——每轮 Gate 反馈喂回下一轮，STALL/CIRCUIT-BREAK 防死锁，早停省 token。

### 2.3 与顶级解法的差距（这个设计有什么短板）

| 2hao 现状 | 顶级解法 | 差距 |
|---|---|---|
| 自研 AgentGraph DAG，裸 dict 上下文 | **LangGraph**（40.8k star）：TypedDict/pydantic State + per-node checkpoint + 可序列化恢复 | 状态类型化、节点级持久化 |
| checkpoint 只覆盖写改循环 | **Temporal**（22.7k star）：durable execution，每步持久化，进程崩溃恢复 | 全链路持久化 |
| 串行主链+同层扇出 | **Ray**（43.7k star）：分布式任务并行 | 多机扩展 |
| 手写重试/熔断 | **Prefect/Airflow**（23k/46k star）：重试策略/DAG 调度/监控 UI | 运维成熟度 |
| 手写 LLM 路由 | **LiteLLM**（57.7k star）：100+ API 统一网关 | 网关完整性 |
| prompt 拼 JSON 用正则抓 | **Instructor**（13.8k star）：pydantic 结构化输出强约束 | 结构化可靠性 |

---

## 三、网上顶级解法——清单与对照

### 3.1 多 Agent / 多阶段编排框架

| 项目 | Stars | 定位 | 对 2hao 的启示 |
|---|---|---|---|
| **MetaGPT** | 70.1k | 多 Agent 框架（软件公司 SOP 化：PM/架构师/工程师） | **SOP 化思想与 2hao 的 SAC 维度完全同源**——它是"软件开发版 SAC"，2hao 是"投研版"；其"标准操作流程内化为 Agent 角色"值得吸收 |
| **AutoGen** | 60.7k | 微软多 Agent 对话框架（agent 可对话、可工具、可人机协作） | 多 Agent 对话的成熟实现；2hao 的 debate_engine 可对标其 GroupChat |
| **CrewAI** | 57.9k | 角色扮演协作编排（Role/Task/Process） | 简洁的 Role-Task-Process 抽象；2hao 的"机构角色"（分析师/风控/合规）可借鉴其定义方式 |
| **LangGraph** | 40.8k | 图编排（状态机+checkpoint+human-in-the-loop） | **最接近 2hao AgentGraph 的升级版**——状态类型化、节点 checkpoint、中断恢复、human-in-the-loop 全是 2hao 缺的 |
| **OpenAI Agents SDK** | 29.1k | 轻量多 Agent 工作流（handoff） | Handoff 模式（agent 交接）比 2hao 的"硬路由"灵活 |
| **Claude Code** | 143.6k | Agentic 编码（任务分解+工具+自省） | 2hao 的"Agent 作为执行者"的运行宿主参照 |

### 3.2 深度研究 agent（2hao 最直接的对标层）

| 项目 | Stars | 定位 | 关键可借鉴点 |
|---|---|---|---|
| **STORM**（stanford-oval） | 31.2k | LLM 知识策展：多视角问题生成 + 写手×专家模拟 + 大纲策展 + **claim-level citation** | 2hao 的 SAC≈perspective 发现、critic_panel≈模拟对话；**差距在"每个论断落引用"**——这就是我们方案里 yichen claim ledger 要补的 |
| **gpt-researcher** | 29.2k | 自治深度研究 agent | 深研范式；规划-检索-写作循环 |
| **通义 DeepResearch** | 19.9k | 中文最强通用深研 | 中文深研 SOTA；问题生成/收敛迭代可学 |
| **deep-researcher（dzhng）** | 19.6k | 最简 deep research | 极简迭代范式——对照可见 2hao"设计过剩、兑现不足" |
| **deep-searcher（zilliz）** | 8.2k | 私有数据深度研究（向量） | 2hao kb_fts 向量化可参考 |
| **TradingAgents** | 101.9k | **多 Agent LLM 金融交易框架**（分析师/研究员/交易员/风控角色辩论） | **金融多 Agent 的顶级参照**——2hao 的 debate_engine 应该对标它的辩论协议与可视化 |
| **dexter** | 27.6k | 自治金融研究 agent（任务规划→实时数据→自省→自我校验） | **与 2hao 思路几乎同构**——印证 2hao 理念不落后；其"自校验循环"是 2hao 写改循环的简化版 |
| **FinRobot** | 7.9k | 开源金融 AI Agent 平台 | 数据/模型/agent 三层架构；金融领域最全 |
| **RD-Agent（微软）** | 14.4k | 因子挖掘/策略研究自演化 agent | **FP5 演化闭环的顶级实现**——2hao learning_loop 缺的"自演化-回测"回路 |

### 3.3 编排/并行/网关基建（工程层）

| 项目 | Stars | 定位 | 对 2hao 的直接意义 |
|---|---|---|---|
| **Ray** | 43.7k | 分布式 AI 计算引擎 | 多机并行执行（2hao 目前单机） |
| **Airflow** | 46.7k | 数据管道调度 | DAG 调度/重试/监控成熟参照 |
| **Prefect** | 23.7k | 弹性工作流编排 | 重试策略/状态管理参照 |
| **Temporal** | 22.7k | Durable execution | 每步持久化、崩溃恢复（2hao 最缺的可靠性） |
| **LiteLLM** | 57.7k | LLM 统一网关（100+ API） | 2hao 自研 deepseek_client 的成熟替代（fallback/限流/缓存/成本） |
| **Instructor** | 13.8k | LLM 结构化输出（pydantic） | 替代 2hao 的"正则抓 {.*}"反模式 |
| **DSPy** | 37.7k | 编程式 prompt（compile 优化） | 2hao context_compiler 的 DSPy 升级版（roadmap 已列未做） |

### 3.4 中国投研同层

| 项目 | Stars | 定位 |
|---|---|---|
| **ai-berkshire** | 16.1k | 价值投资研究框架（巴菲特/芒格/段永平/李录+多 Agent） |
| **TradingAgents-astock** | 3.1k | A股多 Agent 投研（龙虎榜/游资/解禁+7 分析师辩论） |
| **Vibe-Research** | 2.3k | 个人投研 agent（复盘/雷达/持仓/回测） |
| **last30days-cn** | 1.7k | 中国 8 平台 30 天舆情研究 |

---

## 四、对照后的核心结论

### 4.1 双模架构在业界的定位

**2hao 的双模是"罕见且正确"的设计**——业界主流（TradingAgents/MetaGPT/STORM）都是单一编排，要么自动要么手动；2hao 的"同一引擎两个驾驶位 + 共享门禁"在理念上接近 **LangGraph 的 human-in-the-loop**（人可以在关键节点介入）和 **Claude Code 的交互式 agent**（可观察、可干预）。**理念不落后，缺的是把"训练模式的白盒价值"量化**（没有 A/B 对照实验证明训练模式产出质量高于性能模式）。

### 4.2 并行逻辑的升级路径（不推倒，是"方言转普通话"）

2hao 的自研 AgentGraph 已具备拓扑排序/契约校验/写改循环——**这个设计是对的方向**。升级是"用成熟方言替换自研方言"：
1. **状态类型化**：裸 dict → pydantic PipelineContext（commit 30dbcb3 已做一半）——LangGraph State 同款
2. **节点级持久化**：checkpoint 从"写改循环层"扩展到"全节点层"——Temporal 同款
3. **编排层替换**：AgentGraph → LangGraph（可选，作为长期演进），或保留自研但补齐 checkpoint/超时真执行
4. **LLM 网关**：自研 deepseek_client → LiteLLM（或补齐限流/缓存/成本追踪）
5. **结构化输出**：正则抓 {.*} → Instructor/pydantic

### 4.3 一句话总结

> 2hao 的双模设计（可靠+深度的双驾驶位）和多节点并行设计（流水线+扇出+写改循环）**在理念上是行业前沿，与 STORM/TradingAgents/LangGraph 的成熟度差距不在想法，而在工程兑现**：状态没类型化、checkpoint 没到节点级、编排没接成熟框架、结构化输出靠正则。**升级路径不是重写，是把自研"方言"翻译成行业"普通话"（LangGraph 状态 + Temporal 持久化 + LiteLLM 网关 + Instructor 输出 + RD-Agent 自演化）**。
