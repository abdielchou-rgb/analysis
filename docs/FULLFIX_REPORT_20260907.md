# 2026-09-07 复核问题（R1-R4）全量修复报告

**日期**：2026-09-07
**复核依据**：`docs/FULLFIX_REVIEW_20260907.md`
**修复范围**：R1（resolve schema 数据剥离风险）/ R2（partial 语义漂移）/ R3（除零边界）/ R4（IronGate 双重事实漂移）
**验证口径**：磁盘实测 + ruff correctness gate + pytest 回归（93 passed）

---

## 一、修复清单与证据

| # | 问题（复核断言） | 修复 | 验证证据 |
|---|---|---|---|
| R1 | `resolve_outcome` 写回 `alpha/bench/return_pct/resolved_at` 不在 `Prediction` dataclass 上 → 任何 `_load→_save` 往返被白名单剥离，10-31 真结算时归因静默丢失 | 4 字段补进 dataclass（一等字段，非孤儿 key）；`_save` 用 `p.__dict__` 天然保留 | `test_resolve_fields_survive_round_trip`：写→load→save→再读 alpha/bench/return_pct/resolved_at 全保留 |
| R1b | 静态守卫缺失：将来 resolve 再加 key 又会漏 | `test_resolve_write_keys_are_on_dataclass`：AST 扫 `update_outcomes.py` 全部 `prediction["key"]=` 写入键 ⊆ dataclass 字段 | 新增 key 不在 dataclass → 测试红（防回归） |
| R2 | `RESOLVED_OUTCOMES` 含 `partial` 但统计只认 `hit/miss` → 词表与口径漂移 | 新增 `OUTCOME_CREDIT={hit:1, partial:0.5, miss:0}`；`accuracy`/`by_industry`/`summary`/`get_public_summary` 全部改信用加权 + 统一 `RESOLVED_OUTCOMES` 过滤；新增 `partial_count`/`resolved_count` | `test_partial_counts_in_resolved_and_credit`：hit+partial+miss → resolved=3, accuracy=0.5, summary.resolved_calls=3 |
| R3 | `_real_pnl_pct` 只挡 `make==0`，`expiry==0`（退市归零）会除零 | `make<=0 or expiry<=0` 一律 fail-closed 返回 None | `test_non_positive_expiry_price_returns_none`：expiry=0 → None 不炸 |
| R4 | `PIPELINE_FACTS`(103/0.55) vs `pipeline_contract`(24/0.55) vs IronGate v2(0.78) 三重事实漂移 | 单一事实源 = `pipeline/iron_gate.py` 源码：generate_docs 新增 `_ig_constants()`/`_gate_pass_threshold()`/`_gate_judge_version()` 直接读 iron_gate 常量；PIPELINE_FACTS 重生成（`PASS_THRESHOLD：0.78`）；`pipeline_contract.min_score` 快照改 0.78 并标注"非事实源，仅供索引" | `test_docs_threshold_equals_runtime`：文档阈值==运行时 PASS_THRESHOLD；`test_generate_docs_single_source_helpers`：helpers 返回 0.78/v2-error-mean |

---

## 二、改动文件清单

| 文件 | 改动 |
|---|---|
| `core/tools/track_record.py` | Prediction +`alpha/bench/return_pct/resolved_at` 四字段；新增 `OUTCOME_CREDIT`/`resolved_outcome_list`；`accuracy`/`by_industry`/`summary`/`get_public_summary` 信用加权 + `RESOLVED_OUTCOMES` 统一；`_real_pnl_pct` 非正价 fail-closed；新增 `partial_count`/`resolved_count` |
| `harness/generate_docs.py` | 新增 `_ig_constants/_gate_pass_threshold/_gate_judge_version`（读 iron_gate.py 源码）；PIPELINE_FACTS IronGate 段改用单一事实源；架构行 `(JUDGE_VERSION=..., PASS_THRESHOLD=...)` 替代硬编码 "24 项/0.55" |
| `harness/pipeline_contract.py` | `min_score` 0.55→0.78 + 注释"非事实源，事实在 iron_gate.PASS_THRESHOLD" |
| `docs/PIPELINE_FACTS.md` | 重新生成（阈值/版本来自单一事实源） |
| `tests/test_deep_audit_fixes.py` | +6 用例（R1 往返 / R1b 写键守卫 / R2 / R3 / R4 文档阈值 / R4 helpers） |

---

## 三、回归验证

```
ruff --select=F821,F601,E9 (core pipeline web export scripts harness) → All checks passed
pytest test_deep_audit_fixes + test_calibration + test_outcome_vocab_unified
     + test_prediction_contract + test_golden_numeric + test_claim_citation
     + test_price_feeder + test_significance_guard
     → 93 passed, 0 failed
```

实测：

```text
TrackRecord accuracy(hit+partial+miss) = 0.5  # partial 信用 0.5，不再游离
_get_public_summary().resolved_calls 含 partial
_real_pnl_pct(expiry=0) = None          # 不除零
PIPELINE_FACTS.md: PASS_THRESHOLD 0.78 = iron_gate.PASS_THRESHOLD 0.78  # 单一事实源
```

---

## 四、残余观察（非本轮阻断）

1. `update_outcomes.py` resolve 走的是**裸 dict 写 JSON**（`run_outcome_update`），与 `TrackRecordManager` dataclass 写路径并存——本轮以"字段补全 + 写键守卫测试"收口，最彻底的方向（resolve 改走 dataclass 单写路径）留作后续 M3 重构，避免真价结算前大改。
2. `scripts/irongate_v2.py`（5 层 0.55）与 `run_all`（0.78）**双门禁引擎**职责边界未在本轮裁决——R4 只统一了"文档/合约"对 run_all 的事实源；v2 是否退役属 M3/产品决策。
3. vendored `scripts/last30days`（PEP701）仍在 correctness gate exclude 名单——第三方 skill，待上游升级。

---

## 五、结论

复核报告的 R1-R4 四项断言全部属实并已闭环。最有价值的一处是 **R1**——它揭示的是"修复引入新同源 bug"的模式（schema 白名单成了数据丢失元凶）；本轮以 **字段补全 + 往返测试 + AST 写键守卫** 三重收口，使"resolve 写什么 → dataclass 装什么"从约定变成被测试强制的不变式。加上 R4 单一事实源，**同一事实（Gate 阈值）在全仓只剩一个定义点**，文档/合约/运行时代码三方漂移从此可被 CI 拦截。
