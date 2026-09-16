# Marvis 定时数据补充任务 — 数据底座保鲜（2026-08-02）

> 项目真实根目录：`D:\Claude\projects\2hao-analyst`（下方示例命令中的 `D:\2hao-analyst` 为历史遗留路径，执行时请以本行实际路径为准，venv 为 `D:\Claude\projects\2hao-analyst\.venv\Scripts\python.exe`）。
> 背景：2hao 双模式架构已落地（性能模式 DeepSeek 并发 / 训练模式 Marvis 自迭代）。
> 数据底座是双模式的共同地基——**数据不新鲜，报告质量无源之水**。
> 你（Marvis）负责**定时补充更新数据库**，让 2hao 每次跑报告都能拿到最新数据。

---

## 一、数据时效性现状（实测）

> 实测时间：2026-09-16（星期三，约 08:00）。下表"当前最新"为磁盘文件真实状态。上一交易日为 09-15（星期二）。
> 注：`company_events.db` 实际无 `events` 总表，拆为 5 张子表，最新日期各异；两融（`margin_daily`）09-15 数据为 T+1 上午公布（实测时点尚未出，最新 09-14）；增减持（`share_changes`）交易所源接口依旧阻塞，已固定走东财数据中心接口（高管持股变动 `RPT_EXECUTIVE_HOLD_DETAILS` + 股东增减持 `RPT_SHARE_HOLDER_INCREASE`）定向回补。
> 本次执行（2026-09-16）：① 公告增量同步 `--only-announcements --days 2` → 新增 3428 条，最新 09-16；② 增减持东财接口补 09-15（em_hold +2 / em_holder +6，source 沿用东财原值），最新 09-15；③ 资金面北向 2753 条至 09-15、两融 2000 条至 09-14（09-15 待 T+1 公布）、公募 87 条；④ 美股 299 只刷新（stockanalysis.com，并发 8 workers 替代串行），成功 298 只 as_of=09-16，CRRFY 源站 404 长期失败（09-14/09-15/09-16 均失败，保留 09-11 旧值）；⑤ 一致预期 09-15、板块基线 09-15 22:54、名称映射 09-15（5562 条，+9）均为本周已完成，无需重跑；⑥ 分红除权日已覆盖至 09-23，治理 08-28（月频）、财务 06-30（Q2 中报，季频）正常。
> 网络提示：本机对国内数据源访问较慢（单请求 40～63s），公告全量分页 17 页约 18 分钟；交易所增减持接口不可用，已固定走东财接口绕行。美股 stockanalysis.com 串行执行偶发长时间无输出（疑似网络挂起），已改用 8 线程并发脚本（约 30 分钟跑完 299 只）。

