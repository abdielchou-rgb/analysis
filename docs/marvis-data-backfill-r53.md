# Marvis 数据补强任务指令 — R53 宏观框架数据扩采（2026-08-03）

> 执行环境：**用户本机**（需 akshare/baostock 网络；沙箱不可执行）
> 背景：2hao 已完成宏观知识库深度吸收（methodology_macro_deep.json），但新框架的
> 方法论指标缺数据支撑。本任务是给 Marvis 的**详细执行指令**，按优先级逐项落地。
> 核心约束：**数据质量优先**——每条数据带 source 标注、幂等写入、失败隔离。

---

## 零、任务总览

| 优先级 | 任务 | 目标 | 交付物 |
|---|---|---|---|
| P0-1 | 财务 4 字段补采 | DA/interestDebt/RD 进 financials.db | 全库补齐 |
| P0-2 | 一致预期历史序列化 | 保留每日快照，可算"预测斜率" | consensus_estimates.db 改造 |
| P1-1 | 宏观高频指标采集 | 粗钢/PTA/螺纹钢/沥青/30城成交等 | macro_highfreq.json |
| P1-2 | 大股东质押率 | pledgeRatio 进财务库 | financials.db 补字段 |
| P2-1 | 领先指标库 | 财政/专项债/土地/能繁母猪/信贷脉冲 | leading_indicators.json |
| P2-2 | 美国高频 | CFNAI/WEI/盈亏平衡通胀率 | us_highfreq.json |

**执行顺序**：P0-1 → P0-2 → P1-1 → P1-2 → P2-1 → P2-2。
每完成一项，跑一次对应验证，再进入下一项。

---

## 一、P0-1：财务 4 字段补采（最高优先，解锁四模型）

### 目标
`financials.db` 补齐 3 个缺失字段：`DA`（折旧摊销）、`interestDebt`（有息债务）、`RD`（研发费用）。
加上已有的 `capex`，即可计算产业生命周期的 `Capex/DA` 黄金比例和固定成本比重。

### 数据源
baostock（免费免 token，字段稳定）：
- `query_balance_data` → 折旧摊销 `depreciation`？需实测字段名
- 有息债务 = 短期借款 + 长期借款 + 应付债券（用已有 `shortLoan` + `longLoan` + 需补 `bondPayable`）
- 研发费用：baostock 无研发字段 → **换 akshare** `stock_financial_abstract_ths`（同花顺财务摘要，有"研发费用"列）

### 操作步骤
1. **探测字段**：先写个小脚本实测 baostock `query_balance_data` 返回哪些字段，确认折旧摊销/应付债券的字段名。
   ```python
   import baostock as bs

   bs.login()
   rs = bs.query_balance_data(code="sh.600519", year="2024", quarter="4")
   while rs.next():
       r = rs.get_row_data()
       print(dict(zip(rs.fields, r)))  # 打印全部字段名
   ```
2. **改造 `scripts/sync_financials.py`**：
   - `query_balance_data` 的 fields 列表追加：折旧摊销、应付债券（若 baostock 有）
   - 若 baostock 无研发字段，新增一段用 akshare `stock_financial_abstract_ths` 补研发费用
   - 写入 `financials.db` 的 `field` 值为：`DA` / `bondPayable` / `RD`
3. **有息债务派生**：不直接存，写一个派生函数 `interest_debt = shortLoan + longLoan + bondPayable`，
   在读取层（core/financial_extract.py）计算，避免冗余存储。
4. **全量重跑**：
   ```bash
   python scripts/sync_financials.py --all --workers 2
   ```

### 验证标准
```python
import sqlite3

conn = sqlite3.connect("data/financials.db")
# 抽查：茅台/柯力 有 DA/RD 字段
for code in ["600519", "603662"]:
    da = conn.execute("SELECT COUNT(*) FROM financials WHERE code=? AND field='DA'", (code,)).fetchone()[0]
    rd = conn.execute("SELECT COUNT(*) FROM financials WHERE code=? AND field='RD'", (code,)).fetchone()[0]
    print(f"{code}: DA={da}条, RD={rd}条")
conn.close()
```
**通过标准**：覆盖 ≥3000 只，DA/RD 每只 ≥4 个季度。

---

