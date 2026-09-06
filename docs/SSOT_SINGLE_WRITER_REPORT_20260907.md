# SSOT + 单写路径 + 门禁分层 · 执行报告

**日期**：2026-09-07
**依据**：`docs/SSOT_SINGLE_WRITER_PLAN_20260907.md`（四原则：SSOT / round-trip / Strangler Fig / Layer-Don't-Choose）
**验证口径**：ruff correctness gate + pytest 回归（102 passed）+ py_compile

---

## 一、执行清单与证据

| 任务 | 改动 | 验证证据 |
|---|---|---|
| T1 单写路径：`update_outcomes` 收编进 SSOT 门面 | `core/tools/track_record.py` 新增 `TrackRecordManager.apply_resolved()`——唯一外部批量写入门面：只写 dataclass 已知字段、未知键丢弃并告警、outcome 词表校验、`_save()` 落盘；`scripts/update_outcomes.py` 删裸 `save_track_record` 直写，`run_outcome_update` 改走 `apply_resolved` | `test_apply_resolved_persists_resolve_fields`：alpha/bench/return_pct/resolved_at/expiry_date 落盘保留；`test_apply_resolved_rejects_bad_outcome`：非词表值拒绝、不污染；`test_run_outcome_update_uses_ssot_path`：模拟到期+取价 → hit + 真价落盘 |
| T2 round-trip 恒等 | `tests/test_ssot_single_writer.py`：4 组字段组合（全默认/全填/含 resolve 键/unverifiable）+ 真实文件 `_load→_save→_load` | `test_roundtrip_invariant` ×4 + `test_load_save_roundtrip_preserves_all_fields` 全绿 |
| T3 门禁分层：run_all=门，v2=advisor | `pipeline/iron_gate.py` `_run_irongate_v2_checks`：v2 layer severity 恒为 `warning`（曾 `error if score<0.5`）；unavailable/error 兜底也降 warning——v2 永不进 error-mean 门禁判定，进 report card 供人看 | `test_v2_checks_never_error_severity`：源码级守卫锁"v2 段无 error severity" |
| T4 schema 派生衔接 | R4 已让 generate_docs 从 iron_gate.py 读阈值；Prediction 字段由 dataclass 派生（不手写第二份 schema） | 既有 `test_generate_docs_single_source_helpers` 保持绿 |

**一个关键实测发现**：`_run_irongate_v2_checks` 定义于 `pipeline/iron_gate.py:758` 但**无任何 run_all 调用点**（grep 仅定义处）——v2 实际从未作为第二门禁参与 `run_all` 判定；真正的 v2 消费在 `pipeline/engine_bridge.py:237`（L1 hard-stop 前置校验，engine 路径，非 run_all）。本裁定把"代码里残留的 v2-as-error 语义"消除，使代码与"advisor 非 gate"定位一致，避免未来误接线时变成双事实源。

---

## 二、改动文件

| 文件 | 改动 |
|---|---|
| `core/tools/track_record.py` | +`apply_resolved()`（SSOT 单写门面） |
| `scripts/update_outcomes.py` | `run_outcome_update` 弃裸写，改走 `apply_resolved`；unverifiable 也落盘（诚实标注需持久化） |
| `pipeline/iron_gate.py` | v2 段 severity 全降 warning（3 处：layer append / unavailable / error 兜底） |
| `tests/test_ssot_single_writer.py` | **新增** 9 用例（T1 单写 ×3 + T2 round-trip ×5 + T3 门禁分层 ×1） |
| `docs/SSOT_SINGLE_WRITER_PLAN_20260907.md` | 方案文档（先于执行交付） |

---

## 三、回归验证

```
ruff --select=F821,F601,E9 (core pipeline web export scripts harness) → All checks passed
py_compile 4 个改动文件 → OK
pytest test_ssot_single_writer + test_deep_audit_fixes + test_calibration
     + test_outcome_vocab_unified + test_prediction_contract + test_golden_numeric
     + test_claim_citation + test_price_feeder + test_significance_guard
     → 102 passed, 0 failed
```

---

## 四、残余项（非本轮阻断，转决策）

1. **`save_track_record`/`load_track_record` 仍留在 update_outcomes.py**：`load` 读路径保留（读无副作用，SSOT 只管写）；`save_track_record` 已无调用（run_outcome_update 不再用），建议下轮删除函数本体避免复活裸写。
2. **engine_bridge.py 的 v2 L1 hard-stop** 是独立 engine 路径，与 run_all 无涉——本轮不裁定其去留；若产品要统一门禁，需单独评估 shadow 对比。
3. **真正把 run_all 与 engine_bridge 双门禁拉齐**属 M3/产品决策（同 irongate_v2 去留）。

---

## 五、结论

SSOT 四原则已落地三条可执行项：**写路径收敛为唯一门面**（`apply_resolved`，带词表校验与未知键告警）、**round-trip 恒等测试锁 schema 演进**、**v2 门禁语义降为 advisor**（消除双 error 事实源隐患）。从此 track_record 的"resolve 写什么 → dataclass 装什么"不再是约定，而是被测试强制的不变式；后续若有人新增 resolve 字段但不同步 dataclass，`apply_resolved` 会告警丢键、round-trip 测试会红——打地鼠循环在机制层被截断。
