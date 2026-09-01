# 二号分析师（2hao-analyst）全面工程优化方案

**版本**：v1.0 | **日期**：2026-09-01
**依据**：AUDIT_20260901_ultra.md（深度审计）+ EVAL_20260901_research_enhancement.md（外部增强评估）
**总目标**：从「高设计、低兑现的原型」→「可稳定交付、可验证、可持续演化的投研引擎」

---

## 〇、方案总览

### 0.1 三句话诊断（方案的前提）

1. **骨架是真的**：数据层（akshare/本地库）、计算引擎（纯数值）、IronGate（99 项真实检查）、LLM 通道（7 provider 熔断）都是真材实料——**不需要推倒重来**。
2. **三块空白拖垮全局**：测量层（quality_trends=0）、评估层（无独立验证）、预测闭环（0 回测）——**一切"收敛/演化/降级"都以这三块为前提**。
3. **最大的杠杆不是写更多功能，而是把已有的 19640 条失败记录、8955 次调用、49 个 commit 用起来**——数据是干净的，问题在没被用起来。

### 0.2 优化原则（约束）

- **FP0 意图第一**：每个优化项都回答"这能让 2hao 更好地回答委托方必答问题吗？"
- **CLAUDE.md 双模宪法**：不破坏"性能模式=调度管线、训练模式=直接调模块"的边界
- **TDD 纪律**：改代码先写失败测试，一次一片，验收可机械验证
- **Strangler Fig**：重构巨石时每步以 golden diff 为验收，可回退
- **先通电，后优化**：优先级顺序 = 止血 → 通电 → 收敛 → 能力 → 治理

### 0.3 阶段总览（8 周）

| 阶段 | 周期 | 主题 | 核心交付 |
|---|---|---|---|
| **Phase 0 止血** | 3 天 | 清硬伤 | 指纹漏洞、硬编码清零、卫生清理、失败归因 |
| **Phase 1 通电** | 1 周 | 让防线真实 | 测量层、CI、测试修复、依赖管理 |
| **Phase 2 收敛** | 2 周 | 让系统自己变好 | 失败聚类、Learning Loop 真实化、Gate 阈值校准 |
| **Phase 3 能力** | 2 周 | 补调研短板 | last30days 桥接、yichen 证据协议、预测回测闭环 |
| **Phase 4 治理** | 1 周 | 让演化可持续 | 规则注册表、模块拆分、文档单源、交付 SOP |

每阶段含：目标 / 任务清单（带文件路径）/ 验收标准 / 预计工作量。

---

## 一、Phase 0：止血（3 天）

### 目标
消除已知硬伤，让系统不再"带病运行"。不动架构，只修明确缺陷。

### 1.1 出口指纹绕过洞（P0，半天）

**现状**（export/report_gate.py L45-68）：指纹校验有 3 个洞——`glob("*_pipeline_fingerprint.json")` 取 matches[0] 可跨资产复用；JSON 解析失败"放行"；明文 JSON 无正文绑定可伪造。

**改法**：
```python
# export/report_gate.py _verify_pipeline_fingerprint 重构
# 1. 指纹文件必须与报告同名：{asset}_pipeline_fingerprint.json，不接受通配匹配
# 2. 指纹内记录 report_sha256 = sha256(报告正文)，校验时重算比对——正文被改即失效
# 3. 解析失败改为硬失败（fail_closed），不再 warning 放行
```

**验收**：写 `tests/test_fingerprint_bypass.py`：① 复制 A 资产指纹改名为 B 资产 → 必须拒绝；② 修改正文后 → 必须拒绝；③ 指纹 JSON 损坏 → 必须拒绝。三条全红后改代码，改完全绿。

### 1.2 硬编码/占位符清零（P0，1 天）

