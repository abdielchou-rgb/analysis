# 油位传感器 v0.86 Gate 失败 — 深层次系统性问题分析

> 基于：`D:\2hao-analyst\output\油位传感器_行业深度报告_v0.86.docx`（0.86分最佳稿）
> + `D:\Marvis\output\reports\油位传感器Gate失败深度复盘_20260806.md`
> + R68-R76 全量模块审计背景
> 审计日期：2026-08-06

---

## 一、表面现象 vs 深层真相

### 表面：8轮Gate失败，score卡在0.82~0.86

### 真相：不是报告质量问题，是整个反馈-重写闭环存在**3个结构性缺陷**，让系统做了44分钟的布朗运动

| 表面诊断 | 实际根因 |
|---------|---------|
| so_what_chain 不达标（min=0.00死角段） | fail_locator 无法定位死角段→只能全量重写→死角段以高概率再现 |
| annotation_types 被标为FAIL | 运行时已达标，归因正则把"来源标注空泛"误归为"标注类型缺失" |
| data_conflicts 被标为FAIL | 复算0冲突，归因正则把"口径不一致"误归为"数据字典冲突" |
| 8轮不收敛 | 全量重写每轮推倒已修复段 + 最佳稿未作为基线固化 + LLM provider超时放大成本 |

---

## 二、4个深层次系统性问题

### 问题1：反馈桥断裂（Feedback Bridge Collapse）

**这是最根本的缺陷。** Gate 产生失败信号 → fail_locator 把失败信号翻译成"哪些段需要重写" → section_writer 重写这些段。这个链条上的每一步都在退化：

```
Gate 产生信号：
  ✓ so_what_chain: min=0.00，正确
  ✗ annotation_types: 已达标但被标FAIL（运行时文件被覆盖导致时序错位）
  ✗ data_conflicts: 复算0冲突但被标FAIL（"口径"被误匹配）

fail_locator 翻译：
  ✗ 对 so_what_chain: 正确识别但定位失败→全量重写
  ✗ 对 annotation_types: 误判全局失败→全量重写
  ✗ 对 data_conflicts: 误判全局失败→全量重写
  
section_writer 执行：
  ✗ 每次全量重写=20k字→新LLM调用→新随机种子→新错误
  ✗ 已修复段被推倒→新的死角段出现→新的数据口径→新的来源表述→永动循环
```

