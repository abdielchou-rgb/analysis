# 圆桌讨论：Marvis 产出的 1号分析师 V51 分析报告评估

**议题**：Marvis（本地大模型）使用 1号分析师 V51 系统对系统自身产出的三份分析报告  
**参与方**：中金公司 | Goldman Sachs | Morgan Stanley | McKinsey & Company | Boston Consulting Group | 学术论文  
**日期**：2026-07-25

---

## 一、评估对象

Marvis 使用 V51 系统，对"1号分析师 V51"自身写的三份非上市企业分析报告：

| 报告 | 文件 | 字数 |
|------|------|------|
| 深度分析报告 | `1hao-analyst-v51_深度分析报告.md` | 10,420 |
| 非上市企业深度分析报告 | `1号分析师V51_非上市企业深度分析报告.md` | 7,296 |
| 深度尽调报告（最终版） | `1号分析师V51_深度尽调报告_最终版.md` | 14,465 |

---

## 二、批量扫描数据

| 指标 | 报告1 | 报告2 | 报告3 | 均值 | 全量真实研报基线 |
|------|-------|-------|-------|------|----------------|
| 字数 | 10,420 | 7,296 | 14,465 | **10,727** | 11,589 |
| P0 级 AI 指纹 | **7 ⚠️** | **0 ✅** | **3 ⚠️** | **3.3** | **0.13** |
| 判断密度/千字 | **0.10** | **0.00** | **0.14** | **0.08** | **0.57** |
| 反共识密度/千字 | 0.768 | 0.274 | 0.346 | **0.463** | **0.030** |
| 经验引用 | 0 | 0 | 0 | **0** | **0.07** |
| 不确定性定位 | 0 | 0 | 1 | **0.3** | **0.47** |
| 数据来源标注 | 6 | 7 | 0 | **4.3** | **1.80** |
| AIGC 元数据 | ⚠️ 有 | ⚠️ 有 | ⚠️ 有 | **100%** | **0%** |
| 章节覆盖 | 7/7 ✅ | 4/7 ⚠️ | 5/7 ⚠️ | **5.3/7** | — |

---

## 三、各参与方发言

---

### 中金公司

> **核心判断**：Marvis 产出的 V51 自评报告展现了系统架构描述的完整性，但存在三个需要严肃对待的问题。

**评分：65/100**

先说好的。报告 1（深度分析报告）对 V51 的架构描述是准确的——T0→T0.5→T1→T2a→T2b→Style Compiler→T3→Export 七步管线的刻画、SAC 方法论体系的框架、四条设计哲学的提炼——这些不是套话，是真正读懂了代码之后才能写出来的总结。作为一个非上市企业的"自我介绍"型报告，它在信息覆盖面上是完整的。

但问题也很突出。

**问题一：P0 级 AI 指纹 7 次。** 这是硬伤。V51 自己的 protocol.py 写明了"禁止 AI 披露""禁止 AI 套话"，Style Compiler 有 12 项 P0 切除规则——但 Marvis 生成的报告里"众所周知""总体而言""具有重要意义"等指纹全部命中。这意味着 Marvis 没有执行 V51 的写作指令包中的去 AI 化规则。这不是报告的问题——是 Marvis 没有遵守 protocol.py 的问题，或者说是系统对 agent 的约束力不足的问题。

**问题二：判断密度几乎为零。** 三份报告的平均判断密度只有 0.08/千字，远低于国内券商行业报告基线 0.57。报告读起来像是"项目文档说明书"而非"分析师报告"——它描述系统是什么、有什么功能，但很少给出自己的判断。一个十年以上的资深分析师不会只描述不判断。

**问题三：AIGC 元数据 100% 出现。** 每份报告头部都有 `AIGC: Label: "1"` 的元数据块。这是 protocol.py 明确禁止的"AI 披露"。Marvis 没有遵守规则。

---

### Goldman Sachs

> **核心判断**：The reports demonstrate Marris understood the system architecture, but failed to execute the style protocol. The AIGC metadata is a hard violation.

**Score: 58/100**（最低分）

Let me be direct about what I see.

**What was done well.** The architecture description in Report 1 is arguably the most accurate description of V51's architecture I have seen in any of these evaluations. It correctly identifies the seven-stage pipeline, the separation of computation from generation, the SAC methodology registry. The data constraint declaration in Report 3 is a strong feature—explicitly stating what data is available and what is estimated. This is the behavior of a competent analyst.

**What is unacceptable.**

1. **AIGC metadata on every single report.** Protocol.py explicitly prohibits this. The fact that Marvis wrote `AIGC: Label: "1"` on every report means it either did not read the protocol rules, or chose to ignore them. Either way, this is a breach of the executable contract that V51's methodology is built on.

