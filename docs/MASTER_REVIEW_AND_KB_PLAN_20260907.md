# 二号分析师 · 全会话复盘 + 知识库方法论落地审计与改造计划

> 日期：2026-09-07
> 性质：复盘 + 只读审计 + 落地计划（本轮不改代码，改动留待确认后单独执行）
> 依据：仓库实际代码/数据实测 + 本会话已产出的多份文档（见文末引用清单）

---

## 0. 结论速览（写给不看正文的人）

1. **二号分析师是什么**：不是"一个能写研报的 prompt"，而是一套把研究质量拆成
   "数据真实 × 方法结构 × 生成纪律 × 门禁强制"四层的生产管线；SAC 是它的骨架，
   IronGate/StyleCompiler 是它的纪律，fail-closed 是它的伦理底线。
2. **前几轮修复（20260906/07）全部闭环**：死模块、假业绩、缺 import、CI 形同虚设、
   重复 key、_load 静默清空、partial 口径、除零边界、门禁阈值双重事实——93 个回归测试
   全绿。本会话审计没有再发现同源未修项，只有四个已知残余（见 §3.4）。
3. **知识库方法论"注入了但正文体现不出来"——上一轮升级没有真正解决**。审计证据：
   KB/MKB 注入块被包在 `if _tm_str`（工具模块开关）里，工具模块为空时 15 个注入块
   全部消失；串行写作路径根本不注入 KB；检索白名单把 01-宏观/08-四大审计/09-国际投行
   三个方法论目录排除在外；端到端没有"注入→引用→体现率"门禁。最近两份完整报告正文
   各只有 1 处 `[KB1]`、0 处 MKB 痕迹。
4. **网上不存在"一劳永逸"**。业界收敛结论只有一句：**别靠提示词让模型"用"知识，
   靠结构让它"只能用"知识**。对应五类顶级方案（Evidence-First 封存、引用契约、
   检索纪律、抗噪生成、端到端评测），已在 §9 给出并映射成本计划的 P0/P1/P2。
5. **成本/速度/本地模型问题此前已闭环分析**（`docs/ANALYSIS_cost_speed_local_20260907.md`
   等），本文只做摘要与交叉引用。

---

## 1. 本会话问题地图

| # | 用户问题 | 结论落点 |
|---|---------|---------|
| 1 | 深度理解仓库；按第一性原理审计代码 | §2、§3 |
| 2 | 上一轮 FULLFIX 后类似问题是否还在 | §3.3（R1-R4 已闭环，残余见 §3.4） |
| 3 | 二号分析师是什么、怎么用、交付什么 | §2 |
| 4 | 训练模式 vs 性能模式；SAC 侧重可否随用户要求调整 | §4、§5 |
| 5 | 四大投行/MBB/四大会所/顶级券商资深分析师会承认它更强吗 | §6 |
| 6 | 调研交给 Kimi 是否增强；训练模式是否只是 LLM 用 agent | §7.1、§4.3 |
| 7 | Kimi token 贵不贵、更省方案；并行后仍慢怎么办 | §7.2（详见已产出的成本/耗时文档） |
| 8 | 本地 qwen3-30B-A3b 能不能用起来、有无更好方案 | §7.3 |
| 9 | KB 方法论"进不了报告"升级后解决了吗 | §8（核心：未解决） |
| 10 | 网上同类问题与顶级解法，能否一劳永逸 | §9、§11 |

---

## 2. 二号分析师：我的理解、用法与交付物

### 2.1 一句话

二号分析师是**面向机构级深度研究的确定性生产管线**：把 CICC/GS/McKinsey 式研究
拆成可执行的框架（SAC）→ 数据/计算（akshare/Tavily/yfinance + DCF/可比/场景/SOTP）
→ 分节写作（DeepSeek）→ 风格净化（StyleCompiler 8 条确定性规则）→ 质量门禁
（IronGate，101 项注册检查）→ 交付（DOCX + Gate 报告）。

### 2.2 它的第一性原理（我提炼的 6 条）

1. **可靠性 > 聪明**：没有真实输入就不产出数字，宁可 `None`/留白不可编造
   （20260906 P0-2"假业绩"修复即此原则的具象化）。
2. **质量是结构的函数**：SAC YAML 把"资深分析师的脑子里有什么"显性化为
   决策门 → 核心分歧 → 商业模式 → 财务验证 → 竞争 → 增长 → 治理/ESG → 估值 →
   催化剂 → 证伪 → 母子公司 → 资金面 → Bold Call → 风险，14 维因果链，而不是
   prompt 自由发挥。
3. **纪律不能被 prompt 承诺替代**：AIGC 指纹、个人叙事、系统指令泄露由
   StyleCompiler 确定性移除；图表/表格/数据来源/SAC 覆盖率由 IronGate 硬性把关。
