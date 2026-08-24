# Marvis Skills 深度分析 —— 对2号分析师的启发

> 评估日期：2026-07-30
> 评估对象：D:\Marvis\skills 下5个项目

---

## 一、5个项目的核心设计哲学对比

### 1. genli-market-research-skills（清华大学李根）

**定位**：投资分析师端到端研究工作流 skill

**核心设计**：
- 三档模式（light/medium/heavy），按需适配
- 三件套体系：SKILL.md（入口）→ workflow.md（流程纪律）→ chart_template.py + report_style_spec.md（视觉规范）
- Quarto QMD → PDF/Word/HTML 多输出
- 3个 sign-off 硬检查点（outline / draft / final）
- FT chart-doctor 视觉哲学：双字号、去装饰、单强调色、标题即论点
- 精确像素级图表排版（FIG_W=6.69 inch、2000px 上限）

**最大的两个亮点**：
1. **mode 分层**——用户用一句话选档，系统自动适配深度，而不是一刀切
2. **视觉规范即契约**——图表规范不是写在提示词里，而是写在一个`report_style_spec.md`文件里，agent 和用户共同遵守

### 2. mckinsey-research

**定位**：麦肯锡级市场研究（12个专项分析）

**核心设计**：
- 12 个独立 prompts，按依赖分批并行执行
- 4个批次（Batch 1-4），子 agent 并行，交付物合成
- Adaptive Stage Logic（根据公司阶段自动跳过/精简某些分析）
- Diamond Gate 检查点
- HTML 报告输出

**最大亮点**：
1. **并行子 agent 架构**——TAM、竞争、用户画像、趋势同时跑，互不阻塞
2. **自适应阶段逻辑**——idea/startup/growth/mature 不同阶段跳过不必要分析

### 3. zircote-sigint

**定位**：最接近企业级生产环境的 skill 系统（16个子 skill）

**核心设计**：
- 每个子 skill 独立：SKILL.md + evals + examples + references
- 强制框架（Porter 5 Forces、竞争者矩阵必须完整输出评级）
- 哑元客户应对逻辑（当用户不提供上下文时不编造数据，而是引导）
- eval 驱动开发（每个 skill 有测试用例）

**最大亮点**：
1. **eval 体系**——每个 skill 有可衡量的测试用例
2. **框架强制执行**——不是让它"尽力而为"，而是明确要求必须输出哪些框架

### 4. wshuyi-deep-research

**定位**：8 步系统化调研方法论

**核心设计**：
- 问题类型分类（概念对比/决策支持/趋势分析/问题诊断/知识梳理）
- 时效敏感性判断（🔴🟠🟡🟢 四级，直接控制资料窗口）
- 资料分层（L1 官方 > L2 博客 > L3 媒体 > L4 社区）
- 事实卡片（区分「官方说的」和「我推测的」）
- 独立 Agent 校验（Step 6.5）
- 中间产物全部持久化到文件

**最大亮点**：
1. **时效敏感度引擎**——AI 领域 3 个月过期，算法原理无限制——不同领域不同策略
2. **独立 Agent 校验**——不是自己写自己审，而是第二个 agent 专门做事实核查
3. **事实卡片系统**——每条结论追溯到来源，区分事实和推断

### 5. last30days

**定位**：多平台社交媒体监控引擎（15+源）

**核心设计**：
- Doctor 健康检查：运行前诊断配置健康，运行后 postmortem 分析故障
- Stale-clone 自检：启动时先检查自己是不是过期版本
- Source status 追踪：每个数据源的状态（partial/rate-limited/auth-failed/timeout）
- Judge Agent 合成：多个数据源→一个综合判断
- 版本 3.18.4，严肃的 CI/CD 管线

**最大亮点**：
1. **Doctor 健康检查**——运行前做预检，运行后做复盘
2. **Source status 透明**——不隐藏数据源的问题，而是明确标注"partial coverage"
3. **Community voice 嵌入**——不只是提取数据，而是把真实用户评论嵌入报告

---

## 二、与2号分析师的对比矩阵

| 维度 | 2号分析师 | genli | mckinsey | zircote | wshuyi | last30days |
|------|-----------|-------|----------|---------|--------|------------|
| **模式分层** | 无 | 三档 mode | 四阶段自适应 | 无 | 问题类型分类 | 有 |
| **图表规范** | 有但弱 | FT标准 | 无 | 无 | 无 | 无 |
| **子 agent 并行** | 无 | 无 | 有(12 agent) | 有 | 有(校验agent) | 有 |
| **eval 体系** | 无 | 无 | 无 | 有 | 无 | 有 |
| **健康检查** | IronGate(后检) | sign-off(后检) | Diamond Gate | 无 | 独立校验 | Doctor(预检+后检) |
| **数据源透明** | 弱 | 脚注引用 | 标注假设 | 哑元引导 | L1-L4分层 | source_status |
| **中间产物保存** | 无 | 有 | 有 | 有 | 有(强) | 有 |
| **框架强制执行** | 软(靠prompt) | 硬(写进workflow) | 硬(12分析) | 硬(强制框架) | 软 | 硬 |
| **多输出格式** | DOCX | PDF+Word+HTML | HTML | - | MD | MD |
| **版本管理** | 无 | 无 | 无 | CHANGELOG.md | 无 | v3.18.4+CI/CD |

---

## 三、核心发现：2号分析师的6个结构性落差

### 落差1：没有模式分层——一次运行策略无法适配不同需求

genli 的 light/medium/heavy 三档模式是**关键设计决策**。不是所有报告都需要 30 页深度分析。

**2号分析师的问题**：所有报告都走同样的管线、同样的深度、同样的图表数量。对"快速判断"场景太重，对"深度旗舰"场景可能深度不够。