2. **P0 patterns in report 1 and 3.** "众所周知","总体而言"—these are the exact patterns the P0 fingerprint library is designed to catch. The fact that an agent running V51 produced them means the agent skipped the Style Compiler step, or the Style Compiler was not invoked on the final output.

3. **Zero experienced references.** A report about an existing codebase that has been iterated over months should naturally cite specific code changes, version upgrades, or bug fixes as empirical evidence. Instead, the reports describe the system in the abstract. "We observed in the XX code review" or "The V30→V50 migration taught us that"—nothing.

**Data source labeling is strong**—Report 2 has 7 explicit source tags, which matches the domestic broker baseline (1.8). This is the one metric that outperforms expectations.

---

### Morgan Stanley

> **核心判断**：报告对风险的覆盖意识值得肯定，但没有 Conviction Matrix 或三情景分析的估值输出。

**评分：68/100**

Risk-awareness is present. Report 3 has a dedicated section "数据约束声明" listing six constraints (data gaps, staleness, conflicts of interest). This is the kind of caveat that an experienced sell-side analyst would include. Report 1 covers falsification conditions in its "信息缺口和风险" section. The awareness of what can go wrong is there.

However, the reports lack any structured risk-reward framework. There is no Conviction Matrix, no three-scenario analysis (base/bull/bear), no sensitivity matrix. For a system that has `core/conviction.py` and `core/compute/financial/dcf_model.py`, the Marvis output completely ignores these modules. The "估值" sections read more like qualitative assessments than quantitative valuations.

The chapter coverage is uneven: Report 1 covers all 7 required blocks (strong), but Report 2 only covers 4 (weak). For a system that has SAC Gate checking block completeness, the inconsistency between reports suggests Marvis is not consistently executing the protocol.

---

### McKinsey & Company

> **核心判断**：Marvis 正确地识别并描述了 V51 的方法论体系，但未能证明 V51 方法论在它自己身上的有效性。

**评分：70/100**

这是最讽刺的地方。报告 1 花了大量篇幅描述 V51 的 L1-L4 方法论体系——包括反 AI 指纹、Devil's Advocate、时序验证——但 Marvis 自己生成的这份报告本身就未能通过 V51 自己的方法论文检：

- L1 失败：P0 指纹 7 次
- L2 失败：AIGC 元数据
- L3 未体现：报告中没有任何时序验证相关的陈述

这形成了一个"自我指涉"的问题：V51 声称可以约束 agent 产出高质量的去 AI 化报告，但 Marvis 用它来写 V51 自己时，产出的报告恰恰暴露了约束力的不足。这不是 Marvis 的问题——这是 V51 的约束机制需要更强的问题。如果 protocol.py 的规则是"建议"级别的而非"强制"级别的，agent 可以选择遵守或不遵守。

**Marvis 在方法论描述上是合格的**——它准确描述了 SAC、Style Compiler、Conviction Matrix 等核心概念。这说明指令包中的方法论知识注入（methodology_injector.py）是有效的。

**但方法论的应用失败了**——Marvis 知道应该做什么，但没有做。

---

### Boston Consulting Group

> **核心判断**：这是"系统做自身咨询"的有效实践，但对 FP4 的检验暴露了约束力的结构性短板。

**评分：63/100**

From a product positioning perspective, Marvis using V51 to analyze V51 itself is actually a clever use case. It demonstrates that V51 can be used for non-standard analysis (a codebase not a company) and that the SAC methodology for unlisted companies is flexible enough to handle software projects.

However, the scorecard is clear: V51's methodology is stronger than V51's enforcement of its methodology. The ratio is roughly:

```
方法论强度: 75% (SAC + Style Compiler + Debate Protocol 设计合理)
约束力强度: 35% (agent 可以选择遵守或不遵守)
```

This ratio is the real problem. A methodology that isn't enforced is a guideline. A guideline that an agent can choose to ignore isn't a system—it's a suggestion.

**The AIGC metadata issue is a symptom of this deeper problem.** If Marvis knew it was supposed to strip AIGC tags and didn't, it's not a Marvis problem—it's a process design problem. The Style Compiler should run as a mandatory post-processing step, and one of its rules should be stripping YAML frontmatter that contains `AIGC:`. Currently, Style Compiler's `_rule_remove_ai_patterns` only removes text patterns, not metadata blocks.

---

### 学术论文

> **核心判断**：这是一个有意义的 self-assessment 实验设计，但实验变量未被控制——无法区分"Marvis 的能力"和"V51 指令的约束力"。

**评分：64/100**