4. **单一事实源**：一个事实（Gate 阈值、财务口径、resolve 字段）在全仓只能有一个
   定义点，用生成器 + 守护测试防止文档/合约/运行时三方漂移（R4 修复）。
5. **模式即不变量**：写什么 key、dataclass 装什么字段，用 AST 守卫测试强制
   （R1b），不是靠约定。
6. **诚实留白 > 粉饰**：数据缺口显式标注不扣分，"没有真相就不讲"被设计成激励结构。

### 2.3 怎么用

入口是 `scheduler.py`/`main.py` → `E2EOrchestratorV2`。使用者只需要提供：

- 报告类型（`listed_company` / `industry_deep` / `unlisted_company` /
  `earnings_notes` / `decision_memo`，各自对应一套 SAC YAML）；
- 标的或行业（公司名/行业名 + 可选证券代码）；
- 用户要求（`custom_requirement`，如决策场景、侧重维度、必答问题）；
- 模式选择（训练/性能，§4）。

系统侧通过 `RUN_MODE`、`LLM_PROVIDER`、`NODE_PROVIDER_*` 与 `route_policy.py`
做模型路由与节点级混编。

### 2.4 能交付什么

- 单份 5-15 万字级、SAC 全维度覆盖的深度报告正文（含 Bold Call、催化剂、证伪、
  目标价+评级、每段 So What）；
- 图表 ≥5、表格 ≥3、数据来源标注 ≥30%（低于红线被 IronGate 阻断）；
- DOCX/Markdown 导出 + Gate 判定报告 + 数据缺口诚实留白清单；
- 训练模式额外交付：修改历史、审计反馈回流、学习沉淀（可用于下一份报告的初始
  findings）。

---

## 3. 第一性原理代码审计：20260906/07 修复闭环复核

### 3.1 审计透镜（不是"找 bug"，是查"不变量是否被代码强制"）

- **fail-closed**：无真价 → 无 PnL；非正价 → None；未知 schema 键 → 告警不丢弃。
- **单一事实源**：Gate 阈值/检查数全仓只留 `pipeline/iron_gate.py` 一个定义点。
- **写读同构**：`resolve_outcome` 写什么 key，dataclass 必须装得下（AST 守卫）。
- **词表语义一致**：`RESOLVED_OUTCOMES`、信用权重、统计口径同源。
- **门禁有效**：CI correctness gate 不可 continue-on-error。

### 3.2 已闭环清单（证据见 docs/FULLFIX_REPORT_20260906.md / 20260907.md）

| 项 | 问题 | 修复 |
|---|---|---|
| P0-1 | `core/calibration.py` 同名包遮蔽成死模块 | 迁移 `core/calibration/metrics.py`，删除死文件 |
| P0-2 | `get_public_summary` 假业绩（硬编码 +10%/-5%、假 kelly 1.3x） | 只从真实价算，无价一律 None |
| P1-1 | `attribution.py` 缺 `datetime` import，运行即炸 | 补 import |
| P1-3 | CI `continue-on-error: true`，真实缺陷码永不拦截 | correctness gate 硬拦 F821/F601/E9 |
| F601 | dict 重复 key 静默覆盖 | 合并单键 + 显式 fallback |
| H1 | `_load` 遇未知键整单清空（数据"看起来丢了"） | 白名单过滤 + warning，不清空 |
| R1/R1b | resolve 4 字段会被 dataclass 白名单剥离 | 补字段 + 写→load→save 往返测试 + AST 写键守卫 |
| R2 | `partial` 声明已结算但不进统计 | 信用加权（hit=1/partial=0.5/miss=0），口径统一 |
| R3 | `expiry=0`（退市归零）除零 | 非正价 fail-closed |
| R4 | PIPELINE_FACTS(103/0.55) vs contract(24/0.55) vs 运行时(0.78) 三重漂移 | 单一事实源=iron_gate.py，文档由 generate_docs 生成 |

回归口径：`ruff --select=F821,F601,E9` 全绿 + `pytest` 93 passed（20260907）。

### 3.3 本会话复查结论

对上面十项逐一代码复核，**全部真实落地**：`core/calibration.py` 不存在、
`core/calibration/metrics.py` 存在、`Prediction` dataclass 字段齐全、
`_real_pnl_pct` 覆盖非正价、`PIPELINE_FACTS.md` 的 0.78 与运行时一致、
`test_resolve_write_keys_are_on_dataclass` 存在。结论：**上一轮"同类问题"没有留下
同源未修项**。

### 3.4 已知残余（不属于"同类未修"，是范围外或产品决策）

