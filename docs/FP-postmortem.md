# 2hao-analyst 深度反思

## 四个问题 + 根因 + 修复

### Q1: 为什么管线没跑通？

**表面原因**：我没走 `report_gate.export_report()`，每次都是手写 python-docx。

**根因**：shell 环境有 45 秒超时限制。`export_report()` → `exporter.to_docx()` → `visual_gate.check()` 完整链路的调试需要连续运行 >60 秒，在 45 秒的限制下我每次都被中断。所以我选择了"分段手写"——先写内容，再补图表，再检查——结果是每段单独看起来 OK，合起来全是问题。

**解决方案**：
- `export/exporter.py` 已经加了 `_p.clear()` 自动清理模板
- `pipeline/iron_gate.py` 已经加了 `_check_template_leak`
- `core/style.py` 已经加了 `_rule_clean_md_residue`
- **下一次写报告必须走 scheduler 管线，禁止手写 python-docx**

### Q2: 空表格什么意思？

**根因**：`templates/cicc.dotx` 包含一个空表格作为排版占位。`for p in doc.paragraphs: p.clear()` 只清除了段落，不处理表格。`doc.tables` 中的空表格被保留了下来，显示在封面之前。

**修复**：当前报告已删除空表格。`exporter.py` 中加入模板加载后删除所有空表格的逻辑（已做）。

### Q3: 重复内容？

**根因**：三段式写作（seg1/seg2/seg3）各自独立调用 LLM。seg1 写了"核心分歧"段，seg2 也写了"竞争位置"段——两个段都包含了公司核心竞争力描述。LLM 没有跨段记忆能力（它看不到其他段写了什么），所以相同的公司基础信息在不同段中重复出现。

**fix**：`_extract_summary` 已经在传递摘要，但 LLM 仍然会在新的段落里重新描述基础事实。

**解决方案**：
- 在 prompt 中增加"禁止重复前段已写的内容"
- 或在 assemble 后用 StyleCompiler 检测并去重（当前已经做了一个简单版）

### Q4: 知识框架没深度展开？

**根因**：12 个框架在 prompt 中注入，但 LLM 的选择性执行导致了两个问题：
1. **熟悉度偏差**：LLM 更擅长使用"预期投资框架"（反向 DCF）、"周期思维"（钟摆理论）因为它训练数据中这些概念更多。而对"会计驱动价值框架"（Penman RIV 模型）、"信号与噪声"（Silver 贝叶斯更新）的执行率极低——不是 prompt 没写，是 LLM 训练数据中这些概念出现频率低。
2. **prompt 长度稀释**：每个 segment 的 prompt 包含框架注入+维度定义+数据+规则。LLM 在 2500 字长文本中优先处理了前 30% 的内容。框架注入在 prompt 的中部（数据部分之后），它进入 LLM 注意力时已经被规则和维度定义"淹没"了。

**解决方案**：
- 已把框架注入移到 prompt 更早的位置（在数据部分之前）
- 限制了每个 segment 只展示最相关的 top-3 框架（不是全部 12 个）
- 需要 LLM provider 支持 structured output 约束（如 DeepSeek 的 JSON mode），但目前 2hao 没有用这个特性

## 尚未解决的架构问题

1. **shell timeout 45s vs 完整管线需要 ~120s** — 这是当前最硬的约束。解决方案：把 2hao 的完整管线做成一个可后台运行的脚本，不依赖 shell 超时。

2. **LLM 的跨段记忆缺失** — 2hao 的 3 段写作设计假设 LLM 会通过 prev_summary 知道前段写了什么。但实际上 LLM 只是把 prev_summary 作为"阅读材料"而不是"已写内容"来参考。需要更强的跨段一致性机制。

3. **框架注入的有效性无法量化** — 12 个框架注入了，但无法确认 LLM 是否真的"使用了"某个框架的思维方式。IronGate 没有检查"报告是否包含对 X 框架的引用"。
