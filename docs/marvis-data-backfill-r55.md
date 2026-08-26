# Marvis 数据补充综合指令 — R55 行业方法论全球视野升级（2026-08-03）

> 执行环境：**用户本机**（需 akshare/baostock/网络；沙箱不可执行）
> 背景：2hao 已完成行业方法论系统性升级（R55）——SAC 升级到 23 维、新增
> **全球-区域-细分三段式**（渗透率错位/时光机/对手盘参照）和**公司层四层金字塔**
> （玩家分层/可比/选股传导/非上市威胁）。这些新维度需要**全球视角数据底座**支撑。
> 本指令是**综合前面所有讨论**（R53 数据扩采 + R55 方法论升级）的完整数据补充清单。
> 核心约束：**数据质量优先**——每条数据带 source、幂等写入、失败隔离、无数据不编造。

---

## 零、任务总览

| 优先级 | 任务 | 目标 | 交付物 |
|---|---|---|---|
| **P0-1** | **细分行业全球玩家映射** | 全球龙头按细分行业归位（传感器/半导体/机器人等） | `global_industry_players.json` |
| **P0-2** | **区域渗透率参照库** | 中国 vs 海外领先国的渗透率错位数据 | `regional_penetration.json` |
| **P1-1** | **全球龙头财务扩充** | global_leaders 细分行业标签细化 + 海外营收占比 | 更新 `global_leaders.json` |
| **P1-2** | **细分市场规模全球拆分** | 热门行业全球/区域/细分三层规模数据 | `global_market_segments.json` |
| **P2-1** | **非上市关键玩家档案** | 热门行业非上市玩家威胁度判断数据 | `unlisted_players.json` |
| **P2-2** | **一致预期目标价补全** | consensus_prices 结构化（评级→目标价） | 更新 `consensus_prices.json` |
| **P3-1** | **R53 遗留补齐** | 受限项（SCFI/柯桥纺织/土地成交） | 补 macro_highfreq/leading_indicators |

**执行顺序**：P0-1 → P0-2 → P1-1 → P1-2 → P2-1 → P2-2 → P3-1。
每完成一项，跑一次对应验证，再进入下一项。

---

## 一、P0-1：细分行业全球玩家映射（最高优先，解锁全球竞争维度）

### 为什么需要
R55 升级后，行业报告 `global_competition` 维度要求"中国玩家 vs 国际玩家的份额/
技术代差/成本优势对比"，但当前 `global_leaders.json` 只有 150 家龙头且行业标签
是"科技/医药"这种**粗粒度**——**没有"传感器→Sensirion/博世/霍尼韦尔"这种
细分行业全球玩家映射**。没有这个，报告写不出"中国 vs 全球在每个细分的位置"。

### 目标
新建 `data/global_industry_players.json`，为**热门行业**提供全球玩家清单。

### Schema
```json
{
  "气体传感器": {
    "players": [
      {"name": "Honeywell", "ticker": "HON", "country": "US", "segment": "工业安全",
       "role": "global_leader", "market_share_est": 22, "confidence": "E",
       "public": true, "note": "含City Technology"},
      {"name": "Sensirion", "ticker": "SENSIRION.SW", "country": "CH", "segment": "环境监测",
       "role": "global_leader", "market_share_est": 10, "confidence": "E",
       "public": true, "note": "MEMS热导/湿度"},
      {"name": "博世", "ticker": "", "country": "DE", "segment": "汽车电子",
       "role": "global_leader", "market_share_est": null, "confidence": "E",
       "public": false, "note": "非上市，MEMS汽车传感器龙头"}
    ],
    "source": "ai_search: 传感器行业全球格局",
    "updated_at": "2026-08-03"
  }
}
```

### 操作步骤
1. 新建 `scripts/build_global_industry_players.py`
2. **首批覆盖行业**（至少 8 个热门行业，2hao 高频分析对象）：
   `气体传感器`、`半导体`、`人形机器人`、`光伏`、`锂电`、`工控/自动化`、`医疗器械`、`消费电子`
3. 每个行业：用 WebSearch/ai_search 找**全球前 5-8 家参与者**（含非上市），
   记录：名称/国家/所在细分/角色（全球龙头/中国龙头/挑战者）/市占率估算（标置信度 E=估算）/是否上市
4. 市占率**不确定就填 null + confidence="E"**，不编造精确数字
5. 数据带 `source`（哪个搜索来源）

### 验证标准
```python
import json

d = json.load(open("data/global_industry_players.json"))
# 至少 8 个行业，每个行业 ≥5 家玩家
print("行业数:", len(d))  # 应 ≥8
for ind, v in d.items():
    print(f"{ind}: {len(v['players'])}家玩家, public={sum(1 for p in v['players'] if p.get('public'))}家上市")
```
**通过标准**：≥8 行业 × ≥5 家玩家，每家有 country/role/confidence 字段。