1. `update_outcomes.py` resolve 仍走裸 dict 直写 JSON，与 dataclass 写路径并存；
   已用守卫测试收口，彻底单写重构留 M3（真价结算前不宜大改）。
2. `scripts/irongate_v2.py`（5 层 0.55）与 `run_all`（0.78）双门禁引擎职责未裁决。
3. 真价闭环依赖 akshare/yfinance 网络可用；当前 2251 条 pending 是真实状态。
4. vendored `scripts/last30days`（PEP701）仍在 correctness gate exclude 名单。

---

## 4. 训练模式 vs 性能模式

### 4.1 正确定义（来自代码与设计文档，不是猜测）

双模式的差异**只有三个维度：模型路由、迭代深度、并发策略**。其余一切
（SAC 方法论、StyleCompiler、IronGate、计算引擎、数据契约、渲染目检）双模式共享
同一套。这就是 `route_policy.py` 写明的原则：**双模式 = 路由策略差异，不是
provider 全换**。

| 维度 | 训练模式（train） | 性能模式（perf） |
|---|---|---|
| 目的 | 质量打磨 + 学习沉淀 | 多报告并发高速交付 |
| 生成 LLM | agent_provider（Marvis 免费草稿）或本地 | DeepSeek（质量红线） |
| 校验 LLM | DeepSeek（终审保底） | agent_provider 或本地（对侧校验，防同源偏见） |
| 迭代深度 | MAX_ATTEMPTS 可配 5-10，Gate 全过 + 审计无 P0 才停 | 默认 3，快速收敛 |
| 流程 | 写 → 审 → 改 → 记（自迭代 + 学习回流） | 一次写对 + 失败段局部重写 |
| 并发 | 不占性能配额，schedule 定时独立跑 | ReportQueue + workers + 输出隔离 |
| 数据复用 | 首轮采集缓存、重试轮复用（20260803 已接线） | 同左 |

代码锚点：`pipeline/e2e_orchestrator.py:1748`（性能默认 3，训练 5-10）、
`pipeline/data_collector.py:709`、`pipeline/checks/llm_checks_mixin.py:157`（生成/
校验对侧模型）、`pipeline/route_policy.py:25`（节点级混编）。

### 4.2 性能模式的三条铁律（20260802 冒烟测试确立）

1. **不整篇重写**：REVISE 只定位失败段，全局性失败返回 None 触发全写并明示。
2. **失败项变化检测**：上轮失败 = 本轮失败 → 提前终止或换策略，禁止无效空转。
3. **state_anchor 记录已修项**：每轮明确"只剩 Y"，收敛加速。

### 4.3 你的问题："训练模式是不是只让 LLM 用 agent，其他还是走方法论/门禁/计算"

**基本正确，但表述要修正两点**：

1. agent 不是训练模式专属。训练模式的核心差异是**廉价生成 + 昂贵终审**的
   两段式（Marvis/本地草稿 → DeepSeek 校验合并）和"写→审→改→记"的迭代深度；
   agent（多实例/圆桌/研究）是两个模式都有的工具形态。
2. 门禁/方法论/计算确实永远走二号自己的模块，不会因为切到训练模式就退化成纯
   LLM 对话——这是双模式最重要的共同底线。

---

## 5. 能否充分理解使用者要求、灵活调整 SAC 侧重

### 5.1 已支持（代码证据）

- **FP8 分析方法选择**：`section_writer.py:973-1010` 注入"采用的分析框架与聚焦维度"，
  支持 `focus`（聚焦维度）与 `slim`（精简维度）。
- **用户要求解析**：`custom_requirement` → `skill_composer.parse_requirement` →
  研究计划 → `侧重维度（权重翻倍）` 注入写作 prompt（`section_writer.py:993-1027`）。
- **决策备忘录场景化**：对必需维度追加"委托方必答问题清单"级引导
  （`section_writer.py:691-770`），并有 `_check_client_questions_coverage` 门禁
  （`iron_gate.py:405`）。

### 5.2 缺口（诚实评估）

1. 目前侧重是**离散的维度级翻倍/精简**，不是连续权重分配；"为什么用户这样要求"
   的意图理解仍是浅层关键词解析。
2. "要求 → SAC 维度映射"没有独立评测集，解析错了用户也看不见（没有"需求覆盖
   率"报告）。
3. 维度的侧重体现在"注入和骨架"，但**没有验证"侧重是否真的改变了正文篇幅/深度
   分布"**——与 KB 方法论不落地是同一类问题：注入层到正文层之间缺可观测性。

**结论**：结构上已具备"随用户要求调整 SAC 侧重"的能力，且强于多数开源 RAG 写报告
方案；离"充分理解"还差"意图工程闭环"（要求澄清 → 约束编译 → 权重分配 → 正文分布
验证），建议并入 §10 的 P1 可观测层一并做。

