# Marvis 数据储备扩充任务 — 对标顶级投行报告（2026-08-02）

> 背景：双模式架构已落地，数据底座是共同地基。当前数据能支撑"结构完整"的报告，
> 但要**对标顶级投行/券商深度报告**，还缺几类关键数据。
> 你（Marvis）负责**批量储备**这些数据，让 2hao 写报告时有足够弹药。

---

## 一、对标差距分析（实测）

| 顶级报告要素 | 2hao 现状 | 差距 |
|---|---|---|
| **分业务线收入拆分** | 仅柯力/思必驰等个别 enrich 有 | **缺全库分业务数据**（称重/物联网/机器人各占多少） |
| **可比公司估值矩阵** | global_leaders 150 家（全球） | **缺 A 股同行业可比明细**（中航电测/睿创微纳等 PE/PB/增速） |
| **一致预期目标价** | consensus 1264 只有 EPS/评级，**target_price 全 NULL** | 免费源不可得（已确认），**需付费源或人工维护** |
| **盈利预测表** | predict_model 单标的 | **缺行业/同业预测对照** |
| **产业链利润池** | industry_chain 69 行业 | 缺**环节利润分布**（上游/中游/下游各占多少利润） |
| **美股对标** | us_stocks.db 300 只 | **缺分行业美股**（半导体/机器人/传感器美股） |
| **估值参数库** | valuation_params 66 个标的 | 可扩充至**更多标的** |
| **政策库** | policy_library 800 条/80 行业 | 可**增量补充最新政策** |

---

## 二、数据储备任务（按优先级）

### P0：A 股可比公司估值明细（最高价值）

**为什么**：报告估值章节需要"可比公司 PE/PB/市值/增速"矩阵。当前只有全球龙头，A 股可比靠 enrich 手补。

**任务**：为沪深300 + 中证1000 全量（约 1300 只）建立**同行业可比估值库**，写入新 db 或 json：
```json
{
  "603662": {
    "industry": "仪器仪表",
    "peers": [
      {"name": "中航电测", "code": "300114", "pe_ttm": 49.9, "pb": 3.2, "mcap_b": 220, "rev_growth": 15},
      {"name": "汉威科技", "code": "300007", "pe_ttm": 85.9, "pb": 4.1, "mcap_b": 80, "rev_growth": 8}
    ],
    "industry_avg_pe": 46.5, "industry_median_pe": 44.0,
    "as_of": "2026-08-02", "source": "akshare: stock_board_industry_cons_em"
  }
}
```
**命令**：
```bash
python scripts/build_peer_valuation.py --index 000300,000852 --workers 2
# 产出 data/peer_valuation.json，覆盖 ~1300 只
```

### P0：分业务线收入拆分库（消除"预测无拆解"）

**为什么**：审计反复指出"盈利预测无分业务线拆解"。顶级报告都有称重/物联网/机器人三层预测表。

**任务**：为沪深300 + 中证1000 全量补**分业务收入结构**（主营构成），写入 `data/segment_revenue.json`：
```json
{
  "603662": {
    "segments": [
      {"name": "称重传感器", "revenue_2025": 12.0, "pct": 77, "growth": 15},
      {"name": "工业物联网", "revenue_2025": 2.0, "pct": 13, "growth": 30},
      {"name": "其他", "revenue_2025": 1.6, "pct": 10, "growth": 5}
    ],
    "source": "akshare: stock_zygc_em",
    "as_of": "2026-08-02"
  }
}
```
**命令**：
```bash
python scripts/build_segment_revenue.py --index 000300 --workers 2
# 产出 data/segment_revenue.json
```

### P1：产业链利润池分布（瓶颈引擎增强）

**为什么**：`bottleneck_engine` 需要"各环节利润占比"判断卡点，当前只有环节列表无利润分布。

**任务**：为 industry_chain.json 的 69 行业补**环节利润占比**（上游/中游/下游各 %）：
```json
{"name": "传感器", "profit_pool": {"上游": 25, "中游": 45, "下游": 30}, "source": "..."}
```
**命令**：脚本或 AI 搜索补全，产出 `data/industry_profit_pool.json`。

### P1：分行业美股龙头库（全球对标）

**为什么**：global_leaders 150 家偏泛，缺**半导体/机器人/传感器**等关键行业美股明细。

**任务**：为热门赛道补美股龙头（每行业 5-10 家），含财务/估值：
```json
{"industry": "半导体设备", "stocks": [
  {"ticker": "AMAT", "name": "Applied Materials", "pe": 20, "revenue_b": 26, "mcap_b": 160},
  {"ticker": "LRCX", "name": "Lam Research", "pe": 25, "revenue_b": 17, "mcap_b": 95}
]}
```
**命令**：扩充 `data/us_stocks.db` 或新增 `data/us_sector_leaders.json`。

### P2：一致预期目标价（付费源 or 人工）

**已确认**：免费接口无 target_price。建议：
- 若你有 Wind/Choice/iFind 访问，手动导出 CSV 补 `consensus_estimates.db` 的 target_price_avg
- 或建立**人工维护清单**：重点 50 只标的的目标价由人工定期更新

### P2：政策库增量

**任务**：每月增量补充最新政策（新政策/新行业），`policy_library.json` 800 → 1000+ 条。

---

## 三、执行建议（你来自动化）

### 一次性大储备
```bash
cd D:\2hao-analyst
# P0-1 可比估值库（沪深300+中证1000）
python scripts/build_peer_valuation.py --index 000300,000852 --workers 2
# P0-2 分业务收入库
python scripts/build_segment_revenue.py --index 000300 --workers 2
# P1 产业链利润池
python scripts/build_industry_profit_pool.py
```

### 定时增量（并入你已有的每日/每周任务）
| 频率 | 任务 |
|---|---|
| 每日 | 资金面 + 公司事件 + 美股（已有） |
| 每周 | 可比估值刷新 + 一致预期 + 名称映射 |
| 每月 | 政策库增量 + 产业链利润池核查 |

---

## 四、验证命令

```bash
# 可比估值库
python -c "
import json
d = json.load(open('data/peer_valuation.json', encoding='utf-8'))
print('覆盖标的:', len(d))
print('柯力:', json.dumps(d.get('603662', {}), ensure_ascii=False)[:200])"

# 分业务库
python -c "
import json
d = json.load(open('data/segment_revenue.json', encoding='utf-8'))
print('覆盖标的:', len(d))
print('柯力:', json.dumps(d.get('603662', {}), ensure_ascii=False)[:200])"

# 利润池
python -c "
import json
d = json.load(open('data/industry_profit_pool.json', encoding='utf-8'))
print('行业数:', len(d))
print('传感器:', json.dumps(d.get('传感器', {}), ensure_ascii=False)[:200])"
```

---

## 五、核心原则

1. **所有数据带 source**（FP2 零编造）——akshare/年报/公开数据
2. **幂等**：重复执行不重复计行
3. **全量优先**：先覆盖沪深300+中证1000，再扩展
4. **验证跑通再交付**：每条命令必须输出可读结果

---

*这份任务让 2hao 写报告时能有：A股可比估值矩阵、分业务预测、产业链利润池、行业美股对标——对标顶级投行报告的数据底座。*
