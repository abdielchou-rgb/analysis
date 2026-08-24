# 行业参数搜集 — Round 7（喂给方法论规则库）

> 交接给 Marvis。**Marvis token 免费 → 大规模搜集各行业参数**。
> 主分析 agent 已把投行方法论固化为可执行规则（`core/methodology_rules.py`），
> 但规则需要**行业具体参数**才能落地（如"半导体 WACC 用 10%、生命周期=成长期"）。
> 本轮：Marvis 搜集各行业参数，写回 `data/methodology_rules.json`，自动合并生效。
> 生成日期：2026-08-01

---

## 核心逻辑

方法论规则库已有判断逻辑（condition → signal），但缺行业参数填进去：
- "动态PE < 静态PE → 估值拐点" 需要知道**该行业的历史 PE 分位**
- "营收增速>20% + 资本开支高 → 成长赛道期" 需要知道**该行业的实际增速/资本开支**
- "消费品看利润率" 需要知道**该行业平均毛利率/费用率**

**产出**：`data/methodology_rules.json`（追加 `industry_params` 段，自动合并）

---

## 任务 A（P0）：行业估值参数 → 每个行业 WACC/折现率/估值倍数

为 **30 个重点行业**搜集估值参数。

| 行业 | 需搜集 |
|---|---|
| 半导体、消费电子、汽车、新能源车、光伏、风电、锂电、储能、白酒、医药、医疗器械、创新药、军工、工程机械、家电、面板、钢铁、煤炭、化工、有色、银行、保险、券商、房地产、水泥、物流、零售、食品饮料、云计算、人工智能 | WACC/折现率、PE区间、PB区间、PS区间、股息率、行业特性(周期/成长/防御) |

**输出**（写入 methodology_rules.json 的 `industry_params`）：
```json
{
  "topic": "industry_params",
  "items": [
    {
      "industry": "半导体",
      "wacc": 10.0,
      "pe_range": [25, 60],
      "pb_range": [3, 8],
      "ps_range": [3, 10],
      "dividend_yield": 0.5,
      "nature": "成长",
      "notes": "先进制程/设备高估值，成熟制程低",
      "source": "URL"
    }
  ]
}
```

**数据来源**：Tavily 搜 "<行业> WACC 折现率 估值" / "<行业> PE 区间 估值 2026"；或从投喂研报提取。

---

## 任务 B（P0）：行业生命周期判定 → 每个行业处于哪个阶段

为 **30 个重点行业**判定生命周期阶段。

| 输入 | 需搜集 |
|---|---|
| 营收增速、资本开支、渗透率、竞争格局(CR5)、产能 | 行业所处阶段(导入/成长/成熟/衰退) |

**输出**（写入 `industry_params`）：
```json
{
  "industry": "储能",
  "lifecycle_stage": "成长期",
  "revenue_growth_pct": 25,
  "capex_growth_pct": 30,
  "penetration_pct": 30,
  "cr5_pct": 40,
  "evidence": "渗透率30%处于加速期，资本开支高扩产",
  "source": "URL"
}
```

**判断依据**（用主 agent 的方法论规则）：
- 营收增速>20% + 资本开支高 → 成长赛道期
- 营收低增长 + 洗牌 → 洗牌期/出清末期
- 营收企稳 + 集中度提升 → 龙头进阶期

---

## 任务 C（P1）：行业盈利参数 → 毛利率/净利率/ROE 基线

为 **30 个重点行业**搜集盈利基线。

**输出**（写入 `industry_params`）：
```json
{
  "industry": "白酒",
  "avg_gross_margin_pct": 70,
  "avg_net_margin_pct": 35,
  "avg_roe_pct": 20,
  "avg_revenue_growth_pct": 8,
  "profit_driver": "利润率驱动(品牌溢价)",
  "source": "URL"
}
```

**判断依据**：消费品看利润率、制造业看周转率（主 agent 盈利框架规则）。

---

## 任务 D（P1）：行业产业链成本占比 → 上游/中游/下游成本结构

为 **30 个重点行业**搜集产业链成本占比。

**输出**（写入 `industry_params`）：
```json
{
  "industry": "光伏",
  "chain_cost": {
    "上游硅料": 40,
    "中游电池片": 25,
    "下游组件": 20,
    "其他": 15
  },
  "profit_center": "上游硅料(周期波动大)",
  "source": "URL"
}
```

---

## 任务 E（P1）：行业政策方向评分 → 鼓励/中性/限制

为 **30 个重点行业**搜集政策方向。

**输出**（写入 `industry_params`）：
```json
{
  "industry": "半导体",
  "policy_direction": 1,
  "policy_level": "国家级",
  "policy_summary": "大基金三期+国产替代战略",
  "source": "URL"
}
```

（direction: 1=鼓励 / 0=中性 / -1=限制）

---

## 数据源建议

- **Tavily**：`<行业> WACC 估值参数`、`<行业> 毛利率 净利率 ROE 2026`、`<行业> 渗透率 生命周期`、`<行业> 产业链 成本占比`
- **已有数据复用**：`data/industry_baselines.json`（335 行业 PE/PB/股息率）、`data/industry_drivers.json`（供需）、`data/industry_penetration.json`（渗透率）
- **投喂研报**：`data/baseline_findings.json`（评级/预测）

---

## 格式规范

- **source 标注**：每条带 URL 或"已有数据: industry_baselines"等来源
- **幂等**：重跑合并去重（同 industry + 同字段）
- **完整性**：30 个重点行业每个都要有 A/B/C/E 四项（D 产业链成本可选）
- **写回方式**：追加到 `data/methodology_rules.json`，结构见各任务输出示例
- **验证**：写完读回检查，确认能 merge

---

## 完成状态表

| 任务 | 目标 | 状态 |
|---|---|---|
| A 估值参数 | 30 行业 WACC/PE/PB/PS | ☐ |
| B 生命周期 | 30 行业阶段判定 | ☐ |
| C 盈利参数 | 30 行业毛利率/净利率/ROE | ☐ |
| D 产业链成本 | 30 行业成本占比 | ☐ |
| E 政策方向 | 30 行业方向评分 | ☐ |

## 参考资料
- 规则库：`core/methodology_rules.py`（save_external_rules 写入）
- 现有行业数据：`data/industry_baselines.json` / `industry_drivers.json` / `industry_penetration.json`
- 方法论规则（判断依据）：`data/methodology_rules.json`