---

## 6. 诚实回答：四大投行 / MBB / 四大会所 / 顶级券商资深分析师会承认它更强吗

### 6.1 分层回答，避免自嗨

**第一层：作为"个体智识 + 信息优势 + 商业关系"的竞争者——他们不会承认，也不该
承认。** 机构资深分析师的价值不在文字：他们有非公开信息渠道、公司关系、交易台
反馈、历史信誉与"影响力变现"。二号分析师没有这些，所以在这一层没有可比性。

**第二层：作为"标准化深度研究的生产系统"——多数方面已经超他们个人，但他们没有
义务承认，因为承认的收益为负、风险为正。** 真正可比的是：覆盖速度、结构完整度、
数据忠实度（无伪造数字的不变量）、格式一致性、7×24 可重复生产。这些是客观能力，
不需要他们点头才成立。

**第三层：机构会怎么表态**：他们不会说"它比我强"，但会做三件事——买它、并进流程、
用它压初级分析师产能。**"承认与否"不是一个可证伪的问题，可证伪的问题是"有没有
机构真的把它当生产资料"。**

### 6.2 什么条件下才会换来公开承认

给三个可量化的里程碑（都可用现有设施构建）：

1. **引用可验证率**：正文每个关键判断可回溯到数据/证据编号，抽查错误率低于机构
   内部复核标准（需 Citation Gate + 独立 LLM judge，见 §10 P1-2）。
2. **预测校准**：Bold Call/目标价的命中与置信度校准（Brier/ECE）优于新财富级
   分析师历史基线（仓库已建 `core/calibration/metrics.py`，缺真实结算数据闭环）。
3. **盲评一致率**：把报告匿名混入真实研报，请在职分析师盲评，结构/可用性评分
   进入同行中位数以上（当前只缺一个小样本评测协议）。

诚实版结论：**二号真正的对手不是"顶级分析师"，而是"顶级分析师所在机构的生产
流程"。它应定位为 analyst operating system，不是替代品。**

---

## 7. Kimi / token 成本 / 写报告慢 / 本地模型（摘要）

> 详细论证、定价表与代码锚点在 `docs/ANALYSIS_cost_speed_local_20260907.md`，
> 实测瓶颈数据在 `docs/PROFILE_BOTTLENECK_ANALYSIS_20260907.md`，本文只留结论。

### 7.1 调研交给 Kimi 会不会增强

- **会增强"广度与新鲜度"**（agentic 多步检索、长上下文整合），前提是产出走统一
  证据 schema 入库、写作侧只消费已封存证据（Evidence-First，§9）。
- **不会增强"方法论落地与忠实度"**——那取决于注入与门禁，不取决于调研者是谁。
- 不要"调研即写作"：调研负责"拿到什么"，二号负责"怎么用、用什么、不用什么"。

### 7.2 成本与速度（一句话结论 + 交叉引用）

- Kimi 不是最贵但也不便宜；DeepSeek 缓存命中可低一个数量级。正解是**分层路由**：
  本地搬走批量短任务，DeepSeek 扛质量红线，Kimi 只打 agentic 硬调研。
- "并行到顶还慢"的真根因是**串行收尾链 + 偶发灾难性慢调用（重尾）**：实测
  `research_planner` 中位 155s（最差 20 分钟，已修：45s 共享预算熔断）、
  `write_sections` 中位 107s（最差 41 分钟，段级 profile 待做）；charts 只有 1.5s，
  给 charts 写缓存是伪优化。
- 下一步不写缓存：先段级 profile write_sections、修重尾（全局耗时预算 + 熔断）、
  把 attempt 轮收敛为"失败段重写 + diff merge"。

### 7.3 本地 qwen3-30B-A3b

- 能接（Ollama 自动注册），但当前只是 priority=9 的最后兜底，健康云链路轮不到。
- MoE 激活 3B，**撑不起 2 万字跨章一致性/So What/Bold Call**，禁止承担
  write/merge/revise 质量红线。
- 正确用法：`NODE_PROVIDER_EXTRACT=ollama_local`（抽取/分类/短校验）、训练模式
  草稿、critic 冗余席、对侧校验；先小样本对比 Gate 失败率再放量。

---

## 8. 知识库方法论落地：上一轮"升级"后，问题解决了吗

### 8.1 审计结论

**没有真正解决。** 本会话对"KB/MKB 注入 → 正文引用"全链路做了磁盘实测，发现三处
结构性硬伤 + 一处盲区；最近完成的完整报告（`output/贵州茅台_cicc.md`、`_gate_check.md`，
各约 142KB）正文分别只有 **1 处 `[KB...]`、0 处 MKB 痕迹**，直接印证。

