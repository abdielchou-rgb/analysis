# Marvis 数据补充指令 — 传感器行业深度报告（2026-08-04）

> 执行环境：**用户本机**（需 WebSearch/免费接口；沙箱不可执行）
> 背景：用户将写一篇**传感器行业深度报告**（先用 26 维 SAC 框架，参照已跑通的"气体传感器行业深度报告"Gate 0.9487）。
> 本指令为传感器行业报告补齐数据缺口 + 修复 R55/R58 交付数据的口径矛盾。
> 核心约束：**数据质量优先**——每条带 source、幂等、失败隔离、无数据不编造（FP2）。

---

## 零、任务总览

| 优先级 | 任务 | 目标 | 交付物 |
|---|---|---|---|
| **P0-1** | 传感器行业市场规模口径校准 | 修复 R55 交付的 global_market_segments 全球/中国 TAM 矛盾 | 更新 `global_market_segments.json` |
| **P0-2** | 全球传感器龙头全景 | 补齐气体传感器之外的全品类传感器龙头（MEMS/图像/压力/温度） | 更新 `global_industry_players.json` |
| **P0-3** | 传感器产业链细分映射 | 让 data_basement 的 industry_chain 能命中"传感器"细分品类 | 更新 `industry_chain.json` |
| **P1-1** | 渗透率曲线数据 | 各场景（汽车/工业/医疗/消费）传感器渗透率 | 更新 `industry_penetration.json` |
| **P1-2** | 区域市场拆分 | 北美/欧洲/亚太气体传感器+传感器市场规模/增速 | 更新 `regional_penetration.json` |
| **P1-3** | 中国传感器政策库 | 传感器产业政策文件（工业强基/国产替代/专项） | 更新 `policy_db.json` |
| **P2-1** | 并购案例补充 | 传感器行业国内并购案例（现有3个全是海外） | 更新 `m_and_a_cases.json` |
| **P2-2** | ESG 传感器数据 | 确认 industry_esg.json 传感器条目已存在并补齐 | 核查 `industry_esg.json` |

**执行顺序**：P0-1 → P0-2 → P0-3 → P1-1 → P1-2 → P1-3 → P2-1 → P2-2。

---

## 一、P0-1：市场规模口径校准（最高优先）

### 为什么需要
R55 交付的 `data/global_market_segments.json` "气体传感器"条目存在**口径矛盾**：
- global_tam_2025 = 22 亿美元
- china_tam_2025 = 115 亿人民币（≈16 亿美元，按 7.0 汇率）
- 而气体传感器深度报告（Gate 已过）引用的口径是 **全球 45 亿美元 / 中国 12 亿美元**（Yole/MarketsandMarkets）

两组数字对不上（全球 22 vs 45、中国 115亿人民币 vs 12亿美元），报告若同时引用会触发一致性 Gate 拦截。

### 目标
校准 `data/global_market_segments.json` 的"气体传感器"条目，同时**新增"传感器"大行业条目**（供用户写传感器大行业报告用）。

### Schema（保持现有结构不变）
```json
{
  "气体传感器": {
    "global_tam_2025": {"value": 45.0, "unit": "亿美元", "source": "Yole/MarketsandMarkets"},
    "china_tam_2025": {"value": 12.0, "unit": "亿美元", "source": "中国传感器产业联盟/前瞻"},
    "segments": {
      "工业安全与环保监测": {"global": 12.0, "china": 3.5, "growth_cagr": 6.5, "unit": "亿美元"},
      "汽车电子(热失控监测)": {"global": 11.0, "china": 3.0, "growth_cagr": 12.0, "unit": "亿美元"},
      "消费电子与智能家居": {"global": 10.0, "china": 2.5, "growth_cagr": 8.0, "unit": "亿美元"},
      "医疗健康": {"global": 8.0, "china": 2.0, "growth_cagr": 7.0, "unit": "亿美元"}
    },
    "source": "WebSearch 交叉验证 Yole/MarketsandMarkets/前瞻/中商",
    "confidence": "B"
  },
  "传感器(大行业)": {
    "global_tam_2025": {"value": 2800.0, "unit": "亿美元", "source": "..."},
    "china_tam_2025": {"value": 3600.0, "unit": "亿人民币", "source": "..."},
    "segments": {
      "MEMS传感器": {"global": 180.0, "china": 400.0, "growth_cagr": 8.0, "unit": "亿美元/亿人民币"},
      "图像传感器(CIS)": {"global": 220.0, "china": 600.0, "growth_cagr": 5.0, "unit": "亿美元/亿人民币"},
      "压力/温度/流量传感器": {"global": 150.0, "china": 350.0, "growth_cagr": 7.0, "unit": "亿美元/亿人民币"},
      "气体传感器": {"global": 45.0, "china": 90.0, "growth_cagr": 10.0, "unit": "亿美元/亿人民币"}
    },
    "source": "...",
    "confidence": "B"
  }
}
```