## 二、P0-2：一致预期历史序列化（解锁"景气预期斜率"）

### 目标
改造 `consensus_estimates.db`，让同一股票**按日期累积**，形成预测时间序列，从而能算
"预测修正斜率"（景气预期框架核心信号）。

### 现状问题
现有 `consensus` 表主键 `(code, as_of)`，as_of 是日期。但 `sync_consensus_estimates.py`
每天跑会 `INSERT OR REPLACE` 覆盖当天——没有保留历史。

### 操作步骤
1. **改造 `scripts/sync_consensus_estimates.py`**：
   - 主键改 `(code, as_of, updated_at)` 或增加 `version` 字段，保证同一天多次运行不覆盖历史
   - 每次运行插入**新快照**（含完整 as_of 时间戳到秒），保留旧快照
   - 增加 `--history` 模式：用 `stock_research_report_em` 拉取**每份研报的发布时间**，
     按研报日期重建历史预测点（东财研报接口返回的研报列表含发布日期 + 目标价/评级）
2. **重建历史**：对已覆盖的 1315 只跑 `--history`，把研报历史日期作为 as_of 插入，
   形成"预测随时间的演变"。
3. **新增派生字段**：`revision_slope`（近 30 天预测修正方向）、`revision_breadth`（上调家数占比）。
   这些由 Marvis 在采集层计算，或留待 2hao 读取层算（二选一，建议采集层算好存库）。

### 验证标准
```python
import sqlite3

conn = sqlite3.connect("data/consensus_estimates.db")
# 单只股票应有多个历史 as_of
n = conn.execute("SELECT COUNT(DISTINCT as_of) FROM consensus WHERE code='600519'").fetchone()[0]
print(f"茅台历史预测点: {n}个")  # 应 ≥5 才说明历史序列建起来了
conn.close()
```
**通过标准**：≥500 只股票有 ≥3 个历史 as_of；revision_slope 可计算。

---

## 三、P1-1：宏观高频指标采集（解锁高频跟踪）

### 目标
新建 `data/macro_highfreq.json`，采集信达宏观方法论的**高频指数底层指标**（周频/旬频），
让 2hao 能构建生产/消费/固投/出口四大高频指数。

### 需采集的高频指标

| 高频指数 | 底层指标 | 数据源 |
|---|---|---|
| 生产指数 | 粗钢产量（旬）、江浙织机 PTA 负荷率（日）、半钢胎开工率（周） | akshare: 工业品/化纤相关接口 |
| 消费指数 | 乘用车零售（周）、布伦特原油（日）、柯桥纺织价格指数（周） | akshare + 国际油价 |
| 固投指数 | 螺纹钢产量/价格（日）、石油沥青开工率（周）、30城商品房成交（日）、浮法玻璃价格（日） | akshare |
| 出口指数 | BDI、SCFI 运价指数（日） | akshare 海运接口 |

### 操作步骤
1. 新建 `scripts/sync_macro_highfreq.py`（参照 sync_macro 风格）
2. 逐指标探测 akshare 可用接口，确认能拿到哪个频率（日/周/旬）
3. 存成 `data/macro_highfreq.json`：`{指标名: [{date, value}...]}`，带 `source`
4. **能拿到的先存**；akshare 没有的（如柯桥纺织指数）标注 `"unavailable"` 并记录原因

### 验证标准
```python
import json

hf = json.load(open("data/macro_highfreq.json"))
# 至少要有 螺纹钢、粗钢、原油 三组
for k in ["螺纹钢", "粗钢", "原油"]:
    has = any(k in key for key in hf)
    print(f"{k}: {'✓' if has else '✗'}")
```
**通过标准**：≥5 个高频指标入库，每个 ≥30 个数据点。

---

## 四、P1-2：大股东质押率（爆雷识别）

### 目标
`financials.db` 补 `pledgeRatio`（大股东质押率），用于 A 股爆雷识别清单。

### 数据源
akshare：
- `stock_pledge_ratio_detail_em`（东方财富股权质押比例）或 `stock_gpzy_pledge_ratio_em`
- 按股票代码拉取，取最新质押比例

