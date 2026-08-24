# Marvis 数据补充指令 — R58 后续工作数据（2026-08-03）

> 执行环境：**用户本机**（需 akshare/baostock/网络；沙箱不可执行）
> 背景：2hao 已完成 R53-R57 系统性升级（SAC 26 维 + 7 深度知识库 + 30+ Gate 检查）。
> 本指令是 R58 后续工作的数据补充，聚焦**能力扩展所需的数据和报告**。
> 核心约束：**数据质量优先**——每条带 source、幂等、失败隔离、无数据不编造（FP2）。

---

## 零、任务总览

| 优先级 | 任务 | 目标 | 交付物 |
|---|---|---|---|
| **P0-1** | 行业并购案例库 | 为 consolidation 模块提供真实并购数据 | `m_and_a_cases.json` |
| **P0-2** | ESG 行业数据 | 为 esg_materiality 维度提供行业 ESG 风险数据 | `industry_esg.json` |
| **P1-1** | 四大审计报告原文 | 补充知识库"审计方法论"原文（当前为子代理调研合成） | 知识库新增板块 |
| **P1-2** | 预测验证样本 | 产生首批有效预测（方向+目标价）供 FP5 闭环 | 更新 `forward_picks.csv` |
| **P2-1** | 全球并购估值倍数 | 分行业 EV/EBITDA 真实并购倍数校准 | 更新 `consolidation.py` 基准 |
| **P2-2** | 投行研报方法论原文 | 补充国际投行报告结构原文吸收 | 知识库新增板块 |

**执行顺序**：P0-1 → P0-2 → P1-1 → P1-2 → P2-1 → P2-2。

---

## 一、P0-1：行业并购案例库（最高优先）

### 为什么需要
R57 建了 `core/compute/consolidation.py`（并购估值模块），但只有**静态行业倍数基准**
（`_INDUSTRY_EV_EBITDA` 字典）。没有真实并购案例，模块无法验证、无法给出"当前行业
并购估值处于历史什么分位"。

### 目标
新建 `data/m_and_a_cases.json`，为热门行业提供真实并购案例。

### Schema
```json
{
  "气体传感器": [
    {"acquirer": "霍尼韦尔", "target": "City Technology", "year": 2016,
     "ev_ebitda": 14.5, "ev_revenue": 3.2, "value_b": 5.8, "country": "US",
     "deal_type": "横向整合", "source": "公开披露"},
    {"acquirer": "汉威科技", "target": "炜盛电子", "year": 2023,
     "ev_ebitda": null, "ev_revenue": null, "value_b": 0.5, "country": "CN",
     "deal_type": "纵向整合", "source": "公告"}
  ]
}
```

### 操作步骤
1. 新建 `scripts/build_ma_cases.py`
2. **首批行业**（与 R55 对齐 8 个）：气体传感器/半导体/人形机器人/光伏/锂电/工控/医疗器械/消费电子
3. 每个行业用 WebSearch 找 **3-5 个代表性并购案例**（近 5 年），记录：收购方/标的/年份/EV-EBITDA（拿不到标 null）/交易金额/国家/交易类型
4. **EV/EBITDA 无权威来源就标 null**（FP2 诚实边界），不编造
5. 数据带 source

### 验证标准
**通过标准**：≥6 行业 × ≥3 案例，每案例含 acquirer/target/year/value（或显式 null）。

---

## 二、P0-2：ESG 行业数据

### 为什么需要
R57 加了 `esg_materiality` 维度（SASB/TCFD 行业实质议题），但**没有行业 ESG 数据底座**。
报告只能靠 LLM 常识写，无数据支撑。

### 目标
新建 `data/industry_esg.json`，为热门行业提供 ESG 风险矩阵。

### Schema
```json
{
  "气体传感器": {
    "material_topics": [
      {"topic": "碳排与能源强度", "materiality": "high", "metric": "Scope1+2 强度", "sasb_std": "RT-IG"},
      {"topic": "有害物质管理", "materiality": "medium", "metric": "危废合规", "sasb_std": "RT-IG"}
    ],
    "esg_risk_level": "medium",
    "esg_valuation_impact": "环境敏感行业，ESG 折价 5-15%",
    "china_policy": "双碳目标下高耗能环节受限",
    "source": "SASB/TCFD 行业地图 + WebSearch"
  }
}
```

### 操作步骤
1. 新建 `scripts/build_industry_esg.py`
2. 首批行业：气体传感器/半导体/光伏/锂电/医疗器械（能源/制造敏感行业优先）
3. 每个行业：找 SASB/TCFD 行业地图的实质议题 + 中国双碳政策影响 + ESG 估值影响
4. 数据不可得标 null/confidence="E"