### 操作步骤
1. 读现有 `data/global_market_segments.json`
2. 用 WebSearch 找**气体传感器全球/中国市场规模**的多来源数字（Yole、MarketsandMarkets、Mordor、前瞻、中商、华经）
3. **交叉验证**：保留 2-3 个来源做区间，标注主口径；若 22 vs 45 亿差距源于"气体传感器"定义边界不同，注明口径差异
4. 新增"传感器(大行业)"条目，含 MEMS/CIS/压力温度/气体等细分品类拆分
5. **单位统一**：global 用亿美元，china 用亿人民币或亿美元（报告一致即可），每条 value 带 unit

### 验证标准
**通过标准**：
- 气体传感器全球 TAM 与报告口径（45亿/12亿美元）交叉一致，或显式标注差异原因
- 新增"传感器(大行业)"条目 ≥4 个细分品类
- 每条带 source + confidence

---

## 二、P0-2：全球传感器龙头全景

### 为什么需要
R55 交付的 `global_industry_players.json` "气体传感器"条目只有 Honeywell/Sensirion 等 2-4 家。
用户写**传感器大行业报告**需要全品类龙头（MEMS/图像/压力/温度），以及中国 vs 全球的份额/技术代差。

### 目标
补充 `global_industry_players.json` 的"传感器(大行业)"条目，覆盖全品类龙头。

### Schema（保持现有结构）
```json
{
  "传感器(大行业)": {
    "players": [
      {"name": "Bosch Sensortec", "ticker": "BOSCH", "country": "DE", "segment": "MEMS(加速度/陀螺仪)", "role": "global_leader", "market_share_est": 25.0, "confidence": "B", "public": false, "note": "MEMS惯性传感器全球第一"},
      {"name": "Sony Semiconductor", "ticker": "6758.T", "country": "JP", "segment": "图像传感器(CIS)", "role": "global_leader", "market_share_est": 42.0, "confidence": "B", "public": true, "note": "CIS全球第一"},
      {"name": "STMicroelectronics", "ticker": "STM", "country": "CH/IT", "segment": "MEMS(压力/温度)", "role": "global_leader", "market_share_est": 15.0, "confidence": "B", "public": true, "note": ""},
      {"name": "TE Connectivity", "ticker": "TEL", "country": "US", "segment": "压力/湿度传感器", "role": "global_leader", "market_share_est": 10.0, "confidence": "C", "public": true, "note": ""},
      {"name": "汉威科技", "ticker": "300007.SZ", "country": "CN", "segment": "气体传感器", "role": "china_leader", "market_share_est": 20.8, "confidence": "B", "public": true, "note": "中国气体传感器龙头"},
      {"name": "四方光电", "ticker": "688665.SH", "country": "CN", "segment": "气体传感器(光学)", "role": "china_leader", "market_share_est": 8.3, "confidence": "B", "public": true, "note": ""}
    ],
    "source": "Yole/MarketsandMarkets/各公司年报/WebSearch",
    "confidence": "B"
  }
}
```