### 8.2 证据链（均可复现）

**硬伤 1：KB/MKB 的总开关是一个无关信号。**

`pipeline/section_writer.py:2577-2592` 的 prompt 组装里，`kb_str`、`mkb_str`、
`valuation_kb_str`、`policy_str`、`consulting_str` 等 15 个注入块全部包在
`if _tm_str:`（工具模块开关）的块内。`_tm_str` 来自
`compute_results.tool_modules.modules`，只要工具模块为空/全部 skip，**KB 检索到
内容也整段不注入**。实测注入侧 `_inj_kb_str` 能取到结果（FTS5 命中），但写作侧
被开关吞掉。

代码锚点：`pipeline/section_writer.py:2339`（取 `_tm_str`）、`:2344-2354`（取
`kb_str`/`mkb_str`）、`:2577-2592`（组装处的错误包裹）；
`pipeline/prompt_injectors.py:877-884`（注册表：`_tm_str` 排在 `kb_str` 前）。

**硬伤 2：串行写作路径从不注入 KB/MKB。**

`section_writer.py` 串行分支 `_write_segment` 调用 `_build_prompt_v4`
（`:1091` / `:1108` / `:1186`），`_build_prompt_v4`（`:1233`）只拼 SAC 维度定义、
数据锚卡、单一事实源、FP8 计划等，**没有 build_injections / kb_str / mkb_str**。
也就是说 KB 注入只存在于并行路径，`dimension_parallel=False` 时方法论知识库完全
缺席。这也意味着"同一份报告，串行/并行两种跑法产出的知识输入不同"——模式间特性
不一致。

**硬伤 3：检索白名单排除了最该给方法论的那几个目录（且代码复制了三遍）。**

`core/knowledge_base.py` 的 `search()` 对非指定类别检索加白名单，只放行名称含
"观点 / 行业 / 估值 / 回测 / 原始"的类别（`:181-207`，同一段代码重复三次，复制粘贴
残留）。实测 `data/kb_fts.db`（422MB / 122,422 chunks）类别分布：

| 类别 | chunks | 是否在白名单 |
|---|---|---|
| 04-回测基线库 | 76,336 | 是（回测） |
| 02-行业与公司研究 | 20,576 | 是（行业） |
| 03-估值与测算 | 16,660 | 是（估值） |
| 05-Excel知识库 | 6,970 | 否（教学，符合 V1 排除意图） |
| 01-宏观分析框架 | 1,691 | **否（方法论被误杀）** |
| 07-原始文档提取 | 92 | 是（原始） |
| 06-PPT排版美学 | 60 | 否（教学） |
| 08-四大审计方法论 | 17 | **否（方法论被误杀）** |
| 09-国际投行方法论 | 10 | **否（方法论被误杀）** |

注释写明 V1 修复动机是"排除 Excel/PPT 教学"，但实现把 01/08/09 三个方法论目录一起
误杀了——而这些恰恰是"方法论"而不是"数据"，正是本轮要救的内容。

**盲区 4：没有"注入 → 正文引用 → 体现率"门禁。**

- 注入器契约只有入口没有出口：`build_injections` 保证注入不失败，但不保证注入
  被消费；
- `pipeline/checks/methodology_compliance.py` 只做关键词弱检查（生命周期/利润池/
  竞争/估值），命中即 passed，warning 级，不拦"KB 一个没用"；
- 无任何 check 统计 `[KB#]`/`[MKB#]`/`[E#]` 在正文的覆盖率；IronGate 现有引用类
  检查（`inline_citations`、`evidence_coverage`、`client_questions_coverage`）都
  不指向知识库注入。

### 8.3 "升级"改了什么（公平归因）

09-06/07 相关提交确实做了大量邻域升级：Phase A-E（evidence chain、hypothesis
plan、data contract、intent+KG、kg_peers 注入）、golden numeric 46 条、数据锚卡、
contamination 清理等，质量方向正确。但它们改的是"证据/数字/竞争格局弹药"的注入，
**没有触及 KB/MKB 方法论的组装逻辑**——注入器文件在 08-24 Strangler-Fig 重构后就
没有针对 KB 总开关/串行缺口/白名单做过修正。所以表现为"升级了，但知识库方法论
依然进不了报告"。

---

## 9. 网上同类问题与顶级解法

### 9.1 问题的学名

这不是"模型笨"，是一组有名字的失败模式：

- **faithfulness failure / citation hallucination**：知识给了但正文与来源不符或
  无引用；
- **Lost in the Middle / context blindness**：注入被埋在 2 万字 prompt 尾部，
  中段上下文被模型无视；