### 验证标准
**通过标准**：≥5 行业，每行业 ≥2 个实质议题 + esg_risk_level。

---

## 三、P1-1：四大审计报告原文

### 为什么需要
知识库 02-行业与公司研究/03-估值与测算 已吸收投行/券商/估值方法，但**缺四大审计方法论原文**。
R57 的 `methodology_audit_deep.json` 是子代理调研合成的，需要**原文 PDF 提炼**增强可信度。

### 目标
把四大审计方法论原文（审计程序/收入确认/三表勾稽/财务造假案例）加入知识库。

### 操作步骤
1. 在 `data/知识库/08-四大审计方法论/` 新建板块
2. 收集原文（WebSearch 公开资料）：
   - 收入确认审计（IFRS15/ASC606）
   - 三表勾稽审计程序
   - 财务造假识别（M-Score/Fraud Triangle/证监会案例）
   - 审计意见类型与含义
3. 转成 MD 存入知识库板块
4. 完成后**在 2hao 侧重跑 `scripts/refresh_knowledge_base.py`**，触发深度吸收

### 验证标准
**通过标准**：≥4 篇原文 MD，含审计程序/造假识别/收入确认。

---

## 四、P1-2：预测验证样本（FP5 闭环）

### 为什么需要
FP5 智能演化的核心是预测验证闭环，但 `forward_picks.csv` 几乎空（268 字节）——
**系统没有产出过有效预测，无法验证自己是否变聪明**。

### 目标
产生首批有效预测（方向+目标价+时间窗），供 validate_predictions 到期验证。

### 操作步骤
1. 从 R55 全球视野数据里挑 10 家龙头（如宁德时代/比亚迪/迈瑞/隆基等）
2. 对每家给出：`direction`（看多/看空）+ `target_price`（具体数字）+ `horizon`（3/6/12月）+ `as_of`
3. 存 `data/forward_picks.csv`（追加到现有表，格式：asset, code, direction, target_price, horizon, as_of, conviction）
4. **只对你有把握的公司给预测**（FP2 诚实边界：无把握不预测），目标价基于现有数据测算

### 验证标准
**通过标准**：≥10 条有效预测（direction≠neutral + target_price>0 + conviction非空）。

---

## 五、P2-1：全球并购估值倍数校准

### 为什么需要
`consolidation.py` 的 `_INDUSTRY_EV_EBITDA` 是静态估算，需真实并购数据校准。

### 操作步骤
1. 用 P0-1 的并购案例库，统计各行业**中位 EV/EBITDA**
2. 更新 `core/compute/consolidation.py` 的 `_INDUSTRY_EV_EBITDA` 字典
3. 或输出建议值到 `data/m_and_a_ev_ebitda.json`（2hao 侧读）

### 验证标准
**通过标准**：输出每行业中位 EV/EBITDA + 案例数。

---

## 六、P2-2：国际投行研报方法论原文

### 为什么需要
知识库有中资券商（ifind研报/行业分析），但**缺国际投行（高盛/大摩/摩根大通）报告结构原文**。

### 操作步骤
1. 在 `data/知识库/09-国际投行方法论/` 新建板块
2. 收集公开的国际投行报告结构/方法论（如 Investment Primer 结构、sector deep dive 框架）
3. 转 MD 存入，2hao 侧重跑 refresh_knowledge_base 触发吸收

### 验证标准
**通过标准**：≥3 篇原文 MD（高盛/大摩/摩根大通结构方法论）。

---

## 七、通用规范（所有任务遵守）

1. **幂等**：脚本可重复运行，覆盖写入
2. **source 标注**：每条数据带 source（搜索来源/接口/URL）
3. **失败隔离**：单行业/单案例失败不中断整体
4. **诚实边界（FP2）**：EV/EBITDA/目标价/ESG 数据无权威来源标 null/confidence="E"，**严禁编造**
5. **验证**：每项完成跑对应验证，通过才算完成
6. **报告**：每项写小结，最终汇总成执行报告

---

## 八、完成验收清单

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| P0-1 | m_and_a_cases.json | ≥6行业 × ≥3案例 |
| P0-2 | industry_esg.json | ≥5行业 × ≥2实质议题 |
| P1-1 | 知识库 08-四大审计方法论 | ≥4篇原文 MD |
| P1-2 | forward_picks.csv 更新 | ≥10条有效预测 |
| P2-1 | 并购倍数校准 | 每行业中位 EV/EBITDA |
| P2-2 | 知识库 09-国际投行方法论 | ≥3篇原文 MD |

> 全部完成后，写执行报告到 `D:\Marvis\output\R58后续工作数据执行报告.md`，
> 格式参照 `R55全球视野数据扩采执行报告.md`。报告里**明确标注**可得/不可得项。
