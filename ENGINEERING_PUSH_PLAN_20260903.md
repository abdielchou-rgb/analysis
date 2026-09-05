# 二号分析师 · P0 收尾修正工程推进方案

**版本**：v1.0
**日期**：2026-09-03
**定位**：对 `docs/P0_SUMMARY_2026-09-03.md` 的**修正执行篇**。P0-1~P0-7 框架已交付（55 测试绿、golden 46 条、mock 已清出生产库），但 ultrathink 审计发现：**验证系统的两套协议在结构上分裂**——`hit/miss/partial`（W2 时代）与 `correct/incorrect`（P0 时代）并存且互不相认；alpha 判据主线未落地；ArgumentEngine 只堵了出口没修根因。若不统一，10-31 首次真实验证会产出**协议自洽但语义分裂**的结果。
**一句话**：框架齐了，**协议还没统一、判据还是绝对涨跌、根因还埋在 argument 里**——本方案把这三件事 + 数据债务一次性闭环。
**铁律**：无测试不交付；根因不明不修复；无真实价格源不得 resolve（FP2a）。

---

## 一、现状基线（2026-09-03 磁盘实测）

### 1.1 已确认的进展（真货）

| 项 | 实测 | 证据 |
|---|---|---|
| Mock 清出生产库 | ✅ track_record.json = **2025 条全 pending、0 mock**（曾 2062 含 20 mock） | `core/data/forward_picks/track_record.json` |
| Mock 隔离库 | ✅ `core/data/forward_picks/mock_track_record.json` 存在 | 磁盘 |
| price_feeder 真取价 | ✅ akshare→yfinance→None（不编 0），`get_price_or_unverifiable` 三态 | `core/price_feeder.py` L50-100 |
| Golden 数值真值 | ✅ 46 条（target_price 27 / pe_ratio 15 / revenue 4） | `benchmark/golden_numeric/truth_set.json` |
| Argument 失败显式化 | ✅ `context["node_errors"]["argument"]` + scaffold 进 D1 证据清单 | `pipeline/e2e_orchestrator.py` |
| 占位符硬拦 | ✅ 残留 `{{xxx}}` → ValueError | `pipeline/section_writer.py` `_replace_placeholders` |
| MC Guard | ✅ `_require_valid_outcomes(min=20)` + `InsufficientOutcomes` | `core/significance.py` L21-31 |
| 生产写路径 source 校验 | ✅ `Prediction.source ∈ {pipeline, backfill}`，注释"(mock 禁止写入生产库)" | `core/tools/track_record.py` L40 |
| Dashboard HTML / CI import+P0 tests | ✅ `output/dashboard.html`；ci.yml 有 P0 tests job | 磁盘 |

### 1.2 核心问题：outcome 词汇表在模块级分裂（本次实测全景）

**同一 track_record 里并存两套互不相认的 outcome 词汇**：

| 词汇 | 写入方（谁产） | 读取方（谁消费） |
|---|---|---|
| `correct` / `incorrect` | `scripts/update_outcomes.py` L121-144（生产 resolve）；`resolve_mock_outcomes.py` | `core/significance.py`（只认这两个）；`core/cohort.py` L128/135（stats 分支）；`core/attribution.py`（只认这两个）；`core/calibration/` |
| `hit` / `miss` / `partial` | `scripts/verify_predictions.py` L206-222；`prediction_daily.py`；`prediction_monthly.py`；`prediction_attribution.py` | `core/backtest.py`；`core/forward_picks.py`；`core/target_tracker.py`；`pipeline/learning_loop.py`；`scripts/prediction_*.py` |
| **混用** | `core/tools/track_record.py` Prediction.outcome docstring = "correct/incorrect/pending/**partial**"；`core/prediction_validator.py` 两套都碰 | `core/cohort.py` 自身内部不一致（L89 用 `!=pending`，L128 用 correct/incorrect） |

**后果**：
1. `update_outcomes` 写 `correct/incorrect` → `cohort` 的"非 pending 过期"统计能数到，但 `prediction_monthly`/`learning_loop`（读 `hit/miss/partial`）**看不见它们**——归因、学习回流、月度报告对同一批预测"部分失明"。
2. `verify_predictions` 写 `hit/miss/partial` → `significance` 的 Guard **直接过滤掉**（只认 correct/incorrect）——**用旧判据验证的到期预测进不了 MC**。
3. 校准分桶（confidence→实际命中）跨两套词汇时会把同一条预测算两次或漏一次。