- **knowledge-use gap（检索增强不生效）**：中文社区经验（非严格统计）估算约 65%
  "注入了不用"的案例可归因于检索排序 + prompt 设计，而非模型能力；
- **retrieval 目录误伤**：过滤规则把"有用"和"垃圾"一起删了（本仓库正是此例）。

### 9.2 五类顶级解法 → 病灶映射

| 病灶 | 顶级方案 | 借鉴点 |
|---|---|---|
| 写作时才临时注入，知识没有先被"选中封存" | STORM（outline-guided retrieval）；RAG4Reports 的 Evidence-First + Source Gatekeeping（EFSG，"seal 封存"） | 检索前移到规划期，产出"本报告每节用哪几条方法论"契约，写作只消费契约 |
| 引用无契约、无强校验 | WueRAG（无引用标记的句子直接剔除）；Bedrock Knowledge Bases 的 citation precision/coverage；Azure AI groundedness detection；Anthropic 多智能体研究（独立 LLM judge 检引用，不让同一个 agent 边写边自检） | 引用覆盖率/忠实度成为 IronGate 硬检查；judge 与 writer 分离 |
| 检索纪律差 + 目录误伤 | Azure enterprise-rag-stack / GPT-RAG；券商双层 agent（信息检索层 + 方法论层分离）；MinerU / Docling 先把 PDF 文本化 | 方法论库 vs 证据库双通道；混合检索 + 重排；allowlist 显式化 |
| 模型抗噪/易忽略上下文 | RAFT（训练时忽略 distractor 的样本）；Self-RAG（reflection 判断检索与生成是否够格）；CRAG（检索结果自查纠错） | 给模型"够用就停"的信号，而不是无限塞知识 |
| 没有端到端可观测与评测 | RAGAS（faithfulness/context precision）；Anthropic 建议从 20 条小样本评测起步；evaluation-driven development | 注入非空 → 断言必含 → 正文引用数可查 → 回归样本集 |

代表性资料（社区/论文/X 常被引）：STORM、RAG4Reports、RAFT、Self-RAG、CRAG、
RAGAS、WueRAG、Anthropic "How we built our multi-agent research system"、
Azure GPT-RAG / enterprise-rag-stack、华鑫/中泰等券商研究所 LLM 研报实践、
MinerU / Docling。外链在文末附录。

---

## 10. 落地计划：P0/P1/P2（文件 + 行号 + 改动点 + 验证口径）

原则：先解"总开关/路径缺失/白名单"三个必现 bug，再上"引用契约 + 可观测"，最后
做 evidence-first 结构性重构。每步都带回归测试，防止回到"改完依然没人用"。

### P0-1 解耦 KB/MKB 注入的总开关（必现 bug）

- 文件/位置：`pipeline/section_writer.py:2577-2592`
- 改动：把 `ev_str/mc_str/rp_str/macro_str/valuation_kb_str/policy_str/esg_data_str/
  ma_cases_str/segment_rev_str/consulting_str/market_seg_str/analogy_str/kb_str/
  mkb_str` 从 `if _tm_str:` 大块中移出，各自独立 `if xxx_str:` 注入；`_tm_str` 只
  管它自己的工具模块块。
- 验证：构造 `tool_modules` 为空/全 skip 的 data_context，断言组装后的 prompt
  仍含 `## [知识库参考]` 与 `## [方法论知识库精选]` 两个块头；新增单测覆盖
  "kb/mkb 非空 + tm 空 → 注入仍出现"。

### P0-2 串行路径补齐 KB/MKB（路径缺失）

- 文件/位置：`pipeline/section_writer.py` `_write_segment`（约 `:1083-1120`）与
  `_build_prompt_v4`（`:1233`）
- 改动：抽一个轻量 `_kb_mkb_for(asset, report_type, data_context)`（复用
  `_inj_kb_str`/`_inj_mkb_str`），串行路径在骨架与正文 prompt 各注入一次；保持与
  并行路径同一套函数，杜绝"两套实现"。
- 验证：`dimension_parallel=False` 时同样出现 KB 块头；同一资产串行/并行两种跑法
  的注入块一致性测试。

### P0-3 检索白名单修正 + 去重（目录误伤）

- 文件/位置：`core/knowledge_base.py:181-207`
- 改动：删除三份重复代码，抽 `_relevant_categories(conn)` 单函数；白名单从
  "名称关键词"改为显式 allowlist 常量，纳入：02-行业与公司研究、03-估值与测算、
  04-回测基线库、07-原始文档提取、**01-宏观分析框架、08-四大审计方法论、
  09-国际投行方法论**；05/06（Excel/PPT 教学）维持排除并写注释说明意图边界；
  目录名变化时给出告警而不是静默漏检。