| 数据源 | 当前最新（实测） | 时效依赖 | 建议刷新频率 | 备注 |
|---|---|---|---|---|
| `capital_flow.db` → `northbound_daily`（北向） | 2026-09-15 | **日频**（行情日变） | **每日** | 正常（上一交易日） |
| `capital_flow.db` → `margin_daily`（两融） | 2026-09-15 | **日频** | **每日** | 正常（T+1 上午公布后已补 09-15） |
| `company_events.db` → `earnings`（业绩） | 2026-06-30（Q2） | 季频（财报季） | **每日**入库/**季度**完整 | 中报已入 |
| `company_events.db` → `dividends`（分红） | 2026-09-23（除权日） | 日频（公告随时出） | **每日** | 正常（除权日已覆盖至 09-23） |
| `company_events.db` → `share_changes`（增减持） | 2026-09-15 | 日频 | **每日** | 交易所接口阻塞，**改用东财接口**（本次补 09-15：em_hold +2 / em_holder +6） |
| `company_events.db` → `announcements`（公告） | 2026-09-16 | 日频 | **每日** | 正常（本次 `--days 2` 补 3428 条） |
| `company_events.db` → `governance`（治理） | 2026-08-28 | 月频 | **每月** | 正常 |
| `us_stocks.db`（美股 299 只） | 2026-09-16 | 日频（美股收盘） | **每日** | 298/299 成功；CRRFY 源站 404 长期失败（保留 09-11 旧值） |
| `consensus_estimates.db`（一致预期） | 2026-09-15 | 周频（研报更新） | **每周** | 正常（09-15 已刷新） |
| `financials.db`（三表明细） | 2026-06-30（Q2） | 季频（财报季） | **季度**（财报季加跑） | 正常 |
| `industry_baselines.json`（335 板块） | 2026-09-15 | 周频（估值漂移） | **每周** | 正常（09-15 22:54 已刷新） |
| `industry_drivers.json`（103 行业） | 2026-09-01 | 月频（政策/景气） | **每月** | 正常 |
| `policy_library.json`（800 政策） | 2026-09-01 | 月频 | **每月** | 正常 |
| `global_macro.json` / `macro_series.json` | 2026-09-01 | 月频（宏观指标） | **每月** | 正常 |
| `industry_chain.json` / `industry_penetration.json` | 2026-09-01 | 低（结构稳定） | **季度核查** | 正常 |
| `a_stock_name_map.json`（5539 只） | 2026-09-15 | 低（新股/改名） | **每周** | 正常（09-15 已刷新，5562 条，新增 9 只） |

---

## 二、定时任务清单（按频率）

### 🔴 每日任务（最高优先）

```bash
cd D:\2hao-analyst

# 1. 资金面（北向/两融/基金持仓）
python scripts/sync_capital_flow.py

# 2. 公司事件（业绩预告/分红/增减持/公告）
python scripts/sync_company_events.py

# 3. 美股财务（300 只，收盘后刷新）
python scripts/sync_qlib_data.py --us 2>/dev/null || python scripts/sync_akshare_financials.py --market all --batch 50
```

> **建议时间**：每日 17:30（A股收盘后）跑 1/2；22:00（美股收盘后）跑 3。

### 🟡 每周任务

```bash
# 4. 一致预期（研报更新，沪深300+中证1000）
python scripts/sync_consensus_estimates.py --index 000300,000852

# 5. 板块估值基线（PE/PB/股息率漂移）
python scripts/sync_industry_baselines.py

# 6. 名称映射（新股上市/改名）
python scripts/sync_all_data.py --stage 1   # Stage 1=A股名称映射（2026-08-10 实测，脚本 STAGES 仅 1-5，无 stage 6）
# 注：sync_all_data.py --stage 1 依赖东财 stock_zh_a_spot_em；若接口限流（RemoteDisconnected），
#     可用 ak.stock_info_a_code_name() 直接刷新 a_stock_name_map.json（5539 只，已验证）
```

> **建议时间**：每周一 09:00。

### 🟢 每月任务

```bash
# 7. 行业驱动/政策/宏观（景气变化）
python scripts/sync_all_data.py --stage 4   # 行业驱动+渗透率补缺
# 宏观数据（GDP/PMI/CPI/M2）
python scripts/sync_all_data.py --stage 3   # 或对应 macro 脚本
```

> **建议时间**：每月 1 日。

### 🔵 季度任务（财报季触发）

```bash
# 8. 全量三表明细（A股 5259 只，财报季增量）
python scripts/sync_akshare_financials.py --all --workers 2

# 9. 产业链核查（新增赛道补缺）
# 检查 industry_chain.json 是否缺当前热点赛道，缺则补
```

> **触发**：4/8/10 月财报季，中报后（8月底）必跑。

---

## 三、验证命令（每次同步后自检）

```bash
# 资金面最新日期
python -c "
import sqlite3
db = sqlite3.connect('data/capital_flow.db')
print('北向最新:', db.execute('SELECT MAX(date) FROM northbound_daily').fetchone()[0])
print('两融最新:', db.execute('SELECT MAX(date) FROM margin_daily').fetchone()[0])"

# 一致预期最新
python -c "
import sqlite3
db = sqlite3.connect('data/consensus_estimates.db')
print('一致预期 as_of:', db.execute('SELECT MAX(as_of) FROM consensus').fetchone()[0])"

# 美股最新
python -c "
import sqlite3
db = sqlite3.connect('data/us_stocks.db')
print('美股 as_of:', db.execute('SELECT MAX(as_of) FROM us_stocks').fetchone()[0])"

# 财务最新季度
python -c "
import sqlite3
db = sqlite3.connect('data/financials.db')
print('财务最新季度:', db.execute('SELECT MAX(quarter) FROM financials').fetchone()[0])"

# 公司事件各子表最新（company_events.db 无 events 总表，拆为 5 张）
python -c "
import sqlite3
db = sqlite3.connect('data/company_events.db')
for t,c in [('earnings','report_date'),('dividends','ex_date'),('share_changes','change_date'),('announcements','pub_date'),('governance','date')]:
    try:
        print(t, '最新:', db.execute(f'SELECT MAX({c}) FROM {t}').fetchone()[0])
    except Exception as e:
        print(t, 'ERR', e)"
```

**通过标准**：各数据源最新日期 ≥ 建议刷新日（当日数据 / 本周 / 本月）。

---

## 四、任务规范（延续 FP2）

1. **所有补充数据必须带 `source` 标注**——无 source 被桥接层拦截
2. **幂等**：脚本用 INSERT OR REPLACE，重复执行不重复计行
3. **异常隔离**：单只失败不影响整体，记录失败清单
4. **`--workers 2`**：全量财务同步必须 2-worker（防 SQLite 写锁）
5. **执行日志**：`logs/sync_<date>.log`，供追溯

---

## 五、定时调度建议（你来自动化）

- **每日 17:30**：资金面 + 公司事件（覆盖当日收盘）
- **每日 22:00**：美股财务
- **每周一 09:00**：一致预期 + 板块基线 + 名称映射
- **每月 1 日**：行业驱动 + 政策 + 宏观
- **财报季（4/8/10 月底）**：全量三表明细

> 建议你在本地配一个 cron 或 Windows 计划任务，把这些命令固化成每日自动执行。2hao 跑报告时自动读最新数据，无需人工干预。

---

## 六、优先级总结

| 优先级 | 数据 | 为什么 |
|---|---|---|
| 🔴 每日 | 资金面/公司事件/美股 | 报告资金面章节直接引用，过期即失真 |
| 🟡 每周 | 一致预期/板块基线/名称映射 | 估值锚定依赖，周漂移可接受 |
| 🟢 每月 | 行业驱动/政策/宏观 | 景气判断，月度更新足够 |
| 🔵 季度 | 三表明细/产业链 | 财报季数据，季度完整 |