### 操作步骤
1. 覆盖品类：MEMS惯性、图像传感器(CIS)、压力/温度/流量、气体、湿度、磁传感器
2. 每个品类找全球龙头（Bosch/ST/Sony/Omron/霍尼韦尔/TE/村田/Allegro 等）
3. **中国市场对标**：每个品类给中国龙头（如韦尔股份-图像、瑞声/歌尔-声学MEMS、汉威/四方-气体、敏芯/纳芯微-压力）
4. 市场份额找不到标 null 或 confidence="E"
5. 已有"气体传感器"条目**不重复**，只补大行业条目

### 验证标准
**通过标准**：传感器(大行业)条目 ≥6 家全球龙头 + ≥4 家中国龙头，每品类至少1家。

---

## 三、P0-3：产业链细分映射

### 为什么需要
`data/industry_chain.json` 已有"传感器"条目，但它是**称重/力传感器导向**的：
- upstream 是"弹性体/应变计/精密机械加工"（称重专用）
- key_players 是"柯力传感/中航电测"（称重龙头）
用户写**传感器大行业报告**需要的是通用/MEMS/气体传感器产业链（上游晶圆/材料 → 中游器件 → 下游汽车/工业/医疗/消费），当前条目不适用。

### 目标
在 `industry_chain.json` 的 `industries` 数组**追加**两条，不覆盖现有"传感器"条目：
1. `"传感器"` 通用产业链（新增，替换称重导向覆盖不足的问题）
2. `"气体传感器"` 细分产业链

### Schema（`industries` 数组 append，与 loader 兼容）
```json
[
  {
    "name": "传感器",
    "upstream": ["MEMS晶圆代工", "敏感材料(硅/压电/金属氧化物)", "ASIC/信号调理芯片", "封装基板", "稀土/贵金属"],
    "midstream": ["MEMS器件制造", "CMOS图像传感器(CIS)", "气体传感器(电化学/MOS/NDIR)", "压力/温度/流量器件", "模组封装测试"],
    "downstream": ["汽车电子", "工业自动化", "消费电子", "医疗设备", "物联网/IoT", "机器人"],
    "key_players": ["韦尔股份", "瑞声科技", "歌尔股份", "汉威科技", "四方光电", "敏芯股份", "纳芯微", "保隆科技"],
    "source": "Yole/WebSearch（通用传感器产业链，2026-08）"
  },
  {
    "name": "气体传感器",
    "upstream": ["贵金属浆料(铂/钯)", "MEMS晶圆", "红外光源/探测器", "金属氧化物半导体材料"],
    "midstream": ["电化学传感器", "催化燃烧传感器", "金属氧化物(MOS)传感器", "非分散红外(NDIR)", "激光/光声光谱"],
    "downstream": ["工业安全(化工/煤矿/冶金)", "环保监测(CEMS)", "汽车电子(热失控监测)", "智慧医疗", "消费电子(燃气报警)"],
    "key_players": ["汉威科技", "四方光电", "霍尼韦尔", "Sensirion", "Figaro", "Dräger", "炜盛电子"],
    "source": "Yole/MarketsandMarkets/公司年报（2026-08）"
  }
]
```

### 验证标准
**通过标准**：`load_industry_chain("气体传感器")` 和 `load_industry_chain("传感器")` 都能返回非空（匹配 name 字段）。

---

## 四、P1-1：渗透率曲线数据

### 为什么需要
`data/industry_penetration.json` 目前**空**（0 条）。SAC 26 维的"市场空间"维度要求渗透率曲线判断（加速器拐点/时光机/稳态仪）。

### 目标
填充 `industry_penetration.json` 的"气体传感器"与"传感器(大行业)"条目。

