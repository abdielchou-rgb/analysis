# 2hao 估值体系第一性原理工程计划

> 基于 FP1-FP7 宪法 + 网上顶级打法（投行/券商/四大/咨询/学术）+ 2hao 当下真实约束
> 核心判断：2hao 不是"缺方法论"，是**缺自我检验**——FP5 智能演化从未真正运转（137 条预测 0 验证）

## 一、第一性原理推导

### FP5 智能演化 = 反馈闭环是系统核心
宪法要求"每次 Bold Call 必须被追踪 → 到期后与实际对比 → 准确率统计"。
**实测：137 条预测全 pending，0 条被验证。FP5 空转。**

### 第一性推导链
```
分析的本质 = 预测未来（目标价/增速/评级）
预测的价值 = 验证后才知道准不准（否则是自嗨）
验证的循环 = 记录 → 到期 → 对比 → 修正假设 → 下次更准
顶级分析师 = 被市场打了多年分，知道盲区
2hao 的差距 = 从来没被打过分
```

### 结论
2hao 缺的不是"造报告"的能力，是"验报告"的机制。
一切优化的地基 = **激活预测验证闭环**。这个信号一旦流动，FP5（演化）、FP7（反脆弱）、目标价追踪、预期差、校准全部开始迭代。

---

## 二、真实约束（工程计划的边界）

| 约束 | 现状 |
|---|---|
| LLM | 单 provider DeepSeek（.env 仅 DEEPSEEK_API_KEY）；本地 Ollama 可选 |
| 数据源 | 8 个 SQLite（financials/capital_flow/consensus/company_events 等）+ JSON（industry_chain/penetration/drivers/global_leaders） |
| 财务明细 | 沪深300+中证1000 全量明细扩展中（R27），柯力 balance 仅 6 字段 |
| 测试 | 21 个测试文件，59 项回归 |
| 运行环境 | VM Linux Python 3.10，bash 45s 上限，无 akshare（用户机有） |
| 上下文 | 曾 104 万 token 崩溃，需 checkpoint |
| 已有框架 | ForwardPicksDB/ScoreTracker/PredictionValidator/CognitiveBaseline 均存在但未打通 |

---

## 三、对标五大机构的模块化工程计划

### 模块 1【P0】预测回测闭环激活 —— 对标：投行目标价考核

**目标**：让 137 条 pending 预测开始被验证，FP5 从"空转"变"运转"。

| 步骤 | 具体动作 | 文件 |
|---|---|---|
| 1a | `PredictionValidator` 改为读 `forward_picks.csv` + `track_record.json` 合并去重 | `core/prediction_validator.py` |
| 1b | 过期判定：`created_at + 3个月` 或 `verified_at` 到期 → 拉实际价验证 | 同上 |
| 1c | 价格源：优先本地 `fig_qlib_price`（离线），降级 yfinance | `core/prediction_validator.py` `_get_price` |
| 1d | 验证后回流 `CognitiveBaseline`（校准下次判断） | `core/forward_picks.py` `_sync_to_baseline` |
| 1e | 预测质量门槛：target>0、direction≠neutral 才记录，垃圾不入库 | `core/forward_picks.py` `append` |
| 1f | 新增 `scripts/validate_predictions.py` CLI：手动触发全量验证 | 新增 |
| 1g | 新增测试：记录→过期→验证→评分全链路 | `tests/test_prediction_loop.py` |

**成功标准**：137 条中过期预测被标记 hit/miss；命中率/平均 alpha 可读。

### 模块 2【P0】目标价追踪台账 —— 对标：投行分析师考核

**目标**：每个目标价到期后自动对照实际价，记录误差，形成"分析师准确率档案"。

| 步骤 | 具体动作 | 文件 |
|---|---|---|
| 2a | `data/forward_picks/target_tracker.csv`：目标价/现价/到期价/误差% | `core/forward_picks.py` |
| 2b | 到期判定：报告日期 + 12 个月 → 拉实际价 → 误差 + 达成率 | `core/target_tracker.py`（新） |
| 2c | 达成率分级：误差<5%=命中 / <15%=接近 / >15%=miss | 同上 |
| 2d | 按标的/行业/报告类型聚合 → 分析师能力档案 | 同上 |
| 2e | 档案回流 prompt：写报告时"我过去对这类标的目标价命中率 X%" | `core/cognitive_baseline.py` |

**成功标准**：柯力传感目标价 48 元在到期后自动验证，误差可查。

### 模块 3【P1】三表勾稽验证 —— 对标：四大审计

**目标**：报表数字必须"勾稽平衡"，不只展示。

| 步骤 | 具体动作 | 文件 |
|---|---|---|
| 3a | 勾稽规则引擎：资产=负债+权益；营收-成本=毛利；现金流三活动=净变化 | `core/three_statement_audit.py`（新） |
| 3b | 从 financials.db 提取三表 → 跑勾稽 → 输出不平衡项 | 同上 |
| 3c | 数据缺口清单：缺应收/存货/商誉 → 走 enrich 或标缺口 | 接入 `data_enrichment.py` |
| 3d | Gate 新增 `_check_balance_sheet_audit`：三表不平衡 → 阻断 | `pipeline/iron_gate.py` |
| 3e | 注入 prompt：财务章节必须展示勾稽验证 | `pipeline/section_writer.py` |

**成功标准**：柯力传感三表勾稽通过或明确标出缺口；不平衡项被 Gate 拦截。

### 模块 4【P1】可比公司对标矩阵 —— 对标：麦肯锡/咨询

**目标**：每个标的与行业基准逐项对比，形成结构化对标表。

