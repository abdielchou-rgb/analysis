# 行业深度分析方法论系统性升级方案

> 版本：v1.0 ｜ 日期：2026-08-03 ｜ 状态：待评审
> 定位：2hao 行业深度报告（industry_deep）的方法论升级设计文档
> 触发：用户提出——"行业报告颗粒度是否应精细到上市公司/非上市公司态势分析" + "中国公司全球发力，行业分析应从全球视野俯瞰各市场再分细分市场"

---

## 〇、执行摘要

本方案基于**顶级机构方法论联网调研**（4 路子代理：国际投行/中资券商、MBB/四大/市场研究机构、学术理论、AI 生成报告最佳实践），结合 2hao 系统现状实证核查，对行业深度报告方法论做系统性升级。

**核心判断（一句话）**：行业报告不能悬浮在行业层面，必须**落到公司层（四层金字塔）+ 打开全球视野（全球-区域-细分三段式）**，但二者的方法论内核都是**"参照系"而非"罗列"**——用海外做时光机参照、用全球玩家做对手盘参照、用细分×全球做利润池判断。同时，所有升级必须守住**数据诚实边界**（FP2）。

**升级要点**：
1. 公司层：从"玩家分层+可比框架"升级为**四层金字塔**（分层→可比→选股→非上市威胁）
2. 全球视野：从"全球市场并列枚举"升级为**全球-区域-细分三段式分析链**（渗透率错位/时光机/对手盘）
3. 数据底座：补**细分行业全球玩家映射** + **市场规模数据四元组**（来源/年份/口径/置信等级）
4. 质量护栏：新增 **TAM/SAM/SOM 自底向上校验** + **原子事实溯源门禁** + **区域渗透率错位检查**

---

## 一、顶级机构方法论调研结论（4 条线综合）

### 1.1 国际投行（高盛/大摩/摩根大通）+ 中资券商（中金/中信/申万）

**国际投行行业报告标准结构**（调研合成）：

```
一、Investment Summary（观点先行：评级/目标价/催化剂/市场未定价什么）
二、Market Overview（市场全景：TAM、5年CAGR、四维切分）
三、Industry Structure（行业结构：价值链+价值沉淀环节+CR5+壁垒）
四、Supply & Demand（供需：需求端客户拆分 vs 宏观推算双轨校验）
五、Global → Regional（全球俯瞰→分区域规模/增速/竞争强度）
六、Competitive Landscape（竞争格局：按细分逐段给份额表，含非上市龙头）
七、Company Profiles & Peers（头部5-10家 peer 矩阵+估值快照）
八、Valuation Context（板块估值区间+溢价折价驱动+M&A倍数）
九、Investment Implications（多空辩论+催化剂日历+风险清单）
```

**关键发现**：
- 高盛按"行业分析师+区域专家+主题团队"三层架构，报告普遍用**"全球→区域→子行业→代表公司"漏斗式展开**；图表标配市场规模瀑布、竞争定位矩阵、估值散点
- 大摩 AlphaWise 用**一手数据调研**支撑市场规模，避免二手互相抄；报告强调 **Variant view**（先给共识再给差异判断）
- 中金差异化 = **全球视角 + 产业链研究**（《大国产业链》框架：全球产业格局俯瞰 → 中国位置与替代弹性 → 细分竞争 → 受益标的）
- 中信系统框架：**需求分析 → 供给分析 → 供需平衡 → 行业分类（生命周期×经济周期）**；竞争分析四步法（界定行业→标的划入细分→评价对手→概括优劣势）
- **颗粒度结论**：国际投行对细分市场**逐段给玩家态势是标配**（规模+增速+CR份额表，头部5-10家深度档案，非上市龙头进份额表但估值只在上市层展开）；中资券商对非上市玩家深度弱于国际投行

### 1.2 MBB / 四大 / 市场研究机构