**对标：CogGen论文（ACL 2026）** 提出"recursive refinement with outline anchoring"——每次重写不推倒全文，而是以第一稿的大纲为锚点，只局部重写被标记为不达标的段。2hao 的 fail_locator 承担了这个"大纲锚定"的角色，但它做反了——不能定位的段硬判全量重写，把大纲也一并推倒。参考：[CogGen: Recursive Report Generation](https://arxiv.org/abs/2604.17072)

### 问题2：归因正则的无监督退化

fail_locator 用正则匹配 Gate 反馈文本来决定重写策略。正则匹配是一种**无监督分类器**，但它没有反馈回路——没有人在告诉它"你这次判错了"。

后果：
- `(data_conflicts|数据冲突|口径)` → "口径"二字太宽，匹配到 market_size_consistency 的反馈文本，误归因
- `(annotation_types|来源标注|A/E/F/B|标注类型)` → "来源标注"匹配到 source_entity 的反馈文本，误归因
- 每个误归因触发一次全量重写→3个误归因×8轮=24次无效全量重写

**对标：AgentGuard-LLM** 提出 "fault-signature-based retry"——每次失败后记录"失败指纹"（检查器+具体错误文本摘要），同一指纹连续出现2次以上触发归因重评估，而非盲重试。2hao 的 fail_locator 没有这一层。[GitHub: AgentGuard-LLM](https://github.com/maheshmakvana/agentguard-llm)

### 问题3：无正向累积机制（No Progressive Accumulation）

R66 引入了 `_best_so_far` 字典（"记录最高分草稿供回滚"），但复盘暴露该机制在 Gate 反馈引入后**从未生效**：

- v0.86 的最佳稿 `_gate_prev.md`（0.86分）在第1-2轮产生
- 第3-8轮的6轮重写全部在更差的稿子上迭代
- `_best_so_far` 只记录了分数，没有把最佳稿的**已达标段**固化为基线
- 所以每轮全量重写都从零开始，而不是"在0.86分稿的基础上改失败段"

**对标：EviReport（ACL 2026）** 提出 "evidence-tracked outlines" ——大纲+证据链被锁定为不变量，重写只修改推理和措辞，不改变已确证的证据引用和数据锚点。[EviReport: Evidence Tracked Reports](https://aclanthology.org/2026.findings-acl.1397/)

### 问题4：死角段是系统性非随机问题

so_what_chain 的 min=0.00 死角段不是随机出现的——它是系统性的：

复盘确认：min=0.00 的死角段在8轮中都出现，只是换不同位置——因为全量重写每次产生新的死角段。真正的原因是 **Writing Charter 不给 LLM 强制推理链约束**：

- LLM 可以写一大段纯数据罗列而不加"因此/我们判断/这意味着"等推理标记
- Gate 规则要求每段至少 2+N 个推理标记，但 prompt 中没有对应的"每段末尾必须有 Therefore Statement" 要求
- 写作和检查是两个独立环节，各自有各自的标准——写作标准弱于检查标准

**对标：Multi-Agent Orchestration Patterns（2026）** 提出 "validation-feedback alignment"——写作Agent的prompt中必须包含与Gate检查规则**完全对齐**的结构化约束，避免"Agent按A标准写，Gate按B标准查"的错位。

---

## 三、顶级解法对标（6项国际最佳实践）

| # | 解法 | 来源 | 直接应用于 |
|---|------|------|----------|
| 1 | **Recursive Refinement with Outline Anchoring** | CogGen (ACL 2026) | fail_locator → 大纲锚定局部重写 |
| 2 | **Fault-Signature-Based Retry** | AgentGuard-LLM | fail_locator → 失败指纹匹配防重复失效 |
| 3 | **Evidence-Tracked Outlines** | EviReport (ACL 2026) | _best_so_far → 数据锚点固化 |
| 4 | **Validation-Feedback Alignment** | Multi-Agent Orchestration (2026) | Writing Charter → 让写作标准与Gate规则同步 |
| 5 | **Progressive Refinement with Segment Freeze** | Durable Execution Pattern | section_writer → 已达标段冻结不受重写 |
| 6 | **Regular-Expression Guardrails with Confidence Scoring** | AgentGuard-LLM | fail_locator → 归因正则+置信度评分降误判 |

---

## 四、v0.86 报告本身的质量评估

从 docx 提取的 20435 字内容：

| 维度 | 评分 | 问题 |
|------|------|------|
| SAC 覆盖 | 7/10 | 决策门截断到半句话（"双的分析"） |
| 数据一致性 | 5/10 | 正文18.6亿 vs 数据字典46.0亿 vs 附件65.0亿——三种口径未统一 |
| 推理链 | 5/10 | 死角段 min=0.00，数据罗列+So What 链断裂 |
| Bold Call | 6/10 | 增持/38.5目标价有，但目标价推导不完整（缺少估值锚交叉验证） |
| AI 指纹 | 9/10 | 良好，附录段"AI生成仅供参考"残留（R72已修但此稿为修复前产物） |
| 排版 | 7/10 | docx有完整结构，但图表全部在附录末尾（R74已修） |
| **综合** | **70/100** | 0.86分被高估——盖特检查看重结构化门禁（SAC关键词覆盖），数据口径混乱未被充分扣分 |

**一句话**：v0.86 是一份"通过关键词检索能找到所有 SAC 维度、但细读发现数据口径混乱+推理链不连贯+决策门截断"的报告——门禁打出了高分，但人的阅读体验不会给 86 分。
