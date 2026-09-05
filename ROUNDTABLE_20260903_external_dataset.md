# 圆桌纪要 · 外部数据集集成评估与推进路线

**日期**：2026-09-03
**议题**：`reports/2026-09-03_external_dataset_integration.md`（外部数据集集成工作报告）评审
**作者**：ultrathink 审计 + 圆桌讨论（评测/数值可靠/预测校准/金融多智能体/报告引用/可靠执行 六视角）
**定位**：对本次"数据集成"工作的**独立质量评审**与**后续推进建议**。先核实、再判断、后给路线。
**一句话结论**：这份工作有一个**良性的名字**（外部数据整合）和一个**危险的用途**（在旧模型输出的噪声上做 SFT 训练 + 用生成内容做 exemplar 循环 + 对自我生成输出做 golden 基准验证）。**完整路径已进入自举区。** 而其中一件"彩排"动作已把 mock 数据写进了生产预测库——这是数据完整性事故，须先处置。

---

## 〇、事实核查（先说哪些是真的）

报告的**结构性事实全部为真**（git 与磁盘核实）：

| 声称 | 实测 | 判定 |
|---|---|---|
| 12 个脚本（assess/convert/build_exemplar/prepare_sft/sft_train/irongate_v2/context_enrichment/integrate_pipeline/verify 等） | 全部存在，1.5KB-11KB | ✅ |
| 数据目录 | external_datasets 1.9G（FinRpt 597M / AlphaFin 425M / CFQA 11M）、exemplar_bank 478M、sft_training 537M | ✅ |
| 管线三处集成 | section_writer L1590 `_build_exemplar_injection`、iron_gate L720 `_run_irongate_v2_checks`、data_collector L102 `_enrich_with_context`——均真实存在 | ✅ 但见 P4 |
| exemplar_retriever | 有 `retrieve()`（L59）+ diversity 两段检索（L120 "First pass: one per sector"） | ✅ 非 stub |
| SFT 数据 | `sft_train.jsonl` 107,437 行 | ✅ |
| golden_numeric | `truth_set.json` 30 条（target_price/pe_ratio/revenue，含 canonical/allow_values/tolerance） | ✅ 全仓唯一真值资产 |
| MinerU 转换 | reports/ 内进度报告；13,562 份中 7,914 完成（58.4%） | ✅ 但与自举相关（P3） |
| 管线三处 imports | 均为 **sys.path 运行时注入**（section_writer L1594-95、iron_gate L724-25、data_collector L106-07） | ✅ 但见 P4 |

---

## 一、六个深层问题（按严重度）

### 🔴 P0'（新发现，最优先）：mock 数据已污染生产预测库

`412c464`（P0-6 MC 彩排）把 **20 条 mock 预测写进了 `core/data/forward_picks/track_record.json`**——预测系统的事实源。

实测现状：

```
total: 2062（原 2028 + mock 20 + 后续新增）
outcome: {pending: 2042, correct: 16, incorrect: 4}
```

问题：
1. **语义污染**：mock 用 `correct`/`incorrect`（而非契约的 `hit`/`miss`/`partial`）——任何按契约过滤的统计会漏掉它们，但**任何不过滤的统计（cohort/dashboard/significance/归因）会把这 20 条当成 20 条真实到期预测**。dashboard `--significance` 一跑，MC 就把 mock 的"80% 命中"当成系统真实业绩。
2. **永久残留**：一旦计入月度报告/校准曲线，这 20 条 mock 永远污染命中率、alpha、p 值——除非显式剔除。
3. **违反数据纪律**：mock 演练必须走**隔离库**（`data/mock_track_record.json` 或 `--mock-db`），绝不能进生产 track_record。

> 处置（P0，见路线 R0）：从生产库剥离 mock（按 `id`/`bold_call` 标记过滤），迁入隔离 mock 库；对已计入的统计**声明作废**；给 `track_record` 写路径加 `source ∈ {pipeline, backfill, mock}` 校验，mock 只允许写隔离库。

### 🔴 P1：这些"外部数据集"没有真值——被当 golden 用的是"风格语料"

被下载的内容本质：
- **FinRpt（6,825 篇）**：输入=结构化财务数据+新闻，输出=分析师风格分析——但东方财富版"研报"本身由 **LLM 从半结构化数据生成**，带模板痕迹；
- **AlphaFin（162K 条）**：instruction-input-output 三元组，LLM 合成；
- **CFQA（10K 条）**：年报 QA，LLM 生成。

这些对**风格吸收**有价值，但对"Gold 标准"意义上的质量评测**没有真值**。更危险的是 exemplar 机制（报告 §2.4）：**把 LLM 生成的内容当权威样例喂回给模型**——递归自引用。这与 AUDIT_20260901 早已诊断的"没有独立验证层，所有 score 都是自证"是同一病的变体；golden 必须是**独立真值**（真实分析师标注/确定性计算结果），不能是自产语料。

