# R81 全球视角+行业框架接线修复——执行记录

> 修复："全球视角下的市场调研"和"行业分析框架"融入了但没生效的问题
> 日期：2026-08-06

---

## 一、问题根因（为什么融入了没生效）

| 断裂点 | 现状 | 结果 |
|--------|------|------|
| 框架注入只有"名字" | 注入 core_thesis + 步骤名，无具体分析操作 | LLM 看到框架名不知怎么用，忽略 |
| 全球数据源没进写作prompt | load_global_leaders 在 data_basement，写作时未注入 | LLM 无全球数据可用，写不出全球视角 |
| 行业-框架静态匹配 | 按 report_type 一刀切 | 油位小行业匹配不到咨询/产业框架 |
| 30+注入变量稀释 | 框架/全球被淹没 | LLM 注意力被摊薄 |

---

## 二、修复落地（4 项）

### 2.1 框架注入用法化（core/framework_injector.py）
- 从注入"框架名"升级为注入"具体分析操作"
- 每个框架的 logic_chain → dimensions → indicators 具体注入
- 例：护城河框架现在注入"无形资产：看品牌溢价/专利保护/监管牌照；转换成本：看客户粘性/定制化程度/迁移成本..."
- **效果**：LLM 拿到的是"怎么分析"而非"分析什么"

### 2.2 全球视角数据接入（pipeline/section_writer.py）
- 新增 `global_str` 注入块：读 chart_data 的 fig_global_leaders / global_industry_players / overseas_revenue
- 序列化注入写作 prompt，要求"报告必须体现全球视野"
- **效果**：LLM 有全球龙头数据可用，能写"VEGA 高端主导，柯力对标..."而非只写中国

### 2.3 行业-框架动态匹配（core/framework_injector.py）
- `get_frameworks_for_report` 增加 `industry_hint` 参数
- 框架 tags/适用行业包含行业关键词 → 优先级提升排前
- section_writer 从 asset 提取行业关键词传入
- **效果**：传感器行业命中相关框架，而非 report_type 一刀切

### 2.4 补全球对标数据（data/keli_oil_enrich_20260805.json）
- enrich-file 14 项，新增：
  - fig_global_leaders：VEGA/Siemens/E+H/Emerson/Yokogawa 全球龙头 + 中国玩家定位
  - fig_overseas_revenue：柯力海外收入3.07亿/久通80+国家/中东东南亚机会

---

## 三、回归

43 pytest 全绿（test_r79/test_r78_geopolitical/test_fact_quality）

---

## 四、新报告将体现什么

| 能力 | 修复前 | 修复后 |
|------|--------|--------|
| 行业框架 | 框架名，LLM 忽略 | 具体分析步骤（护城河五类型看什么指标） |
| 全球视角 | 只有市场规模数字 | 全球龙头对标/海外竞争格局/海外收入分析 |
| 行业适配 | report_type 一刀切 | 传感器行业命中相关框架 |

---

## 五、未落地（需续）

- 全球数据真实采集（当前用 v8 报告 + 公开资料的静态数据）
- 框架注入在真实报告中的效果验证（需跑新报告看是否体现）
- 注入变量瘦身（30+ → 15，进一步提升 LLM 注意力）
