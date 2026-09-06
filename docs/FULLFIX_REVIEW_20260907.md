# 2026-09-07 修复闭环复核与优化建议

**日期**：2026-09-07
**复核对象**：`docs/FULLFIX_REPORT_20260906.md`
**复核方式**：磁盘实测 + ruff 实测 + 代码路径追踪（只读，未改代码）
**结论速览**：报告六项声明全部落地且验证口径可信；但同类缺陷模式仍有残余，其中一项为潜伏的 resolve 数据剥离风险。

---

## 一、修复闭环复核结论

| 声明项 | 复核证据 | 结论 |
|---|---|---|
| P0-1 `core/calibration.py` 死模块迁移 | `core/calibration.py` 已删除；`core/calibration/metrics.py` 与 `dashboard.py` 并存，`__init__.py` re-export | 闭环 |
| P0-2 假业绩 fail-closed | `Prediction` dataclass 补齐 5 个 resolve 字段（`expiry_date/price_at_make/price_at_expiry/outcome_reason/judge_ver`）；`_real_pnl_pct()` 无真实价一律 None；假 `kelly_sizing` 字面量移除 | 闭环 |
| P1-1 `attribution.py` 缺 import | 已补 `from datetime import datetime` | 闭环 |
| P1-3 CI lint fail-closed | correctness gate 不 `continue-on-error`，`--select=F821,F601,E9`；full style 降为 informational | 闭环 |
| F601 重复 dict key | `_call_row` 合并为单键 + 显式 fallback | 闭环 |
| H1 `_load` 静默清空炸弹 | `_load` 按 `valid_fields` 白名单过滤未知键并 `logger.warning`，不再整单清空 | 闭环 |

**实测数据**：

```text
ruff check core pipeline web export scripts harness --exclude "scripts/last30days,legacy" --select=F821,F601,E9
→ All checks passed!

pytest（test_deep_audit_fixes 等 6 个文件）
→ 61 passed, 0 failed

TrackRecordManager().get_public_summary()
→ total=2251, resolved=0, avg_pnl=None, kelly=None（无伪造 PnL 可达）
```

结论：报告所列止血项真实落地，不是纸面修复。

---

## 二、仍存在的"类似问题"

按风险从高到低排列。

### R1. resolve 字段会被 dataclass 白名单静默剥离（同类于 H1，潜伏）

**位置**：

- 写入侧：`scripts/update_outcomes.py:161-169`（`resolve_outcome`）
- 读取侧：`core/tools/track_record.py` `_load`（按 `Prediction.__dataclass_fields__` 过滤）
- 触发点：`core/tools/track_record.py` `register_prediction`/`log_run` → `_save`

**问题**：`resolve_outcome` 成功后将 `alpha / bench / return_pct / resolved_at` 写回原始 dict，但这 4 个 key **不在** `Prediction` dataclass 上（本次只补了 5 个字段，未包含它们）。任何代码路径一旦发生 `_load() → _save()` 往返，这 4 个 key 就会被白名单过滤并随重写静默消失。

**实测触发点存在**：

- `core/bold_call_extractor.py:169` → `tm.register_prediction(...)` → `_save()`
- `web/app.py:325` → `tm.log_run(...)` → `register_prediction` → `_save()`

**风险**：当前 resolved=0，尚无真实结算数据，因此尚未爆发；一旦 10-31 真价结算开始，任何一次经 `TrackRecordManager` 的保存都会抹掉 alpha/bench/收益归因，且无报错。

**建议**：resolve 前先补一次"写 → load → save → 再读"往返测试；或让 `_load` 保留未映射 key 并告警，而非丢弃。

### R2. `partial` 语义漂移

**位置**：`core/tools/track_record.py:24` 与 `get_public_summary` 的 resolved 过滤

**问题**：`RESOLVED_OUTCOMES = frozenset({"hit", "miss", "partial"})` 声明 `partial` 属已结算，但 `get_public_summary` 只统计 `outcome in ("hit", "miss")`，`partial` 既不进正确率分母也不计入 `resolved_calls`，词表与统计口径不一致。

### R3. `_real_pnl_pct` 除零边界未闭合

**位置**：`core/tools/track_record.py` `_real_pnl_pct`

**问题**：已挡 `price_at_make == 0`，但 `price_at_expiry == 0`（退市/归零标的）时仍会 `ZeroDivisionError`。非正价格应同样 fail-closed 返回 None。

### R4. IronGate 合约双重事实漂移（P1-2 未闭环）

**位置**：`docs/PIPELINE_FACTS.md:7-10` vs `harness/pipeline_contract.py` vs IronGate v2 实际阈值

**问题**：文档声称 103 checks / min_score 0.55，harness 侧仍为 24 checks / 0.55 旧口径，v2 与 legacy 双重门禁并存。报告未声称修复该项，但作为上轮审计 P1-2 一直遗留至今。

---

## 三、进一步优化建议（按 ROI 排序）

### 1. resolve 写入纳入唯一 schema（最高优先级）

- `scripts/update_outcomes.py` 与 `Prediction` dataclass 共用同一字段封口；
- 二选一：补齐 `alpha/bench/return_pct/resolved_at` 字段，或 `_load` 保留未知 key + 告警；
- 在首次真实 resolve 前跑通"resolve → load → save → 再读"往返测试。

### 2. 单一门禁事实源

- threshold / check 数只保留一份（建议以 IronGate 注册表或 `harness/pipeline_contract.py` 为源）；
- `PIPELINE_FACTS.md` 及所有文档由同一 generator 生成，消除 0.55/0.78、103/24 双重事实。

### 3. 语义一致性收尾

- `partial` 纳入 resolved 统计，或从 `RESOLVED_OUTCOMES` 词表剔除；
- `price_at_expiry <= 0` fail-closed；
- CI correctness gate 的目标范围与 pyproject exclude 规则统一，避免 `archive/` 等目录游离在门禁外。

### 4. 真价数据积累后的原则延续

- 引入 Kelly/仓位模型、校准曲线时沿用本次确立的原则：**没有真实输入就不产出数字，宁可 None 不可编造**；
- 任何对外的业绩/校准数字先过一轮"是否全部来自真实数据"的检查再展示。

---

## 四、附：本轮验证命令

```text
# 正确性门禁复跑
ruff check core pipeline web export scripts harness --exclude "scripts/last30days,legacy" --select=F821,F601,E9

# 关键文件存在性
core/calibration.py            → 不存在（已删除）
core/calibration/metrics.py    → 存在
tests/test_deep_audit_fixes.py → 存在（5648 bytes）

# 调用链确认
rg "register_prediction|log_run\(" core pipeline web
→ core/bold_call_extractor.py:169、web/app.py:325（均经 manager _save）
```

---

> 本文件为复核记录，不改动代码。修复动作请单独走 MR 并附回归测试。
