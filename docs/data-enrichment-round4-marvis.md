# 离线数据补充需求 — Round 4（信息全覆盖版）

> 交接给 Marvis。前 3 轮（财务/资金面/一致预期/治理/行业估值）已验收通过。
> 本轮目标：补齐 SAC 框架仍缺的 5 类离线数据，全部落地为本地文件，带 source 可追溯。
> 生成日期：2026-08-01

---

## 背景：为什么需要这些数据

对照 SAC 分析框架，现有数据已覆盖：财务、个股资金面、一致预期、治理ESG、行业估值、公司事件。
但以下维度**完全没有离线数据**（现靠 WebSearch 临时搜或 LLM 估算），是行业/公司报告深度不足的根因：

| SAC 维度 | 缺口 | 报告影响 |
|---|---|---|
| supply_demand | 行业供需/产能/库存/价格 | "稀缺层/供需分析"章节无数据 |
| policy | 政策库 | "政策传导链+力度评分"靠现场搜 |
| industry_chain | 产业链上下游传导 | "利润池/产业链"分析无价格联动 |
| life_cycle | 行业渗透率 | "生命周期判断"靠 LLM 拍脑袋 |
| elasticity_analysis | 宏观弹性序列 | "需求收入弹性"无宏观数据 |

**执行原则（FP2）**：所有数据必须来自真实来源（Tavily 网页 / akshare 接口 / 统计局），每条带 source（URL 或接口名）。禁止编造。

---

## 数据源就绪情况

- `TAVILY_API_KEY` 已在 `.env`（tvly-dev-2uvo9o...），Tavily 网页搜索可用
- akshare 在本机已装（前几轮验证过）
- 需安装：`pip install tavily-python`（若未装）

---

## 任务 A（P0）：行业供需/产能/库存数据 → `data/industry_drivers.json`

### 目标
用 Tavily 为**30 个重点行业**各搜一次供需/产能/库存/价格，提取数据点，写入 `industry_drivers.json`（扩展现有格式）。

### 行业清单（30 个）
半导体、消费电子、汽车、新能源汽车、光伏、风电、锂电、储能、白酒、乳制品、医药、医疗器械、CXO、创新药、军工、工程机械、重卡、家电、白电、面板、LED、PCB、消费电子、钢铁、煤炭、化工、有色、黄金、银行、保险、券商、房地产、水泥、建筑、物流、零售。

### 搜索词模板（每行业 4 条）
```
<行业> 2026 产量 产能 供给
<行业> 2026 库存 需求 消费量
<行业> 2026 价格 景气 开工率
<行业> 2026 供需 缺口 平衡
```

### 输出格式（追加到现有 industry_drivers.json）
```json
{
  "半导体": [
    "• 2026年全球晶圆产能预计增长7%，先进工艺节点增速更快 (来源: https://... Tavily: 2026 半导体 产能)",
    "• 存储器市场2026年增长20.5%，达1963亿美元 (来源: https://...)"
  ],
  "汽车": [...]
}
```

### 规范
- 每条一个 `• ` 前缀 + 数据点 + `(来源: URL)`
- 保留现有 6 个行业已有内容，追加新行业，不覆盖
- 幂等：重跑去重（同 URL+同句首不重复）

---

## 任务 B（P0）：政策库 → 新建 `data/policy_db.json`

### 目标
建一个**政策事件库**，覆盖 30 个行业 2020-2026 年的重要政策，供政策传导分析。

### 搜索词模板（每行业 2-3 条）
```
<行业> 政策 2025 2026 支持 规划 补贴
<行业> 十五五 <行业> 政策 方向
<行业> 监管 法规 2026 限制
```

### 输出格式
```json
{
  "policies": [
    {
      "industry": "半导体",
      "title": "国家集成电路产业投资基金三期成立",
      "date": "2024-05-24",
      "level": "国家级",
      "direction": 1,           // 1=鼓励, 0=中性, -1=限制
      "summary": "注册资本3440亿元，重点投向设备材料领域",
      "related_sectors": ["设备", "材料"],
      "source": "https://..."
    }
  ]
}
```

### 规范
- `direction` 评分：鼓励=1，中性=0，限制=-1
- 每行业至少 3 条政策（2020-2026 覆盖）
- 30 行业 × 3 条 = 90 条起

---

## 任务 C（P1）：产业链传导数据 → 新建 `data/industry_chain.json`

### 目标
建**产业链上下游价格/毛利传导**数据，供利润池分析。

### 结构
```json
{
  "chains": [
    {
      "industry": "半导体",
      "upstream": ["硅片", "光刻胶", "气体"],
      "midstream": ["晶圆代工", "封测"],
      "downstream": ["手机", "服务器", "汽车"],
      "price_links": [
        {"from": "硅片价格", "to": "晶圆成本", "link": "硅片占晶圆成本15-20%", "source": "..."}
      ],
      "margin_flow": "利润向具备车规工艺的IDM集中",
      "source": "..."
    }
  ]
}
```

