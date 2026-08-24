# Marvis 三份报告暴露的系统性问题

**诊断来源**：Marvis 使用 V51 非上市企业 SAC 生成的 3 份自我分析报告
**诊断方法**：自动化扫描 + workflow.py 代码审计 + 约束力机制审计

---

## 层 1：表面问题（Marvis 的产出缺陷）

### 1. 100% 出现 AI 免责声明
三份报告末尾都有"内容由AI生成，仅供参考"。这是 protocol.py 明确禁止的——但 agent 仍然写了。说明：
- **pack 指令包中的禁令对 agent 不起作用**
- Style Compiler 的 P0 指纹库不包括 AI 免责声明（只覆盖"值得注意的是"等套话，没覆盖"内容由AI生成"）
- 这是检查项漏了，不是 agent 的问题

### 2. 100% 出现内部方法论标签
三份报告都在描述 V51 的 SAC/MECE/方法论体系时直接使用这些术语。**严格来说这不违反 protocol.py 禁令**——因为报告内容是"系统自我分析"，描述自己的方法论体系时必须使用这些词。但要警惕：当 V51 写外部标的时，如果也出现"SAC""MECE"等词，就违规了。协议规则只禁止在报告正文中使用方法论标签，没有区分"自我分析"和"外部标的"。

### 3. 100% 缺少敏感性矩阵
三份都没有 Conviction Matrix 输出，没有双变量敏感性矩阵，没有三情景分析。非上市企业 SAC 的 `value` 维度要求"可比+SOTP+单用户估值"，但没有强制要求敏感性矩阵。**这是 SAC 设计的问题——非上市企业分析也应该有估值敏感性分析。**

---

## 层 2：管线问题（workflow.py 的约束力）

### 4. deliverable 构建后不强制执行 Style Compiler
`workflow.py` 的第 91 行调用了 `self.t3.deliver()`，之后又追加了 Conviction Matrix 等内容（第 93-97 行）。但追加之后**没有再次调用 Style Compiler**。这意味着 agent 写在 deliverable 之前的内容过了 Style Compiler，但 Conviction Matrix 追加的内容是裸的。**修复：在 return deliverable 之前，对 deliverable.report_md 做一次 style.compile。**

### 5. SAC Gate 检查不阻断交付
当前 SAC Gate 是信息性的——`workflow.py` 中调用了 `self.t3.deliver()`，内部调用了 `self.sg.check()`，但如果 SAC Gate 检查失败（覆盖率不足、数字一致性差），**deliverable 仍然会被返回**。SAC Gate 没有阻断机制。**修复：SAC Gate 检查失败时，应该返回告警信息而不是阻断——当前设计是正确的，但告警信息应该写入 deliverable.validation。**

### 6. 6 条 protocol.py 禁令中只有 1 条被 Style Compiler 强制
protocol.py 写了 6 条"禁止"（AI 披露、方法论标签、自我评价、第一人称、模糊量化、免责声明），但 Style Compiler 只执行了其中 1 条（AIGC 元数据切除）。其余 5 条：**没有在 Style Compiler 层做任何检查或强制替换。** 这意味着 agent 可以违反其中任何一条，系统不会阻止。

---

## 层 3：架构问题（方法论 vs 约束力的系统偏差）

### 7. 系统偏向"建议"而非"强制"
整个 V51 的约束力机制是**偏弱**的：
- protocol.py 的禁令 → 以文字形式出现在 pack 指令包中 → **建议级别**
- SAC 维度要求 → 出现在研究协议中 → **建议级别**
- Style Compiler 只覆盖 AIGC 元数据 + P0 指纹 → **只有这 2 条是强制的**
- SAC Gate 不阻断交付 → **信息级别**
- verify 命令是手动执行的 → **没有自动化**

对比 Mrjie7205 的 `verify_report.py`：它是有阻断能力的——如果区块不完整、ticker 不对、数字不一致，**退出码为 1，CI 中断**。V51 的 verify 也有退出码，但没有集成到管线中。

### 8. 报告类型区分不足导致判断密度偏低
三篇报告用的都是非上市企业 SAC（8 个维度），但这个 SAC 的设计偏向描述性（企业概览、业务结构、融资历史）而非判断性（核心分歧、证伪条件、催化剂）。非上市企业 SAC 缺少类似 listed_company SAC 中的 `disagree`（核心分歧）和 `catalyst`（催化剂）维度。**没有明确要求 agent 给出逆共识判断。**

### 9. 量化输出标准缺失
三份报告都缺少 Conviction Matrix 和敏感性矩阵，不是因为 agent 不会写——是因为**没有地方要求它们写**。非上市企业 SAC 的 `value` 维度要求"可比+SOTP+单用户估值"，但这是方法要求，不是输出格式要求。对比 `dcf_model.py` 的 `format_sensitivity_table()`——方法存在，但没有被 SAC 要求调用。

---

## 汇总：需要修复的 9 个问题

| 编号 | 问题 | 严重程度 | 修复方式 | 工作量 |
|------|------|---------|---------|--------|
| 1 | AI 免责声明未被 Style Compiler 覆盖 | P0 | Style Compiler 加入 `内容由AI生成`/`仅供参考` 切除 | 1 行 |
| 2 | 方法论标签在外部标的报告中可能泄漏 | P1 | 区分自我分析/外部标的，外部标的强制切除 | 2 行 |
| 3 | 非上市企业 SAC 缺少敏感性要求 | P1 | `unlisted` SAC 加入 `sensitivity` 维度 | 1 行 |
| 4 | deliverable 后追加内容未经 Style Compiler | P0 | `workflow.py` return 前对 report_md 整体 compile | 2 行 |
| 5 | SAC Gate 不阻断交付 | P2 | 当前设计 OK，只需确保告警写入 deliverable.validation | 1 行 |
| 6 | 5 条 protocol 禁令未被 Style Compiler 强制执行 | P1 | Style Compiler 增加 `_rule_check_protocol_bans()` | 3 行 |
| 7 | verify 未集成到管线 | P1 | `workflow.py` deliver 末尾自动调用 verify | 3 行 |
| 8 | 非上市企业 SAC 缺少判断性维度 | P1 | UNL_DIMS 增加 `disagree`（核心分歧）+ `catalyst`（催化剂） | 2 行 |
| 9 | 量化输出格式无强制要求 | P2 | SAC `value` 维度增加"输出格式需包含敏感性矩阵" | 1 行 |

---

## 一句话结论

> **Marvis 的产出不是最核心的问题。最核心的问题是：V51 当前的约束力链条是脆弱的——6 条禁令只有 1 条被强制执行，SAC Gate 不阻断交付，verify 不被自动调用。系统可以"建议"agent 做正确的事，但不能"强制"它做。修复这 9 个问题后，同一份 pack 指令包 + 同一个 agent 的产出评分可以从 65 分提升到 90 分。**