### 1.3 判据未升级：仍是绝对涨跌，alpha 主线（W2）未落地

- `core/prediction_judge.py` **不存在**；
- `scripts/update_outcomes.py` L131-135：`correct if price_change > 0 else incorrect`（按方向符号判，**无 alpha、无风格基准、无 ±2% 阈值**）——这正是 OPTIMIZATION_DEEP_20260902 审计的"绝对方向验证"；
- `core/significance.py` 中 37 处 "alpha" 全部是 **MC 随机模拟的局部变量**（`random_hits`），与"超额收益 alpha"无关；
- `update_outcomes.py` **零 import** `core/benchmark_client.py`。

### 1.4 数据债务未清（10-31 命脉）

- 生产库 2025 条 pending 中，**带 target_price/falsification 的比例仍 ≈0.25%**（5 条级，P0 各 commit 未做存量 backfill）；
- 到期判定仍分裂：`verify_predictions.is_due(made, horizon)` vs `prediction_daily` 硬编码 365 天（G5 未闭环）；
- 方向脏值只清了存量 5 条，extractor 白名单（W1.3）写入侧是否强校验未验证。

---

## 二、问题分级与修复任务书

### M0 — 协议统一（P0，1 天）★ 先做：不做则以下全白搭

| # | 任务 | 改动 | 守护测试 | 验收 |
|---|---|---|---|---|
| U1 | **outcome 词汇表统一** | 全仓唯一词汇 = `{pending, hit, miss, partial, unverifiable, pending_review}`；`OUTCOME_VOCAB` 常量放 `core/tools/track_record.py`；改：`update_outcomes.py`（correct→hit / incorrect→miss，unverifiable 保留）、`resolve_mock_outcomes.py`、`core/cohort.py`（L128/135 统一）、`core/attribution.py`（L100-103）、`core/calibration/dashboard.py`、`core/significance.py`（L25/31 有效 outcome 集）；废弃字符串在代码内**禁止再出现**（加 lint/测试断言） | `test_outcome_vocab_unified.py`：grep 断言核心 writer/reader 无 `"correct"`/`"incorrect"` 裸串；同一预测喂 significance/cohort/monthly → 三处口径一致 | 全仓单一词汇；`python -m scripts.dashboard` 三模块读同一批 outcome |
| U2 | **Prediction 契约对齐** | `Prediction.outcome` 注释改 `hit/miss/partial/...`；`outcome_detail` 约定 `judge_ver=<v>`；新增 `judge_ver: int` 字段（判据版本，默认 2） | 现有 `test_prediction_contract.py` 扩展 | 契约注释=代码=文档 |
| U3 | **写路径强校验** | `register_prediction`/`save` 处：outcome 不在词汇表 → 拒绝；direction 不在 `{bullish,bearish,neutral}` → 拒绝；`source` 缺失 → 默认 `pipeline`；mock 源 → 强制隔离库（已有基础，补硬校验） | `test_track_record_isolation.py`：非法 outcome/direction → 拒绝；mock→生产库 → 拒绝 | 非法写不入库 |

**M0 DoD**：`grep -rn '"correct"\|"incorrect"' core/ scripts/` 只在 mock 隔离库/历史备份出现；dashboard 三模块口径一致。

---

### M1 — W2 判据落地（P0，1 天）