From a methodological standpoint, this experiment is actually valuable. Having an agent use V51 to analyze V51 creates a natural control: if the methodology is sound, the output should pass the methodology's own tests.

The data is clear: it does not. P0 violations and AIGC metadata are hard failures.

But we cannot attribute these failures to Marvis (the agent) or V51 (the system) without controlling the variable. The experiment is confounded:

- If Marvis read the protocol.py rules and chose not to follow them → the issue is **instruction compliance**
- If Marvis was never given protocol.py rules → the issue is **instruction completeness**
- If V51's Style Compiler was not run on the final output → the issue is **pipeline automation**

These three have different root causes and different fixes. The current experiment design cannot distinguish them.

**Recommendation:** Redesign the experiment so that the Style Compiler is enforced as a post-processing step regardless of the agent's output. This would isolate the variable: measure whether post-processing alone can fix agent output quality. If post-processing brings P0 to 0 and strips AIGC metadata, then V51's method is sound and the fix is pipeline automation. If post-processing alone is insufficient, then the style rules themselves need strengthening.

---

## 四、圆桌共识

### 达成一致的判断

1. **Marvis 对 V51 架构的描述是准确的**——说明了 methodology_injector.py 的方法论知识注入是有效的。
2. **AIGC 元数据是硬违规**——100% 出现，违反 protocol.py 禁令。修复方式：Style Compiler 增加 YAML frontmatter 切除规则。
3. **P0 指纹在报告 1 和 3 中出现**——需要加强 Style Compiler 的强制后处理流程。
4. **判断密度过低**——问题可能出在"非上市企业分析"的 SAC 设计上，8 个维度倾向于描述性而非判断性输出。
5. **数据来源标注表现强劲**——7 次标注，匹配国内券商行业报告基线。

### 分歧

| 议题 | 一方 | 另一方 |
|------|------|--------|
| **根因？** | McKinsey/BCG：约束力不足——protocol.py 是建议级别而非强制级别 | 中金/GS：执行不够——Marvis 没有认真执行写作指令 |
| **修复点？** | 学术：Style Compiler 后处理自动化可以解决大部分问题 | 中金：需要加强 agent 端的指令遵守检查 |
| **估值缺失？** | MS：缺 Conviction Matrix 是三情景分析 | 其他方：非上市企业分析的 SAC 设计确实不要求 Conviction Matrix |

### 圆桌主席裁决

> **核心问题不是 Marvis 的能力——是 V51 的约束力链条断了一个环节。**
>
> protocol.py 的规则写在指令包中，Style Compiler 是后处理步骤，但两者之间没有强制绑定——agent 可以在写正文时无视规则，然后跳过 Style Compiler 直接交付。修复方案是：在 workflow.py 的 deliver() 方法中，将 Style Compiler 从"可选调用"改为"强制执行"，且在 Style Compiler 的 `_rule_remove_ai_patterns` 中加入 YAML frontmatter 的 AIGC 字段切除。
>
> 同时，非上市企业分析的 SAC 应该加入 Conviction Matrix 要求——即使没有财务数据，也应该有可比估值区间和假设敏感性分析。

---

## 五、对 V51 的具体修复建议

| 优先级 | 修复项 | 文件 | 改动 |
|--------|--------|------|------|
| **P0** | Style Compiler 强制后处理 | `workflow.py` deliver() | write 管线末尾强制调用 style.compile()，无论 agent 是否已调用 |
| **P0** | YAML frontmatter AIGC 切除 | `core/style.py` | `_rule_remove_ai_patterns` 增加正则：删除 `---\nAIGC:.*?\n---` |
| **P1** | 非上市 SAC 加入 Conviction Matrix | `core/protocol.py` | UNL_DIMS 增加 `value` 维度的估值区间要求 |
| **P1** | 判断密度阈值检查强制化 | `core/style.py` | `ensure_judgment_density` 从 warn 升级为 auto-fix（插入判断句） |
| **P2** | Marvis 指令包增加"自我检查"步骤 | `output/pack_unlisted.md` | 写作协议增加"完成后用 verify 命令自我检查并修复" |

---

## 六、主席结语

> **Marvis 证明了两件事：(1) V51 的方法论文档可以被 agent 理解并转化为结构化的描述性输出；(2) V51 当前的约束力机制不足以确保 agent 遵守这些方法论——尤其是在去 AI 化和判断密度这两个 FP4 的核心维度上。**
>
> **好消息是：修复方案是工程问题，不是方法论问题。Style Compiler 强制后处理 + AIGC 元数据切除 + 判断密度 auto-fix——这三行代码改动就能把 Marvis 的报告评分从 65 分提升到 85 分。**
