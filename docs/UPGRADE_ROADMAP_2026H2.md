# 二号分析师升级白皮书（2026 H2）

> 定位：基于四轮深度审计（代码级）+ 2026 年业界 SOTA 调研（STORM/Co-STORM、SCORE、
> AgentCPM-Report、ACE/MCE 技能进化、AgeMem/COS-PLAY 记忆协同、Balyasny/Versant/Rykos
> 金融智能体生产实践）的系统性升级路线。
> 原则：**不推倒重来——把已有资产接上业界已验证的闭环。**

---

## 一、先认清自己：2hao 手里的五张独特牌

多数开源深研智能体（GPT-Researcher、STORM 等）是"通用研究员"；2hao 经过四轮治理后，
手里有几张业内少见的牌。升级路线必须围绕放大这些牌，而不是追逐通用能力。

| # | 资产 | 现状 | 业界稀缺度 |
|---|------|------|-----------|
| 牌1 | **确定性验证栈** | IronGate 93 项检查 + 数值链自洽 + 估值四方勾稽 + 数据口径冲突检测 | ★★★★★ 开源研报智能体几乎为零数字验证 |
| 牌2 | **预测问责种子** | prediction_loop v2 + consensus_estimates.db(6.3万行) + revision_slope 刚打通 | ★★★★★ 无先例：研报结论的"事后对账"机制 |
| 牌3 | **机构方法论编码** | SAC 五类型维度矩阵 + 17 家风格模板 + methodology_rules.json + 24MB 券商研报语料 + MinerU 解析 | ★★★★ |
| 牌4 | **学习回路雏形** | FP5 反馈、reviewer_reputation、edit_learning、method_reflection_log、LearningLoop 挂钩 Gate 失败 | ★★★★ 全是散件，未成环 |
| 牌5 | **领域数据地基** | qlib_bin 行情 + financials.db + company_events + 北向/质押 + point-in-time 潜力 | ★★★ |

**核心判断：2hao 的终局形态不是"更好的报告生成器"，而是「带预测问责的研究操作系统」
（Research OS with Forecast Accountability）。这是 Balyasny 内部系统在做的事，
开源界没有对标物。**

---

## 二、六大升级轴（每轴：SOTA 对标 → 现状缺口 → 具体动作 → 验收标准）

### 轴 1｜研究深度：从"采集"到"多视角研究"（STORM 化）

**SOTA 对标**：STORM 的 pre-writing 阶段（视角发现→写手×专家模拟对话→大纲策展）；
SCORE 的"评估也要检索取证"；Co-STORM 的人机协同心智图。

**现状缺口**：critic_panel/Bold Call 辩论存在于**写作阶段**；但**研究阶段**仍是
DataCollectorV5 六段线性采集——没有问题驱动的补采循环、没有来源可信度分层。

**动作**：
1. 新增 `pipeline/research_planner.py` 节点（插在 enrich 之后 compute 之前）：
   - 输入 hypothesis + SAC 维度 → 生成"必答问题树"（每维 2-4 问）
   - 每问触发定向补采（tavily 深搜 / 研报语料检索 / db 查询），产出 `evidence_pool`
   - 冲突驱动追问：两个来源矛盾 → 自动生成仲裁查询（这正是 IronGate 数据口径
     检查的前移——把冲突消灭在写作之前而非之后）
2. 来源可信度分层落地：core/models.py 已有 EvidenceLevel 七级枚举但采集端未填——
   按"官方公告 > 一线券商 > 财经媒体 > 自媒体"打分，低置信来源只允许进"背景"不允许
   进"论据"
3. 研报语料 RAG 化：MinerU 解析技能已存在 → 对 24MB 券商 PDF 建 chunk+页码索引，
   研究阶段可引用自家知识库并给页级引用

**验收**：同一标的，research_planner 产出的 evidence_pool 中"高置信证据支撑率"≥60%；
IronGate 数据冲突类失败较基线下降 ≥50%（冲突前移的效果）。

### 轴 2｜写作范式：从"一次生成+修订"到"交错起草-深化"

