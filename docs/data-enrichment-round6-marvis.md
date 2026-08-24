# 数据底座扩大 — Round 6（免费 token 深度覆盖版）

> 交接给 Marvis。**Marvis token 免费 → 本轮策略是"大规模、深度、冗余覆盖"**，不惜调用量。
> 已确认：数据底座已被管线消费（柯力 data_dict 吃到 24 个 basement key）。
> 目标：让**每个维度都有足够深、足够新、足够多的数据**，支撑任意标深度报告。
> 生成日期：2026-08-01

---

## 核心策略：免费 token = 可以"每行业深挖 + 每指标多源 + 全覆盖"

前几轮已建好骨架，本轮**把数据做厚**。重点扩短板 + 修 bug。

---

## 任务 A（P0）：产业链 → 补 50+ 行业结构化 + 修复空数组

**现状**：`industry_chain.json` 只有 10 行业，且 upstream/midstream/downstream 数组**全空**（只有 raw_points 文本）。
**目标**：50+ 行业，每个行业补全结构化数组。

**搜索词**：`<行业> 产业链 上游 中游 下游 成本结构`、`<行业> 上游原材料 中游制造 下游应用`

**输出**（每个行业）：
```json
{
  "industry": "半导体",
  "upstream": ["硅片", "光刻胶", "特种气体", "半导体设备"],
  "midstream": ["晶圆代工", "封装测试", "芯片设计"],
  "downstream": ["智能手机", "服务器", "汽车", "AI芯片"],
  "price_links": [{"from": "硅片价格", "to": "晶圆成本", "link": "占晶圆成本15-20%", "source": "URL"}],
  "margin_flow": "利润向具备车规工艺的IDM集中",
  "source": "URL"
}
```

**重点行业（必做 30 个）**：半导体、消费电子、汽车、新能源车、光伏、风电、锂电、储能、白酒、医药、医疗器械、创新药、军工、工程机械、家电、面板、钢铁、煤炭、化工、有色、银行、券商、保险、房地产、水泥、物流、零售、食品饮料、云计算、人工智能。

---

## 任务 B（P0）：渗透率 → 扩到 200+ 条（覆盖 80 行业细分）

**现状**：12 条。
**目标**：200+ 条，覆盖 80 行业主要细分。

**搜索词**：`<行业> <细分> 渗透率 2025 2026`、`<行业> 市场渗透率 增长`

**输出**：`{industry, segment, penetration_pct, as_of, life_cycle, growth_curve, source}`
- life_cycle：<5% 导入期 / 5-30% 成长早期 / 30-60% 成长期 / 60-85% 成熟期 / >85% 衰退期
- 每个细分必须带 source（URL）

---

## 任务 C（P0）：政策库 → 扩到 80 行业 × 10 条 + 修 title

**现状**：187 条/41 行业，但 **120 条 title 是长文本**（整段正文当标题）。
**目标**：80 行业 × 10 条 = 800 条，title 全部 ≤30 字简洁化。

**修 title**：对现有 120 条长 title，重写为简洁标题（≤30 字），保留 date/direction/source。

**输出**：`{industry, title(≤30字), date, level, direction, summary, source}`

---

## 任务 D（P1）：全球龙头 → 扩到 150 家（覆盖 40+ 行业）

**现状**：34 家/15 行业。
**目标**：150 家/40+ 行业。

**扩充**（每行业 3-5 家，含中国龙头）：
- TMT：腾讯、阿里、字节、美团、拼多多、中芯、海康、中兴、联想、小米
- 消费：农夫山泉、海天、伊利、蒙牛、青岛啤酒、贵州茅台、五粮液
- 医药：恒瑞、药明康德、迈瑞、百济神州、复星
- 制造：三一重工、宁德时代、比亚迪、隆基、通威
- 金融：工行、建行、招行、平安、中信证券
- 能源：中石油、中石化、神华、长江电力
- 全球：谷歌、苹果、微软、英伟达、特斯拉、丰田、大众、辉瑞、强生、摩根大通