**现状**：
- `section_writer.py` L551/L1171 残留"托肯恒山/富仁高科/GVR 中国"等柯力传感专属客户案例——违反 FP2a，任何其他公司 report 都会被注入无关数据
- 交付物占位符：`_gate_prev.md` 16 处坏标点/`（数据来源：公司年度报告）`无来源锚

**改法**：
1. L551/L1171 的客户案例移入 `core/sacs/sac_decision_memo.yaml` 的示例字段或 enrich-file，仅在对应行业/标的时注入
2. 新增 Gate 检查 `_check_placeholder_source`：扫描"（数据来源：公司年度报告）"等 5 类无具体来源锚点 → error 级
3. `_check_forbidden_patterns` 扩展：`。。`、`（数据来源：` 开头的裸锚

**验收**：`grep -rn "托肯恒山\|富仁高科" pipeline/ core/` 返回空（除 SAC 示例文件）；新 Gate 检查有测试。

### 1.3 卫生清理（P0，半天）

**现状**：根目录 7 个 `fix_*.py` 一次性脚本、`.bak_*` 备份（含 iron_gate.py.bak_r61 202KB）、test_output*/test_batch/time_test 临时目录、`=` 散件。

**改法**：
- `fix_*.py`/`patch_*.py`/`rerun_*.py` 一次性脚本 → 移入 `archive/one_off_scripts/`（保留不删，防历史追溯）
- `.bak_*` → 移入 `archive/backups/`
- 临时目录 test_output* 等 → 清理，加入 .gitignore
- **关键**：这些清理必须通过 git 提交完成（不再"对话即开发"），commit message 标注 `chore(cleanup): Phase 0`

**验收**：`find . -maxdepth 1 -name "fix_*.py"` 为空；`.gitignore` 补 `archive/`、`test_output*/`。

### 1.4 失败归因 SOP（P0，1 天）

**现状**：8/29-8/31 三次 E2E 失败（浙江觉纤 Gate blocked、商业航天 charts 0.4、觉纤光电图表降级），失败后被抛在 `_gate_prev.md`，无归因文档。

**改法**：
1. 写 `scripts/gate_failure_triage.py`：读 `output/*_err.log` + `learning_data.db` 的 report_failures 最近 N 条 → 按失败项聚类 → 输出 `output/failure_triage_<date>.md`（top 失败项 + 对应检查代码 + 建议修复方向）
2. 在 CLAUDE.md 加一条：**任何 E2E 失败 3 轮后，必须先跑 triage 归因，再决定修什么**（2hao-root-cause skill 同源）
3. 8/31 三次失败做一次归因演练，产出 triage 文档作为模板

**验收**：triage 脚本能跑；8/31 三次失败各有归因结论（哪个检查、为什么、怎么修）。

---

## 二、Phase 1：通电（1 周）

### 目标
让"声称的防线"全部真实通电：测量、CI、测试、依赖。这是自洽性断裂的根治层。

### 2.1 测量层通电（P0，2 天）

**现状**：`observability.db` 的 `validate_history` 17 条空记录停更、`quality_trends` 0 条；`learning_loop.recurrence_rate` 返回 `{}`（stub）、`auto_apply_lessons` 返回 0（stub）——FP3/FP5 的收敛要求全部空转。

**改法**：
1. `pipeline/iron_gate.py` run_all 结束时写 `observability.record_gate()`：overall_score、passed、失败项列表、报告类型 → `validate_history` 每跑必记
2. 新增 `record_quality_trend()`：每日聚合 gate_score 均值/方差、通过率、判断密度均值 → `quality_trends` 每日一行
3. `learning_loop.py` L192-198 的 stub 真实现：
   - `recurrence_rate(months)`：对 learning_lessons 按失败 pattern 分组，统计近 3 月复发率（本月失败项中上个月也失败的占比）
   - `auto_apply_lessons()`：把 top 5 高频失败 pattern 对应的 lesson 注入 `before_report` 的 prompt（替代现在的无差别注入）