**MBB 视角**（战略经营视角，区别于投行投资视角）：
- 麦肯锡：**利润池分析**（收入份额≠利润份额，找利润最厚环节）、SCP 范式、产业吸引力（五力）、GE/麦肯锡矩阵、三层面增长
- BCG：增长份额矩阵、**经验曲线**（累计产量翻倍成本降10-30%）、**三四规则**（成熟市场稳定在3-4家）
- 贝恩：**市场定义**（先界定竞争边界：产品/需求替代性+地域）、NPS/忠诚度经济学

**四大视角**（规范/风险视角）：监管合规影响、风险与治理、产业链韧性、数据合规、ESG——回答"合不合规、风险多大、账怎么算"

**市场研究机构**（Gartner/IDC/Frost&Sullivan/Euromonitor）：
- **市场规模测算**：厂商收入加总为基准，**top-down（宏观驱动×渗透率×单价）与 bottom-up（微观样本外推）双轨交叉验证**
- **细分维度**：技术/产品→应用场景→地域→客户，层层拆分再加总回总盘
- **增长预测**：CAGR 外推 + 渗透率假设 + 驱动因子模型 + 乐观/中性/保守三档
- **TAM/SAM/SOM**：逐层收缩假设（渠道/地域/产品力约束），防"天文数字 TAM"幻觉
- **诚实边界**：无法验证时用**区间+灵敏度**而非单点数字；引用第三方数据必带方法局限

### 1.3 学术理论基石

| 理论 | 应用环节 | 可落地检查维度 |
|---|---|---|
| SCP 范式 + 芝加哥学派 | 竞争格局与盈利质量 | 集中度 CR3/5、HHI；高ROE归因（垄断 vs 效率） |
| 波特五力 + 动态能力 | 行业结构扫描 | 五力逐项评分+方向；警惕静态化套模板 |
| 波特价值链 + 微笑曲线 | 利润分布与升级路径 | 逐环节毛利率/价值占比；本土企业两端布局 |
| GVC 治理（Gereffi） | 全球产业链地位 | 供应商依赖度、切换成本、标准制定权 |
| 生命周期（Vernon）+ 主导设计（Utterback-Abernathy） | 阶段判断与技术收敛 | 增速/渗透率/竞争者数；主导设计是否确立 |
| 技术 S 曲线（Foster） | 技术换代风险 | 性能-投入曲线斜率、新旧路线交叉点 |
| 破坏性创新（Christensen） | 颠覆风险预警 | 是否存在过度服务市场、挑战者路径 |
| 市场细分（Smith）+ TAM/SAM/SOM | 行业空间测算 | 细分维度、各子市场增速差异、逐层收缩假设 |
| 创新扩散（Rogers/Bass） | 渗透率拐点预测 | 渗透率处于 S 形哪段、对标成熟市场、p/q 系数 |
| 乌普萨拉模型 + OLI（邓宁） | 出海逻辑 | 心理距离、O/L/I 三要素成立性 |
| **时光机**（恩格尔/Vernon 映射） | **海外对标** | 人均GDP时差、购买力差异、数字化跳变修正 |

### 1.4 AI 生成报告最佳实践（BloombergGPT/Deep Research/FinSight/FinDVer/FActScore）

- **证据追溯**：每段正文加 `claim → source_id → 字符区间` 引用注解（Deep Research annotation / FinSight Chain-of-Analysis）
- **数据分级**：结构化DB=高置信 / PDF-OCR=中 / LLM推断=低，低置信强制进 enrich-file 回流
- **原子事实核验**：FActScore 思路——报告拆成原子断言逐条对账，非整体评分
- **长文档分通道验证**：文本/表格/图表分开核验（FinDVer：混合内容下 LLM claim verification 显著落后人类）
- **市场数据四元组**：来源+年份+口径+置信等级，缺任一降级为估算区间
- **TAM 自底向上**：价格×数量推导+假设披露，禁引"某机构市场规模"就完事

---

## 二、2hao 系统现状核查（实证）