### 操作步骤
1. 新建 `scripts/sync_pledge_ratio.py`
2. 全量拉取（参照 sync_consensus 的 BATCH=200 + sleep + 重试模式）
3. 存入 financials.db（field='pledgeRatio'）或单独 `pledge_ratio.json`

### 验证标准
```python
# 抽查几只质押率已知的股票，数值合理（0-100%）
```
**通过标准**：覆盖 ≥2000 只，数值在 0-100 合理区间。

---

## 五、P2-1：领先指标库（解锁"领先关系"预测）

### 目标
新建 `data/leading_indicators.json`，采集宏观方法论的**领先关系**中提到的指标。

### 需采集

| 领先指标 | 领先目标 | 数据源 |
|---|---|---|
| 财政支出/一般公共预算 | 基建投资（领先1月） | 财政部月度数据 |
| 专项债发行 | 基建投资（领先3-5月） | 财政部/统计局 |
| 土地成交总价 | 土地购置费（领先3-4季度） | 中指院/统计局 |
| 能繁母猪存栏 | 猪肉价格（领先10月） | 农业农村部 |
| 信贷脉冲 | 全球增长（领先2-4季度） | 社融派生 |
| M1-M2 剪刀差 | 实体景气 | 央行 |

### 操作步骤
1. 新建 `scripts/sync_leading_indicators.py`
2. 逐指标探测可用接口；**人工维护型**（如能繁母猪存栏）先用公开已知的最新值填上并标 source
3. 存 `data/leading_indicators.json`：`{指标: {latest_value, latest_date, source, history: [...]}}`

### 验证标准
**通过标准**：≥4 个领先指标入库，每个含 latest_value + source。

---

## 六、P2-2：美国高频指标（对标海外 nowcasting）

### 目标
新建 `data/us_highfreq.json`：CFNAI、WEI、盈亏平衡通胀率（5y5y）。

### 数据源
- FRED API（免费）：`CFNAI`（芝加哥联储）、`WEI`（纽约联储）
- 盈亏平衡通胀率 = 美国 10Y 名义收益率 - 10Y TIPS 实际收益率（FRED 两组序列）

### 操作步骤
1. 新建 `scripts/sync_us_highfreq.py`
2. 用 FRED API 拉取（需注册免费 API key，Marvis 配置在 `.env` 的 `FRED_API_KEY`）
3. 存 `data/us_highfreq.json`

### 验证标准
```python
import json

us = json.load(open("data/us_highfreq.json"))
print("CFNAI:", len(us.get("CFNAI", [])), "期")
```
**通过标准**：CFNAI + WEI 各 ≥100 期。

---

## 七、通用规范（所有任务遵守）

1. **幂等**：脚本可重复运行，INSERT OR REPLACE / 覆盖写入，不产生脏数据
2. **source 标注**：每条数据带 `source`（如 "akshare: xxx接口" / "baostock: query_balance_data"）
3. **失败隔离**：单只/单指标失败不中断整体，打印 `[FAIL]` 并继续
4. **重试**：网络接口用 5 次退避重试（参照 sync_consensus_estimates.py 的 `_retry`）
5. **批处理**：批量接口 BATCH=200，批间 sleep 0.6s，防限流
6. **验证**：每项完成跑对应验证脚本，通过才算完成
7. **报告**：完成一项写一项小结（产出文件/覆盖数/验证结果/遇到的问题），最终汇总成执行报告

---

## 八、执行环境准备

```bash
cd D:\2hao-analyst
pip install akshare baostock  # 若未装
# FRED API key（P2-2 需要）: 在 .env 加 FRED_API_KEY=xxx
```

---

## 九、完成验收清单

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| P0-1 | financials.db 含 DA/RD/bondPayable | ≥3000只 × ≥4季度 |
| P0-2 | consensus 历史序列 | ≥500只 × ≥3 as_of + revision_slope |
| P1-1 | macro_highfreq.json | ≥5指标 × ≥30点 |
| P1-2 | pledgeRatio | ≥2000只 0-100% |
| P2-1 | leading_indicators.json | ≥4指标 + source |
| P2-2 | us_highfreq.json | CFNAI+WEI ≥100期 |

> 全部完成后，写执行报告到 `D:\Marvis\output\R53数据扩采执行报告.md`，
> 格式参照 `R37数据底座补强执行报告.md`。