4. `e2e_orchestrator.py` 的 learning 节点（L298-308）调用上面两个方法

**验收**：
- 跑一次完整管线（或 mock 管线），`validate_history` +1 条、`quality_trends` 当日有值
- `recurrence_rate(3)` 返回非空 dict（从 19640 条 report_failures 真实计算）
- `auto_apply_lessons` 返回 >0（有真实 lesson 被应用）
- **写测试**：`tests/test_observability_wiring.py` 断言这三条

### 2.2 CI 通电（P0，2 天）

**现状**：ci.yml 配置合理但 `git remote` 为空——从未触发过；测试套件当前红（7 项 lastfailed）；`requirements.txt` 含 crawl4ai/playwright 等 CI 上安装沉重。

**改法**：
1. 修复 7 项失败：
   - `test_r88_numeric_chain::test_market_size_industry_warning`——类内实际方法是 `test_market_size_industry_warning_real_text`，**收集失败是名字漂移**，改 pytest 引用即可（先验证再修）
   - `test_r78_geopolitical.py`——**已实测 6 passed**，是历史 lastfailed 残留，清缓存
   - `test_blindspot_modules` 4 项（chart_engine/cross_validator）——逐项看是环境性还是逻辑性
   - `test_e2e::test_orphan_suite`——脱管测试收编问题
2. CI 依赖拆分：`requirements-ci.txt`（pytest+轻量依赖）vs `requirements.txt`（全量），CI 用轻量集跑单元+golden
3. 推 remote（GitHub 或自建），CI 首跑全绿
4. pre-commit 已工作（ruff+SDD 钩子），保持

**验收**：`pytest tests/ -q -k "not e2e" --ignore=benchmark_full.py --ignore=run_all.py` 全绿；GitHub Actions 首跑通过；`git remote -v` 非空。

### 2.3 覆盖率基线 + 核心计算补测试（P1，2 天）

**现状**：覆盖率 35.8%（coverage_baseline.json），advanced_charts/assumption_benchmark/probabilistic_deep_check 0 覆盖；**run_dcf/run_comparable 无数学正确性测试**（这是 2hao 最值钱的资产）。

**改法**：
1. 补 `tests/test_compute_math.py`：
   - `run_dcf`：已知输入的 DCF 结果断言（手算验证）、终值占比护栏、WACC 边界、零 FCF 不崩
   - `run_comparable`：多倍数组中位数/均值、空输入、除零
   - `run_scenario`：Bull/Base/Bear 加权正确性、概率和 =1 校验
2. pytest-cov 接入：`pytest --cov=pipeline/core/compute` 的覆盖报告作为 Phase 3 的基准
3. 0 覆盖的核心文件（chart_engine 34KB、report_gate、cross_validator）各补 1 个冒烟测试

**验收**：`test_compute_math.py` 全绿；compute 模块覆盖率 >60%。

### 2.4 依赖卫生（P1，1 天）

**现状**：当前 python3 缺 akshare/openai/tavily/yfinance/crawl4ai/playwright 等（.venv 是 Windows 二进制无法在沙箱用）；`llm_cache.py`、`llm_provider.py` 等零消费者。

**改法**：
1. `requirements.txt` 分级：core（运行必需）/ optional（akshare 数据源可选）/ dev（测试工具）
2. 零消费者模块归档：`llm_provider.py`（被 deepseek_client 取代）→ `archive/dead_code/`，保留 import 说明
3. 用 pip-tools 生成 `requirements.lock`（可复现构建）

**验收**：新机器 `pip install -r requirements-core.txt` 后可跑通 scheduler 主链路；`pip install -r requirements-dev.txt` 后可跑全量测试。

---

## 三、Phase 2：收敛（2 周）

### 目标
让系统开始"自己变好"：失败模式被学习、Gate 阈值被校准、写作质量可度量。

### 3.1 失败模式聚类与修复（P0，1 周）

