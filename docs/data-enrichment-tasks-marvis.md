# 数据丰富度提升 — Marvis 执行需求说明书

> 交接给独立 agent（Marvis/其他）执行。目标：让 2hao-analyst 的数据底座覆盖更多维度，提升报告分析深度。
> 生成日期：2026-08-01

## 0. 背景与目标

2hao-analyst 目前财务+行情数据扎实，但以下维度薄弱，直接影响行业/公司报告的分析深度：
- 行业级数据（baselines/drivers）仅 12KB，行业报告支撑不足
- 资金面（北向/公募/两融）完全缺失，SAC 行业报告硬性要求
- 一致预期（EPS/目标价/评级）来自研报，只消化了 ~8%
- 公司治理/事件数据缺失，listed/unlisted 报告需要

**执行原则（FP2 数据零编造）**：所有数据必须来自真实来源（akshare 接口 / 研报 PDF / 公开数据），每条带 source 标注。禁止编造或估算当真实数据。

---

## 1. 任务清单（按优先级）

### P0-① 消化基线研报（原料已有，收益最大）

**现状**：`data/基线/` 有 2419 份 PDF（回测基线库/估值模型/宏观方法论/行业分析框架），但 `baseline_findings.json` 只有 124 条（gold 53 + A级 + academic），消化率 ~8%。
**目标**：把回测基线库的 2 阶段 + 金牌库剩余 ~1700 份消化入库。

**命令**（分批跑，避免一次全量）：
```bash
python scripts/feed_reports.py --status                    # 先看当前状态
python scripts/feed_reports.py --batch 200                 # 每次消化 200 份
# 重复直到 --status 显示全量消化
```

**产出**：`data/baseline_findings.json`（增量合并）、`data/feed_history.json`（去重记录）
**字段**：每条含 rating / analysts / market_size / forecasts / file / level

---

### P0-② 资金面数据同步（SAC 行业报告硬要求）

**现状**：无。SAC `capital_flow` 维度要求"北向资金/公募仓位/两融至少 2 个维度"。
**数据源**：akshare 免费接口。

**要写一个 sync 脚本**（仿照 `scripts/sync_akshare_financials.py` 的分批+异常隔离模式），拉取并入库：

| 数据 | akshare 接口 | 用途 |
|---|---|---|
| 北向资金持仓 | `stock_hsgt_hold_stock_em` | 个股北向持仓 |
| 北向资金流向 | `stock_hsgt_fund_flow_summary_em` | 板块资金流向 |
| 两融余额 | `stock_margin_detail_szse` / `stock_margin_sse` | 融资融券 |
| 公募重仓 | `fund_portfolio_hold_stock` | 基金重仓股 |

**存储**：新建 `data/capital_flow.db`，表结构建议：
```sql
CREATE TABLE capital_flow (
  code TEXT, date TEXT, metric TEXT,  -- 如 north_hold/north_flow/margin/fund_hold
  value REAL, source TEXT,
  PRIMARY KEY (code, date, metric)
);
```

**产出**：`data/capital_flow.db` + 一个 `scripts/sync_capital_flow.py` 脚本

---

### P0-③ 行业级数据扩充

**现状**：`industry_baselines.json`(287B) / `industry_drivers.json`(8KB) / `industry_cache.json`(3KB) 太薄。
**目标**：为常用行业补全基线数据。

**方案 A（简单）**：从已消化的研报 PDF 里提取行业财务基线（毛利率/ROE/增速中位数），结构化写入 `industry_baselines.json`。
**方案 B（推荐，可批量）**：写一个行业基线同步脚本，用 akshare 行业板块接口拉取：

| 数据 | akshare 接口 |
|---|---|
| 行业财务指标 | `stock_board_industry_*` / `stock_sector_fund_flow_rank` |
| 行业估值 | `stock_board_industry_name_em`（PE/PB/股息率） |
| 行业涨跌/资金 | `stock_sector_spot` |