**启发**：引入 `mode` 参数（quick/standard/flagship），不同 mode 调用不同管线、不同图表数、不同输出格式。

### 落差2：没有子 agent 并行——所有分析串行，效率低

mckinsey-research 的 12 个子 agent 并行执行，Batch 1（TAM+竞争+画像+趋势）同时跑，互不阻塞。而 2 号分析师的写作→评分→修正是串行的。

**启发**：数据采集、竞争分析、财务分析可以并行。引入 sub-agent 池。

### 落差3：图表规范不够硬——视觉质量取决于 LLM 的临场发挥

genli 的 `report_style_spec.md` + `chart_template.py` 是**接口契约**——不是"尽量做好看"，而是"必须遵守这个规范"。而 2 号分析师的图表是一行行 Python matplotlib 代码，每次都从零写。

**启发**：采用 genli 的 `chart_template.py` 模式，固定 FIG_W、字号、调色板、输出格式。

### 落差4：没有 eval 体系——每次修复后无法确认质量是否真的提升

zircote 每个子 skill 都有 `evals/evals.json`。而 2 号分析师的 IronGate 是事后检查，不是预定义测试用例。

**启发**：为每个分析模块建立 eval 测试集（比如图表类型覆盖率、数据源标注率、分析框架完整度）。

### 落差5：数据源不透明——不清楚报告中的数字到底来自哪里

wshuyi 的 L1-L4 分层和 last30days 的 source_status 透明化是2号分析师最缺乏的。

**2号分析师的问题**：报告中出现"2024年中国市场规模12亿美元"，但阅读者无法知道这个数字是 Tavily 搜索来的，还是 LLM 编造的。

**启发**：每个数据点标注来源层级和置信度。

### 落差6：没有版本管理和 CI/CD——每次修改不可追溯

对比 last30days 的 v3.18.4 + CI/CD 管线，2 号分析师没有任何版本管理和自动化测试。

---

## 四、最大启发：genli 的三件套设计 + zircote 的子 skill 架构

### genli 的三件套 —— 最值得借鉴的设计模式

```
SKILL.md（入口+模式选择）
  ├── workflows/（流程定义：light/medium/heavy 各一套）
  ├── references/report_style_spec.md（视觉规范）
  └── scripts/chart_template.py（图表实现——唯一的绘图代码）
```

核心优势：
1. **关注点分离**——流程在 workflow 里，视觉在 spec 里，实现代码在 script 里
2. **规范即契约**——`report_style_spec.md` 是 agent 和用户的共同约定
3. **一次实现多次复用**——`chart_template.py` 对所有图表生效

### zircote 的子 skill 架构 —— 适合模块化扩展

```
skills/
  ├── competitive-analysis/（SKILL.md + evals + examples + references）
  ├── financial-analysis/
  ├── market-sizing/
  ├── trend-analysis/
  └── ...
```

每个子 skill 独立并可测试。

---

## 五、对2号分析师的改造启发

### 短期可以学到的（1-2天）

1. **用genli的chart_template.py替换2号分析师的chart_pipeline.py**——统一FIG_W、调色板、输出格式
2. **添加source metadata**——每个data_point附带来源URL和置信度
3. **引入mode分层**——quick/standard/flagship

### 中期可以学的（1周）

4. **子skill架构**——把行业分析、公司分析、财务分析拆成独立skill
5. **并行子agent**——数据采集、竞争分析、财务计算并行执行
6. **eval体系**——每个分析模块配备测试用例

### 长期可以学的（1月+）

7. **独立校验agent**——wshuyi的Step 6.5，第二个agent做事实核查
8. **Doctor健康检查**——last30days的预检+postmortem
9. **社区声音嵌入**——last30days的verbatim quote嵌入
10. **版本管理+CI/CD**——CHANGELOG、版本号、自动化测试

---

## 六、我的最深一层思考

所有的 skill 项目都在解决同一个问题：**如何让 AI 稳定地产出高质量的分析报告**。

但它们的解法不同：

| 项目 | 核心解法 | 哲学 |
|------|---------|------|
| genli | **规范约束**——写死视觉规范和流程 | "通过契约保证质量" |
| mckinsey | **并行拆解**——12个分析各自独立 | "通过分解降低复杂度" |
| zircote | **框架强制**——必须跑完指定框架 | "通过流程保证覆盖度" |
| wshuyi | **校验分离**——独立Agent核查 | "通过隔离开避免自欺欺人" |
| last30days | **健康透明**——预检+源状态透明 | "通过可见性建立信任" |

2号分析师当前的问题是：**它同时采用了所有这些思路，但每个都只做了一半**。

它有并行管线（但串行执行）、有质量门禁（但事后才检）、有图表模板（但不统一）、有数据采集（但不标注来源）。

**最大的启发不是某一个 skill 的技术细节，而是：这5个项目都在"约定的质量"上做了强制，而2号分析师在"尽力而为"上做了依赖。**

genli 写死了 FIG_W，所以它的图永远不会超出页宽。
zircote 写死了 Porter 5 Forces 必须输出评级，所以它的竞争分析永远不会遗漏关键维度。
wshuyi 写死了 Step 6.5 必须独立 agent 校验，所以它的报告永远有第二双眼睛。

**而2号分析师的代码在写着 `try: ... except: pass`。**

这个差距不是代码量的差距，是设计哲学的差距。每一次 `except: pass` 都在向系统宣告："失败是可以接受的"。每一次空壳模块（HeritageIntegrator）都在向系统宣告："承诺可以不兑现"。

**所以改造2号分析师的核心不是加功能，而是加契约。**