**现状**：19640 条 report_failures 躺库，8/31 失败项集中在 compliance/so_what_chain/judgment_density。

**改法**：
1. `scripts/gate_failure_triage.py`（Phase 0 产物）升级为**每周自动跑**（scheduled task）：聚类 top 10 失败项 → 输出归因报告
2. 对 top 失败项逐类修复，例如：
   - **judgment_density 0.8 < 1.2**：section_writer 的 prompt 加"每段必须有 1 句判断句"的结构约束（不是措辞要求）
   - **so_what_chain**：So-What 链检查失败 → 注入器加显式"因此/所以链"模板
   - **compliance/inline_citations**：来源标注率不足 → 数据注入时强制 [En] 标注
3. 每修复一个模式，写一个回归测试（`tests/test_failure_pattern_<name>.py`：构造含该硬伤的报告 → 断言 Gate 拦截）

**验收**：下一轮 E2E 的失败项中，被修复的 top 5 模式消失；回归测试全绿。

### 3.2 Learning Loop 真实化（P1，3 天）

**现状**：数据流真实（19640 失败/1758 lessons/2418 scores），但回放是"文本提示注入"、收敛指标 stub、`fp5_feedback.on_report_delivered` 零调用者。

**改法**：
1. `recurrence_rate`/`auto_apply_lessons` 真实现（Phase 1.2.1 已做）→ 接进 section_writer 的 lesson 注入
2. `fp5_feedback.py` 接线：e2e 交付成功后调用 `on_report_delivered` → 写 feedback 记录
3. **收敛可视**：`scripts/learning_health.py` 输出"复发率曲线"（近 6 周每周 top 失败项复发率）→ 这就是 FP5 要求的收敛指标
4. `edit_learn.py` 只有 13 条案例 → 加自动采集：任何人工修订（workbench 路径）落 edit_cases

**验收**：复发率曲线能画出来且呈下降趋势（或能明确指出哪项不降）；on_report_delivered 有调用记录。

### 3.3 Gate 阈值校准闭环（P1，3 天）

**现状**：`calibrated_thresholds.v9.38.json`、`benchmark/report_baseline.csv`（73 行券商统计）存在，但校准是一次性的。

**改法**：
1. `scripts/calibrate.py` 定期（每月）重跑：从 `benchmark/golden/` 的分类子目录（listed_company/industry_deep/earnings_notes/decision_memo）统计判断密度/数据密度/图表数 P10-P50 分位 → 更新 Gate 阈值
2. 阈值变更走 git 提交 + 回归测试（阈值测试断言"金牌报告必须过、超短报告必须拒"）
3. **把 output/ 自产报告从校准样本池剔除**（破自证循环——AUDIT 已点名）

**验收**：校准脚本可跑且产出差量报告；阈值变更都有 git 记录与测试守护。

### 3.4 出口质量红线（P1，1 天）

**现状**：8/31 失败产物留在 `_gate_prev.md` 且含乱码/占位符；AICleanCheck 只在 docx 上查"AI生成"字样。

**改法**：
1. `_check_placeholder_charts` 升级：图表缺失 → error 级（商业航天 charts 0.4 连挂 3 次说明 L1 降级无产出出口）
2. 新增 `_check_gbk_encoding`：报告文本检测乱码特征（替换字符 U+FFFD/GBK 错位模式）→ error
3. 失败产物管理：E2E 失败 3 轮后 `_gate_prev.md` 自动移入 `output/failed/<asset>_<date>/`（不再留在根目录误导）

**验收**：含乱码的报告被 Gate 拦；失败产物归档路径生效。

---

## 四、Phase 3：能力（2 周）

### 目标
补上审计点出的调研能力短板，并让预测系统第一次闭环。

### 4.1 last30days 桥接（P0，3 天）——信息新鲜度

**现状**：2hao 数据层无"近 30 天动态/舆情/情绪"通道；Tavily 搜索无时效锚。

