# 方法论与风格指纹升级报告（2026 H2）

> 回答两个问题：**报告的方法论怎么升级**、**写作的风格指纹怎么升级**。
> 并把历次遗留工作整合为一张总表。
> 依据：代码级资产盘点（本文件 §0）+ 四轮工程审计 + 2026 SOTA 调研
> （STORM/SCORE/AgentCPM-Report、ACE 技能进化、Balyasny/Versant 金融智能体实践）。

---

## §0 现状地图：两层资产的真实底座

### 0.1 方法论层（三层结构，覆盖率惊人地低）

| 层 | 资产 | 实际状态 |
|---|---|---|
| 结构层 | SAC 五类型维度矩阵（20/26/26/5/12 维） | ✅ 活的，Gate 强制覆盖 |
| 规则层 | `data/methodology_rules.json` | ⚠️ **只有 2 个主题**（valuation 7 条 + industry_framework 1 条），而 `topic_map` 引用了 **13 个主题**（industry_lifecycle/profit_pool/competitive_forces/elasticity_analysis/signal_chain/policy_transmission/global_competition/technology_roadmap/capital_market/business_model/reference_class/unit_economics/exit_pathways）→ `mr_str` 注入对大多数类型**实际为空** |
| 知识层 | 20+ 框架注入器（bottleneck/reverse_dcf/catalyst/bull_bear/triangulation/geopolitical/thinking_models/xiao_jing/greenwald/kelly…） | ✅ 活的，但**无路由、无组合、无失效模式** |

### 0.2 风格指纹层（四类资产，三类未接线）

| 资产 | 内容 | 接线状态 |
|---|---|---|
| `core/style_profiles.py` STYLES | 6 家机构 × {writing: conclusion_first/judgment_density/max_sentence_chars/forbidden_terms/signature_terms, colors, typography} | ⚠️ 写作路径**零消费** |
| `utils/writing_dna.py` WritingDNA + apply_dna() | DNA 数据类 + 文本应用器 | ❌ **零消费者** |
| `prompts/system/*.md` 人格卡 | cicc/gs/mckinsey 等 system prompt | ❌ **零 Python 消费者** |
| StyleCompiler 确定性规则 + template_blacklist(10) + format_sheriff | 去 AI 化负面清单 | ✅ 活的 |
| 券商研报语料 24MB（数千 PDF） | 指纹学习的金矿 | ❌ 未用于风格层 |

**一句话诊断：方法论"有骨架缺血肉"，风格"有零件没引擎"。升级的主旋律是接线与扩容，
不是新建系统。**

---

## Part I 方法论升级（M1–M6）

### M1 规则库扩容工程：从 2/13 → 13/13

**做法**：
1. 以现有 schema 为准绳扩展字段：
   ```yaml
   rule_id: profit_pool_tech
   name: 利润池迁移判断
   source: MinerU解析-<券商名><日期>
   inputs: [细分市场规模, 毛利率, 竞争格局]
   rules: [{condition, stage, implication}]
   applicability:            # ← 新增
     industries: [半导体, 消费电子]
     cycle_stage: [成长期, 成熟期]
     data_requirements: [segment_revenue, gross_margin_by_segment]
   failure_modes:            # ← 新增（喂 Bold Call 证伪段）
     - "利润池迁移被误读为份额流失：需区分总量扩张与结构性迁移"
   ```
2. 批量抽取管线复用：`scripts/absorb_framework.py` / `absorb_knowledge_base.py`
   已有 argparse 入口 → 对 24MB 语料跑 MinerU → LLM 抽取候选规则 → **人工审校后入库**
   （规则层必须人审，这是方法论纪律）
3. 缺失主题的最小骨架先行：11 个缺失主题各建 3–5 条"保底规则"（来自 SAC 维度
   定义与既有评审文档），让 `mr_str` 不再空转；随后用语料持续增厚

**验收**：`python -c "from core.methodology_rules import serialize_rules_for_prompt; print(len(serialize_rules_for_prompt(['profit_pool'])))"` 对全部 13 主题非空；
每条规则含 applicability + ≥1 条 failure_modes。

### M2 方法论路由器：从"全量注入"到"按需组队"

**问题**：注入器目前按 report_type 全开/全关，行业差异靠 LLM 自觉。
**做法**：`config/methodology_router.yaml`

```yaml
电池行业:
  primary: [bottleneck, profit_pool]        # 主框架
  verify:  [triangulation, valuation_crosscheck]
  oppose:  [bull_bear_matrix]               # 反方框架
  dims_boost: [supply_chain, technology_roadmap]
医药行业:
  primary: [catalyst_timeline, reverse_dcf]
  ...
默认:
  primary: [methodology_rules(topics), harvard]
```