| 步骤 | 具体动作 | 文件 |
|---|---|---|
| 4a | `core/peer_matrix.py`（新）：标的 vs 同行业可比（估值/增速/ROE/毛利率） | 新增 |
| 4b | 行业映射：resolve_asset → 行业 → global_leaders/peers 匹配 | `core/asset_resolver.py` |
| 4c | 对标矩阵输出：多行多列表（指标 × 公司），含偏离度 | 同上 |
| 4d | 注入 prompt：竞争章节必须引用对标矩阵 | `pipeline/section_writer.py` |
| 4e | 补 global_leaders 行业覆盖（传感器/仪器仪表/工控） | Marvis 命令 |

**成功标准**：柯力传感对标矩阵（vs 泰科/霍尼韦尔/华工/歌尔）可生成。

### 模块 5【P1】预期差引擎 —— 对标：券商研究所

**目标**：一致预期 vs 实际/预测 → 超预期信号。

| 步骤 | 具体动作 | 文件 |
|---|---|---|
| 5a | consensus 扩充到 300 只（沪深300） | `scripts/sync_consensus_estimates.py` |
| 5b | 新增业绩预告/快报同步（akshare stock_yjyg_em/yjkb_em） | `scripts/sync_earnings_forecast.py`（新） |
| 5c | `core/earnings_surprise.py`（新）：预告 vs 一致预期 → 超/低于预期 | 新增 |
| 5d | 注入 prompt：核心判断章节引用预期差信号 | `pipeline/section_writer.py` |

**成功标准**：柯力传感业绩预告 vs 一致预期的超预期信号可读。

### 模块 6【P1】估值锚统一 —— 对标：投行三表→估值

**目标**：DCF/可比/SOTP 交叉验证，单一结论，不并列矛盾。

| 步骤 | 具体动作 | 文件 |
|---|---|---|
| 6a | 估值交叉验证器：多方法结果 → 差异>20% 时强制声明取值逻辑 | `core/valuation_crosscheck.py`（新） |
| 6b | 接入 R28 的 `_check_rating_target_consistency`（已有） | `pipeline/iron_gate.py` |
| 6c | 反向 DCF 深化：隐含 FCF margin 反推（对标 New Constructs） | `core/data_caliber.py` |

**成功标准**：柯力报告不再出现"PE 65x vs 79.79x"矛盾。

### 模块 7【P2】预测 vs 基准检验 —— 对标：学术研究

**目标**：2hao 的预测跑赢"均值回归"基准吗？

| 步骤 | 具体动作 | 文件 |
|---|---|---|
| 7a | 基准 = 行业平均增速延续 / 均值回归 | `core/prediction_validator.py` |
| 7b | 2hao 预测误差 vs 基准误差 → 超额准确率 | 同上 |
| 7c | 不足时触发校准：调整悲观/乐观倾向 | `core/cognitive_baseline.py` |

**成功标准**：报告准确率 vs 基准的超额可量化。

---

## 四、依赖关系与执行顺序

```
模块1（预测闭环）─┬→ 模块2（目标价追踪）──┐
                  ├→ 模块7（基准检验）────┤
                  └→ 模块5c（预期差）────┐
模块3（勾稽）  ──────────────────────────┤
模块4（对标矩阵）────────────────────────┴→ 报告质量提升
模块6（估值锚统一）← 依赖 R28 已有检查
```

**执行顺序**：
1. **模块 1**（P0，预测闭环）—— 地基，先打通
2. **模块 2**（P0，目标价追踪）—— 依赖模块1
3. **模块 3**（P1，勾稽）—— 独立
4. **模块 5**（P1，预期差）—— 独立，数据补强
5. **模块 6**（P1，估值锚）—— 依赖 R28
6. **模块 4**（P1，对标矩阵）—— 依赖 global_leaders
7. **模块 7**（P2，基准检验）—— 依赖模块1

## 五、FP 宪法对齐

| 模块 | 兑现的 FP |
|---|---|
| 模块1 | FP5（智能演化：预测追踪）+ FP7a（失败学习） |
| 模块2 | FP5（准确率统计） |
| 模块3 | FP2a（数据履约：勾稽验证） |
| 模块4 | FP3（超人类维度：系统性对标） |
| 模块5 | FP2b（分析履约：预期差） |
| 模块6 | FP2a + FP6（推理透明） |
| 模块7 | FP5（收敛指标：超额准确率） |

## 六、验证策略

每个模块带独立测试 + 全量回归：
- 模块1/2：`tests/test_prediction_loop.py`、`tests/test_target_tracker.py`
- 模块3：`tests/test_three_statement_audit.py`
- 模块4：`tests/test_peer_matrix.py`
- 模块5：`tests/test_earnings_surprise.py`
- 模块6：复用 `tests/test_fact_quality.py`
- 模块7：`tests/test_benchmark_compare.py`

最终验收：柯力传感完整报告 → 预测被记录 → 到期被验证 → 目标价误差可查 → 三表勾稽通过 → 对标矩阵完整 → 预期差信号明确。

## 七、约束适配说明

- **VM 无 akshare**：数据同步（模块5）由 Marvis 用户机执行；模块1-4 逻辑验证用 VM 现有数据
- **单 provider DeepSeek**：校准依赖 LLM 的模块用确定性规则优先（验证/评分不依赖 LLM）
- **bash 45s 上限**：长验证拆小步；预测验证 CLI 分批跑
- **上下文约束**：长任务用 checkpoint（已有 2hao-context-guard skill）

---

**一句话总结**：2hao 的估值模块不缺方法论，缺的是**"被打分"的机制**。模块1+2 把预测验证闭环激活，是让系统真正开始"从错误中学习"（FP5）的第一步——其他所有模块都是在这个反馈信号之上长出来的。