| # | 任务 | 改动 | 守护测试 | 验收 |
|---|---|---|---|---|
| W1 | **`core/prediction_judge.py` 新建** | `judge_outcome(actual_return, direction, bench_return=None, target_price=None) -> (outcome, detail)`：有 bench → **alpha 判据**（hit=alpha>+2% / miss=alpha<-2% / partial）；无 bench → 方向判据（降级并标注 `bench=none`）；带 target → 目标价触及判据（最严）；写 `judge_ver` | `test_prediction_judge.py`：大盘-10% 标的-3% → **hit**（alpha=+7%）；无 bench 降级分支；target 触及分支 | 判据可回答"相对市场是否创造 alpha" |
| W2 | **update_outcomes 接 judge** | L131-135 删符号判向，改调 `judge_outcome`；`get_price_func` 传入时同时取基准（`benchmark_client.select_benchmark` 按风格，**弃 max(hs300,zz500)**） | `test_price_feeder.py` 扩展：resolve 一条 bullish 标的大盘跌 → hit | 真实 resolve 走 alpha 判据 |
| W3 | **prediction_daily / verify 到期逻辑统一** | prediction_daily 弃硬编码 365d → 复用 `is_due(made, parse_time_horizon(horizon))`（G5 闭环）；verify 的 outcome 写 hit/miss/partial（本就如此，确认不写 correct） | 现有 is_due 用例参数化 | 两脚本对同一条到期判定一致 |
| W4 | **significance 接新词汇 + alpha 口径** | Guard 有效集 `{hit, miss, partial}`；MC 支持"alpha 命中"定义（hit 且 alpha>阈值）；dashboard 展示方向命中率 + alpha 命中率两口径 | `test_significance_guard.py` 更新 | MC 对 alpha 口径可跑 |

**M1 DoD**：`update_outcomes --dry-run`（有价时）产出 alpha 口径 outcome；significance 有效集不再过滤 verify 的结果。

---

### M2 — 根因修复 + 隔离强化（P1，半天~1 天）

| # | 任务 | 改动 | 守护测试 | 验收 |
|---|---|---|---|---|
| A1 | **ArgumentEngine 根因** | `e2e_orchestrator.argument_engine`：`WritingBrief(asset=context.get("asset",""))` 的 asset 为空串根因——从 `collected_data` 取 asset（`context["collected_data"].get("asset") or context["collected_data"].get("stock_name") or "UNKNOWN"`）并在构造失败时**把异常原样记录 + 报告类型为 decision_memo 时整链失败，其余类型显式标注降级**（不静默）；DataPoint 构建时跳过空 value 键 | `test_argument_node_contract.py` 扩展：asset 为空→从 collected_data 兜底；构造抛错→node_errors 有栈 | argument 不再因空 asset 崩；异常可见可诊断 |
| A2 | **协议穿透防护** | `significance`/`cohort`/`dashboard`/`attribution`/`calibration` 入口统一过滤：`p["source"] == "mock" → 跳过`（生产库本无 mock，但防隔离库误喂）；新增 `Prediction.is_mock()` | `test_mock_protocol_isolation.py`：喂 mock 库给 dashboard → 输出 0 条 mock | 系统级"mock 永不进真实统计"（非仅文件隔离） |
| A3 | **方向脏值写入侧校验** | `bold_call_extractor` 写 direction 前白名单校验（bullish/bearish/neutral，非法→neutral+reason 标注） | `test_prediction_contract.py` 扩展 | 新预测 direction 100% 合法 |

**M2 DoD**：argument 空 asset 不再触发异常链；mock 库喂 dashboard 不影响真实统计。

---

### M3 — 10-31 真验证闭环（P1，2-3 天，硬期限前）

| # | 任务 | 改动 | 验收 |
|---|---|---|---|
| B1 | **存量 backfill（W1.2 补课）** | 对到期的 3m 池（及全部 pending）从 output/ 报告回填 target_price/falsification；提取不到 → `verifiable=False` | 到期池带目标价率 >90% 或显式 unverifiable |
| B2 | **到期模拟真跑** | 复用 20 条 mock（已隔离）但**改走真实代码路径**：mock 库 → `update_outcomes --dry-run --mock-db` → judge(alpha) → MC → dashboard | 全链路无 mock 泄漏进生产统计 |
| B3 | **定时任务注册** | schedule：prediction_daily（每日）+ refresh_data（每日）+ prediction_monthly（每月1日）+ update_outcomes（每周） | 定时列表可见可触发 |
| B4 | **CI 加 golden 门禁** | ci.yml 加 job：`validate_golden.py --numeric` 全绿才过；`dashboard --dry-run` 冒烟 | CI 首次真正守质量门（非仅 import） |

**M3 DoD**：10-31 首次真实验证可产出"方向+alpha+目标价三口径命中率 + ECE/Brier 校准 + MC 分位/p 值"的业绩报告。

---

### M4 — 中长线（季度，不进硬期限承诺）