消费点：`build_injections()` 增加 `router_hint` 参数，由 research_planner/hypothesis
节点给出 `{industry, cycle_stage}` → router 决定本次激活集与顺序（接 Phase B 的
SKELETON_SKIP 机制泛化为 ROUTE_SKIP）。

**验收**：同一标的换行业，注入集合可解释地不同（快照测试）。

### M3 框架三件套制式化：主框架 × 验证框架 × 反方框架

**现状**：bottleneck（卡位）、valuation_crosscheck（互验）、bull_bear（反方）
各自为战。
**做法**：group prompt 的框架指令改为三槽位制式输出：

```
[主框架应用] 用<bottleneck五步>分析本标的：结论1/2/3
[交叉验证]   上述结论与<triangulation三法>一致性：一致/分歧点
[反方攻击]   若该结论错误，最可能的两个原因 + 可观察信号
```

**收益**：把"框架应用结论强制"从口号变成输出契约；同时天然产出 Bold Call 的
证伪条件素材（喂 prediction ledger 的 statement 质量）。

### M4 行业方法包（Playbooks）：先做三个示范

每个 playbook = YAML：维度权重覆盖（SAC dims 哪些加重/哪些豁免）+ 行业专属
指标红线（如电池：碳酸锂价差、产能利用率阈值）+ 典型证伪条件库 + 历史失败案例
（引用 docs/reports 评审实录）。先做：**动力电池 / 半导体 / 创新药**。
落 `config/playbooks/<industry>.yaml`，由 M2 路由器消费。

**验收**：playbook 行业的 Gate 失败 Top10 中"行业错配类"（如对创新药要求 DCF
矩阵）归零。

### M5 框架胜率榜：方法论层的预测问责

prediction ledger 已活。补两件事：
1. 打标通道：M3 三件套输出的框架应用卡自带 `[FW:<name>]` 标记 →
   prediction_extract 把标记带入 statement
2. 季度报表 `scripts/framework_scoreboard.py`：按 framework 聚合 ±10% 命中率、
   平均偏差、样本数 → 低胜率框架自动进"观察名单"（prompt 注入时附警告，
   连续两季不改善则默认关闭）

**验收**：报表能回答"过去一季 bottleneck 卡位判断在电池行业的兑现率"。

### M6 伪框架黑名单：反方法论机制

template_blacklist（现 10 条）扩容为双清单：
- 句式黑名单（已有）：AI 腔、模板腔
- **伪框架黑名单（新增）**：听起来专业实则不可证伪的话术模式
  （例："长期看好""竞争壁垒深厚""护城河稳固"无量化支撑即违规）——
  来源=圆桌评审否决案例月度提炼，进 `data/anti_patterns.yaml`，
  由 format_sheriff 同款机制拦截

---

## Part II 风格指纹升级（S1–S7）

### S1 指纹向量化 v1：让"像不像中金"变成可测量

**做法**：`core/style_fingerprint.py` —— 对文本计算 8 维可解释特征向量：

```python
Fingerprint = {
  "sent_len_p50": …, "sent_len_p90": …,       # 句长分布
  "judgment_density": …,                       # 判断动词/千字（我们判断/预计/…）
  "number_density": …,                         # 数字+单位/千字
  "connective_spectrum": {因此:…, 然而:…, 但:…},# 连接词频谱 top10 归一
  "heading_depth_hist": {h1:…, h2:…, h3:…},    # 标题层级分布
  "table_per_kchar": …,                        # 表格频率
  "first_sentence_pattern": "claim_first|data_first|question",
  "signature_hit_ratio": …,                    # profile.signature_terms 命中比
}
```

- `extract(text) -> vec`（纯 re+statistics，零依赖）
- `distance(a, b) -> float`（数值维分位偏差 + 类目维杰卡德，加权合成）
- 冷启动：对语料库中每家券商抽 3–5 篇代表作 → `fingerprints/<inst>.json`
  （人工确认代表篇）；与现 style_profiles.writing 六字段合并为完整档案

### S2 风格距离门禁（warning 级）

新 Gate warning 检查 `_check_style_distance`：输出向量 vs 目标机构指纹距离
超阈 → 告警列出**偏离最大的 3 个维度及建议**（如"句长 p90 超标 60%，长句过多"）。
**红线：只比形式特征，不比内容词——防止教模型抄措辞导致实质性抄袭。**

### S3 把闲置引擎接上：WritingDNA / style_profiles 进写作链

- `apply_dna()` 已存在但零消费 → 在 `_editor_merge` 之后、`_inject_report_header`
  之前插入 `apply_dna(text, get_dna(style_id))` 作为**确定性后处理**
  （DNA 字段与 S1 向量对齐后驱动微调：句子切分、连接词替换、signature 补充）
- persona md（prompts/system）接入：写作 system prompt = 基础角色 + persona md 全文
  （一次性接线，`_load_persona(style_id)` 带 fallback）