| 项 | 现状 | 缺口 |
|---|---|---|
| SAC 行业维度 | 21 维（含 global_market_sizing/global_competition/geopolitical_risk） | 无"区域渗透率错位/时光机"判断链；无"选股传导链"；无"非上市威胁判断" |
| 全球数据底座 | `global_leaders.json` 150 家龙头，但行业标签粗（"科技"16家） | **无传感器/仪器等细分行业的全球玩家映射**（无 Sensirion/Honeywell/Bosch） |
| 行业基线 | `industry_baselines.json` 335 细分行业（申万三级），有 PE/PB | 只有估值数据，无全球参照、无细分市场空间 |
| 可比框架 | `peer_matrix` 已接线，依赖 data_dict 行业标签 | 行业标签→全球可比公司映射缺失 |
| 市场规模 | `market_size` 用 TAM/SAM/SOM，国内口径为主 | 无"海外同细分渗透率/格局"参照；TAM 收缩假设无强制披露 |
| 质量门禁 | IronGate 34 检查（R54 增 3） | 无 TAM 自底向上校验；无原子事实溯源门禁；无区域错位检查 |
| 数据诚实 | FP2 零编造 + enrich source 强制 | enrich 置信度单标量（圆桌 P1-2 遗留），无四元组 |

**核心差距总结**：框架层（SAC 有全球维度）够了，但**判断链没落地**——`global_market_sizing` 是区域并列枚举而非"渗透率错位→中国路径参照"；`market_size` 是总量而非"细分×全球参照"；公司层缺"选股传导"和"非上市威胁"两个维度。

---

## 三、方法论升级方案

### 3.1 公司层：四层金字塔（升级 competitive/peer_benchmarking）

```
┌─────────────────────────────────────────────┐
│ 第一层 玩家分层 Landscape     全球+国内按技术路线/市场定位分群   5-8群（定性+份额）
│ 第二层 可比框架 Peers         代表性上市公司 5-8 家统一财务对比   定量表（营收/增速/PE/ROE）
│ 第三层 选股逻辑 Stock Picks   行业逻辑→2-3 受益标的+评级+目标价   传导链（为什么是它）
│ 第四层 非上市威胁 Unlisted    关键非上市玩家 3-5 家威胁度判断     战略动作→利润池影响（定性）
└─────────────────────────────────────────────┘
```

**升级要点**：
- **第三层（新增维度 `investable_standouts`）**：从行业判断推导选股——不是罗列上市公司，而是回答"如果看好行业，买谁、为什么是它而不是它"。证据链：行业逻辑 → 受益标的 → 财务验证 → 评级目标价
- **第四层（新增维度 `unlisted_players`）**：非上市关键玩家的**威胁度判断**（其产能/技术/客户布局如何改变格局），只做定性战略影响，**不假装有财务数据**（FP2 诚实边界）；有可信数据才给数字，否则显式标注置信度

### 3.2 全球视野：全球-区域-细分三段式（升级 global_market_sizing/market_size）

```
全球俯瞰（总量层）   全球 TAM + 增速 + 区域结构      → 行业β在哪、增长引擎在哪
区域透视（结构层）   北美/欧洲/亚太/中国各自规模/增速/渗透率/政策/客户 → 增长差异从哪来
                    关键判断: 区域渗透率错位（谁领先、差几年）+ 时光机（人均GDP映射）
细分赛道（赛道层）   按应用/技术/客户切分，每细分给全球+中国 → 钱往哪流（利润池）
                    关键判断: 细分×全球渗透率错位 / 全球玩家在每细分的位置 / 关税地缘差异
```

**升级要点**：
- `global_market_sizing` 从"区域并列"升级为**区域透视**：强制回答 (a) 各区域渗透率错位（谁领先、差几年）(b) 增长引擎在哪 (c) 中国路径参照（时光机逻辑）
- `market_size`（细分）增加**全球参照**：每个细分必须给"海外同细分的规模/渗透率/格局"作对照，不能只看中国