| 优先级 | 主题 | 说明 |
|---|---|---|
| 高 | golden_numeric 扩到 100+ 条 + 单位归一 | 现在 revenue 允许 10 倍差异（4500 vs 450）会放过真实单位错误；同字段同单位 |
| 高 | B2 evidence 字段 Gate 接线 | `_check_evidence_layer` 已存在（data_quality_mixin L1342），但 claim 的 evidence 字段（value 有值/evidence 空=可检测幻觉）未接入——补"每数字带注"检查 |
| 中 | 外部数据集治理 | FinRpt/AlphaFin 只做风格吸收 A/B，**不做 SFT**（自举风险，见 ROUNDTABLE_20260903）；exemplar 注入前清洗 + 体积压缩 |
| 中 | 校准反馈闭环 | confidence 分桶 → 高估桶写 learning_loop（W6.4） |

---

## 三、执行顺序与依赖

```
M0 协议统一（U1→U2→U3，串行 1 天）——全局前提
M1 W2 判据（W1→W2→W3/W4，1 天）——依赖 M0
M2 根因+隔离（A1/A2/A3 可并行，半天-1 天）
M3 10-31 闭环（B1→B2→B3/B4，2-3 天）——依赖 M0-M2
M4 中长线（季度）
─────────────────────────────
硬期限 2026-10-31
```

**今天建议**：M0（协议统一）+ M2-A1（argument 根因）并行开；M1 明天；M3 视 akshare 限流恢复推进。

---

## 四、风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 词汇统一改挂历史统计 | 中 | 报表数字跳变 | outcome 迁移脚本先 dry-run 出 diff；`judge_ver` 保留可回溯 |
| alpha 判据改变 pending 语义 | 中 | 口径变化 | 每条 outcome 带 `judge_ver` + `bench` 来源标注 |
| akshare/yfinance 持续限流 | 高 | 无法真取价 | 双后端 + None→unverifiable（已建）；10-31 前监控 |
| argument 根因修出新问题 | 中 | 管线断 | 先复现（跑一次带 asset 的真实 e2e）再改；守护测试先行 |
| mock 隔离库被误当生产 | 低 | 统计污染 | A2 协议穿透防护 + source 过滤（本轮落地） |

**通用纪律**：任务独立 commit 语义前缀（`fix(vocab)` / `feat(judge)` / `fix(argument)`）；M0/M1 各自 revert 不影响其余；根因不明不修复。

---

## 五、Definition of Done（全部勾选）

- [ ] M0：全仓单一 outcome 词汇；dashboard 三模块口径一致；非法写不入库
- [ ] M1：`prediction_judge.py` alpha 判据生效；update_outcomes 走 judge；到期逻辑统一；significance 支持 alpha 口径
- [ ] M2：argument 空 asset 根因修复（异常可见非静默）；mock 协议穿透被系统级拦截；新预测 direction 100% 合法
- [ ] M3：存量 backfill 到期池 >90% 带目标价或显式 unverifiable；mock 彩排走真实代码路径零泄漏；定时任务注册；CI 含 numeric golden 门禁
- [ ] 全部守护测试红→绿；git 提交带语义前缀

---

## 六、反模式清单（沉淀）

1. **同一系统两套 outcome 词汇 = 统计失明**——协议先统一再谈数字
2. **判据降级不标注 = 悄悄回到绝对涨跌**——无 bench 时必须标 `bench=none`
3. **只堵出口不修根因 = 异常必然复现**——argument 要传对 asset，而非等它崩
4. **文件级隔离 ≠ 协议级隔离**——mock 要在统计入口被过滤
5. **单位容差 10 倍 = 放行真实单位错误**——golden 同字段同单位
6. **框架先行、数据滞后 = 传感器没接**——backfill 与真价是 10-31 命脉，优先级高于新功能

---

## 七、文档关系

| 文档 | 关系 |
|---|---|
| docs/P0_SUMMARY_2026-09-03.md | 本方案是它的修正执行篇（框架已交付，本方案统一协议/落判据/修根因） |
| WORK_EXECUTION_PLAN_20260903.md | 其 P0-1~7 已交付；本方案 M1 补其未覆盖的 W2 判据 |
| MASTER_PLAN_20260902.md | 本方案 M1/M3 对应其 W2/W1.2/W9；M0 为新增协议治理 |
| ROUNDTABLE_20260903_external_dataset.md | 外部数据集治理（M4 引用其结论：不做 SFT、A/B 先行） |