**验收**：切换 style=cicc/gs，S1 向量距离单调靠近对应指纹（同输入对比实验）。

### S4 节奏模板：章节级写作节奏指令

顶级报告不是均匀腔调。按 segment 类型注入节奏指令表：

| 段类型 | 节奏指令 |
|---|---|
| 决策门/Bold Call | 短句高密度：每句 ≤30 字，三连排比收束 |
| 财务验证 | 数字链式：每判断必带分子分母，表格优先 |
| 竞争格局 | 点名制：每段至少 N 个具名玩家+份额数字 |
| 风险/证伪 | 条件句式：'若 X 则 Y，可观察信号 Z' |

落 `config/rhythm_patterns.yaml`，由 group prompt 按 dims→segment 类型拼装。

### S5 双声部分离

分析师声部（我们判断/我们预计…）与编辑声部（风险提示/口径说明/数据缺口）
混排是指纹模糊的另一根因。规则化：编辑声部只允许出现在固定容器
（章末『口径与数据说明』块），由确定性后处理搬运归位。

### S6 指纹进化环

golden flywheel 入库时同步做两件事：
1. 该篇 fingerprint 追加进 `<inst>.json` 的滚动样本池（P50 更新）
2. 人工微调 diff（提交记录）标注为 style_delta，季度性回写 profile
   （judgment_density 目标值等）

---

## Part III 遗留工作整合总表（全部归位）

| # | 遗留项 | 来源 | 归属 | 阶段 |
|---|---|---|---|---|
| 1 | research_planner 完整节点（问题树+冲突驱动补采） | 白皮书轴1 | 独立专项（最大单项） | P-B1 |
| 2 | eval_gate 分型阈值（earnings_notes 入库被深度基线拒） | 本轮实测 | 工程轴：thresholds 加 per-type 段 | P-B1 |
| 3 | Gate 收敛最后一公里（SAC 覆盖 PASS 验证） | E2E 实测 | 工艺轮：跑一轮验证 | P-B1 |
| 4 | Promptfoo npm 镜像配置 + UI 试运行 | node v24 已备 | 工程轴 | P-B2 |
| 5 | coverage 35%→55%（四⭐盲区） | 审计 | 与 M1/S1 开发同步补测 | 持续 |
| 6 | route_policy/probabilistic_deep_check 等 13 个零直测模块处置 | 审计 | M2 路由器动到时一并裁决（接线或归档） | P-B2 |
| 7 | F841/F401 渐进清理、ruff I/N/UP 目录级恢复 | lint 零违基线 | 每次触碰顺手 | 持续 |
| 8 | editor_merge 分桶合并的大篇幅真实验证（industry_deep 1.5 万字） | 本轮新增能力 | 工艺轮 | P-B2 |
| 9 | claim 内联脚注转默认开 | Phase A | 产品决策：交付形态确认后 | P-C |
| 10 | LiteLLM 迁移终审 vs 自研网关 | 白皮书轴6 | 成本 KPI 攒 1 个月数据后决策 | P-C |

---

## Part IV 实施顺序（价值×成本矩阵）

```
            高价值
             │
   M5胜率榜  │  M1规则库扩容   S1指纹向量化
   (账本已通)│  M2路由器      S3闲置引擎接线
             │  M4行业包×3
   ──────────┼─────────────────── 高成本
   M6伪框架  │  S2距离门禁     S4节奏模板
   快赢区    │  S5双声部      S6进化环
             │
            低成本
```

**三阶段**：
- **P-B1（两周内）**：M1 最小骨架（11 主题保底规则）＋ S1 extractor v1 ＋
  S3 persona/DNA 接线 ＋ 遗留#2/#3
- **P-B2（Q4 上旬）**：M2 路由器 ＋ M4 三个 playbooks ＋ S2 距离门禁 ＋
  M5 打标通道 ＋ 遗留#4/#6/#8
- **P-C（2027H1）**：M5 完整胜率榜 ＋ S4/S5/S6 ＋ research_planner ＋ 遗留#9/#10

**北极星指标**：
1. 方法论层：13/13 主题非空、框架胜率榜可出报表
2. 风格层：同输入下输出向量到目标机构指纹的距离较基线下降 ≥40%
3. 综合：earnings_notes Gate 首过率 ≥50%、industry_deep 三轮收敛率 ≥80%

---

## 一句话战略

**方法论升级 = 让 20 个框架学会"排队上车"（路由）、互相"对答案"（三件套）、
记住自己"考了多少分"（胜率榜）；风格升级 = 把散落的指纹零件组装成
"能量尺的引擎"（向量化+距离门禁+闲置接线），并用自家语料冷启动、
用真实微调热更新。方法论决定说得对不对，风格决定像不像"那个人"说的。**