**SOTA 对标**：AgentCPM-Report 的 interleaving drafting-deepening；
Anthropic Skills 的上下文按需加载。

**现状缺口**：维度分组并行写 → 编辑合并，组间信息不对称靠共享 prompt 前缀；
790 行方法已拆成注入器注册表，但注入内容仍是一次性全量拼接。

**动作**：
1. 组间"接力摘要"：每组写完生成 ≤200 字结构化交接卡（结论/数据/悬念），下一组
   prompt 注入前序卡片而非全文——治重复与口径漂移的结构性手段
2. 注入器分级加载：`INJECTORS` 已是注册表 → 加 `tier` 字段（core/extended/skeleton），
   配合 settings.skeleton_mode 实现三档上下文预算（对应 context rot 研究：长文可靠性
   在标称窗口 50% 处开始劣化，MECW 纪律）
3. Bold Call 辩论升级为"红蓝对抗+裁判记分"：bull/bear/judge 已有 → 加分数化裁决
   （论据强度×来源等级×证伪成本），分数写入 lineage 供后续追溯

**验收**：组间重复句（semantic_repeat）失败项下降；单篇 token 成本下降 ≥20%
（接力卡替代全文重注）。

### 轴 3｜自进化闭环：把四张学习牌串成一个环（最大战略赌注）

**SOTA 对标**：SCORE 评估器-求解器共同进化；COS-PLAY 决策体×技能库协同进化；
ACE/MCE 的上下文/技能自动演化；AgeMem 把记忆操作变成可学习的工具调用。

**现状缺口**：四张学习牌互不相连——Gate 失败进 LearningLoop 但无处消化；
prediction_loop 会记账但没人读；reviewer_reputation 只影响圆桌权重；
method_reflection_log 是死日志。

**动作（三步串环）**：
1. **预测账本激活**：写报告时 Bold Call/评级/EPS 区间自动写入 prediction_loop.record()
   （挂 e2e 出口节点）；到期由 sync 任务拉实际值 verify() → 回写偏差。
   **这是护城河的核心一环：让每一份研报的每个硬结论都可被事后追责。**
2. **方法论置信度**：backtest_summary 聚合出"某类判断（如'毛利率修复'逻辑）在
   某行业的历史命中分布" → 写作 prompt 注入先验提示（"该逻辑近 3 年在电池行业
   命中 2/5，请给出更强的证伪条件"）——把 FP5 从日志变成先验
3. **检查器技能库**：IronGate 93 项检查中 heuristic 部分参数化（阈值/模式存 YAML）；
   Gate 失败-修复轨迹（已有 repair circuit-break 记录）定期聚类 → 高频失败模式
   生成新检查规则草案（人审后入库）。即 COS-PLAY 的 skill-bank 思想应用于质量门禁

**验收**：6 个月后系统能回答"我过去半年给出的评级，方向准确率多少？哪类逻辑
拖了后腿？"——这个问题今天无法回答。

### 轴 4｜记忆与上下文工程（长程纪律）

**SOTA 对标**：context rot/MECW 纪律；Memanto/AgeMem 分型记忆；MemSkill span 级
记忆技能；记忆陈旧性（staleness）是公认开放难题。

**动作**：
1. 三层记忆落地：
   - 情景层：每次运行的 trace/lineage（已有 lineage json）归档可查
   - 语义层：industry_baselines/methodology_rules 加 **as_of 时间戳 + 陈旧度标记**
     （超期基线在 prompt 中显式降权："以下基线截至 X 月，仅供参考"）——直接回应
     记忆陈旧性难题
   - 程序层：把"怎么写好某类段落"的知识从散落 R 补丁迁入技能文件（skills/ 已有骨架）
2. 上下文预算器：REPORT_TOKEN_BUDGET 已有 → 细化到注入器级别配额
   （settings 注册 per-injector max_chars），超预算按 tier 优先级裁剪而非静默截断
3. 修订轮摘要保留推理链（context rot 研究要点：压缩要保留"为什么"，否则修订无法回溯）