**字段**：industry/company/ticker/revenue_ttm_m/net_income_ttm_m/eps_ttm/pe_ttm/market_cap_b/source

---

## 任务 E（P1）：美股 → 扩到 300 只（标普 500 前 300 + 中概）

**现状**：202 只。
**目标**：300 只。

**扩充池**：标普 500 剩余权重股 + 中概股（BABA/PDD/JD/EDU/TME/BILI/NIO/XPEV 等）

**⚠️ 列序纪律（吸取 Round4 教训）**：
- INSERT 列序必须和 DDL 完全一致：`ticker, as_of, revenue, net_profit, market_cap, pe_ttm, pb, source`
- 写后抽查：`SELECT ticker,revenue,net_profit,market_cap,pe_ttm FROM us_stocks WHERE ticker='AAPL'` → AAPL 营收≈466823 才对
- 亏损公司 pe_ttm 留 null

---

## 任务 F（P1）：akshare 财务补 MBRevenue/netProfit（关键，解锁个股预测）

**现状**：柯力 financials 的 profit 表只有 epsTTM/gpMargin/roeAvg，**缺 MBRevenue（营收）/netProfit（净利）**。导致个股盈利预测模型拿不到真实营收/净利。

**目标**：修复 sync 脚本字段映射，让 profit 表补齐 MBRevenue/netProfit。

**做法**：检查 `sync_akshare_financials.py` 的 PROFIT_MAP 字段映射，确认"营业总收入/净利润"列是否被正确映射到 MBRevenue/netProfit。若有映射但没写进库，排查是接口列名变化还是写入跳过。

**验证**：跑柯力 603662，确认 profit 表有 MBRevenue/netProfit 历史序列。

---

## 任务 G（P1）：宏观数据口径修复

**现状**：`macro_gdp_growth_q = 47831.7` 明显错误——47831 是 GDP 绝对值（亿元）被当成了增速。正确增速应 4-6%。

**根因**：`load_macro_latest` 取序列最后一条的 value，但 gdp_growth_q 序列可能存的是"季度 GDP 绝对值"而非"同比增速"。

**修法**：检查 macro_series.json 的 gdp_growth_q 数据，若是绝对值需换算成同比增速，或改取正确的增速字段。同时核查其他宏观序列（pmi/cpi/ppi/m2）口径是否一致。

---

## 通用规范（延续前几轮）

- **source 标注**：每条带 URL 或接口名，FP2 强制
- **幂等**：重跑合并去重
- **质量优先**：宁可少也要真实，禁止编造
- **验证**：每任务读回验证 + 更新状态表
- **SQLite 列序纪律**：写前对照 DDL，写后抽查

---

## 完成状态表

| 任务 | 现状 | 目标 | 状态 |
|---|---|---|---|
| A 产业链结构化 | 10 行业/空数组 | 50+ 行业/结构化 | ✅ 54 行业，source 已补 |
| B 渗透率 | 12 条 | 200+ 条 | ✅ 200 条/84 行业 |
| C 政策库 | 41 行业/187 条/长title | 80 行业/800 条/短title | ✅ 80 行业/800 条/0 长 title |
| D 全球龙头 | 34 家 | 150 家 | ✅ 150 家/49 行业 |
| E 美股 | 202 只 | 300 只 | ✅ 300 只（标普500前300权重+中概） |
| F akshare 补 MBRevenue | 缺失 | profit 表补齐 | ✅ 603662 有 MBRevenue/netProfit 序列 |
| G 宏观口径修复 | gdp 增速错误 | 口径正确 | ✅ gdp_growth_q 3.85~5.89，绝对值单列 |

## 参考资料
- 接入层：`core/data_basement.py`（已支持全部，扩量自动生效）
- 前几轮脚本：`scripts/round4_*.py` / `scripts/sync_*.py`
- 现有数据：`data/` 下各 json/db