而"质量均分 9.88/10"来自 `compute_quality_score()`——**基于长度的启发式打分**（150-350 字为佳、JSON 结构加分），却以"质量分"呈现。这是假精度：启发式自评 ≠ 风格质量 ≠ 分析质量。

### 🔴 P2：自举（模型自噬）是最大隐性风险

最直接的风险链条：**拿 FinRpt/报告输出做 SFT 训练 → 把模型自己的输出（或其 LLM 模板的近亲）导入训练分布 → 与测试记录已在合成管线输出上训练叠加 → 自举坍缩**。

特征完全吻合已知的"model collapse / 自我吞噬"症状：
- 输出多样性收窄（模板回声）；
- 罕见事件/尾部观点消失；
- **一旦管线生成规则改变，训练过的模型会对抗性抵抗重训练**（旧规格焊死在权重里）。

2hao 自己的宪法/方法论文件里早有同款禁令："绝不能把 LLM 生成的文本当权威来源喂回模型"。SFT 训练数据（107K 条）**全部来自模型生成源**，无一条来自"已过 Gate 的真实交付 + 人工复核"。

### 🔴 P3：SFT 的成本效益极差且无法验证

- **成本**：FinRpt 覆盖 2024-09-03 ~ 11-05 **单季窗口**、A 股 SZ/SS 代码、6,825 只股票——对未见行业泛化差（报告自列风险 1）；
- **收益**：Qwen2.5-7B + LoRA/QLoRA 微调**大概率低于 base**——7B 在投研任务上 SFT 常把通用能力洗掉，换来窄任务"像"，而且是在**未经微调的旧规则数据**上训练；
- **可验证性**：沙箱无 GPU（报告说 24GB VRAM，需真实训练机）——依赖装不上、跑不起来，**无法验证**。P0"运行 SFT 训练 1-2 天"在沙箱是空头承诺。

### 🟡 P4：集成全是"运行时 sys.path 注入 + 静默降级"

三处集成都是执行期 `sys.path.insert + from xxx import`（把 scripts/ 塞进 path）。意味着：
- **缺依赖即静默降级**：与 ArgumentEngine 同款反模式（`try: from ... except: 降级`）——可选集成只占成本、不占行为；
- 核心路径被拉低到"无 exemplar / 无 v2 / 无 enrichment"也能跑，而这些模块**从未冒烟验证**；
- 对 Gate 分数的影响：v2 检查结果在 `iron_gate._run_irongate_v2_checks` 转成 checks 追加——若 v2 import 失败，Gate 安静少一层。

### 🟡 P5：Exemplar 注入 = 复制未知旧瑕疵 + 上下文爆炸 + 注入面

- **注入物未清洗**：FinRpt/AlphaFin 是抓取自网络的语料，含幻觉数字、虚假引用、非机构句法——**原样注入 prompt** 会把旧瑕疵当"好榜样"教给写作层；
- **体积**：`exemplar_index.jsonl` 421MB / 6,825 条 exemplar，每条携带完整 9-section JSON——即使 diversity 检索取 2-3 条，单次 section 写作的上下文/成本也显著上升，且**无信息压缩**；
- **注入面**：外部语料直接进 prompt = 提示注入/输出走私面（与 AUDIT 已识别的 crawl4ai 注入面同类），需要 spotlighting/delimiting 纵深。

### 🟡 P6：MinerU 58h 投入用错了目的

13,562 份内部报告仓库转 .md（58.4%，剩 5,647 份 ≈ 2.4 天）——若用途是**风格吸收训练**，又是自举（见 P2）。真正该转的是**已过 Gate 的验证报告**（少量、可证明），而非 53% 仍在转换中的原始池。2 份 decision_memo 永久失败（PDF 渲染超时）应在清单里显式标注，而非"58.4%"带过。

---

## 二、对报告"下一步建议"的逐条重判

| 报告建议 | 优先级 | 重判 | 理由 |
|---|---|---|---|
| P0 运行 SFT 训练 | P0 | **⬇ 降为 DROP/搁置** | 沙箱无 GPU 无法验证；自举风险（P2）；大概率低于 base（P3） |
| P1 验证 pipeline 集成 | P1 | **⬆ 升为 P0** | 三处 sys.path 注入从未冒烟；先验证"装上没接"再谈训练 |
| P2 补充 sector 分类 | P2 | 保持 P2 | 低风险低收益，可做 |
| P3 DPO 偏好对齐 | P3 | **⬆ 升为 P1（若做 SFT 的前提）** | 唯一"非自举"的训练数据源（真实分析师偏好），但需真实标注者；**不可用 LLM 生成偏好对** |
| P4 DISC-FinLLM 完整版 | P4 | 保持 P4 | 认证门槛高，收益未知 |

---

## 三、推进路线（按优先级重排）

### R0（今天，P0）：数据完整性事故处置