**验收**：长报告（>1.5万字）后半部分的事实引用密度不低于前半（context rot 的
可测代理指标）；过期基线零静默使用。

### 轴 5｜可信度与合规（机构级门槛）

**SOTA 对标**：Captide/Balyasny 的机构要求——可审计、可溯源、私有部署；
instruction hierarchy + spotlighting（已做第一层）。

**动作**：
1. 引用双向绑定完成态：现在附录/脚注是导出期附加 → 升级为**写作期约束**
   （prompt 要求关键数字带 `[E#]` 占位，validate 节点校验 E# 与 evidence_pool
   对应关系，无主引用数字被 Gate 标记）——从"事后贴标签"到"生而可溯源"
2. 可复现性：run 时 pin 数据快照（db 视图+采集时间戳+模型版本入 lineage），
   支持一键复算任意历史报告的数值链
3. 红队常态化：Promptfoo 配置（node v24 已具备）覆盖三类攻击——目标价操纵注入、
   评级劫持、来源伪造；接入 CI 夜间跑
4. 私有化路径：敏感客户场景预留 Ollama/vLLM 本地档（provider 注册表已支持）

**验收**：任选历史报告，5 分钟内给出"这个数字从哪个来源哪一页来"的完整链路；
红队用例集通过率 100%。

### 轴 6｜评估与经济学

**SOTA 对标**：两工具策略（CI 门禁+平台观测）；cheap-judge 分层；evals 只有能阻断
才算数（已落地）；金融场景特有——**用投资结果校准评估**（Stanford AI analyst 论文
的 30 年回测思路的小型化）。

**动作**：
1. Golden 飞轮：每次"过 Gate + 人工微调"的真实报告自动成为 golden 候选（人工确认
   入库）→ 半年内 golden 集 3→30+
2. 双评竞技场：新旧版本管线同标的各出一篇，DeepEval pairwise 对比 + 人工抽检，
   版本升级需"不输旧版"证据
3. 成本 KPI：ObservabilityDB 已记录每次调用 → 出"单篇报告成本/token 分布"报表，
   结合 LiteLLM 迁移决策（或继续自研网关+加批量接口）
4. 模型路由经济学：抽取/格式类任务路由到廉价快速档（route_policy.py 骨架已在），
   综合/评审保持强档——预计省 30%+ 成本

---

## 三、工程债清单（随升级顺带偿还）

| 项 | 说明 | 时机 |
|---|---|---|
| coverage 35%→55% | chart_engine/dcf/report_gate/deepseek_client 四个⭐盲区 | 与轴 1/2 同步补测试 |
| F841/F401 存量债务 | noqa 已标注，按目录渐进真清理 | 每次触碰到某文件顺手做 |
| ruff 风格族恢复 | legacy 排除后按目录启用 I/N/UP | 每季一次 |
| route_policy/probabilistic_deep_check 等 13 个零直测模块 | 要么接线要么归档 | 轴 1 动到时一并处理 |
| generate_docs 的 generate_claude_md | 已退役保留，删除待宪法稳定 | Q4 |

---

## 四、路线图与优先级

### Phase A（未来 4-6 周）——把现有牌打出去
| 事项 | 所属轴 | 为什么最先 |
|---|---|---|
| Gate 收敛率专项（annotation_types/source_entity 实体化 prompt 打磨） | 轴2 | E2E 实测暴露的最高频失败，直接决定可用性 |
| prediction_loop 激活（出口节点挂钩） | 轴3 | 成本最低、护城河最高的一步 |
| evidence_pool + 来源可信度分层 | 轴1 | 后续一切研究深度的地基 |
| Promptfoo 红队夜间跑 | 轴5 | node 已就绪，纯配置工作 |

