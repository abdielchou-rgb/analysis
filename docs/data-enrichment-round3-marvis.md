# Marvis 数据底座补充需求 — Round 3

> 交接给 Marvis。Round 2 的 3 项修复已由主分析 agent 验收通过（数据质量达标）。
> 本轮目标：补齐 SAC 分析框架仍缺的数据维度。
> 生成日期：2026-08-01

---

## 背景

主分析 agent 已把 Round 2 的新数据源接入管线（`core/data_basement.py`）：
- ✅ `capital_flow.db` → 资金面（北向/两融/公募）
- ✅ `industry_baselines.json` → 行业基线（PE/PB/股息率）
- ✅ `company_events.db` → 公司事件（财报/分红/增减持）

这些已进入 data_dict，报告的资金面/行业对比/公司事件维度开始有真实数据支撑。

但对照 SAC 分析框架，仍有多处维度**没有数据源**（当前靠 LLM 估算或空）。以下是缺口清单。

---

## 缺口清单（按 SAC 维度）

### ① 资金面细化（listed/unlisted 都缺）

**现状**：capital_flow.db 有**市场级**北向/两融，但缺**个股级**资金面。
**SAC 要求**：`capital_flow` 维度要"北向资金/公募仓位/两融等至少 2 个维度"**针对标个股**。

| 数据 | akshare 接口 | 粒度 |
|---|---|---|
| 个股北向持仓 | `stock_hsgt_hold_stock_em(symbol="北向持股")` | 个股每日 |
| 个股两融余额 | `stock_margin_detail_sse` / `stock_margin_detail_szse` | 个股每日 |
| 个股资金流向 | `stock_individual_fund_flow(stock="600519")` | 个股每日 |
| 龙虎榜 | `stock_lhb_detail_em` | 个股事件 |

**存储**：扩充 `capital_flow.db` 加表 `stock_fund_flow(code, date, net_inflow, main_inflow, source)`。

### ② 一致预期 / 市场共识（industry 的 core_disagreement 缺）

**现状**：`consensus_prices.json` 仅 1KB，几乎空。
**SAC 要求**：`core_disagreement`（市场共识 vs 我们判断）、`capital_market`（一致预期差）。

| 数据 | akshare 接口 | 用途 |
|---|---|---|
| 一致预期 EPS/营收 | `stock_profit_forecast_em(symbol="600519")` | 未来3年预测 |
| 目标价 | `stock_analyst_rating_em` / `stock_analyst_em` | 分析师评级+目标价 |
| 一致评级分布 | 上述聚合 | 买入/增持/中性 分布 |

**存储**：新建 `data/consensus_estimates.db`，表 `consensus(code, as_of, eps_2026e, eps_2027e, target_price_avg, rating_buy, rating_hold, rating_sell, n_analysts, source)`。

### ③ 治理/ESG（listed 的 governance_esg 缺）

**SAC 要求**：`governance_esg` 要治理结构/ESG 评分。

| 数据 | akshare 接口 |
|---|---|
| 股东户数 | `stock_zh_a_gdhs_detail_em` |
| 高管变动 | `stock_manager_change` |
| ESG 评级 | `stock_esg_*`（华证/商道） |
| 股权质押 | `stock_pledge_ratio` |

**存储**：扩充 `company_events.db` 加表 `governance(code, date, metric, value, source)`。

### ④ 行业供需 / 产业链（industry 的 supply_demand / industry_chain 缺）

**现状**：industry_drivers.json 仅 8KB。
**SAC 要求**：`supply_demand`（供需/产能/平衡表）、`industry_chain`（上游-中游-下游）。

| 数据 | 来源 |
|---|---|
| 行业产量/销量 | 统计局/行业协会（需投喂研报提取） |
| 行业库存/开工率 | 同上 |
| 上下游价格 | 钢联/百川（需人工或研报） |
| 产业链传导 | 研报提取 |

**存储**：扩充 `data/industry_drivers.json`，按行业存供需指标。

### ⑤ 未上市/早期公司数据（unlisted 全维度缺）

**现状**：unlisted_company 的 21 个维度（funding_history / founder_team / product_tech / deal_win / runway 等）**没有结构化数据源**。
**SAC 要求**：这些维度要公司资料/融资/团队。

| 数据 | 来源 |
|---|---|
| 融资历程 | 天眼查/企查查（tyc-it MCP 可查） |
| 创始人背景 | 同上 |
| 产品/专利 | 专利库 / 官网 |
| 估值区间 | 一级市场交易 |

**做法**：这维建议用 tyc-it MCP 或人工尽调，不易 akshare 批量。**Marvis 可先不做**，由主 agent 用天眼查 MCP 按需补。

---

## 优先级建议

| 优先级 | 任务 | 理由 |
|---|---|---|
| P0 | ① 个股资金面 | listed/unlisted 硬需求，akshare 接口现成 |
| P0 | ② 一致预期 | industry core_disagreement 硬需求 |
| P1 | ③ 治理/ESG | listed governance_esg |
| P2 | ④ 行业供需 | 需研报投喂，成本高 |
| P3 | ⑤ 未上市数据 | 用 tyc-it，非批量 |

---

## 格式规范（延续前两轮）

- **source 标注**：每条数据 `akshare: <接口名>`，FP2 强制
- **幂等**：`INSERT OR REPLACE`，重复跑不产生重复
- **分批**：全量任务 BATCH=200，批间 sleep，异常隔离（同 sync_akshare_financials.py）
- **有效性校验**：关键字段空/数值全 0 → 跳过不写库（吸取 round2 教训）
- **完成检查**：每项跑读回验证（count + 抽样），更新下方状态表

---

## 完成状态表

| 任务 | 状态 | 执行日期 | 备注 |
|---|---|---|---|
| ① 个股资金面 | ✅ | 2026-08-01 | capital_flow.db 加 stock_fund_flow 表；北向 76402/49只、两融 5976/1993只、龙虎榜 392/258只；资金流向接口断连 |
| ② 一致预期 | ✅ | 2026-08-01 | 新建 consensus_estimates.db，51 条 |
| ③ 治理/ESG | ✅ | 2026-08-01 | company_events.db 加 governance 表；股东户数 6362/48只、ESG 5963/5963只、质押 2199/2199只 |
| ④ 行业供需 | ☐ | | 依赖研报投喂 |
| ⑤ 未上市数据 | ☐ | | 用 tyc-it，不批量 |

## 参考资料
- 接入层：`core/data_basement.py`（主 agent 已写，Marvis 新库建成后会自动读取）
- 范本：`scripts/sync_capital_flow.py` / `scripts/sync_company_events.py`