### Schema（**顶层 list**，与 `load_penetration` 兼容——注意不是 dict）
```json
[
  {"industry": "气体传感器", "segment": "工业安全(化工/煤矿/冶金)", "penetration_pct": 65.0, "as_of": "2025", "life_cycle": "成熟期", "growth_curve": "存量替换(电化学→红外)", "source": "MIR睿工业/中国环境监测总站"},
  {"industry": "气体传感器", "segment": "汽车电子(电池热失控监测)", "penetration_pct": 9.0, "as_of": "2025", "life_cycle": "导入期末", "growth_curve": "S曲线加速(GB 38031-2025强制)", "source": "..."},
  {"industry": "气体传感器", "segment": "智慧医疗(呼吸机/麻醉机)", "penetration_pct": 10.0, "as_of": "2025", "life_cycle": "成长期", "growth_curve": "医疗设备国产化", "source": "..."},
  {"industry": "气体传感器", "segment": "消费电子(室内空气质量)", "penetration_pct": 5.0, "as_of": "2025", "life_cycle": "导入期", "growth_curve": "家用燃气报警器强制安装", "source": "..."},
  {"industry": "传感器", "segment": "汽车(单车传感器价值量)", "penetration_pct": null, "as_of": "2025", "life_cycle": "成长期", "growth_curve": "智能驾驶L2+渗透", "source": "..."},
  {"industry": "传感器", "segment": "工业自动化", "penetration_pct": null, "as_of": "2025", "life_cycle": "成长期", "growth_curve": "工业4.0/国产替代", "source": "..."}
]
```
> **注意**：loader 按 `industry` 字段遍历 list 匹配（精确→包含→短词兜底）。必须用 `"industry": "气体传感器"` / `"industry": "传感器"` 作为顶层字段，**不要**用 dict keyed by 行业名。

### 验证标准
**通过标准**：气体传感器 ≥3 场景渗透率 + 来源；传感器大行业 ≥2 场景。

---

## 五、P1-2：区域市场拆分

### 为什么需要
R55 的 `regional_penetration.json` "气体传感器"条目有中国 vs 欧美领先国渗透率错位，但**缺北美/欧洲/亚太市场规模拆分**。SAC 26 维"全球分区域市场空间"要求区域透视。

### 目标
补充区域拆分到 `regional_penetration.json`（或 global_market_segments 的 segments 内）。

### Schema（附加字段）
```json
{
  "气体传感器": {
    "china_penetration_pct": "20-30（估算，2023）",
    "leading_country": "美国/德国",
    "leading_penetration_pct": "60-80（估算，2023）",
    "gap_years_est": "5-8",
    "regional_market_2025": {
      "北美": {"value": 12.0, "unit": "亿美元", "growth_cagr": 5.0, "source": "..."},
      "欧洲": {"value": 10.0, "unit": "亿美元", "growth_cagr": 6.0, "source": "..."},
      "亚太(不含中国)": {"value": 8.0, "unit": "亿美元", "growth_cagr": 8.0, "source": "..."},
      "中国": {"value": 12.0, "unit": "亿美元", "growth_cagr": 19.0, "source": "..."}
    },
    "time_machine_basis": "...",
    "source": "...",
    "confidence": "E"
  }
}
```

### 验证标准
**通过标准**：气体传感器区域拆分 ≥3 区域（北美/欧洲/亚太/中国），各带规模+增速。

---

## 六、P1-3：中国传感器政策库

### 为什么需要
`data/policy_db.json` 目前无"传感器"命中（total=2 且不含传感器）。SAC 26 维"政策传导链"需要政策文件。

### 目标
补充 `data/policy_db.json` 的"传感器/工业强基"条目。

### 操作步骤
1. 收集政策文件：《中国传感器产业发展白皮书》、《工业强基工程实施方案》、《基础电子元器件产业发展行动计划(2021-2023)》、《十四五规划纲要》传感相关、"十五五"规划传感器表述
2. **追加到 `policy_db.json` 的 `policies` 数组**（loader 按 `policies[].industry` 匹配），每条结构：
```json
{
  "industry": "传感器",
  "title": "工业强基工程实施方案",
  "issuer": "工信部",
  "year": "2023",
  "content": "核心内容摘要...",
  "impact": "对传感器行业的影响(鼓励/补贴/国产替代)",
  "source": "工信部官网/WebSearch"
}
```
3. 用 WebSearch 找最新政策（2024-2026）
4. **不要新建 dict**——`policy_db.json` 顶层是 `{"policies": [...], "source": "..."}`，把新条目 append 进 `policies`