---

## 二、P0-2：区域渗透率参照库（解锁"渗透率错位/时光机"判断）

### 为什么需要
R55 升级后，`global_market_sizing` 要求**区域渗透率错位判断**（谁领先、中国落后几年）
和**时光机**（对标领先国路径预测中国未来）。这需要"中国 vs 海外领先国"的
渗透率错位数据。当前 `industry_penetration.json` 只有 12 条且无区域对照。

### 目标
新建 `data/regional_penetration.json`，为热门行业提供中国 vs 海外领先国的渗透率对照。

### Schema
```json
{
  "气体传感器": {
    "china_penetration_pct": 30,
    "china_penetration_year": 2025,
    "leading_country": "日本/美国",
    "leading_penetration_pct": 60,
    "leading_penetration_year": 2025,
    "gap_years_est": 5,
    "time_machine_basis": "人均GDP对标/渗透率曲线错位",
    "source": "ai_search: 气体传感器渗透率 日本 美国 对比",
    "confidence": "E"
  }
}
```

### 操作步骤
1. 新建 `scripts/build_regional_penetration.py`
2. **首批覆盖行业**（与 P0-1 对齐）：
   `气体传感器`、`半导体`、`人形机器人`、`光伏`、`锂电`、`工控`、`医疗器械`、`消费电子`
3. 每个行业：用 WebSearch 找中国渗透率、海外领先国（美/日/韩/欧）渗透率，
   估算差距年数（若数据明确给数字，否则给区间/null + confidence="E"）
4. **数据不可得就显式标注 "unavailable" + 原因**，不编造

### 验证标准
**通过标准**：≥6 行业有数据，每个含 china_penetration_pct + leading_penetration_pct
（或显式标注不可得）。

---

## 三、P1-1：全球龙头财务扩充 + 细分标签细化

### 为什么需要
当前 `global_leaders.json`（150 家）行业标签是"科技/医药"粗粒度，且缺**海外营收占比**
（中国公司出海分析需要"中国龙头海外收入占比 40-60%"这个关键指标）。

### 操作步骤
1. **细分标签细化**：把 global_leaders 里粗标签（科技/半导体/消费）细化到
   细分行业（如 "半导体→半导体设备/存储/模拟芯片"）
2. **补海外营收占比**：对 150 家龙头，能拿到海外收入占比的补 `overseas_revenue_pct`，
   拿不到标 null
3. **补中国龙头**：增加中国出海龙头（如宁德时代/比亚迪/美的/海尔）的海外营收占比
   （这是"中国公司全球发力"命题的直接数据支撑）

### Schema（新增字段）
```json
{
  "industry": "半导体设备",
  "company": "Applied Materials",
  "ticker": "AMAT",
  "overseas_revenue_pct": 75,
  "overseas_revenue_pct_source": "FY2024 10-K",
  "china_revenue_pct": 30
}
```

### 验证标准
**通过标准**：≥30 家龙头有细化行业标签；≥20 家中国出海龙头有海外营收占比。

---

## 四、P1-2：细分市场规模全球拆分

### 为什么需要
R55 升级后，`market_size` 要求**每个细分市场给海外同细分的规模/渗透率/格局作对照**。
当前 `peer_valuation.json`（1300只）只有估值数据，无**细分市场的全球规模拆分**。

### 目标
新建 `data/global_market_segments.json`，为热门行业提供全球/区域/细分三层规模。

### Schema
```json
{
  "气体传感器": {
    "global_tam_2025": {"value": 45, "unit": "亿美元", "source": "Gartner/灼识"},
    "china_tam_2025": {"value": 12, "unit": "亿美元"},
    "segments": {
      "工业安全": {"global": 15, "china": 4, "growth_cagr": 8},
      "汽车电子": {"global": 12, "china": 3.5, "growth_cagr": 12},
      "医疗健康": {"global": 5, "china": 1, "growth_cagr": 15}
    },
    "source": "ai_search: 气体传感器市场规模 细分 全球",
    "confidence": "E"
  }
}
```

### 操作步骤
1. 新建 `scripts/build_global_market_segments.py`
2. 首批行业：气体传感器/半导体/人形机器人/光伏/锂电
3. 每个行业：找全球 TAM、中国 TAM、3-4 个细分市场的全球/中国规模 + 增速
4. **数据不可得用 null + confidence="E"**，不编造；引用的第三方数据带年份+来源

### 验证标准
**通过标准**：≥5 行业，每个含 global_tam + 至少 3 个细分市场的 global/china 规模。

---

## 五、P2-1：非上市关键玩家档案

### 为什么需要
R55 新增 `unlisted_players` 维度（非上市威胁判断）。气体传感器行业有大量关键
非上市玩家（如未上市的国产电化学传感器厂商），不覆盖它们"国产替代空间大"
的判断就没有对手盘。