**改法**（严格走 CLAUDE.md 桥接协议）：
1. `pipeline/data_collector.py` 新增 `_last30days_search()` 后端：调 `last30days.py "主题" --emit=json --store`（需安装 last30days-skill 或直接调其 CLI）
2. 结果映射到 enrich 白名单键：`fig_recent_news`（结构化：事件+来源+互动数）、`fig_sentiment`（综合情绪）、`fig_polymarket_prob`（如适用）
3. 桥接层校验：每条带 source + 互动信号；缺 source 拒绝
4. 注入场景：decision_memo 的"近期动态/情绪"段、industry 的"催化剂跟踪"、listed 的"舆情与事件"
5. 可选：`--store` + `watchlist.py` 定时跑 → 自选股动态监控（对接 3hao 交易员系统的潜在协同）

**验收**：对一个真实标的跑 enrich，产出含 last30days 来源的数据块，通过 IronGate；报告含"近 30 天动态"段落且数据带来源。

### 4.2 yichen 证据协议引入（P0，3 天）——claim 级溯源

**现状**：`data_provenance.py` 溯源浅（Tavily 固定查询）；inline_citations 连续失败；AUDIT 点出与 STORM 的 claim-level 差距。

**改法**：
1. 吸收 `yichen-web-research` 的 `hengzong-research.md` 契约：claim-source ledger 结构（claim_id/locator/event_date/scope/supports|contradicts）
2. `core/data_provenance.py` 升级：`claim_citation.py`（已有 6.8KB）扩展为 claim ledger——写作时每个数字论断生成 `[C123]`，报告尾生成"论断-来源"对照表
3. `iron_gate._check_inline_citations` 升级：从"E 标注 ≥ 阈值"改为"关键数字点（数字+判断句）必须带 [Cn] 引用"
4. 结构闸门借鉴：scope_complete/coverage/contradiction 三闸门映射为 Gate 检查项

**验收**：生成一份含 claim ledger 的报告，每个关键数字可点击/可查来源；inline_citations 检查通过率提升（对比基线）。

### 4.3 预测回测闭环（P0，2 天）——问责从 0 到 1

**现状**：forward_picks.csv 12 条预测全 pending、`compare_vs_benchmark` 永远返回"暂无已验证预测"——FP5 问责从未闭环。

**改法**：
1. `scripts/verify_predictions.py`：拉取 12 条预测标的的当前价 → 计算 actual_return/alpha（vs 基准，用 akshare 指数）→ 回填 `update_verification`（已有方法，forward_picks.py L265）
2. 建立**到期自动验证**定时任务（scheduled task，每日）：到期的 forward_pick 自动回填
3. `benchmark_compare.compare_vs_benchmark` 输出真实命中率/超额收益
4. **数据修正**：forward_picks.csv 里 current_price 明显异常（比亚迪 11.37、格力 142.68、base_target 多数 0.0）——验证脚本须标注数据质量问题

**验收**：12 条预测全部回填 verified；能输出"命中率/alpha"报告；新增预测进入循环。

### 4.4 数据层收敛（P1，3 天）

**现状**：三套数据栈（DataCollectorV5 / data_backends 带缓存熔断 / data/ 包 30 文件旧平台）；data_collector.py L106/158 已开始接 data_backends 的 cache+circuit。

**改法**：
1. 完成 data_backends 接线：全部网络采集路径走 `cache_get/cache_set`（TTL 4h）+ `_CIRCUIT`（熔断）
2. `data/` 包旧平台 → `legacy/data_platform/`（commit 243e69f 已做一半，补齐）
3. 数据目录分区：`data/`（代码+运行时库）拆出 `var/data`（金融数据）与 `var/cache`

**验收**：采集层无绕过缓存直连网络的路径；`data/` 旧平台代码全部归档。

### 4.5 广度扩展（P2，3 天）

**现状**：yfinance 硬编码 .SS 后缀、仅取市值；A股为主。

