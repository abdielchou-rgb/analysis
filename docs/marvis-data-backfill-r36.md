# Marvis 数据补强任务清单 — R36（2026-08-02）

> 背景：Marvis 有两个空闲会话（token 免费），用户希望提升 2hao 分析师能力。
> 依据：对系统数据地图的实测——`industry_chain.json` 覆盖 57 行业，但**热门新兴赛道产业链整体缺失**（人形机器人/固态电池/AI算力/自动驾驶等 20 个赛道，其中部分政策数据已有但产业链无）。

---

## 任务 A：产业链结构补全（最高价值，预计 1 会话）

**目标**：为 `data/industry_chain.json` 补充 12 个高价值新兴赛道的产业链结构，对齐现有 schema。

**为什么重要**：`core/bottleneck_engine.py`（供应链卡点分析）、`core/catalyst_timeline.py`（催化剂日历）、`core/data_basement.py` 都消费 `industry_chain.json`。柯力案例已证明：有产业链 vs 无产业链，卡点评分从 4/20 → 10/20，分析质量翻倍。但目前人形机器人/固态电池这类最热的赛道反而没有产业链，分析这些标的时瓶颈引擎读不到。

**需补的 12 个赛道**（按投资热度排序）：

| # | 赛道 | 说明 |
|---|------|------|
| 1 | 人形机器人 | 上游减速器/伺服电机/灵巧手/传感器，中游本体制造，下游工业/家庭场景 |
| 2 | 固态电池 | 上游硫化物电解质/锂金属负极，中游电芯，下游 EV/储能 |
| 3 | AI算力/智算中心 | 上游 GPU/光模块/液冷，中游服务器/IDC，下游大模型训练 |
| 4 | 自动驾驶 | 上游激光雷达/摄像头/芯片，中游方案商，下游整车/出行 |
| 5 | 低空经济 | 上游 eVTOL 电机/飞控，中游整机，下游物流/载人/巡检 |
| 6 | 商业航天 | 上游火箭发动机/卫星平台，中游发射/星座运营，下游通信/遥感 |
| 7 | 光模块 | 上游光芯片/激光器，中游模块封装，下游数据中心/电信 |
| 8 | 半导体设备 | 上游零部件/材料，中游刻蚀/薄膜/光刻设备，下游晶圆厂 |
| 9 | 存储 | 上游存储晶圆/接口芯片，中游模组，下游服务器/消费电子 |
| 10 | 工业母机 | 上游数控系统/丝杠/主轴，中游机床，下游汽车/军工/3C |
| 11 | 氢能 | 上游制氢/储氢，中游燃料电池/电解槽，下游交通/工业/发电 |
| 12 | 卫星互联网 | 上游相控阵/星载计算，中游卫星制造/发射，下游通信/导航 |

**Schema**（对齐现有）：
```json
{"name": "人形机器人", "upstream": [...], "midstream": [...], "downstream": [...],
 "key_players": [...], "source": "R36 ai_search: ..."}
```
要求：每个环节 3-6 个要素，key_players 含 A 股上市公司（便于 `load_industry_chain('公司名')` 命中），每条带 `source`。

**验证**：
```bash
python -c "import json; d=json.load(open('data/industry_chain.json',encoding='utf-8')); print([x['name'] for x in d['industries'] if x['name'] in ('人形机器人','固态电池','AI算力')])"
```

---

## 任务 B：一致预期目标价补全 + 财务字段缺口（第 2 会话）

### B-1：consensus target_price 补全（P1-1 遗留）

**背景**：R33 已同步 EPS/评级/分析师数（1264 只），但 `target_price_avg` 全为 None——东财/同花顺免费接口无目标价字段。

**建议**：尝试以下来源（任一路径成功即可）：
1. `ak.stock_profit_forecast_em`（东财盈利预测，可能有目标价）
2. `ak.stock_research_report_em` 重新解析（检查是否有"目标价"列，之前 Marvis 说无，可再看原始列名）
3. 新浪财经/腾讯行情接口的目标价字段
4. 若都不可用，**记录为明确的技术限制**（在文档标注"目标价免费源不可得，建议付费源"），不要硬编造

**价值**：`core/earnings_surprise.py` 的 `compute_surprise` 的 `consensus_target` 目前是 None，预期差信号少了一半。

### B-2：financials.db 字段覆盖率检查（数据质量审计）

**背景**：financials.db 有 43 个字段，但部分字段覆盖率低（如 `liqaShare` 仅 7 个季度、`longLoan` 8 个）。

**建议**：写一个覆盖率扫描脚本，输出每只股票/每个字段的覆盖率，找出"财务数据存在但关键字段缺失"的标的（尤其沪深300 成分股），供后续 enrich 或补采。

**价值**：三表勾稽审计（`three_statement_audit.py`）依赖 balance/profit/cashflow 字段齐全，覆盖率低的标的勾稽结果会打折扣。

---

## 任务 C（可选，若时间富余）：港股 Layer1 财务明细

