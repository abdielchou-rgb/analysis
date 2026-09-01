# 二号分析师（2hao-analyst）深度审计报告

**审计日期**：2026-09-01
**审计范围**：`D:\Claude\projects\2hao-analyst` 全仓（~11 万行 Python，不含 .venv/legacy）
**审计方式**：目录结构测绘 + 4 路子代理并行审查（数据层/管线门禁/意图框架/测试验证）+ 核心文档精读 + 运行产物实证核对
**证据口径**：所有结论均带文件路径或运行产物证据；对"声称 vs 现实"做了逐项比对

---

## 〇、总判断（三问一句话回答）

1. **这是什么项目、能力效率、能否实现设计目标？**
   这是把投行/MBB/四大的隐性方法论工程化为可复用 AI 分析引擎的**意图驱动报告系统**。数据层（akshare/本地库）、计算引擎（真实数值计算）、门禁体系（99 项真实检查）骨架**真实存在且质量不低**；但**一次端到端运行成功率极低**——最近三次（8/29-8/31）全部 Gate 失败，历史成功产物多靠人肉补丁链驱动。**设计目标（"超越人类资深分析师的超级智能系统"）尚未达成**；当前的真实状态是"方法论工程化原型 + 高设计低兑现"，而非"可稳定交付的投研引擎"。

2. **基于第一性原理，自洽吗？**
   **宪法层高度自洽，落地层多处断裂。** FP0-FP8 八条法则的推导结构（方向→能力→边界→演化→透明→生存→元认知）和冲突裁决规则是自洽的；但"声称"与"实现"之间存在系统性错位：FP5 收敛指标是 stub、FP3 六维收敛没有测量基线（quality_trends 0 条）、FP7 反脆弱实际靠人肉补丁、同一事实四种口径（IronGate 检查数 78/96/99/49 并存）。**自洽性断裂点集中在"测量与验证"——宪法要求的一切收敛都以可观测为前提，而可观测层是瘫痪的。**

3. **与顶级项目还有哪些差距？**
   差距不在设计理念（STORM 的 perspective→question→cite 思路 2hao 都有对应物），而在**验证闭环、引用粒度、可观测性、工程纪律**四条硬差距：无 claim-level 引用（来源标注率 ≥30% 而非逐句溯源）、无真实回测（12 条预测全 pending、backtest 0 条）、CI 从未通电（git 无 remote）、测试套件当前为红（7 项失败）且覆盖率 35.8% 关键模块 0。**一句话：理念领先、兑现落后、验证空白。**

---

## 一、这是什么项目？真实能力与效率

### 1.1 项目本质与规模

| 维度 | 实测 | 证据 |
|---|---|---|
| 定位 | "意图驱动的智能分析系统"——回答委托方必答问题，非生成"看起来完整"的报告 | README.md L3-5 |
| 代码规模 | core 228 文件 / ~50k 行；pipeline 68 文件 / ~30k 行；scripts 132 文件 / ~24k 行；export 18 文件 / 5.6k 行 | 目录统计 |
| 测试 | 89 个测试文件，564 用例收集，**当前 7 项失败** | .pytest_cache/lastfailed |
| 版本 | 49 个 git commit（8/24 首次提交，此前 0 提交被列为 P0） | git log |
| 方法论资产 | 16+ SAC YAML、20 框架 YAML、5086 个 benchmark/golden 语料文件、16 份 deep_reports | core/frameworks、benchmark/golden |
| 数据底座 | financials.db 669MB、kb_fts.db 422MB、observability.db 8955 条 LLM 调用、learning_data.db 19640 条失败记录 | data/ |

架构：双路径——批量/标准化走确定性管线（E2EOrchestratorV2 23 节点图 + SAC + IronGate），深度/高险走工作台混合（数据层 + Claude 直接写 + 用户门禁）。三通道 LLM（DeepSeek/OpenRouter/Marvis），7 个 provider 注册。

### 1.2 真实能力盘点（哪些是真的）