### 数据来源
- Tavily 搜 "<行业> 产业链 上游 中游 下游 成本结构"
- 或从已投喂研报（baseline_findings）提取
- 每行业至少 1 条，重点行业（半导体/新能源/医药）3-5 条

---

## 任务 D（P1）：行业渗透率数据 → 新建 `data/industry_penetration.json`

### 目标
建**各行业渗透率基准**，供生命周期判断（导入期/成长期/成熟期）。

### 输出格式
```json
{
  "penetration": [
    {
      "industry": "新能源车",
      "segment": "电动乘用车",
      "penetration_pct": 45,
      "as_of": "2025",
      "life_cycle": "成长期",
      "growth_curve": "S曲线加速段",
      "source": "https://..."
    }
  ]
}
```

### 规范
- `life_cycle` 判定：<5% 导入期，5-30% 成长期早期，30-60% 成长期，60-85% 成熟期，>85% 衰退期
- 覆盖 30 行业的主要细分赛道，每行业 1-3 条
- 渗透率必须有来源（Tavily 或统计局），禁止拍脑袋

---

## 任务 E（P2）：宏观弹性序列 → 新建 `data/macro_series.json`

### 目标
建**宏观历史序列**（GDP/PMI/社融/CPI/PPI），供需求收入弹性分析。

### 数据来源（akshare 接口，一次性拉全历史）
| 指标 | akshare 接口 |
|---|---|
| GDP 季度 | `macro_china_gdp` |
| PMI 月度 | `macro_china_pmi_yearly` / `macro_china_pmi` |
| 社融 | `macro_china_shrzgm` |
| CPI/PPI | `macro_china_cpi_yearly` / `macro_china_ppi_yearly` |
| 货币供应 M2 | `macro_china_m2_yearly` |

### 输出格式
```json
{
  "series": {
    "gdp_growth_q": [{"date": "2024Q1", "value": 5.3}, ...],
    "pmi": [{"date": "2025-01", "value": 49.8}, ...],
    "cpi_yoy": [...],
    "ppi_yoy": [...],
    "m2_yoy": [...],
    "social_financing": [...]
  },
  "source": "akshare"
}
```

---

## 任务 F（P0）：全球宏观数据 → 新建 `data/global_macro.json`

### 背景
当前数据底座是纯 A 股/中国视角。行业深度报告需要全球宏观起点（美联储利率/美元指数/美债/全球PMI）来分析风险偏好与跨市场传导。此任务补全球宏观层。

### 数据来源（akshare 接口，一次性拉全历史）
| 指标 | akshare 接口 |
|---|---|
| 美联储联邦基金利率 | `macro_fed_interest_rate` |
| 美国非农就业 | `macro_usa_non_farm` |
| 美国 CPI | `macro_usa_cpi` |
| 美国核心 CPI | `macro_usa_core_cpi` |
| 美国 GDP | `macro_usa_gdp` |
| 美元指数 | `macro_usa_...`（若不可用用 Tavily 补充） |
| 美国 10Y 国债收益率 | `macro_usa_...`（若不可用用 Tavily 补充） |
| 全球/美国 PMI | `macro_usa_...` 或 Tavily |

**接口不确定时**：先 `help(ak)` 搜 `macro` 相关接口确认真实名称，再用。接口不可用的指标用 Tavily 补（带 URL）。

### 输出格式
```json
{
  "series": {
    "fed_rate": [{"date": "2024-01", "value": 5.5}, ...],
    "us_nonfarm": [{"date": "2025-01", "value": 142000}, ...],
    "us_cpi_yoy": [...],
    "us_gdp_growth": [...],
    "us10y_yield": [...],
    "dollar_index": [...]
  },
  "source": "akshare + tavily"
}
```

### 规范
- 覆盖 2015-2026 历史
- 每个序列带 source（akshare 接口名 或 Tavily URL）

---

## 任务 G（P1）：全球行业龙头对标 → 新建 `data/global_leaders.json`

### 背景
行业报告"全球对标"章节需要全球龙头数据（市场地位/营收/市值），当前无离线数据，靠 WebSearch 现搜。

### 目标
为 15 个重点行业的全球龙头建对标库。