交接文档遗留的"港股 Layer1（25只）"未同步。若 Marvis 有富余算力：
```bash
python scripts/sync_akshare_financials.py --market HK --index-layer1
```
需先确认 `sync_akshare_financials.py` 是否支持港股参数，不支持则跳过（不硬来）。

---

## 优先级与安排建议

| 任务 | 价值 | 工作量 | 安排 |
|------|------|--------|------|
| A. 产业链补全（12赛道） | 高（瓶颈引擎/催化剂直接受益） | 中（AI 搜索+结构化） | 会话 1 |
| B-1. 目标价补全 | 中（预期差信号激活） | 中（接口试错） | 会话 2 |
| B-2. 字段覆盖率审计 | 中（数据质量基线） | 小（写脚本扫描） | 会话 2 后半 |
| C. 港股 Layer1 | 低（非重点） | 中 | 可选 |

**核心原则**：所有补充数据必须带 `source` 标注（FP2 数据零编造），验证命令必须跑通再交付。

---

## 执行结果（2026-08-02 全量执行完毕）

### 任务 A：产业链补全 ✅ 完成
- 12 个新兴赛道全部加入 `data/industry_chain.json`，行业数 57 → **69**，每条含 upstream/midstream/downstream/key_players/source
- 验证通过：`['人形机器人','固态电池','AI算力']` 均在列
- 新增赛道：人形机器人/固态电池/AI算力/自动驾驶/低空经济/商业航天/光模块/半导体设备/存储/工业母机/氢能/卫星互联网

### 任务 B-1：目标价补全 ⚠️ 记录为技术限制（免费源不可得）
探测路径全部失败，明确记为技术限制，未编造数据：
1. `ak.stock_research_report_em`（东财研报）：**无目标价列**（只有评级/标题/摘要）
2. `ak.stock_profit_forecast_ths`（同花顺盈利预测）：**无目标价**
3. `ak.stock_rank_forecast_cninfo`（巨潮）：有目标价列但为 **2023-08-17 单日快照**（121/391 有值），已过时不可用
4. 新浪/腾讯行情接口：无目标价字段
- **结论**：consensus_estimates.db 现有 1315 条（R33 同步），`target_price_avg` 全为 NULL；建议付费源（Wind/Choice/iFind）或人工维护
- 影响：`core/earnings_surprise.py` 的 `consensus_target` 保持 None，预期差信号仍缺一半

### 任务 B-2：字段覆盖率审计 ✅ 完成（新增扫描脚本 + 报告）
新增脚本 `scripts/scan_financials_coverage.py`，输出 `data/financials_coverage_report.json`。

**全库字段覆盖率**（5259 只）：
| 层级 | 字段 | 覆盖率 |
|------|------|--------|
| 高 | epsTTM | 100% |
| 高 | cashAssets/totalEquity/totalLiab | 99.5% |
| 高 | totalAssets | 98.1% |
| 高 | OCF/ICF/FCF | 98.0% |
| 中 | roeAvg | 90.1% |
| 中 | gpMargin | 53.0% |
| 低 | netProfit | 32.6% |
| 低 | MBRevenue | 30.0% |
| 低 | operateProfit/operatingCost/manageExpense 等明细 | 24.7% |
| 低 | longLoan | 20.5% |
| 极低 | goodwill/npMargin/advanceReceived 等 | <17% |

**沪深300 成分（300 只）**：
- 金融股（48 只，行业不适用）：银行/券商/保险天然无 inventory/sellExpense/OCF 等科目，缺字段属报表结构差异，**非数据缺口**
- 非金融股真实缺口：59 只，其中多数仅缺 shortLoan/longLoan/goodwill 等非核心字段；核心字段（totalAssets/netProfit/MBRevenue/OCF）齐全
- 核心结论：**沪深300 三表勾稽审计可正常执行**，无关键字段缺失

**全库真实缺口（4031 只非金融股）**：以 001/002/300 开头的中小市值标的为主，缺 profit 表明细（netProfit/MBRevenue/operateProfit 等 19 字段），但 balance/cashflow 核心字段齐全。根因：R24 增量同步只覆盖沪深300/中证1000 的 profit 明细，全库未做 profit 明细全量补采。

**建议**：对 4031 只缺口标的跑 `python scripts/sync_akshare_financials.py --all` 补 profit 明细（预计 +50 万条量级，需 2-worker 防 SQLite 写锁），可作为 R37 任务。

### 任务 C：港股 Layer1 ⏭️ 跳过
`sync_akshare_financials.py --market` 仅支持 sh/sz/all，**不支持 HK 参数**。按文档规则"不支持则跳过，不硬来"。

### 回归验证
- 核心单元测试（schema/enforcer/sac_gate/quality_scorer 等 28 项）**全部通过**
- e2e 自定义脚本 16 passed / 3 failed（NO AI/Bear Case/pending 规则缺失）——为 SAC agent brief 既有基线问题，与本次数据补强改动无关