**改法**：
1. 港股/美股采集：yfinance 后缀自动映射（.HK/.SS/.SZ 智能判定）+ 接入财报字段
2. `universe_build.py`（20KB，已存在）激活：跨市场标的池
3. 与 3hao 交易员系统对接（memory 已有 3hao 集成记录）：行情/提醒共享

**验收**：能对 3-5 个港股/美股标的跑通采集+基础报告；无硬编码后缀。

---

## 五、Phase 4：治理（1 周）

### 目标
让演化可持续：规则可查、模块可改、文档不撒谎、交付有 SOP。

### 5.1 R 规则中央注册表（P1，2 天）

**现状**：R1-R96+ 规则散布 40+ docs 文档、代码注释、handoff；无中央注册表。

**改法**：
1. `config/rules_registry.yaml`：id/status/superseded_by/evidence/owner 五字段
2. `scripts/scan_rules.py`：扫描 docs+代码提取 R 编号 → 对比注册表 → 报告"未登记规则"
3. CLAUDE.md 只留指针（遵守"文档单源"原则）

**验收**：`scan_rules.py` 跑出全量 R 规则清单，未登记项为 0 或显式标注。

### 5.2 巨石拆解（Strangler Fig）（P1，3 天）

**现状**：section_writer.py 2969 行、e2e_orchestrator.py 2177 行、analysis_mixin.py 1932 行、data_quality_mixin.py 1656 行。30 注入器注册表已抽（d81c31b），但巨石仍在。

**改法**（每步以 golden diff 为验收，可回退）：
1. `data_quality_mixin.py` 的 `_check_numeric_chain_consistency`（253 行）拆出到 `pipeline/checks/numeric_chain.py`——先加 characterization test 再搬
2. `analysis_mixin.py` 重复定义的 `_check_cross_section_consistency`（两 mixin 双份）——删 MRO 不可达的一份
3. `e2e_orchestrator.run()`（450 行）的 write 改循环抽 `WriteReviseLoop` 类
4. 目标：单文件 <1000 行；拆完 golden 报告 diff 为空

**验收**：每步 PR 独立；golden 报告 diff 为空；测试全绿。

### 5.3 文档单一事实源（P1，1 天）

**现状**：IronGate 检查数四种口径（78/96/99/49）；README/SKILL/AGENTS 硬编码数字。

**改法**：
1. `docs/PIPELINE_FACTS.md`（已由 generate_docs.py 实时生成）扩展为唯一事实源：IronGate 检查数/阈值/维度数全从代码生成
2. README 的"78 项"改引用 PIPELINE_FACTS
3. quick-start.md 的 `D:\2hao-analyst` 失效路径更新

**验收**：README 无硬编码检查数；`generate_docs.py` 产物与代码一致。

### 5.4 交付 SOP（P1，1 天）

**现状**：成功交付靠人肉补丁链（油位 v2.3→v5.5 40 版）；无失败处理的标准化流程。

**改法**：
1. `docs/DELIVERY_SOP.md`：成功路径（E2E 通过→export→用户审核→归档）+ 失败路径（3 轮失败→triage→归因→修复→重跑）写死
2. CLAUDE.md 增加：交付前必须过 `pipeline_fingerprint.json` 校验 + 报告含 claim ledger（Phase 3 后）
3. 新增 scheduled task：每周跑 `gate_failure_triage.py` + `learning_health.py`，产出周报

**验收**：SOP 文档存在；下一份报告交付完全按 SOP 走。

---

## 六、外部增强整合（贯穿 Phase 3）

