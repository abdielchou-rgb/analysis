# Marvis 数据补充任务清单 — R33（2026-08-02）

> 前置：Marvis 已完成沪深300/中证1000 财务明细同步（5259 只、+97万条）与 A 股名称映射（5537 条）。
> 本清单针对**已接入数据的质量缺口**与**管线消费点缺失**，按优先级排序。

---

## 一、数据接入确认（已完成，无需重做）

| 数据 | 状态 | 验证结果 |
|---|---|---|
| financials.db | ✅ 已接入 | 251万行 / 5259 只 / 43 字段；柯力 balance 16 字段（应收/存货/商誉/研发全齐）、profit 11 字段，最新季度 2026-03-31 |
| a_stock_name_map.json | ✅ 已接入 | 5537 条；resolve_asset 能解析柯力/贵州茅台/招商银行等，含后缀匹配（芯联集成-U→688469） |
| industry_chain.json | ✅ 已接入 | 54 行业产业链（上游/中游/下游/关键玩家） |
| industry_drivers.json | ✅ 已接入 | 103 行业驱动（含工控/仪器仪表） |
| industry_baselines.json | ✅ 已接入 | 335 申万板块 PE/PB/股息率 |
| industry_penetration.json | ✅ 已接入 | 200 条渗透率数据 |

---

## 二、P0 缺口（直接影响现有报告质量）

### P0-1：名称映射缺失 7 只股票（financials 有数据但查不到名字）

**背景**：`financials.db` 覆盖 5259 只，但 `a_stock_name_map.json` 缺 7 只代码的名称，管线无法用中文名解析到这些股。

| 代码 | 股票 | 影响 |
|---|---|---|
| 300114 | 中航电测 | **管线可比基准公司**，柯力报告 §3.2/§6.3 引用其 PE 65x |
| 600637 | 东方明珠 | 普通标的 |
| 920690/920717/920718/920719 | 北交所新代码 | 北交所标的 |
| 000300 | 沪深300指数 | 指数非股票，可忽略 |

**Marvis 任务**：用 akshare `stock_info_a_code_name()` 或腾讯行情接口补充这 7 只的名称→代码映射，写入 `data/a_stock_name_map.json`（结构 `{"股票名":"代码"}`，UTF-8、ensure_ascii=False）。校验：300114→中航电测。

### P0-2：industry_chain 缺传感器/仪器仪表/工控产业链

**背景**：柯力传感（称重传感器龙头）瓶颈引擎 `load_industry_chain('柯力传感')` 返回空，产业链分析读不到上游（弹性体/应变计/芯片）、中游（传感器制造）、下游（衡器/机器人/工业物联网）。

**Marvis 任务**：为 `data/industry_chain.json` 补充 3 个行业链条（结构对齐现有：`name/upstream/midstream/downstream/key_players/source`）：
1. **传感器**（含称重/力传感器）：上游=弹性体（不锈钢/合金钢）、应变计、MCU芯片、PCB；中游=传感器制造、模组封装、校准测试；下游=衡器、工业称重系统、机器人力觉、物联网
2. **仪器仪表**：上游=传感器、芯片、精密加工；中游=工业仪表、测试测量设备、自动化仪器；下游=石油化工、电力、智能制造
3. **工控**：上游=PLC/传感器/伺服电机；中游=工控系统集成、工业软件；下游=工厂自动化、机器人

每条必须带 `source` 字段。校验：`python -c "from core.data_basement import load_industry_chain; print(load_industry_chain('柯力传感'))"` 不再为空。

### P0-3：consensus_prices.json 无结构化一致预期

**背景**：`data/consensus_prices.json` 当前只有 8 个 PDF 文件名做 key（`{'rating': '增持'}` 等），**没有结构化个股一致预期价格**。R30 预期差模块 `compute_surprise('603662')` 依赖它判断"一致预期 vs 实际"，当前 target_price_avg 为 null。

**Marvis 任务**：用 akshare `stock_profit_forecast_ths`（同花顺一致预期）为**沪深300 + 中证1000 全量**补充结构化一致预期，写入 `data/consensus_prices.json`，结构建议：
```json
{
  "603662": {
    "eps_2026e": 1.2, "eps_2027e": 1.43, "eps_2028e": 1.64,
    "target_price_avg": 52.0, "rating_buy": 4, "rating_hold": 0, "rating_sell": 0,
    "n_analysts": 12, "as_of": "2026-08-01", "source": "akshare:stock_profit_forecast_ths"
  }
}
```
注意：`earnings_surprise.py` 现有实现从 akshare 直接拉取，需确认写入文件后能被读取（检查 `core/earnings_surprise.py` 的读取路径，当前 `compute_surprise(code)` 走 akshare 实时接口，离线可用性取决于是否有缓存）。

---

## 三、P1 缺口（增强类，锦上添花）

### P1-1：柯力/传感器行业一致预期缺 target_price

`compute_surprise('603662')` 当前 `consensus_target=None`（12 家分析师有 EPS 预测但无目标价均值）。补充 target_price_avg 可激活预期差信号。

### P1-2：北交所/科创板尾部覆盖

`financials.db` 有 920 段北交所数据但名称映射缺 4 只。若北交所不是重点分析对象可降级。

### P1-3：港股 Layer1 财务明细

交接文档提过港股 Layer1（25 只）但本次未同步。若有港股分析需求，可补 `sync_akshare_financials.py --market HK`。

---

## 四、验证命令汇总（Marvis 执行后自检）

```bash
cd D:\2hao-analyst

# 1. 名称映射补全验证
python -c "import json; d=json.load(open('data/a_stock_name_map.json',encoding='utf-8')); print(d.get('中航电测'), d.get('东方明珠'))"

# 2. 产业链补全验证
python -c "from core.data_basement import load_industry_chain; print(bool(load_industry_chain('柯力传感')))"

# 3. 一致预期验证
python -c "
import sys; sys.path.insert(0,'.')
from core.earnings_surprise import compute_surprise
s = compute_surprise('603662')
print(s.get('consensus_target'), s.get('n_analysts'))"

# 4. 回归
python -m pytest tests/test_e2e_keli.py tests/test_engineering_plan.py -q
```

---

## 五、执行建议

- **P0-1（名称映射 7 只）**：5 分钟可完成，建议立即做
- **P0-2（产业链 3 行业）**：需要 AI 搜索/行业知识补充，建议用 tavily/DeepSeek 生成后人工校验
- **P0-3（一致预期全量）**：akshare 接口批量拉取，注意 akshare 名称接口断连时用腾讯兜底（同 Marvis 上次做法）