1. 从 `track_record.json` 剥离 20 条 mock（按 `source=mock`/`id` 前缀/bold_call 标记过滤），迁移到 `data/mock_track_record.json`（隔离库）；
2. 生产库恢复 `pending` 2028+ 真实条目的干净基线；
3. `core/tools/track_record.py` 写路径加 `source ∈ {pipeline, backfill, mock}` 校验：mock → 只写隔离库；
4. 对 mock 彩排已"计入"的任何统计（如有 dashboard 输出）**声明作废**；
5. 守护测试 `test_track_record_isolation.py`：mock 写生产库 → 拒绝；真实预测写 mock 库 → 拒绝。

**验收**：生产 track_record 无 mock；`dashboard` 对生产库不再显示 mock 命中率。

### R1（本周）：管线集成真验证（P4/P5 落地）

1. **e2e 冒烟**：跑一次完整管线（真实标的），确认 exemplar/v2/enrichment 三段**真的执行**（日志出现 `[EXEMPLAR]`/`[V2]`/`[ENRICH]` 标记），而非静默降级；
2. **失败显式化**：可选依赖缺失 → 显式 ERROR + 报告标注"降级运行"，不允许静默；
3. **exemplar 清洗器**：注入前过滤（来源白名单/敏感扫描/占位符/长度），外部语料只进 Tier-2 参考，不进 Tier-1 权威；
4. **注入体积控制**：exemplar 检索结果压缩为"结论要点 + 结构模板"，非整篇 JSON；
5. 上述改动配守护测试（mock 外部模块缺失/注入内容含敏感词 → 拦截）。

### R2（10-31 前主线不变）：真价 → 真验证

按 WORK_EXECUTION_PLAN_20260903 继续：price_feeder 真价（已完成 core 层，需 akshare 网络验证）→ update_outcomes 真实取价 → 到期 cohort 真验证 → MC 只跑真实 outcome。**golden_numeric（30 条，真值锚）是唯一可信评测资产**，扩到 100+ 条并进 CI。

### R3（可选探索，1 天）：FinRpt 只做风格吸收的 A/B

若想用 FinRpt：**不做 SFT**，只做**风格注入 A/B**——同标的同数据，开/关 exemplar 注入，对比 Gate 分与 golden_numeric 命中。无显著提升则关闭该路径。**任何把模型生成内容用于训练的决策，都需要先过"自举检查"**：数据是否含模型自身/近亲输出？是 → 需人工真值稀释或放弃。

### R4（季度，若做训练）：非自举训练路线

1. **数据源**：只允许 ①已过 Gate 的真实交付报告（人工抽检）②真实分析师标注的偏好对（不可 LLM 生成）③golden_numeric 数值真值；
2. **训练前基线**：先跑 base 模型的 golden_numeric 得分，SFT 后必须**不低于 base**（防"训练了个寂寞/更差"）；
3. **评测独立**：SFT 模型过同一套 golden_numeric + 外部 judge（异家族），禁止用训练分布自评；
4. 训练环境在真实 GPU 机，沙箱只做数据准备与评测。

---

## 四、反模式清单（本次评审沉淀）

1. **mock 演练绝不进生产数据源**——隔离库是底线；
2. **不把模型生成内容当权威**（golden/训练/exemplar 都适用）——自举是慢性死亡；
3. **启发式自评分不冒充质量分**——9.88/10 这类数字要有真实依据；
4. **可选依赖必须显式失败**——sys.path 注入 + 静默降级 = 装了没接；
5. **训练前必测 base 基线**——SFT 可能低于 base，不许"训了就当进步"；
6. **外部语料进 prompt 前必清洗**——注入面与旧瑕疵复制；
7. **数字真值锚（golden_numeric）才是唯一可信评测**——风格相似度只算参考。

---

## 五、结论

> 本次"外部数据集集成"的**工程动作真实且量大**（12 脚本 + 4.2GB 数据 + 三处集成 + golden_numeric 30 条），但**方向判断需要纠偏**：最有价值的部分恰恰是最不起眼的 `golden_numeric`（真值锚），而报告自封的 P0"运行 SFT 训练"是风险最高、收益最低、最无法验证的一项。加上 mock 污染生产库这起数据事故，**本阶段的正确动作不是"继续往里加数据/开始训练"，而是"隔离 mock、验证集成、守住真值锚、让真价闭环"**。等 10-31 真验证跑出第一批真实 outcome，再决定是否值得为投研微调——那时训练数据的"真值稀释"才有来源。

---

## 附：涉及文件/提交

- 评审对象：`reports/2026-09-03_external_dataset_integration.md`
- 数据事故：commit `412c464`（mock 写入 track_record.json）
- 真值资产：`benchmark/golden_numeric/truth_set.json`（30 条）；commit `b580782` 扩至 30 条
- 集成点：`pipeline/section_writer.py:1590` / `pipeline/iron_gate.py:720` / `pipeline/data_collector.py:102`
- 相关计划：`WORK_EXECUTION_PLAN_20260903.md`（P0 收尾）、`MASTER_PLAN_20260902.md`、`ULTRA_OPTIMIZATION_ROADMAP_20260902.md`
