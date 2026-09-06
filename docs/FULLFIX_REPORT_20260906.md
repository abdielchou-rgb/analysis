# 2026-09-06 深度审计 · 全量修复报告

**日期**：2026-09-06
**审计依据**：`reports/2026-09-06_deep_audit_and_benchmark.md`
**修复范围**：P0-1 / P0-2 / P1-1 / P1-3 + 审计未覆盖但同源的三处隐性缺陷
**验证口径**：磁盘实测 + ruff 实测 + pytest 回归（61 passed）

---

## 一、修复清单与证据

| # | 问题 | 修复 | 验证证据 |
|---|---|---|---|
| P0-1 | `core/calibration.py` 被同名包遮蔽成死模块；内部 `recal_confidence` F821 必炸 | 迁移 ECE/Brier/BSS/重校准到 `core/calibration/metrics.py`；**删除死文件**；`__init__.py` re-export 保兼容 | `import core.calibration` → 包路径；`ruff --select=F821` 全绿 |
| P0-2 | `get_public_summary` 假业绩：`avg_pnl=命中+10%/错-5%`、`kelly_sizing="1.3x"` 字面量、逐条 `pnl_pct=10/-5/0` 硬编码；`web` 业绩页直接展示 | `_real_pnl_pct()` 只从 `price_at_make/price_at_expiry` 真实价算，无价一律 `None`（fail-closed）；移除假 `kelly`；模板 `None` 显示 "—/N/A"，删 `or '1.3x'` 兜底 | `test_public_summary_no_fake_pnl`：真实价→+20/-10%、avg=+5%；无价→`None` |
| P1-1 | `core/attribution.py:215` 用 `datetime` 但未 import → `generate_attribution_report` 跑到即 NameError | 补 `from datetime import datetime` | `test_generate_attribution_report_runs_datetime_branch`：真执行出 `generated_at` |
| P1-3 | CI lint `continue-on-error: true` + `--ignore=F601` → 真实缺陷码永不拦截 | CI 拆两步：**correctness gate 硬拦**（`--select=F821,F601,E9`，非 continue-on-error）+ 全量 lint 降为 informational | `ruff --select=F821,F601,E9` 全仓（除 vendored last30days/legacy）`All checks passed` |
| F601 | `get_public_summary` dict 重复 key `"falsification"`（:367/:370），后者静默覆盖 | 合并为单键 + 显式 fallback 逻辑（`_call_row`） | ruff F601 清零；vocab 测试改指 `metrics.py` |

### 审计未覆盖、同源新修的隐性缺陷

| # | 问题 | 修复 | 验证 |
|---|---|---|---|
| H1 | **`_load` 静默清空炸弹**：`Prediction(**p)` 遇未知键抛 TypeError 被 `except: pass` 吞 → resolve 写入 `price_at_make/outcome_reason/judge_ver` 后，下次读取返回**空记录**（数据"看起来丢了"） | `Prediction` dataclass 补齐 5 个 resolve 字段（expiry_date/price_at_make/price_at_expiry/outcome_reason/judge_ver）；`_load` 过滤未知键 + `logger.warning`（不清空） | `test_load_tolerant_unknown_keys`：带未来 schema 键的 JSON 正常读出 |
| H2 | 生产数据并行会话写至 2251 条，mock 清理后仍无真实 resolve 记录 | 本次不改数据；`get_public_summary` 对 0 resolved 真实返回 `resolved_calls=0, avg_pnl=None` | 实测 summary 输出 |

---

## 二、改动文件清单

| 文件 | 改动 |
|---|---|
| `core/calibration/metrics.py` | **新增**（死模块迁移；修复 `recal_confidence`→`recalibrate_confidence`） |
| `core/calibration/__init__.py` | re-export metrics 函数；注释迁移原因 |
| `core/calibration.py` | **删除**（死模块） |
| `core/attribution.py` | +`from datetime import datetime` |
| `core/tools/track_record.py` | Prediction +5 字段；`_load` 容错；`_real_pnl_pct` 新增；`get_public_summary` fail-closed；修复重复 key |
| `web/app.py` | 异常兜底 `avg_pnl_pct: None` |
| `web/templates/track_record_fragment.html` | 业绩卡/逐条 PnL `None` 诚实显示，删 `or '1.3x'` |
| `.github/workflows/ci.yml` | lint 拆 correctness gate（硬拦）+ full lint（informational） |
| `tests/test_deep_audit_fixes.py` | **新增** 7 用例覆盖 P0-1/P0-2/P1-1/容错 |
| `tests/test_outcome_vocab_unified.py` | 扫描路径 `core/calibration.py`→`core/calibration/metrics.py` |

---

## 三、回归验证

```
ruff --select=F821,F601,E9 core pipeline web export scripts harness  → All checks passed
pytest test_deep_audit_fixes + test_calibration + test_outcome_vocab_unified
     + test_prediction_contract + test_golden_numeric + test_claim_citation
     → 61 passed, 0 failed
py_compile 6 个改动文件 → OK
```

实测 `TrackRecordManager().get_public_summary()`：total=2251, resolved=0, avg_pnl=None, kelly=None, 逐条 pnl=None —— **公开面不再有假业绩**。

---

## 四、残余项（不属本次止血，转 ENGINEERING_PUSH_PLAN M3/10-31）

1. **真价闭环**：`update_outcomes` 的 `get_price_func` 仍需 akshare/yfinance 网络可用才会真 resolve；当前 2251 条全 pending 是真实状态（非 bug）。
2. **CI 全量 lint 仍 informational**：存量 F401（availability probe 模式）等 60 项未清零；已由 correctness gate 兜住真实缺陷码。渐进清零目录后逐步收紧。
3. **vendored `scripts/last30days`**：PEP701 (3.12) 语法导致 F821 报 invalid-syntax——属第三方 skill，已排除出 gate；待 skill 升级。
4. `get_public_summary` 的 PnL 现在是"真实价才有数"，但 resolve 尚未写价（网络受限）——与 #1 同根。

---

## 五、结论

四类止血项 + 三处隐性缺陷全部修复并回归绿。最关键的一处是 **H1 `_load` 静默清空**——若不修，真价 resolve 一旦开始写入，web 业绩页会"凭空清零"，比假业绩更隐蔽。现数据面已 fail-closed：**没有真实价格就没有 PnL 数字，没有 PnL 数字就没有可被展示的假业绩。**