### 3.3 数据底座升级

1. **细分行业全球玩家映射**（新数据文件 `global_industry_players.json`）
   ```
   {"industry": "气体传感器",
    "players": [
      {"name": "Honeywell", "ticker": "HON", "country": "US", "segment": "工业安全",
       "role": "global_leader", "market_share_est": 22, "confidence": "E"},
      {"name": "盛思锐 Sensirion", "ticker": "SENSIRION.SW", "country": "CH", "segment": "环境监测",
       "role": "global_leader", "market_share_est": 10, "confidence": "E"},
      ...
    ]}
   ```
   → 让 `peer_matrix` 能按行业标签自动拉全球可比公司，替代 enrich 手补

2. **市场规模数据四元组**（升级 enrich schema / data_dict 标注）
   ```
   每个市场规模数字强制带: {source: "Gartner 2025", year: "2025",
                            scope: "全球", confidence_level: "L1官方/L2专业/L4估算"}
   ```
   → 缺任一即降级为估算区间（区间+灵敏度而非单点）

3. **区域渗透率参照库**（新数据或并入 `industry_penetration.json`）
   → 存"中国 vs 海外领先国"的渗透率错位数据，支撑时光机判断

### 3.4 质量护栏升级（IronGate 新增检查）

| 检查 | 类型 | 内容 |
|---|---|---|
| `tam_bottomup` | 硬规则 | TAM/SAM/SOM 必须自底向上推导（价格×数量）或披露收缩假设；禁"引一个机构数字就完事" |
| `regional_penetration_gap` | 硬规则 | 行业报告必须给出区域渗透率错位判断（中国 vs 海外领先国） |
| `stock_pick_chain` | 存在性 | 行业报告必须有选股传导链（行业判断→受益标的→为什么是它） |
| `unlisted_threat` | 存在性 | 行业报告必须有非上市关键玩家的威胁度判断 |
| `atomic_source_trace` | 溯源 | 每条带数字断言必须能在 collected_data/enrich 找到唯一 source（FActScore 思路） |

### 3.5 诚实边界（贯穿所有升级，FP2 底线）

- 非上市公司**不假装有财务数据**：无可信来源只做定性威胁判断，显式标"无权威数据"
- 市场规模数据不可得时用**区间+灵敏度**，禁用单点数字冒充精确
- 引用第三方机构数据（Gartner/IDC）必须带数据年份+覆盖范围+口径+方法局限

---

## 四、对 2hao 系统架构的影响

### 4.1 影响总览

| 模块 | 影响 | 变更量级 |
|---|---|---|
| `core/sacs/sac_industry_deep.yaml` | 新增 2 维（investable_standouts/unlisted_players）+ 升级 2 维（global_market_sizing/market_size） | 中（YAML 编辑 + section_writer prompt） |
| `core/data_basement.py` | 新增 loader：load_global_industry_players / load_regional_penetration | 低（新增 2 个 reader） |
| `data/global_industry_players.json` | 新数据文件（需 Marvis 补传感器/半导体/机器人等热门行业） | 中（数据采集） |
| `pipeline/iron_gate.py` | 新增 5 个检查（tam_bottomup/regional_penetration_gap/stock_pick_chain/unlisted_threat/atomic_source_trace） | 中 |
| `pipeline/section_writer.py` | 维度 prompt 注入新增数据源 + 选股/非上市威胁维度的写法约束 | 中 |
| `pipeline/consistency_engine.py` | 市场规模四元组归一化（来源/年份/口径） | 低 |
| `pipeline/data_enrichment.py` | enrich schema 升级：confidence 单标量 → 四元组 | 低（向后兼容） |
| `scripts/`（Marvis 数据补充） | 新数据采集指令（全球玩家映射/区域渗透率） | 中（Marvis 执行） |

### 4.2 分阶段落地路线图