**存储**：扩充 `data/industry_baselines.json`，结构：
```json
{
  "industry": "半导体",
  "as_of": "2026-08-01",
  "metrics": {"pe_ttm": 45.2, "pb": 3.1, "gross_margin_pct": 32.5, "roe_pct": 12.0, "revenue_growth_pct": 18.0},
  "source": "akshare: stock_board_industry_name_em"
}
```

---

### P0-④ 一致预期数据（提升估值/评级分析）

**现状**：`consensus_prices.json`(1KB) 几乎为空；`投行估值数据全量索引.json`(134KB) 有历史估值参数。
**目标**：补充"一致预期"——市场对标的的 EPS/目标价/评级共识。

**方案**：从已消化的金牌研报中提取评级/目标价/EPS 预测，聚合为一致预期。`baseline_findings.json` 的 `forecasts` 字段已有部分，需结构化。
**产出**：扩充 `data/consensus_prices.json` 或新建 `data/consensus_estimates.json`：
```json
{
  "code": "600519",
  "as_of": "2026-08-01",
  "n_analysts": 12,
  "target_price_avg": 1850.0,
  "rating_dist": {"买入": 8, "增持": 3, "中性": 1},
  "eps_2026e": 62.5,
  "source": "研报聚合(2026-07 金牌库)"
}
```

---

### P0-⑤ 公司治理/事件数据（listed/unlisted 需要）

**数据源**：akshare
| 数据 | akshare 接口 |
|---|---|
| 股东结构 | `stock_shareholder_change` / `stock_main_stock_holder` |
| 高管/董监高 | `stock_manager_profile` / `stock_hold_management` |
| 股权质押 | `stock_pledge_ratio` |
| 限售解禁 | `stock_restricted_release_queue_em` |
| 诉讼/处罚 | `stock_illegal_announcement` / `stock_justice_announcement` |

**存储**：新建 `data/company_events.db`，表结构 `company_events(code, date, event_type, title, detail, source)`。

---

## 2. 格式规范（所有任务必须遵守）

### 2.1 数据入库统一格式
- **SQLite 库**：`data/*.db`，WAL 模式（支持多进程）
- **JSON 库**：`data/*.json`，UTF-8，`ensure_ascii=False`，每条带 `source`
- **主键**：可重复入库（幂等）——`INSERT OR REPLACE` 或按主键去重

### 2.2 source 标注（FP2 强制）
每条数据必须带来源：
- akshare 接口 → `source: "akshare: <接口名>"`
- 研报 → `source: "<机构>_<标的>_<日期>"`
- 人工 → 必须注明出处 URL/文档

### 2.3 脚本规范（仿 sync_akshare_financials.py）
- **分批**：全量任务按 BATCH=200 分批提交，批间 sleep 0.5s
- **异常隔离**：每个 future 包 try/except，单点失败不拖垮全任务
- **进度日志**：每批打印 `[进度] done/total`
- **幂等**：重复跑不产生重复数据
- **--dry-run**：支持预览不写入
- **--workers**：默认 2，akshare 源有限流

### 2.4 完成检查
- 跑 `python scripts/sync_akshare_financials.py --status`（现有）确认库状态
- 新库写完后跑一次读回验证（count + 抽样）
- 更新本文件的"完成状态"段

---

## 3. 完成状态

| 任务 | 状态 | 执行日期 | 备注 |
|---|---|---|---|
| P0-① 消化基线研报 | ☐ 待执行 | | 分批 `--batch 200` |
| P0-② 资金面同步 | ☐ 待执行 | | 需写 sync_capital_flow.py |
| P0-③ 行业基线 | ☐ 待执行 | | 方案 B 推荐 |
| P0-④ 一致预期 | ☐ 待执行 | | 依赖 P0-① 的研报聚合 |
| P0-⑤ 公司事件 | ☐ 待执行 | | |

---

## 4. 参考资料
- 现有脚本范本：`scripts/sync_akshare_financials.py`（分批+异常隔离模式）
- 投喂脚本：`scripts/feed_reports.py`
- 数据字典规范：`core/data_dict.py`
- 财务库结构：`data/financials.db`（profit/balance/cashflow 三表）
