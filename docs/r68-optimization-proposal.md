# 2号分析师模块体系 — 优化方案

> 基于 R68 模块静默失败审计 + 五大顶级思考者视角的综合建议
> 制作日期：2026-08-05

## 一句话结论

**不是加更多模块，是把已有模块的失败从"不可见"变成"不可接受"。三管齐下：日志升级（debug→warning）、结构埋点（prompt依赖声明→运行时验证）、治本重构（末端装饰→compute产出→门禁校验）。**

## 五视角综合建议

### Karpathy（为什么工程化学不难，难的是正确性可验证）

"Software 2.0 的核心不是写得快，是写得对能验证。你的 18 个模块如果失败都不可观测，那它们不是功能，是负担。"

**建议**：借鉴 [PyTest 的 contract test](https://docs.pytest.org/en/stable/explanation/fixtures.html#what-fixtures-are) 思想——每个模块注册时附带一个依赖声明，管道启动时做依赖完整性校验，缺依赖标记 "unavailable" 而非静默跳过。等价于 "pre-flight check for section modules"：runtime 验证每个 `_str` 的产出是否 "有内容"。

### Feynman（最严厉 — 每个声称的能力必须有对应的实验来验证）

"The first principle is that you must not fool yourself, and you are the easiest person to fool. 你的 IronGate 号称全绿，但 18 个模块中 6 个在静默失败。这不是 Gate 检查的质量问题，是 Gate 不知道该检查什么。"

**建议**：在每个 Gate 检查项中加一个最基本的算术逻辑——报告声称使用了某种方法（如 DCF），但没有相应的数据节或关键数值，标记为 "方法缺失"。等价于让 IronGate 的 `_check_arithmetic_audit` 不仅验算术，也验结构完整度：报告的每个部分是否包含了它声称能提供的分析。

### Munger（最务实 — 用清单遏制盲目自信，但别把清单当能力）

"Checklists are like the guardrails on a highway. 你的 18 个模块就是一个清单——但你缺了另一个清单：验证清单。"

**建议**：把 18 个模块变成**一个执行清单**，在管道的 pre-flight check 阶段跑。等价于 "section module execution report"：每个模块的实际产出（有内容/无内容/数据缺失）作为一个结构化报告嵌在 pipeline_fingerprint 里。

### Taleb（最刁钻 — 检验的不是"当一切正常时多好"，而是"当最差条件时你还能做什么"）

"Don't tell me what your system can do when everything works. Show me what happens when the data is incomplete and the model is having a bad day."

**建议**：引入 [chaos engineering for AI pipelines](https://www.fiddler.ai/blog/mcp-agent-observability)——随机破坏数据输入，看哪些模块会静默崩溃。这不是"测试"，这是"反脆弱注射"。等价于改写 `section_writer` 的异常处理：不是 `logger.debug + 空字符串`，而是 `logger.warning + structured module status report + GateFailure`。

### 张一鸣（最结构 — 靠人力检查会退化，靠系统约束才不会忘）

"Context not Control. 不要用更多的检查代替低质量的流程，用更透明的信息流让问题自己暴露出来。"

**建议**：不是加另一个检查层，而是把 18 个模块从 "section_writer 的末端装饰品" 提升为 "compute_engine 的 tool_modules"。这样它们的失败会自然进入 compute_results 的 "skip" 状态，被 IronGate 感知，被 FP5 学习。这就是 context 的力量——让失败在系统里流动，让所有下游环节都知道它发生了。

## 三管齐下

### 第一刀（立即执行，不改架构）

把 16 个 module 相关的 `logger.debug` → `logger.warning`。改动范围在 section_writer.py 的 10 行内，让静默失败在日志中可见。同时加一个 `self._module_execution_report: dict`，在 `write()` 结束后打印每个模块的产出摘要。

### 第二刀（本周完成，改数据链）

补齐柯力 enrich 最缺的两个字段：`market_cap` 和 `fcf`。market_cap 可从 financials.db + 当前价算出，fcf 可从经营现金流 + capex 推。只需一次 Marvis 补采任务即可让反向 DCF / 多空表 / 盈利预测 / 三表勾稽 四个模块从 "静默失败" 变成 "有产出"。

### 第三刀（架构治本，跨版本）

把 section_writer 的 18 个 `_build_*` 函数按数据类型分为三档：
- **可在 compute 中算的**（反向 DCF、多空表、催化剂日历、预期差）→ 移到 compute_engine 的 tool_modules
- **依赖知识库的**（方法论规则、哈佛框架）→ 移到 section_writer 的独立 injection 阶段
- **依赖外部数据的**（基准对标、目标价追踪、审计核查）→ 保持独立模块，但在 prompt 中标注 "data unavailable" 而非跳过

最终让所有 18 个模块像 5 核心工具一样，有 "ok/skip/error" 三态，在 IronGate 中可被感知。

Sources:
- [Production Logging for AI Agents (2026)](https://suzyahyah.github.io/code/generative%20models/2026/04/20/AI-Agent-Logging.html)
- [Best Practices for Logging and Tracing in AI Workflow Automation](https://techdailyshot.com/blog/best-practices-logging-tracing-ai-workflow-2026)
- [How to Detect Silent Failures in Microservices Using Advanced Observability](https://www.frugaltesting.com/blog/how-to-detect-silent-failures-in-microservices-using-advanced-observability-techniques)
- [Your MCP Agent Is Failing Silently](https://www.fiddler.ai/blog/mcp-agent-observability)
- [Fiddler AI — Why Agentic AI Needs Observability Built for Decision Chains](https://www.fiddler.ai/blog/agentic-ai-observability-decision-chains)
