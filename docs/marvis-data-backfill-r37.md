# Marvis 数据补强任务清单 — R37（2026-08-02）

> 背景：R36 覆盖率审计暴露最大缺口——全库 **3542 只标的有 balance 数据但完全无 netProfit**（占 5259 只的 67%），三表勾稽审计（`three_statement_audit.py`）对这些标的的 profit 维度为空。
> 根因：R24 增量同步只覆盖沪深300/中证1000 的 profit 明细，全库未做 profit 全量补采。
> 执行环境：**必须在用户机执行**（沙箱无 akshare，`sync_akshare_financials.py` 启动即报"akshare 未安装"）。

---

## 任务：全库 profit 明细补采（唯一任务，但工作量大）

**目标**：为 3542 只缺 netProfit 的标的全量补采 profit 明细，让全库三表勾稽审计可执行。

**命令**：
```bash
cd D:\2hao-analyst
python scripts/sync_akshare_financials.py --all --workers 2
```

**关键参数说明**（已核对 `--help`）：
- `--all`：全量同步所有过滤后标的
- `--workers 2`：**必须 2**（R24 教训：4-worker 卡死，SQLite 多进程写锁）
- 不要加 `--index`（那是只同步指数成分；本次是全库）

**预计量级**：3542 只 × 平均 30+ 季度 × 多个字段 ≈ **+50~80 万条**，参考 R24 经验需 **1.5~3 小时**。

**验证**：
```bash
# 补采前（记录基线）
python -c "
import sqlite3
db = sqlite3.connect('data/financials.db')
n = db.execute(\"SELECT COUNT(*) FROM financials WHERE field='netProfit'\").fetchone()[0]
print('netProfit 总行数:', n)"

# 补采后
python -c "
import sqlite3
db = sqlite3.connect('data/financials.db')
n = db.execute(\"SELECT COUNT(*) FROM financials WHERE field='netProfit'\").fetchone()[0]
n_codes = db.execute(\"SELECT COUNT(DISTINCT code) FROM financials WHERE field='netProfit'\").fetchone()[0]
print(f'netProfit 总行数: {n}, 覆盖标的: {n_codes}')"
# 期望：覆盖标的从 ~1717 → 接近 5259
```

---

## 注意事项（吸取历史教训）

1. **卡死预防**：全程 `--workers 2`；若中途无进度（DB 行数 10 分钟不变）立即终止，`PRAGMA integrity_check` 后重启（幂等 INSERT OR REPLACE 自动跳过已同步）。
2. **异常隔离**：脚本已按单只 future 异常隔离，某只失败不影响整体；记录失败标的清单供二次补采。
3. **金融股豁免**：银行/券商/保险（48 只沪深300金融股）天然无 inventory/sellExpense/OCF 等科目，属报表结构差异，**不算缺口**，补采时脚本应能自然跳过或产生"无此科目"记录，不要误判为失败。
4. **幂等性**：INSERT OR REPLACE 幂等，重复执行不重复计行。

---

## 交付物

| 产物 | 说明 |
|------|------|
| financials.db | netProfit 覆盖标的从 ~1717 → 接近 5259 |
| 执行日志 | `logs/sync_all_r37_YYYYMMDD.log`（含失败标的清单） |
| 执行总结 | `D:\Marvis\output\R37数据补强执行报告.md` |

---

## 验收标准

1. `field='netProfit'` 覆盖标的 ≥ 5000（现 ~1717）
2. `field='MBRevenue'` 覆盖标的 ≥ 5000（现 ~1577）
3. 三表勾稽测试不回归：`python -m pytest tests/test_engineering_plan.py::test_three_statement_audit -q`
4. 数据库完整性：`PRAGMA integrity_check` = ok