| 外部资产 | 用法 | 合规 |
|---|---|---|
| **last30days-skill**（60k star） | 新数据源后端，只做"近 30 天舆情"采集 | 走 enrich-file 回流，不直接写正文 |
| **last30days-cn**（1.7k star） | 中文平台（微博/知乎/B站/小红书）舆情 | 同上，注意登录态合规 |
| **yichen-web-research** 协议 | claim-source ledger + 结构闸门设计 | 只借鉴协议契约，不引入其 LLM 产出 |
| **ai-berkshire / TradingAgents** | 方法论/多角色辩论参照 | 不引入代码，只吸收设计 |
| **RD-Agent** | FP5 自演化回测参照 | 预测闭环的顶级范式 |

---

## 七、路线图与工作量总表

| # | 任务 | 阶段 | 工作量 | 优先级 |
|---|---|---|---|---|
| 1 | 指纹漏洞修复 | P0 | 半天 | ★★★ |
| 2 | 硬编码/占位符清零 | P0 | 1 天 | ★★★ |
| 3 | 卫生清理 | P0 | 半天 | ★★ |
| 4 | 失败归因 SOP + triage 脚本 | P0 | 1 天 | ★★★ |
| 5 | 测量层通电（validate_history/quality_trends/learning stub） | P1 | 2 天 | ★★★ |
| 6 | CI 通电（修 7 失败 + remote + 轻量依赖） | P1 | 2 天 | ★★★ |
| 7 | 计算引擎补测试 + 覆盖率基线 | P1 | 2 天 | ★★★ |
| 8 | 依赖分级与死代码归档 | P1 | 1 天 | ★★ |
| 9 | 失败模式聚类修复（top 5） | P2 | 1 周 | ★★★ |
| 10 | Learning Loop 真实化（复发率/自动应用/可视） | P2 | 3 天 | ★★★ |
| 11 | Gate 阈值校准闭环 | P2 | 3 天 | ★★ |
| 12 | 出口质量红线（占位符/乱码/失败归档） | P2 | 1 天 | ★★★ |
| 13 | **last30days 桥接** | P3 | 3 天 | ★★★ |
| 14 | **yichen 证据协议/claim ledger** | P3 | 3 天 | ★★★ |
| 15 | **预测回测闭环** | P3 | 2 天 | ★★★ |
| 16 | 数据层收敛（data_backends 全接线） | P3 | 3 天 | ★★ |
| 17 | 港股/美股广度 | P3 | 3 天 | ★★ |
| 18 | R 规则注册表 | P4 | 2 天 | ★★ |
| 19 | 巨石拆解（Strangler Fig） | P4 | 3 天 | ★★ |
| 20 | 文档单一事实源 | P4 | 1 天 | ★★ |
| 21 | 交付 SOP + 周报自动化 | P4 | 1 天 | ★★ |

**总计**：约 6-7 人周（含学习曲线）。**Phase 0+1（1.5 周）做完后，系统将首次拥有"真实防线"**；Phase 2（2 周）做完后，系统开始自收敛；Phase 3（2 周）做完后，调研能力补齐 + 预测首次闭环——届时 2hao 从"高设计低兑现的原型"跨入"可信投研引擎"的实质阶段。

---

## 八、验收总门（怎么判断方案成功）

1. **稳定性**：连续 5 个不同标的 E2E 运行，Gate 通过率 ≥ 3/5（基线：0/3）
2. **防线真实**：pytest 全绿（当前红）、CI 每次 PR 运行、覆盖率 ≥ 50%（基线 35.8%）
3. **测量有数**：quality_trends 连续 30 天有数据，能画出 gate_score 趋势
4. **学习有效**：top 5 失败模式复发率月环比下降（FP5 要求）
5. **问责闭环**：预测 100% 回填，输出命中率/alpha 报告（基线：0 回填）
6. **溯源可查**：报告关键数字带 claim ledger（基线：报告级标注 ≥30%）
7. **治理有序**：R 规则注册表全覆盖、文档单源、无新增一次性补丁脚本

---

*本方案为工程路线图，非一次实施承诺。建议按 Phase 0 → 1 顺序启动，每阶段结束做 gate review，再进入下一阶段。*