### 目标
新建 `data/unlisted_players.json`，为热门行业提供非上市关键玩家威胁度数据。

### Schema
```json
{
  "气体传感器": {
    "players": [
      {"name": "某国产电化学传感器厂商", "public": false,
       "threat_level": "high", "role": "国产替代主力",
       "strategic_actions": "产能扩张/绑定头部客户",
       "impact_on_profit_pool": "压缩电化学路线利润率",
       "data_available": false,
       "note": "无权威财务数据，定性判断"}
    ],
    "source": "ai_search: 气体传感器 非上市 厂商"
  }
}
```

### 操作步骤
1. 新建 `scripts/build_unlisted_players.py`
2. 首批行业：气体传感器/半导体/机器人/光伏
3. 每个行业找 3-5 家非上市关键玩家，记录：威胁度（高/中/低）+ 战略动作 +
   对利润池影响。**无权威数据必须 data_available=false + 定性判断**（FP2 诚实边界）

### 验证标准
**通过标准**：≥4 行业 × 3 家非上市玩家，每家含 threat_level + impact_on_profit_pool。

---

## 六、P2-2：一致预期目标价补全

### 为什么需要
`consensus_prices.json` 当前只从 PDF 文件名解析出 rating（"买入"），**无结构化目标价**。
R35/R46 估值勾稽、R30 目标价台账都需要真实目标价数据（当前 target_price_avg 为 None）。

### 操作步骤
1. 探测 akshare `stock_research_report_em` 返回字段是否含目标价（此前确认只有评级）
2. 若有目标价 → 结构化写入 consensus_prices.json：`{code: {rating, target_price, target_date}}`
3. 若免费接口确认无目标价 → 记录 "unavailable" + 原因（不编造），
   留待付费源/人工维护

### 验证标准
**通过标准**：≥100 只股票有结构化目标价（若接口可得）；否则显式记录不可得。

---

## 七、P3-1：R53 遗留补齐

### 目标
R53 交付时标注 unavailable 的受限项，能补的补上：

| 指标 | R53 状态 | 补充方式 |
|---|---|---|
| SCFI 上海出口集装箱运价指数 | unavailable | 探测 akshare 航运接口；不可得则保持标注 |
| 柯桥纺织价格指数 | unavailable | 探测 akshare 化纤接口；不可得则保持 |
| 土地成交总价 | unavailable（付费） | 保持标注，可用"300城土地成交"替代探测 |
| 粗钢产量旬度 | unavailable | 探测统计局旬度接口；不可得则保持 |

### 验证标准
**通过标准**：能补的补上（每个 ≥30 点），确实不可得的保持 "unavailable" 标注。

---

## 八、通用规范（所有任务遵守）

1. **幂等**：脚本可重复运行，覆盖写入，不产生脏数据
2. **source 标注**：每条数据带 `source`（搜索来源/接口名/URL）
3. **失败隔离**：单行业/单指标失败不中断整体，打印 `[FAIL]` 并继续
4. **重试**：网络接口用 5 次退避重试
5. **批处理**：批量接口 BATCH=200，批间 sleep 0.6s，防限流
6. **诚实边界（FP2）**：无权威数据**显式标注 unavailable/null + confidence="E"**，
   **严禁编造数字**（尤其市占率/渗透率/目标价）
7. **验证**：每项完成跑对应验证脚本，通过才算完成
8. **报告**：每项写小结（产出文件/覆盖数/验证结果/问题），最终汇总成执行报告

---

## 九、执行环境准备

```bash
cd D:\2hao-analyst
# 若需要搜索 API
# Tavily key 在 .env 的 TAVILY_API_KEY
```

---

## 十、完成验收清单

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| P0-1 | global_industry_players.json | ≥8行业 × ≥5家玩家，含 country/role/confidence |
| P0-2 | regional_penetration.json | ≥6行业含中国/领先国渗透率（或标不可得） |
| P1-1 | global_leaders.json 更新 | ≥30家细化标签 + ≥20家中国龙头海外营收占比 |
| P1-2 | global_market_segments.json | ≥5行业 × 全球TAM + ≥3细分市场规模 |
| P2-1 | unlisted_players.json | ≥4行业 × 3家非上市玩家威胁度 |
| P2-2 | consensus_prices.json 更新 | ≥100只有目标价（或标不可得） |
| P3-1 | macro_highfreq/leading_indicators 补 | 能补的补 ≥30点，不可得保持标注 |

> 全部完成后，写执行报告到 `D:\Marvis\output\R55全球视野数据扩采执行报告.md`，
> 格式参照 `R53数据扩采执行报告.md`。报告里**明确标注**哪些数据是可得的、
> 哪些标注了 unavailable（诚实边界，2hao 侧会用这些标注决定是否降级）。