### Phase B（Q4）——形成环
| 事项 | 所属轴 |
|---|---|
| research_planner 节点上线 | 轴1 |
| 方法论置信度注入（预测账本→prompt 先验） | 轴3 |
| 引用双向绑定（[E#] 写作期约束） | 轴5 |
| Golden 飞轮 + 双评竞技场 | 轴6 |
| 注入器分级加载 + 上下文预算器 | 轴4/2 |

### Phase C（2027H1）——自进化与研究 OS
| 事项 | 所属轴 |
|---|---|
| 检查器技能库（失败轨迹→新规则草案） | 轴3 |
| 研报语料 RAG + 页级引用 | 轴1/5 |
| Co-STORM 式交互工作台 v2 | 轴1 |
| 多资产扩展（转债/行业比较） | 产品 |
| LiteLLM 迁移 or 自研网关终审 | 轴6 |

---

## 五、不做清单（同等重要）

1. **不自研基础模型/微调**——当前规模下 prompt/context 工程 ROI 远高于训练
2. **不引入 LangGraph/AutoGen 重写编排**——agent_graph + TypedContext 够用且已被
   验证；框架迁移是负资产
3. **不做"万能报告"**——五类型 SAC 边界守住，新类型走新增 YAML 而非改引擎
4. **不追多模态**——图表已确定性生成，图像理解暂无业务位
5. **不上向量库全家桶**——语料 RAG 用 SQLite+FTS5/embedding 轻方案起步，
   记忆系统自建三层，避免 Mem0/Letta 这类基础设施依赖绑架

---

## 六、一句话战略

**用确定性验证栈守住"不出错"，用预测问责账本积累"谁更准"，用自进化环路让系统
每跑一份报告就变得更准一点——这三件事叠加，就是任何通用深研智能体都复制不了
的护城河。**

---

## 附录：Phase A 执行纪要（2026-08-24）

**已落地**：
- Gate 收敛率专项：R97/R98/R99 双路径注入、dcf_sensitivity 对 earnings_notes
  转 advisory、修订靶向映射 +2 → 三轮 E2E 后 annotation_types / so_what_chain /
  source_entity / dcf 全部退出失败清单（score 0.85→0.88 稳定）
- 预测账本激活：prediction_extract + e2e 出口挂钩（实测提取 增持/318.5）
- 来源分层：source_tier 四层打分 + 池统计 + 高置信占比
- 红队：7 用例确定性回放全 PASS + promptfoo 脚手架（node v24 就绪，npm 源待配）
- SDD 闭环：PIPELINE_FACTS.md 实时生成 + sdd-facts-sync 钩子

**顺手挖出的真 bug（本轮 +4）**：
1. editor_merge 输出 token 上限静默丢尾部维度（SAC 覆盖 3/5 根因）→ 小总量
   确定性拼接 + 超阈分桶两段合并
2. StyleCompiler 注入泛化来源 与 source_entity 检查自相矛盾 → 改为不伪造来源
3. checkpoint attempt≥上限导致重跑砖化 → 上限保护
4. _normalize_indicator 裸子串把 revision_slope 归入 PE 簇 → 词边界匹配

**已知边界**：
- eval_gate 相对基线未按报告类型分层（earnings_notes 会被深度报告基线拒之
  flywheel 外）→ Phase B 待办：阈值分型
- Gate 收敛最后一公里：SAC 维度覆盖（segment_analysis/outlook_implication）
  属修订循环工艺，基础设施已就位

## 附录：Phase B 执行纪要（2026-08-25）

- M1 规则库 2/13→13/13（15 键），新 schema 含 applicability+failure_modes，
  回归测试 test_methodology_rules.py
- S1 指纹向量化 v1：core/style_fingerprint.py（8 维+距离）+ 构建器脚本；
  golden_deep 基准档案已生成（judgment_density 2.66 / number_density 12.95 /
  claim_first）
- S2 风格距离门禁：_check_style_distance warning 注册；实测 _gate_prev.md
  距离 0.20 PASS
- S3 接线：persona md + WritingDNA 进 _call_llm；get_dna 增加 gs/mck/bcg 别名
- 遗留#2：eval_gate 分型阈值上线，earnings_notes 飞轮入库端到端验证通过
- 额外真 bug：_call_llm 第二份硬编码柯力锚点（P0-5 残留副本）已清除