**数据采集（8/10）**：akshare 真实接入（财务摘要/主营构成/资金流/同业对比，data_collector.py L600-717）；Tavily+LLM 提取结构化数据（L446-542）；本地 financials.db/qlib_bin 读取（L361-443）。数据新鲜度到 8/24-8/31，capital_flow/company_events 接近实时。yfinance 仅取市值且硬编码 .SS 后缀（L545-560）。

**计算引擎（8.5/10）**：**真实数值计算，非 LLM 生成**。run_dcf（两阶段+戈登增长+敏感性表）、run_comparable（PE/PB/EV 中位数）、run_scenario（Bull/Base/Bear 加权）、三表勾稽、Damodaran ERP 均为纯函数实现（core/compute/compute.py）；结果经 ComputeInjector 确定性替换占位符注入正文，而非 LLM 后解析（compute_engine.py L296-413，e2e L323，section_writer L872）。估值护栏已接线（valuation_guardrails.validate_dcf_guards）。

**门禁体系（真正在拦）**：IronGate `run_all` 引用 99 项检查，与 checks/ 各 mixin + 本体定义一一对应、无死引用。阻断语义真实：`passed = all(c.passed for c in checks if c.severity == "error")`（iron_gate.py L503-506），warning 不计入阻断。出口 report_gate 叠加 ChartCheck/VisualGate/AICleanCheck/ProductValidation 多道硬阻断。**8/31 三次运行被拦在 Gate 恰好证明门禁是真的。**

**写作（部分真实）**：section_writer.py 2969 行巨石文件，但 30 个注入器已抽成注册表（commit d81c31b）；StyleCompiler 3 条确定性规则真实改写文本（conclusion_first 翻句首/remove_ai_patterns 删 8 口头禅/ensure_judgment_density 阈值），有测试断言"值得注意的是"被清除（test_e2e.py L75-76）。

**意图层（半真实）**：intent_parser 生成必答问题（4 类模板+关键词定制），intent_gate 仅对 decision_memo 硬阻断（覆盖<60% 置 failed，e2e L857-891），其余报告类型是日志级。关键词近似宽松（"市场/规模/风险"任何报告必出现）。

**LLM 通道（9/10，本仓最扎实的模块）**：7 provider 注册 + 熔断（5 次失败指数退避）+ 滑动窗口限流 + 健康预检（5s 探测 /models）+ 全量回退 + agent 落盘兜底（带质量护栏）。OpenRouter 流式聚合解决长响应截断。

### 1.3 效率与成功率的现实