- 验证：`search("DCF 折现 审计 核查 勾稽")` 能命中 08/09 类目；新增"方法论目录
  必在 allowlist"的索引级单测。

### P1-1 检索纪律：方法论双通道 + 查询去泛化

- 文件/位置：`pipeline/prompt_injectors_p3b.py:71-149`、`core/methodology_kb.py`
- 改动：
  - 查询从"资产 + 报告类型 + 估值"（OR MATCH，泛词主导）改为：方法论通道
    （SAC 维度 ID + 报告类型映射词 + methodology tags）与数据通道（资产/行业/
    数据词）分离，各取 top-k；
  - `_inj_mkb_str` 的 docstring 说 6 条、代码默认 8 条（`methodology_kb.py:136`
    `max_items=8`）——对齐契约；
  - 注入块前移 + 按段注入：KB/MKB 不要只挂在整篇 prompt 尾部（Lost in the
    Middle），中后段写作时重复注入与该段维度最相关的方法论条目。
- 验证：检索命中里方法论类目占比可观测；抽样对比改造前后正文 `[KB#]` 引用数。

### P1-2 引用契约 + 强校验（最关键的"消费端不变式"）

- 文件/位置：新增 `pipeline/checks/kb_citation_mixin.py`，注册进
  `pipeline/iron_gate.py`（约 `:400-420` 检查列表）；配套
  `pipeline/section_writer.py` 组装处
- 改动：
  1. **注入断言**：`build_injections` 返回后，若 `kb_str/mkb_str` 非空，写审计日志
     `kb_retrieved=... injected_chars=...`；为空时降级日志（用于区分"没检索到"与
     "检索到但没注入"两类失败）；
  2. **引用覆盖检查**：KB/MKB 注入非空时，正文 `[KB#]`/`[MKB#]`/方法名回指 ≥
     注入条数的一定比例（起步 50%，warning；基线稳定后上调并阻断）；
  3. **忠实度 judge**：抽 N 句（20 条起步）做独立 LLM judge 的 faithfulness 抽查
     （writer 与 judge 分属不同 provider，防同源），可用 RAGAS 指标定义；
  4. **报告级 KB 附录**：正文尾附"本报告采用的知识库方法论文档清单"，双向可查。
- 验证：构造"注入 5 条但正文 0 引用"的 fixture，断言 check 变红；新增
  `test_kb_citation_coverage` 三态测试（无注入跳过 / 有引用通过 / 无引用告警或
  阻断）。

### P1-3 端到端可观测漏斗

- 文件/位置：新增 `harness` 或 `pipeline` 下 `kb_usage_metrics`；Gate 检查消费
- 改动：每份报告输出 JSONL：`kb_retrieved_count / kb_injected_chars / mkb_hits /
  kb_citation_marks / sections_with_kb / injection_nonempty_but_zero_citation`；
  IronGate 检查项与现有 `inline_citations`/`evidence_coverage` 并列展示，结果进入
  Gate 报告，让"知识库方法论体现率"成为可回看、可对比的指标（含串行 vs 并行两路）。
- 验证：两份真实报告的 JSONL 可生成且数字与人工抽查一致。

### P2-1 Evidence-First 重构（治本方向）

- 借鉴 STORM/EFSG：把 KB 检索从"写作时 build_injections 临时拉"前移到
  `research_planner`，产出"方法论运用契约"（每节用哪几条方法论文档、目标是什么），
  写作侧只消费契约；与仓库已有的 Phase A-E evidence chain / hypothesis plan 同构。
- 收益：注入变成规划产物，天然带引用与覆盖率，且可被同一套数据契约校验。

### P2-2 评测集 + 消融

- 固定 5-10 个代表性样本（覆盖 4 种报告类型 + 1 个决策备忘录），每轮 KB/写作改动
  跑 diff：KB on/off、旧注入 vs 新注入 两组消融，指标 = 引用覆盖率 + RAGAS
  faithfulness + 人工盲评一致率；防止"本次修好、下次回退"（对标 Anthropic
  evaluation-driven development 的 20 样本起步思路）。

### P2-3 本地模型分层

- qwen3-30B-A3b 承担 KB 分类、方法论文档与段落匹配、引用覆盖首遍扫描；
  DeepSeek 主写；本地结果只做候选，最终由 Gate 裁决。避免微调，先用上下文裁剪 +
  高信号 3-5 条方法论 + 强制引用格式验证收益。

---

## 11. "一劳永逸"的诚实答案