**Phase 1（方法论骨架落地，2-3 天）**
- SAC 新增 2 维 + 升级 2 维（YAML + section_writer prompt）
- IronGate 新增 2 个存在性检查（stock_pick_chain/unlisted_threat）
- 回归测试锁定新维度写入 + Gate 校验

**Phase 2（数据底座支撑，需 Marvis 协作）**
- `global_industry_players.json` 初始覆盖（传感器/半导体/机器人/光伏等热门行业）
- data_basement 新增 loader + peer_matrix 消费升级
- IronGate 新增 tam_bottomup/regional_penetration_gap 检查

**Phase 3（深度溯源护栏，2-3 天）**
- 市场规模四元组 schema 升级（enrich + data_dict 标注）
- IronGate 新增 atomic_source_trace（FActScore 思路）
- 段落级引用注解（claim→source_id→span）——对齐 Deep Research/FinSight

### 4.3 架构风险与权衡

| 风险 | 缓解 |
|---|---|
| 维度增加导致 Gate 更难通过（新维度写不进） | 沿用 R53 修复：all_dims 取 SAC required + verify_coverage；新维度设 evidence_min=1-2 降低门槛 |
| 非上市玩家数据易滑向编造 | 强制"无权威数据只做定性+标置信度"，Gate 校验不假装有财务 |
| 全球玩家映射数据采集成本高 | Phase 2 只覆盖高频行业（Marvis 已有行业参数接口），长尾按需补 |
| 检查过多拖慢 Gate | 新检查全部确定性扫描（无 LLM），沿用 R15 并行执行 |

---

## 五、对标总结（2hao 升级后 vs 顶级机构）

| 维度 | 顶级机构 | 2hao 现状 | 2hao 升级后 |
|---|---|---|---|
| 报告结构 | 观点先行→全景→结构→供需→全球→竞争→公司→估值 | 因果链框架（异常信号→稀缺层→利润池→竞争→技术→空间→弹性→政策→定价） | 融合：保留因果链 + 补全球-区域-细分三段式 + 公司层四层金字塔 |
| 全球视野 | 全球→区域→子行业漏斗 | 区域并列枚举（缺判断链） | 渗透率错位 + 时光机 + 对手盘参照 |
| 公司层 | 细分逐段玩家态势 + 头部深档 + 非上市进份额表 | 玩家分层 + 可比框架（缺选股传导/非上市威胁） | 四层金字塔 |
| 数据诚实 | 一手调研 + 区间表达 + 方法披露 | enrich source 强制 + FP2 | + 四元组 + TAM 自底向上 + 原子溯源 |
| 市场规模 | 双轨交叉验证 + 三档情景 | TAM/SAM/SOM 国内口径 | + 全球参照 + 自底向上校验 |

---

## 六、待用户决策事项

1. **是否全量执行**：Phase 1（SAC + Gate 骨架）是否立即落地？
2. **全球玩家映射优先级**：首批覆盖哪些行业（传感器/半导体/机器人/光伏/锂电）？
3. **非上市维度口径**：`unlisted_players` 是否允许 LLM 在无数据时定性判断（建议允许，但必须标置信度）？
4. **原子溯源深度**：Phase 3 的段落级引用注解（claim→source→span）是否值得投入（对齐 Deep Research 标准）？

---

## 附：调研来源

- 高盛 GIR 组织架构 / 大摩 AlphaWise / 摩根大通报告结构（Financial Edge / Hebbia）
- 中金《大国产业链》/ 中信行研方法论 / 申万行研培训
- 麦肯锡利润池 / BCG 三四规则 / 贝恩市场定义
- Gartner Market Share / IDC / Frost&Sullivan / Euromonitor 方法论
- 学术：SCP、波特五力、GVC（Gereffi）、微笑曲线、Utterback-Abernathy、S曲线、Christensen、Smith 细分、Rogers/Bass、Uppsala、OLI、时光机
- AI：BloombergGPT、Deep Research API、FinSight、FinDVer、FActScore、FISCAL
