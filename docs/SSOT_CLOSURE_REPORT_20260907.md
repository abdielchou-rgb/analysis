# SSOT 收尾执行报告（死函数清除 + resolved 不变量）

**日期**：2026-09-07
**依据**：ultrathink 三组顶级思考（修 bug 修类不修实例 / 生成≠验证 / make illegal states unrepresentable）落地。
**验证口径**：ruff correctness gate + pytest 回归（104 passed）+ py_compile。

---

## 一、执行清单与证据

| 任务 | 改动 | 验证 |
|---|---|---|
| T1 删死函数 | `scripts/update_outcomes.py` 删除 `save_track_record()`（已无调用方的第二条裸写路径僵尸）；`load_track_record` 保留为只读 | `test_no_save_track_record_function`：源码无 `def save_track_record` |
| T1b 收编第二条裸写路径 | `scripts/dedup_track_record.py`（离线维护脚本）原来也 `json.dump` 直写 track_record——改为重建 `Prediction` 列表经 `TrackRecordManager._save` 落盘 | py_compile OK；仓库内 track_record 裸写点清零 |
| T2 resolved 不变量 | `apply_resolved` 写入侧硬校验：`hit/miss/partial` 必须携带 `price_at_expiry + judge_ver`，否则拒绝并告警（"已结算却无价"成为不可表示状态） | `test_resolved_outcome_requires_price_and_judge`：缺价/缺判据→拒绝且不污染；齐备→通过 |

**回归净变化**：102 → 104 passed（+2 守卫测试）。

---

## 二、改动文件

| 文件 | 改动 |
|---|---|
| `scripts/update_outcomes.py` | 删 `save_track_record`（+注释：写入一律走 apply_resolved） |
| `scripts/dedup_track_record.py` | 裸 `json.dump` → `TrackRecordManager` 重建落盘（SSOT 唯一写路径） |
| `core/tools/track_record.py` | `apply_resolved` 加 resolved 状态不变量校验 |
| `tests/test_ssot_single_writer.py` | +2 用例（死函数守卫 / resolved 不变量） |

---

## 三、验证

```
ruff --select=F821,F601,E9 (core pipeline web export scripts harness) → All checks passed
pytest test_ssot_single_writer + test_deep_audit_fixes + test_calibration
     + test_outcome_vocab_unified + test_prediction_contract + test_golden_numeric
     + test_claim_citation + test_price_feeder + test_significance_guard
     → 104 passed, 0 failed
```

---

## 四、本轮结束后的状态（不再新增护栏）

SSOT 链至此完整闭环：

1. **唯一 store of record**：`Prediction` dataclass——所有写入经 `TrackRecordManager.apply_resolved` / `_save`。
2. **非法状态不可表示**：resolved 必须有真实价+判据版本（构造层强制，非事后检查）。
3. **round-trip 恒等测试**：schema 演进不同步即红。
4. **写键守卫**：resolve 新增 key 不在 dataclass 即红。
5. **唯一门禁事实源**：阈值读 iron_gate.py（R4），v2 降 advisor（T3）。
6. **裸写路径清零**：update_outcomes / dedup 均不再直接 `json.dump` track_record。

**下一步就是主线本身**：10-31 首批 3m 预测到期，真价 resolve 将第一次在这套 SSOT 上跑真实数据——届时护栏会被真实结算检验。按既定纪律：**不再为护栏加护栏。**

---

## 五、涉及提交的语义前缀建议

```
fix(ssot): 删 save_track_record 死函数 + dedup 收编唯一写路径
feat(ssot): apply_resolved resolved 状态不变量(price_at_expiry+judge_ver 强制)
```