**不存在"注入一次就永远生效"的银弹。** 原因是 LLM 没有"读了就必须用"的语义保证；
任何靠提示词祈求的行为都会随上下文长度、模型版本、任务类型漂移。业界收敛的做法是
把"使用知识"从**模型的可选项**变成**结构的必经项**：

1. 证据前置封存（写作前就定好每节用什么方法）；
2. 引用契约 + 后处理强校验（无引用的产出被检测/剔除/重写）；
3. 消费端不变式 + 可观测漏斗（注入非空、引用存在、体现率达标，任何一环缺失即
   告警/阻断）；
4. 小样本评测集长期回归（每次升级跑 diff）。

对二号而言，最小高收益组合 = **P0-1 + P0-2 + P0-3（修注入三硬伤）+ P1-2 引用
覆盖率检查 + P1-3 观测漏斗**。这一组合不改模型、不动 SAC、风险面小，却能把
"知识库方法论体现率"从不可见变成被门禁强制。

---

## 12. 决策与未决清单（供下一轮排期）

1. P0-1/P0-2/P0-3 是否立即执行（建议：是，改动集中在 3 个文件，均带单测）。
2. P1-2 的引用覆盖率阈值起步值（50% warning）与升级阻断时机，需要 2-3 份真实报告
   基线后定。
3. IronGate v2（5 层 0.55）与 run_all（0.78）双门禁职责是否裁决（独立于 KB 计划）。
4. resolve 单写路径重构（M3）与真价结算网络依赖的时间窗。
5. §6.2 的三个"对外承认"里程碑要不要立项（引用可验证率 / 校准 / 盲评），如需可
   单开评测协议。

---

## 13. 本审计证据与复现命令

```text
# 注入总开关实证（data_context 取自真实运行的 _last_data_context）
pipeline/section_writer.py:2577-2592   kb/mkb 等 15 块被 if _tm_str 包裹
pipeline/prompt_injectors.py:877-884   注册表：_tm_str 先于 kb_str/mkb_str
pipeline/prompt_injectors_p3b.py:71     _inj_kb_str（FTS5 top-5，命中可为空）
pipeline/prompt_injectors_p3b.py:112    _inj_mkb_str（build_block，max_items=8）

# 串行路径无注入
pipeline/section_writer.py:1091/1108/1186  _write_segment → _build_prompt_v4
pipeline/section_writer.py:1233             _build_prompt_v4 无 kb/mkb

# 检索白名单（三份重复 + 方法论目录被排除）
core/knowledge_base.py:181-207
sqlite3 data/kb_fts.db → category 分布见 §8.2

# 弱检查（无引用契约）
pipeline/checks/methodology_compliance.py:9

# 正文证据
output/贵州茅台_cicc.md    [KB]引用 1 处，MKB 0 处
output/_gate_check.md      [KB]引用 1 处，MKB 0 处

# 回归
ruff --select=F821,F601,E9 core pipeline web export scripts harness → All checks passed
pytest → 93 passed（20260907 基线）
```

---

## 附录 A：本会话已产出文档引用

- `docs/FULLFIX_REPORT_20260906.md`（死模块/假业绩/CI 门禁等全量修复）
- `docs/FULLFIX_REVIEW_20260907.md`（R1-R4 复核）
- `docs/FULLFIX_REPORT_20260907.md`（R1-R4 修复闭环，93 passed）
- `docs/ANALYSIS_cost_speed_local_20260907.md`（成本/速度/本地模型全景）
- `docs/PROFILE_BOTTLENECK_ANALYSIS_20260907.md`（424 行 PROFILE 实测瓶颈）
- `docs/FIX_REPORT_research_planner_budget_20260907.md`（45s 共享预算熔断）
- `docs/engineering-plan-dual-mode-20260802.md`、`engineering-plan-performance-mode-20260802.md`

## 附录 B：外部参考（社区 / X / 论文 / 顶级项目）

- STORM（Stanford，outline-guided retrieval + 写作）
- RAG4Reports：Evidence-First + Source Gatekeeping（EFSG，证据封存）
- RAFT（检索感知微调，学会忽略 distractor）
- Self-RAG（reflection：检索与生成自评）
- CRAG（Corrective RAG，检索结果纠错）
- RAGAS（faithfulness / context precision 评测）
- WueRAG（无引用句剔除）
- Anthropic：multi-agent research system（独立 judge + 20 样本评测起步）
- Azure enterprise-rag-stack / GPT-RAG（生产级 RAG 引用与治理）
- AWS Bedrock Knowledge Bases（citation precision/coverage 指标）
- 华鑫/中泰等券商研究所 LLM 研报实践（双层 agent：检索层 + 方法论层）
- MinerU / Docling（PDF 文本化，供知识库建索引）
- Lost in the Middle（Liu et al., 2023）——长上下文忽视中间内容
