# Marvis 定时数据补充任务 — 数据底座保鲜（2026-08-02）

> 背景：2hao 双模式架构已落地（性能模式 DeepSeek 并发 / 训练模式 Marvis 自迭代）。
> 数据底座是双模式的共同地基——**数据不新鲜，报告质量无源之水**。
> 你（Marvis）负责**定时补充更新数据库**，让 2hao 每次跑报告都能拿到最新数据。

---

## 一、数据时效性现状（实测）

> 实测时间：2026-08-10（星期一，凌晨 07:00）。下表"当前最新"为磁盘文件真实状态。
> 注：`company_events.db` 实际无 `events` 总表，拆为 5 张子表，最新日期各异；两融（`margin_daily`）已由 `sync_capital_flow.py --margin` 修复至 2026-08-06，但 08-07 因深交所接口返回空无法补全（SSE 08-07 有数据、SZSE 空，需待交易所接口恢复）。
> 本次执行：资金面（北向+两融）、公司事件（全量沪深 300 回溯 5 天）、板块基线（335 行业已刷新）、一致预期（后台运行中）。名称映射本次凌晨已自动刷新，无需补跑。

| 数据源 | 当前最新（实测） | 时效依赖 | 建议刷新频率 | 备注 |
|---|---|---|---|---|
| `capital_flow.db` → `northbound_daily`（北向） | 2026-08-07 | **日频**（行情日变） | **每日** | 正常（上一交易日） |
| `capital_flow.db` → `margin_daily`（两融） | 2026-08-06 | **日频** | **每日** | ⚠️ 缺 08-07，深交所接口空无法补 |
| `company_events.db` → `earnings`（业绩） | 2026-06-30（Q2） | 季频（财报季） | **每日**入库/**季度**完整 | 中报已入 |
| `company_events.db` → `dividends`（分红） | 2026-08-13（除权日） | 日频（公告随时出） | **每日** | 正常，已超前 |
| `company_events.db` → `share_changes`（增减持） | 2026-08-07 | 日频 | **每日** | 正常 |
| `company_events.db` → `announcements`（公告） | 2026-08-08 | 日频 | **每日** | 已修复（原空表） |
| `company_events.db` → `governance`（治理） | 2026-07-31 | 月频 | **每月** | 正常 |
| `us_stocks.db`（美股 300 只） | 2026-08-07 | 日频（美股收盘） | **每日** | 正常（周五收盘） |
| `consensus_estimates.db`（一致预期） | 2026-08-08 | 周频（研报更新） | **每周** | 正常 |
| `financials.db`（三表明细） | 2026-06-30（Q2） | 季频（财报季） | **季度**（财报季加跑） | 正常 |
| `industry_baselines.json`（335 板块） | 2026-08-10 | 周频（估值漂移） | **每周** | 本次已刷新 |
| `industry_drivers.json`（103 行业） | 2026-08-02 | 月频（政策/景气） | **每月** | 正常 |
| `policy_library.json`（800 政策） | 2026-08-02 | 月频 | **每月** | 正常 |
| `global_macro.json` / `macro_series.json` | 2026-08-01 | 月频（宏观指标） | **每月** | 正常 |
| `industry_chain.json` / `industry_penetration.json` | 2026-08-04 | 低（结构稳定） | **季度核查** | 正常 |
| `a_stock_name_map.json`（5539 只） | 2026-08-10 | 低（新股/改名） | **每周** | 本次已刷新（08-10 凌晨） |

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