### 验证标准
**通过标准**：`load_policy("传感器")` 返回 ≥5 条政策。

---

## 七、P2-1：并购案例补充

### 为什么需要
`data/m_and_a_cases.json` 气体传感器条目现有 3 个案例**全是海外**（Honeywell-City Tech / Amphenol-GE / Excelitas-PerkinElmer）。缺中国/亚洲并购案例，无法支撑"行业整合"判断的中美对比。

### 目标
补充传感器大行业+气体传感器的中国/亚洲并购案例到 `m_and_a_cases.json`。

### 操作步骤
1. 保持现有 8 行业结构，补充"传感器(大行业)"条目
2. 找中国传感器并购案例：如汉威科技收购炜盛电子、韦尔股份收购豪威科技(CIS)、思特威/格科微融资、敏芯/纳芯微并购等
3. 字段：acquirer/target/year/value_b/currency/deal_type/source；EV/EBITDA 无权威来源标 null

### 验证标准
**通过标准**：传感器(大行业) ≥3 案例（含 ≥2 个中国/亚洲案例），EV/EBITDA 无数据标 null。

---

## 八、P2-2：ESG 数据核查

### 为什么需要
R58 已交付 `industry_esg.json` 含"气体传感器/工业设备"条目。用户写传感器大行业报告需确认覆盖。

### 操作步骤
1. 读 `data/industry_esg.json`，确认"气体传感器/工业设备"条目存在且 ≥2 实质议题
2. 若缺"传感器(大行业)"条目，补充 MEMS 制造业的 ESG 议题（晶圆制造能耗/化学品/供应链）

### 验证标准
**通过标准**：气体传感器条目已在 + 传感器大行业条目存在（或显式说明已覆盖）。

---

## 九、通用规范（所有任务遵守）

1. **幂等**：脚本可重复运行，覆盖写入
2. **source 标注**：每条数据带 source（搜索来源/接口/URL）
3. **失败隔离**：单行业/单品类失败不中断整体
4. **诚实边界（FP2）**：无权威来源标 null/confidence="E"，**严禁编造**
5. **口径一致**：全球用亿美元、中国用亿人民币或亿美元统一标注；不同来源区间注明主口径
6. **不重复采集**：R55/R58 已交付的"气体传感器"条目（global_market_segments/regional_penetration/unlisted_players/global_industry_players/m_and_a_cases/industry_esg）**有数据就更新，不新建**；只有"传感器(大行业)"条目是新增
7. **验证**：每项完成跑对应验证，通过才算完成
8. **报告**：每项写小结，最终汇总成执行报告

---

## 十、完成验收清单

| 任务 | 交付物 | 验收标准 |
|---|---|---|
| P0-1 | global_market_segments.json | 气体传感器口径与报告一致 + 新增传感器大行业 ≥4 细分 |
| P0-2 | global_industry_players.json | 传感器大行业 ≥6 全球龙头 + ≥4 中国龙头 |
| P0-3 | industry_chain.json | load_industry_chain("气体传感器") 非空 |
| P1-1 | industry_penetration.json | 气体传感器 ≥3 场景渗透率 |
| P1-2 | regional_penetration.json | 气体传感器区域拆分 ≥3 区域 |
| P1-3 | policy_db.json | ≥5 条传感器政策 |
| P2-1 | m_and_a_cases.json | 传感器大行业 ≥3 案例（含 ≥2 中国） |
| P2-2 | industry_esg.json | 传感器大行业 ESG 议题存在 |

> 全部完成后，写执行报告到 `D:\Marvis\output\传感器行业数据补充执行报告.md`，
> 格式参照 `R58后续工作数据执行报告.md`。报告里**明确标注**可得/不可得项与口径差异。
