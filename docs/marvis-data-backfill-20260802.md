# Marvis 数据补充命令集（token 免费，放心执行）

> 2026-08-02 生成。Marvis 执行命令、补充数据后回流管线，2hao 自动吸收。
> 所有补充数据必须带 source（FP2 数据零编造），无 source 的数据点会被桥接层拦截。

---

## 0. 必读：Marvis 的职责边界

- ✅ 你（Marvis）负责**搜数据、写 enrich-file JSON、跑同步脚本**，用你的 token（免费）
- ❌ 你**不写报告正文**。数据通过 `--enrich-file` 回流管线后，由 2hao 的 DeepSeek 写
- 每补一条数据，`source` 字段必须写明来源（URL/数据库名/官方公告）

---

## 1. 立即执行：生成 A 股名称映射缓存（修柯力传感 bug）

根因：`instruments/all.txt` 只有代码无中文名，用"柯力传感"搜代码失败 → 0 图 → Gate 失败。
已加 `_lookup_code_by_name()` 读 `data/a_stock_name_map.json`，但映射需先生成。

```bash
# 在 D:\2hao-analyst 目录执行
cd D:\2hao-analyst
python -c "
import akshare as ak, json
df = ak.stock_zh_a_spot_em()
name_map = {str(r['名称']): str(r['代码']) for _, r in df.iterrows()}
json.dump(name_map, open('data/a_stock_name_map.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'已写入 {len(name_map)} 条 A 股名称映射')
"
```

验证：`python -c "from pipeline.data_collector import _lookup_code_by_name; print(_lookup_code_by_name('柯力传感'))"` 应输出 603662

---

## 2. 数据缺口清单（已盘点）

### 2.1 industry_chain.json（54 行业）缺这些行业条目

| 行业 | 用途 | 数据要求 |
|---|---|---|
| **传感器** | 传感器行业深度报告 | 上游（敏感材料/芯片/封装）/中游（MEMS传感器/力传感器）/下游（工业/汽车/消费） |
| **仪器仪表** | 柯力传感等 | 上游（芯片/传感器元件）/中游（称重/分析仪器）/下游（工业检测） |
| **工控** | 汇川/埃斯顿 | 上游（芯片/伺服电机）/中游（PLC/伺服/变频）/下游（工厂自动化） |
| **机器人** | 具身智能报告 | 上游（减速器/伺服/传感器）/中游（本体/系统集成）/下游（工业/服务） |
| **具身智能** | 具身智能报告 | 上游（传感器/执行器/AI芯片）/中游（本体+算法）/下游（场景） |

**写入方式**：编辑 `data/industry_chain.json`，往 `industries` 数组加对象，格式：
```json
{"name": "传感器", "upstream": ["敏感材料", "MEMS芯片", "封装测试"], "midstream": ["力/压力/温湿度传感器", "智能传感器模组"], "downstream": ["工业自动化", "汽车电子", "消费电子", "医疗"], "key_players": ["柯力传感", "韦尔股份", "华工科技"]}
```

### 2.2 industry_penetration.json（200 条）缺

- 传感器：国产化率/渗透率（如 MEMS 国产化率 ~30%）
- 仪器仪表：高端分析仪器国产化率（~20%）
- 气体传感器：渗透率（工业安全/环保监测）
- 具身智能：人形机器人渗透率/出货量

**写入方式**：往 `data/industry_penetration.json`（顶层 list）加：
```json
{"industry": "传感器", "segment": "中国MEMS传感器国产化率", "penetration_pct": 30.0, "as_of": "2025", "life_cycle": "成长期", "growth_curve": "S曲线加速", "source": "https://..."}
```

### 2.3 industry_drivers.json（103 行业）缺

- **传感器**（当前缺，最优先）：供需条目 5-10 条
- **具身智能**：供需条目
- **AI算力**：供需条目

**写入方式**：`data/industry_drivers.json` 是 dict，加 key：
```json
"传感器": ["2025全球传感器市场规模-Gartner", "• MEMS传感器市场增长XX%达到XX亿美元", "..."]
```

---

## 3. 柯力传感 enrich 数据（当前最紧急）

管线跑柯力传感缺：`fig_revenue_trend` + `fig_profitability`（本地已有，但补全更好）+ 产业地位。

模板已生成：`data/backlog/柯力传感_enrich_template.json`

```bash
# 1. 看模板
cat data/backlog/柯力传感_enrich_template.json
# 2. 用 WebSearch/akshare 填真实数据，改 source 为真实来源，存成 enrich.json
# 3. 回流
python pipeline/scheduler.py "柯力传感" --type listed_company --enrich-file data/backlog/柯力传感_enrich_template.json
```

**需要补的数据点**（每条带 source）：
- 营收趋势 2023/2024/2025（fig_revenue_trend）
- 净利趋势 2023/2024/2025（fig_profitability）
- 传感器行业地位/市占率（fig_competitive_landscape）
- 称重传感器全球/中国市场规模（fig_market_size_china/global）

---

## 4. 其他推荐执行的同步（现有脚本，Marvis 可跑）

```bash
# 全量数据同步（3 阶段：财务/行情/资金面）
python scripts/run_all_sync.py

# 只补某只股票的财务（增量）
python scripts/sync_financials.py "603662" --incremental
python scripts/sync_financials.py "688469" --incremental

# 行业基线（申万三级 PE/PB）
python scripts/sync_industry_baselines.py

# 一致预期（分析师 EPS/评级）
python scripts/sync_consensus_estimates.py

# 公司事件（分红/解禁）
python scripts/sync_company_events.py
```

---

## 5. 优先级总结（按紧迫度）

| 优先级 | 任务 | 命令/文件 | 为什么 |
|---|---|---|---|
| **P0** | 生成 A 股名称映射 | 见 §1 | 修柯力传感 0 图 bug 的最后一步 |
| **P0** | 柯力传感 enrich | 见 §3 | 用户正在等这份报告 |
| **P1** | 补 industry_chain 传感器/仪器仪表/工控 | 见 §2.1 | 让瓶颈引擎有真实产业链数据 |
| **P1** | 补 penetration 传感器/仪器仪表 | 见 §2.2 | 生命周期/渗透率驱动评分 |
| **P2** | 补 drivers 传感器/具身智能 | 见 §2.3 | 行业供需文本 |
| **P2** | run_all_sync 全量同步 | 见 §4 | 刷新离线数据底座 |

---

## 6. 完成后验证

```bash
# 名称映射
python -c "from pipeline.data_collector import _lookup_code_by_name; print(_lookup_code_by_name('柯力传感'))"
# 产业链覆盖
python -c "
import json
c = json.load(open('data/industry_chain.json'))
print([x['name'] for x in c['industries'] if any(k in x['name'] for k in ['传感器','仪器仪表','工控'])])
"
# 柯力传感数据充足性
python -c "
from pipeline.data_collector import DataCollectorV5
from pipeline.data_enrichment import DataSufficiencyChecker
local = DataCollectorV5()._local_search('柯力传感')
print('local keys:', list(local.keys()))
"
```

---

> Marvis 执行完任意 §1-§4 后，用结果更新本文件的状态，或通知 2hao 重新跑对应报告。
> 你的 token 免费——该搜就搜，该跑就跑，别省。