### 行业与龙头清单（15 行业 × 1-3 龙头）
| 行业 | 全球龙头 |
|---|---|
| 半导体设备 | 阿斯麦 ASML、应用材料 AMAT、泛林 LRCX |
| 半导体设计 | 英伟达 NVDA、高通 QCOM、博通 AVGO |
| 消费电子 | 苹果 AAPL、三星 |
| 汽车 | 特斯拉 TSLA、丰田 |
| 新能源 | 宁德时代（全球龙头） |
| 云计算/软件 | 微软 MSFT、甲骨文 ORCL |
| 互联网 | 谷歌 GOOGL、亚马逊 AMZN、Meta |
| 医药 | 辉瑞、礼来 LLY、强生 JNJ |
| 医疗器械 | 美敦力、雅培 |
| 化工 | 巴斯夫、陶氏 |
| 工业 | 西门子、ABB、卡特彼勒 |
| 油气 | 埃克森美孚、雪佛龙 |
| 银行 | 摩根大通 JPM、花旗 |
| 零售 | 沃尔玛、家乐福 |
| 食品饮料 | 可口可乐、百事 |

### 数据来源
- **财务/市值**：yfinance（需 `pip install yfinance`），拉营收/净利/市值/PE
- **市场地位**：Tavily 搜 "<龙头> global market share <行业> 2025"

### 输出格式
```json
{
  "leaders": [
    {
      "industry": "半导体设备",
      "company": "ASML",
      "ticker": "ASML",
      "revenue_2025": 320.0,
      "net_profit_2025": 78.0,
      "market_cap": 2800.0,
      "pe_ttm": 35.0,
      "global_market_share": "EUV光刻机市占率约90%",
      "source": "yfinance + tavily URL"
    }
  ]
}
```

### 规范
- 金额单位：营收/净利/市值用**亿美元**
- 全球龙头按行业覆盖，至少 25 家
- yfinance 拉不到的用 Tavily 补（带 URL）
- **注意**：yfinance 在沙箱/受限网络可能被墙，若拉不到全部用 Tavily 搜财报数字（带来源）

---

## 任务 H（P1）：美股主要公司财务（可选延伸）→ 新建 `data/us_stocks.db`

### 背景
任务 G 是"全球龙头对标"（每行业几家），本任务是"美股主要公司批量财务"，供跨境/美股分析用。

### 目标
拉 **30 家核心美股**的财务（营收/净利/市值/PE/PB），存 SQLite。

### 股票池（30 家）
AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, ORCL, AMD, INTC, QCOM, ASML, AMAT, LRCX, JPM, BAC, WMT, KO, PEP, JNJ, PFE, LLY, MRK, XOM, CVX, CAT, BA, DIS, NFLX

### 数据来源
- yfinance：`yf.Ticker(t).info` 拉营收/净利/市值/PE
- 失败时 Tavily 搜 `"<ticker> 2025 revenue net income market cap"`

### 存储
```sql
CREATE TABLE us_stocks (
  ticker TEXT, as_of TEXT, revenue REAL, net_profit REAL,
  market_cap REAL, pe_ttm REAL, pb REAL, source TEXT,
  PRIMARY KEY (ticker, as_of)
);
```
`data/us_stocks.db`

### 规范
- 金额单位：亿美元
- yfinance 被墙时全走 Tavily（带 URL）
- 失败隔离：单只失败跳过，不中断

---

## 通用规范（延续前 3 轮）

- **source 标注**：Tavily 数据带 URL；akshare/yfinance 带 `akshare/yfinance: <接口名>`
- **幂等**：JSON 重跑合并去重，不产生重复条目
- **有效性**：空值/无来源条目不写入
- **完成检查**：每任务写读回验证（count + 抽样），更新下方状态表
- **时间**：任务 A/B/F 是 P0 优先，C/D/G/H 次之，E 最后
- **全球数据纪律（FP2）**：全球龙头/美股的营收/市值/市占率必须有来源，禁止凭印象编数字；yfinance 拉不到就 Tavily 搜真实来源

---

## 完成状态表

| 任务 | 产出 | 状态 | 执行日期 |
|---|---|---|---|
| A 行业供需 | data/industry_drivers.json | ✅ | 2026-08-01 |
| B 政策库 | data/policy_db.json | ✅ | 2026-08-01 |
| C 产业链 | data/industry_chain.json | ✅ | 2026-08-01 |
| D 渗透率 | data/industry_penetration.json | ✅ | 2026-08-01 |
| E 宏观序列 | data/macro_series.json | ✅ | 2026-08-01 |
| F 全球宏观 | data/global_macro.json | ✅ | 2026-08-01 |
| G 全球龙头对标 | data/global_leaders.json | ✅ | 2026-08-01 |
| H 美股主要公司 | data/us_stocks.db | ✅ | 2026-08-01 |

## 参考资料
- 接入层：`core/data_basement.py`（Marvis 建好后，主 agent 加 reader 即可接入 data_dict）
- 现有格式范本：`data/industry_drivers.json`（{行业: [文本条目]}）
- Tavily 文档：需 `pip install tavily-python`，用 `tavily.TavilyClient(api_key=...)` 搜
- 海外数据需装：`pip install yfinance`（美股财务）