| 指标 | 实测 | 证据 |
|---|---|---|
| 运行频率 | 8/7-8/31 共 8955 次 LLM 调用；8/26-8/30 单日 912-2268 次，高频运行 | observability.db |
| 最近三次端到端 | **全部失败**：浙江觉纤 3 轮 score 0.813/0.833/0.825 全被 Gate 拦；商业航天 charts 0.4 连挂 3 次；觉纤光电图表 3/8 降级 data=template | output/*_err.log、marvis_e2e_run.log |
| 最近成功交付 | 商业航天报告 8/10、油位 v5.5 8/8（docx+pdf）、柯力传感 8/2、芯联集成 7/29 | output/ 时间戳 |
| 成功方式 | **人肉补丁链**：油位报告 v2.3→v5.5 约 40 版，靠 patch_oil_v23.py~v55 系列 + rerun_gate_v5*.py + fix_*.py 6 个定向打补丁 | scripts/、根目录 |
| 质量硬伤残留 | _gate_prev.md 16 处占位符/坏标点；失败产物含"目标价38.40元（数据来源：公司年度报告）"这类无来源锚点；GBK 乱码史 | output/_gate_prev.md |

**效率结论**：单次成本不低（3 轮写改循环 × 每轮多节点 LLM），成功率低到"3 次连挂"，且能交付的报告深度依赖人肉介入。**这不是"自动跑 15 分钟出一份报告"（FP3 宣称 <15 分钟），而是"跑 3 轮失败→人肉补→再跑"的准手工流程。**

### 1.4 设计目标（FP1/FP3）达成度逐条对照

| 宪法目标 | 现状 | 判定 |
|---|---|---|
| FP1 超越人类资深分析师 | 报告结构/深度已接近机构模板，但数据密度、引用、稳定性不达标 | 未达成 |
| FP3-1 速度 <15 分钟/份 | 单次运行 + 3 轮重试远超；靠补丁链则以天计 | 未达成 |
| FP3-2 广度 ≥3 市场/并行 30 家 | akshare A 股为主，港股/美股仅 yfinance 硬编码 | 部分 |
| FP3-3 深度 7 层归因/3 参照系 | SAC 维度齐全，但 So-What/参照系检查常失败（8/31 即败于此） | 部分 |
| FP3-4 记忆：gate_pass_rate +5%/版 | **无收敛测量**；learning_data 有记录但收敛指标 stub | 未达成 |
| FP3-5 协作 5+ agent 辩论 | debate_engine/adversarial_committee 存在，接线程度未验证 | 待验证 |
| FP3-6 持续 7×24 恒定质量 | 高频运行但 Gate 通过率低 | 未达成 |
| FP4 双阈值图灵测试 | StyleCompiler 下阈真实；judgment_density 0.8<1.2 连续失败，自己过不了下阈 | 未达成 |
| FP5 演化闭环 | 记账真实（19640 条），回放是文本提示注入，收敛指标 stub | 未达成 |
| FP6 推理透明 | 报告含推理链；数据溯源到字段级未实现 | 部分 |
| FP7 反脆弱 | 期权性真实（多 provider）；但"优雅降级"靠补丁而非系统 | 部分 |

**设计目标判定**：作为一个"超级智能分析师系统"——**未达成**。作为一个"机构方法论工程化原型"——**已成型且局部扎实**（计算、门禁、LLM 通道是真材实料）。

---

## 二、第一性原理自洽性评估

### 2.1 宪法体系本身（设计层）

FP0（意图第一）→ FP1（方向）→ FP2a/b（数据/分析履约）→ FP3（上限）→ FP4（下限）→ FP5/6（时间/空间轴）→ FP7（生存轴）→ FP8（元认知）的推导链是自洽的，冲突裁决顺序（FP4>FP2a>FP2b>FP6>FP7>FP5>FP3>FP1）逻辑成立。"执行层可靠、推理层聪明"的分工也正确。**这一层没有问题。**

### 2.2 自洽性断裂点（实现层，按严重度排序）

**断裂 1：收敛要求 vs 无测量基线（FP3/FP5 空转）**
宪法要求"每版本 gate_score 日方差降 20%""复发率月环比降 50%"——但 `observability.db` 的 `quality_trends` **0 条记录**、`validate_history` 仅 17 条空记录（7 月调试期）。FP3 的收敛曲线公式是纸面宣言，因为**没有测量就没有收敛**。`learning_loop.recurrence_rate` 返回空 dict、`auto_apply_lessons` 是 stub（learning_loop.py L192-198）——FP5 的"收敛指标"从未实现。

**断裂 2：数据零编造宪法 vs 交付物实际状态**
FP2a 要求"零编造、零幻觉、诚实标注不可得"，但：section_writer.py L551/L1171 仍硬编码"托肯恒山/富仁高科"客户案例数据（P0-5 残留副本）；失败产物有"目标价 38.40 元（数据来源：公司年度报告）"这种无具体来源的锚点数字；forward_picks.csv 预测记录自身数据错误（比亚迪 current_price=11.37、格力 142.68、base_target 多数为 0.0）。**宪法最重的一条，实现层最脏。**

**断裂 3：门禁声称 vs 现实（四种口径）**
README/SKILL 宣称"78 项"，PIPELINE_FACTS 96 项，代码实测 run_all 引用 99 项，一次成功运行快照 n=49。**同一事实四种口径并存**——治理不自洽的直接证据（虽然活门禁是真的）。

**断裂 4：防线声称 vs 通电状态**
ci.yml 配置合理（matrix+golden_check+secrets 扫描）但 **git remote 为空，CI 从未触发过**；测试套件**当前为红**（lastfailed 7 项：test_r88_numeric_chain、test_e2e、test_blindspot_modules×4、test_r78_geopolitical）。覆盖率 35.8%（coverage_baseline.json），advanced_charts/assumption_benchmark/probabilistic_deep_check 等核心文件 **0 覆盖**。

**断裂 5：FP7 反脆弱 vs 补丁链现实**
宪法要"因冲击变强"，现实是油位报告 v2.3→v5.5 靠 40 版一次性 patch 脚本才交付——**这恰恰是脆弱的标志**（每份报告都在重走调试地狱）。L1/L2/L3 降级是纸面：商业航天 charts 失败连挂 3 次 score=0.4，系统没有"部分产出"（L1 降级应允许交付）。

**断裂 6：出口指纹可绕过（FP7d 的洞）**
`_verify_pipeline_fingerprint` 三处绕过洞：① `glob("*_pipeline_fingerprint.json")` 取 matches[0]——**跨资产复用指纹可放行**；② JSON 解析失败"放行"；③ 明文 JSON 无签名/无正文绑定，可手工伪造改名。设计意图（只认管线产物）被打了三个洞。

**断裂 7：可观测瘫痪**
observability.db 记录了 LLM 调用（8 月下旬高频），但 validate_history/quality_trends 停更——**系统在运行，但质量层在失明**。这解释了为什么 Gate 分数能停在 0.83 连续三轮不收敛：没有趋势数据，无从判断是偶发还是系统性退化。

**断裂 8：双模路由文档 vs 代码**
route_policy.py 已按 perf/train 节点混编并真实接线（e2e L610-616），一致性 OK；但 RUN_MODE 语义未在文档集中说明，"DeepSeek 主 vs OpenRouter 主"的历史矛盾虽已解决，残留文档仍有旧表述。

**自洽性结论**：**宪法系统自洽，实现系统不自洽。** 断裂的共性根源只有一个：**验证与测量层从未被真正通电**。所有自洽性要求（收敛、演化、降级、问责）都以"能测量输出质量"为前提，而测量层（quality_trends=0、backtest=0、CI=未跑、覆盖率=35.8%）是全线空白。

---

## 三、与顶级项目的差距

### 3.1 对标基准

- **长文生成**：Stanford STORM / Co-STORM（31k stars，pre-writing 多视角问题生成 + claim-level citation + DSPy/litellm）
- **投研数据**：Bloomberg Terminal、Wind、AlphaSense、Visible Alpha（实时 tick、一致预期、评级-收益追踪）
- **LLM 工程质量**：LiteLLM 网关、DeepEval/Promptfoo evals、Instructor 结构化输出、LangGraph/Temporal durable execution
- **机构研报**：高盛/中金/贝恩（数据来源可点击、合规、评级纪律、可审计）

### 3.2 十大差距（按"对达成设计目标的影响"排序）

**差距 1：引用粒度——报告级 vs 论断级（最实质的产品差距）**
STORM 要求每个论断落引用（claim-level citation）；2hao 是"来源标注率 ≥30%"、inline_citations 检查 0/2 就警告（8/31 浙江觉纤失败项之一）。AUDIT_20260824 也点名此点，commit fcaf202 声称做了"claim-level provenance appendix"，但 inline_citations 连续失败说明**未真正落地**。没有逐句溯源，FP2a/FP6（零编造+推理透明）就没有抓手，也没法对"目标价 38.40 无来源"这类硬伤做系统化拦截。

**差距 2：评估闭环——自评 vs 独立验证**
顶级系统：golden 评估集 + 相对基线容差 + CI 阻断 merge + LLM-as-judge 对侧。2hao：`benchmark/golden/` 5086 个文件是**语料库不是评估集**（用途是风格吸收）；`tests/golden/` 11 个文件的 eval_gate 是确定性正则门禁（有双层阈值，是真实资产）；r80"机构评审"是角色扮演模拟；`benchmark_compare` 因 0 条已验证预测**永远返回"暂无已验证预测"**。**没有独立验证层，所有 score 都是自证。**

**差距 3：预测问责与回测——宪法要求 vs 零落地**
FP2b/FP5 要求 Bold Call 追踪、到期对比、准确率统计。现实：forward_picks.csv 12 条预测**全部 pending 未验证**，predictions.json 仅 3 条，backtest_results **0 条**。对比 IBES/StarMine 的评级-收益追踪、Bloomberg 的回测工具——**2hao 的预测系统从未闭环过一次**。这是"超级智能"声称最脆弱的一环：没有预测记录，就无从证明比人类分析师强。

**差距 4：可观测性与质量趋势——空白**
Bloomberg/顶级量化团队有完整的 metrics 面板。2hao 的 quality_trends=0 条。**没有趋势数据，FP3 的"gate score 日方差降 20%"、FP7 的"半年统计显著上升"都不可验证。** 观测瘫痪是自洽性断裂的根，也是与顶级差距的根。

**差距 5：CI/CD 与交付纪律——从未通电 vs 必须全绿**
顶级项目 PR 合并前测试必全绿、lint 必过、eval 必过。2hao：CI 从未运行（无 remote）、测试套件当前红、覆盖率 35.8%。pre-commit（ruff+SDD 钩子）已修复是进步，但**没有任何远程门禁**。AUDIT_20260824 的 P0-2（0 提交）已修，P0-4（假测试）部分修复，P0-5（硬编码）残留。

**差距 6：数据新鲜度与覆盖——静态本地库 vs 实时数据牌照**
akshare + 本地 financials.db 对 A 股够用；但港股/美股覆盖薄弱（yfinance 硬编码 .SS）、一致预期是本地静态快照、无实时 tick/新闻流。真实机构有 Wind/彭博/TickData/卖方一致预期数据库。**数据深度决定分析深度上限**——2hao 的 TAM/份额/竞对数据大量依赖 Tavily 搜索 + LLM 提取，这决定了它无法稳定做出"数据密度 13.3/千字"（FP4 金牌基准）级别的报告。

**差距 7：工程化——巨石 vs 类型化+durable execution**
section_writer 2969 行、e2e 2177 行、analysis_mixin 1932 行、data_quality_mixin 1656 行。虽有 typed PipelineContext（commit 30dbcb3）和 30 注入器注册表（d81c31b）这些**真实的进步**，但巨石仍在，改造成本指数上升。顶级用 LangGraph/Temporal 每节点持久化 checkpoint、类型化状态。

**差距 8：测试覆盖与核心数值验证——35.8% vs 关键路径 80%+**
run_dcf/run_comparable 的数学正确性缺独立单元测试（只有调用链测试）；advanced_charts/assumption_benchmark 0 覆盖。**计算引擎是 2hao 最值钱的资产，恰恰是测试最薄的地方。**

**差距 9：LLM 网关——手写 vs LiteLLM 级**
2hao 的 deepseek_client 有 7 provider 熔断/限流/流式，是自研里不错的；但缺 JSON schema 强约束（结构化靠正则抓 `{.*}`）、缺 token 计数、缺响应缓存接线完整度。顶级直接上 LiteLLM + Instructor。**这差距不大，且 2hao 的 AUDIT 已列修复方案（commit 04aee36 修了 provider shadowing bug + token bucket，是真实进展）。**

**差距 10：供应链安全与提示注入防御——已启动但需纵深**
AUDIT 已识别 crawl4ai/playwright 抓取内容直接进 prompt 的注入面；commit b28212c 加了 spotlighting 防御 + redteam suite（真实进展）。但对标 OpenAI/Anthropic 纵深四层（delimiting+instruction hierarchy+dual-LLM+出口白名单），还需补 dual-LLM 隔离与系统性红队用例库。

### 3.3 差距的根源（不是架构，是流程）

四条根因：
1. **无独立验证**——自评闭环让"分数"失去外部意义
2. **无度量基线**——观测瘫痪让"收敛/演化/降级"全部无从谈起
3. **无远程 CI**——防线从未通电，"门禁剧场"虽修但无持续保障
4. **开发模式**——49 commit 是 8/24 后才有的，此前 90+ 轮 R 补丁全走"对话即开发"，产出大量一次性 patch 脚本与文档化补丁史；R1-R96 规则散落 40+ docs 无中央注册表

---

## 四、值得保留的资产（公平记录）

- **IronGate 文本矩阵测试**（占比数量级验算/乘积尾数/估值锚交叉/评级-空间一致性）——全仓最值钱的测试资产
- **收敛保护机制**：STALL 检测、组级局部重写、语义早停、best-so-far 回退、checkpoint 断点续跑——设计成熟
- **enrich 通道溯源强制**：缺 source 直接拒 + fig_* 白名单
- **LLM 多通道期权**：7 provider + 熔断 + agent 落盘兜底，反脆弱做得最实的模块
- **方法论资产**：SAC/框架 YAML、5086 份机构语料、Style Compiler 规则——工程化的"机构隐性知识"本体
- **真实运行数据**：19640 条 Gate 失败记录、8955 条 LLM 调用——**数据是干净的，问题在没被用起来**

---

## 五、结论与优先级建议

### 5.1 三问结论

**能力**：数据/计算/门禁/LLM 通道四层骨架真实且质量中上；写作和意图层半真实；可观测/回测/CI 三层空白。
**效率**：一次运行 3 轮全挂是常态，成功交付靠补丁链，距离"15 分钟自动出一份过 Gate 的报告"很远。
**目标**：作为超级智能分析师系统未达成；作为机构方法论工程化原型已成型。**系统缺的不是设计，是让它自动收敛的验证层。**

**自洽性**：宪法自洽，实现不自洽。断裂点全在"测量-验证"链路。

**差距**：引用粒度、评估闭环、预测问责、可观测、CI 纪律五条为主，工程化/网关/安全三条为次。

### 5.2 修复优先级（按 ROI）

| 优先级 | 动作 | 成本 | 收益 |
|---|---|---|---|
| P0 | **把 Gate 失败数据用起来**：19640 条失败记录 → 按失败项聚类的 top 失败模式 → 针对性修 prompt/阈值；建立"每失败必归因"流程 | 1-2 天 | 直接提升当下成功率 |
| P0 | **回测闭环通电**：给 12 条 forward_picks 回填实际价、算 alpha；建立到期自动验证定时任务 | 1-2 天 | FP5 问责从 0 到 1，证明或证伪"预测能力" |
| P1 | **测量层通电**：quality_trends 接入每次 Gate 运行；observability 三表全开；恢复 validate_history 写入 | 2-3 天 | 自洽性断裂 1/4/7 的根本修复 |
| P1 | **CI 真正通电**：推 remote + 让 CI 跑起来（处理 crawl4ai/playwright 依赖问题）+ 修 7 项失败 | 2-3 天 | 防线从剧场变持续门禁 |
| P1 | **指纹漏洞修复**：指纹与报告正文做哈希绑定 + 校验报告归属 | 半天 | 堵住 3 个绕过洞 |
| P2 | **inline_citations 攻坚**：把"来源标注率 ≥30%"升级为"每个数字/论断可点击溯源"（claim-level） | 1-2 周 | 产品差异化跃迁 + FP2a 真正落地 |
| P2 | **硬编码/占位符清零**：section_writer 残留客户案例移入 SAC/enrich；交付物占位符检查入库 | 2-3 天 | 数据真实性宪法落地 |
| P3 | **核心计算补数学测试**：run_dcf/run_comparable 边界值/敏感性表独立测试 | 1 周 | 保护最值钱资产 |
| P3 | **巨石拆解**：Strangler Fig 式，每步以 golden diff 为验收 | 2-4 周 | 改动成本曲线拉平 |

### 5.3 一句话总结

> **2hao 的独特价值在于"把顶级机构的方法论显性化了"，且数据/计算/门禁骨架是真材实料；它离"顶级项目"的差距不是理念，而是三件事——把测量层通电、把评估层独立、把预测层闭环。修好这三件事，它从"高设计低兑现的原型"到"可信的投研引擎"之间只差执行，不差设计。**
