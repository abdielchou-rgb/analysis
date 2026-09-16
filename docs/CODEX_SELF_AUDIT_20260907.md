# 二号分析师 · 知识库/方法论"充分调用"自审报告

> 日期：2026-09-07
> 审计对象：Claude 收尾执行报告（[CODEX_KB_CLOSURE_20260907.md](D:/Claude/projects/2hao-analyst/docs/CODEX_KB_CLOSURE_20260907.md)）声称修复后的二号分析师
> 审计问题：**是否已充分调用所有知识库、方法论用于写报告**
> 验证方式：真实语料只读探针 + 代码接线逐行核对 + pytest 回归 + ruff correctness gate
> 一句话结论：**否，还不能回答"已充分调用"。代码侧的"检索→注入→到达"已经修扎实，但"正文消费→门禁防回退→端到端产物证据"还没闭环——强检查未接进 e2e、最新报告产物仍是修复前的 KB=1/MKB=0。**

---

## 0. 结论速览

把"充分调用知识库方法论"拆成五段链路，逐段审计：

| 链路段 | 含义 | 状态 | 证据 |
|---|---|---|---|
| 1. 库里是否有货 | 语料真实可检索 | ✅ | KB 全库 122,422 chunk；MKB 2,524 条结构化条目（§2.1） |
| 2. 检索是否可得 | 方法论小目录不被大目录淹没 | ✅ 基本闭环 | 类别均衡检索 + 中文子串兜底 + 方法论目录置前（§2.2） |
| 3. 注入是否到达写作者 | KB/MKB 真的进 prompt，且不被截断切掉 | ✅ 已闭环 | 并行/串行两路同一对检索函数；KB 1500 / MKB 2000 块级预算（§2.3、§2.4） |
| 4. 正文是否消费 | LLM 真的在报告里用了注入内容 | ⚠️ 部分 | 弱检查已注册进 IronGate 真跑；**强检查（注入 N 条→正文引用 ≥50%）未在 e2e 接线**（§2.5、§4.1） |
| 5. 是否防回退且有产物证据 | 门禁能拦住退化 + 重跑报告证明提升 | ❌ 未闭环 | 最新报告 [贵州茅台_cicc.md](D:/Claude/projects/2hao-analyst/output/贵州茅台_cicc.md)（10:50 生成）仍 KB=1 / MKB=0，早于本轮代码修复（§4.2） |

所以对 Claude 收尾报告的复核结论是：**它描述的修复方向属实，但文档滞后于工作区**——它称 kb_citation 为"独立模块待接线"，实测已在 [iron_gate.py](D:/Claude/projects/2hao-analyst/pipeline/iron_gate.py:139) 接好并有 IronGate 级测试证明 `run_all()` 真跑（§3）。同时它未覆盖本轮新做的两处主体修复（KB 中文子串兜底、MKB 块预算）。

---

## 1. 审计口径：什么才叫"充分调用"

这不是"库里有没有这些方法论文档"的问题，而是**注入的内容有没有变成正文里的结构回指**。业界对"知识库知识进不了生成结果"的收敛解法只有一句话：**别靠提示词让模型"用"知识，靠结构让它"只能用"知识**（引用契约、证据编号、门禁强制）。

据此，"充分调用"的可证伪判据有四条：

1. 检索可得：方法论目录（08-四大审计 / 09-国际投行 / 01-宏观）在任意标的下都有真实命中，而不是永远被 7.6 万 chunk 的 04-回测基线库淹没；
2. 注入到达：KB/MKB 块在写作侧 `[:1500]` / `[:2000]` 截断前完整到达模型（不出现"检索到了但块尾被切掉"）；
3. 正文消费：注入非空时正文出现 `[KB#]` / `[MKB#]` / 方法名回指，比例有下限；
4. 防回退与产物证据：门禁注册进 `run_all()` 真跑，且用新代码重跑的产物显示引用数确实提升。

前两条是检索/注入工程，后两条是消费/验证工程。下面逐条给证据。

---

## 2. 实测证据

### 2.1 语料真实规模（真实 DB 只读探针）

`data/kb_fts.db`（403 MB，FTS5 索引）：

| 类别 | chunk 数 | 说明 |
|---|---|---|
| 04-回测基线库 | 76,336 | 占全库 62%，是"淹没源" |
| 02-行业与公司研究 | 20,576 | |
| 03-估值与测算 | 16,660 | |
| 05-Excel知识库 | 6,970 | 教学类，检索 allowlist 排除 |
| 01-宏观分析框架 | 1,691 | 方法论目录 |
| 07-原始文档提取 | 92 | |
| 06-PPT排版美学 | 60 | 教学类，检索 allowlist 排除 |
| 08-四大审计方法论 | 17 | 方法论目录，最小体量 |
| 09-国际投行方法论 | 10 | 方法论目录，最小体量 |
| 全库合计 | 122,422 | |

`data/methodology_knowledge_base.json`：8 个内容子类合计 **2,524** 条（其中 backtest_gold 1,873 条占 74%），每条含 title/topic/methods/judgment_signals/summary 结构化字段。

体量差解释了问题本质：08/09 只有 17/10 个 chunk，纯 BM25 全局 top-k 在任意资产查询下都轮不到它们——"注入了知识库"但正文永远只有 04 类的内容。

### 2.2 检索侧修复（代码接线证据）

| 修复 | 位置 | 作用 |
|---|---|---|
| P0-3 检索白名单显式化 | [knowledge_base.py](D:/Claude/projects/2hao-analyst/core/knowledge_base.py:35) `SEARCH_CATEGORY_ALLOWLIST` | 放行 01/02/03/04/07/08/09 七个分析目录，排除 05/06 教学目录 |
| 类别均衡检索 | [knowledge_base.py](D:/Claude/projects/2hao-analyst/core/knowledge_base.py:259) `search_balanced` | 每类别独立检索各取 top-n（注入侧 per_category=1），小目录获得与体量无关的席位 |
| 中文子串兜底 | [knowledge_base.py](D:/Claude/projects/2hao-analyst/core/knowledge_base.py:353) `_substring_balanced_rows` | FTS5 unicode61 不做中文分词，连续中文整段 token 导致"投行/高盛/审计"短词永远匹配不到；FTS 命不足时用 `instr()` 子串兜底 |
| 方法论目录置前 | [knowledge_base.py](D:/Claude/projects/2hao-analyst/core/knowledge_base.py:62) `METHODOLOGY_DISPLAY_PRIORITY` + [L314](D:/Claude/projects/2hao-analyst/core/knowledge_base.py:314) `_order_for_display` | 08/09/01 排到块首，避免被写作侧 `kb_str[:1500]` 截断切掉 |

真实库探针（`_inj_kb_str(宁德时代, listed_company)`）：返回 **1,327 字 ≤ 1500**，共 7 个来源，块首三个确切命中 `[KB1] 四大审计方法论/收入确认审计`、`[KB2] 国际投行方法论/高盛研报结构`、`[KB3] 宏观分析框架`——修复前这些目录在任意资产查询下基本零命中。

### 2.3 注入侧修复（P0-1 / P0-2）

| 修复 | 位置 | 作用 |
|---|---|---|
| P0-1 KB/MKB 与 `_tm_str` 总开关解耦 | [section_writer.py](D:/Claude/projects/2hao-analyst/pipeline/section_writer.py:116) `_assemble_data_injection_tail` | 此前整段包在 `if _tm_str:` 内，工具模块为空时 KB/MKB 等 14 个块整体消失；现每块只由自身非空条件控制 |
| P0-2 串行写作路径补齐 | [section_writer.py](D:/Claude/projects/2hao-analyst/pipeline/section_writer.py:201) `_kb_mkb_for` | 串行骨架档（[L1299](D:/Claude/projects/2hao-analyst/pipeline/section_writer.py:1299)）与串行正文档（[L1709](D:/Claude/projects/2hao-analyst/pipeline/section_writer.py:1709)）都注入 KB/MKB，与并行路径共用 `_inj_kb_str` / `_inj_mkb_str` 同一对函数，杜绝两套实现漂移 |

### 2.4 本轮新修：MKB 空块与块尾截断（探针发现的真实缺口）

审计中发现的真实问题：真实 2,524 条 MKB 的条目标题是"方法/报告主题"（如"2024年锂电行业年度策略"），**不含资产名、也不含 `listed_company` 标签**——纯靠"宁德时代+listed_company"做关键词时整块为空；且即使召回成功，写作侧 `mkb_str[:2000]` 会把块尾内容半截切断。

修复：给 [methodology_kb.py](D:/Claude/projects/2hao-analyst/core/methodology_kb.py:126) 的 `format_block` / [build_block](D:/Claude/projects/2hao-analyst/core/methodology_kb.py:148) 增加 `max_chars` 块级预算（与写作侧 2000 对齐），**只整条丢弃放不下的尾部条目，绝不半截截断**；注入器 [_inj_mkb_str](D:/Claude/projects/2hao-analyst/pipeline/prompt_injectors_p3b.py:121) 传 `max_chars=2000`，并保留行业标签（industry_tags）作为检索关键词。

真实库探针对照：

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 宁德时代 + 锂电/储能 tags | 空 | **1,622 字 ≤ 2000，4 条整条命中**（华福证券 2024 储能/锂电年度策略等真实报告） |
| 宁德时代 无 tags | 空 | 空（检索盲区，§4.3） |
| 贵州茅台 无 tags | 空 | 空（检索盲区，§4.3） |

### 2.5 消费端门禁（P1-2）已注册并真跑

- 检查逻辑：[kb_citation_mixin.py](D:/Claude/projects/2hao-analyst/pipeline/checks/kb_citation_mixin.py:26) `check_kb_citation_coverage`——弱检查（无注入计数：正文无 KB/方法论痕迹则 warning）+ 强检查（有注入计数：正文引用 ≥ 注入 × 0.5）；
- IronGate 接线：[iron_gate.py](D:/Claude/projects/2hao-analyst/pipeline/iron_gate.py:139) import、[L149](D:/Claude/projects/2hao-analyst/pipeline/iron_gate.py:149) MRO、[L428](D:/Claude/projects/2hao-analyst/pipeline/iron_gate.py:428) 注册进 `_check_funcs`；
- R61 AST 全量守卫通过：`run_all()` 执行集合 == 全部 `_check_*` 定义集合，新增检查不会被"定义了但没跑"漏掉。

---

## 3. 对 Claude 收尾报告的复核

| Claude 收尾报告的说法 | 实测复核 | 判定 |
|---|---|---|
| P1-2 是"独立模块，待 codex 接线一行" | 工作区 [iron_gate.py](D:/Claude/projects/2hao-analyst/pipeline/iron_gate.py:139) 已 import + MRO + 注册（L139/L149/L428），`test_iron_gate_runs_kb_citation_check` 证明 `run_all()` 真执行 | **文档滞后**：接线已完成 |
| 收尾"已补 6 个测试" | [test_kb_citation_coverage.py](D:/Claude/projects/2hao-analyst/tests/test_kb_citation_coverage.py) 现为 **9 个**（+3 个 IronGate 级接线回归） | 属实且更完整 |
| 测试契约红 45→47 已修复 | [test_prompt_injectors.py](D:/Claude/projects/2hao-analyst/tests/test_prompt_injectors.py) 全绿 | 属实 |
| 端到端重跑未做（沙箱无 key） | 属实；且当前无任何 post-fix 产物 | 属实 |
| 89 passed | 口径为 29+6+54 三批；本轮复核为 21+16+75=112 三批 + ruff green，各批内容不同 | 方向一致，**不可等价为同一套全量** |
| 未提及 KB 中文分词兜底与 MKB 空块 | 本轮发现并修复（§2.2、§2.4） | 收尾报告未覆盖 |

---

## 4. 诚实审计发现：仍未"充分"的四个点

### 4.1 强检查没有 e2e 调用方（最关键残余）

`set_kb_injection_counts()` 定义于 [kb_citation_mixin.py](D:/Claude/projects/2hao-analyst/pipeline/checks/kb_citation_mixin.py:88)，但全仓搜索 **pipeline/、core/ 内零调用方**（只有测试调用）。e2e 门禁节点 [e2e_orchestrator.py](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py:1250) 构造 IronGate 后直接 [run_all()](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py:1273)，从未传入本轮实际注入的 KB/MKB 条数。

后果：真实报告跑门禁时，`kb_citation_coverage` 永远走**弱检查**（正文只要有 KB 痕迹就放行，warning 不阻断）。它兜住了"完全没消费"，但兜不住"注入 7 条只用了 1 条"——这正是"充分调用"最需要防的退化，目前只防了一半。

### 4.2 没有 post-fix 的端到端产物证据

`output/` 最新报告 [贵州茅台_cicc.md](D:/Claude/projects/2hao-analyst/output/贵州茅台_cicc.md) 与 [_gate_check.md](D:/Claude/projects/2hao-analyst/output/_gate_check.md) 生成于 **09-07 10:50**，实测正文 **KB=1、MKB=0**，早于本轮代码修复。没有用新代码重跑的报告，"注入侧修好了"就没有"正文真的多了引用"的证据。

### 4.3 MKB 关键词检索仍有空召回盲区

真实探针：**宁德时代（无行业标签）→ MKB 空；贵州茅台（无行业标签）→ MKB 空**。MKB 检索靠关键词对 title/topic 打分，中文资产名与报告主题（行业年度策略）天然不重合，行业标签缺失时整块为空。本轮 max_chars 修的是"截断切内容"，**没修"检索不到"**——后者需要行业标签管道兜底或按报告类型的结构化方法论通用块。

### 4.4 "所有知识库"字面上的边界

- 05-Excel知识库、06-PPT排版美学按设计排除（工具教学素材，不是分析引用源）——这是合理产品决策，但"调用所有知识库"字面不成立；
- KB 注入预算 1500 字、每类 top-1，意味着 122,422 chunk 中每份报告实际只能带 7 类 × 少量 snippet——这是**有意的相对充分**，不是全量穷举。断言"充分"时应说明这层边界，否则就是夸大。

---

## 5. 本轮改动与回归证据

### 5.1 工作区改动（全部未提交）

```text
M core/knowledge_base.py            # 白名单/均衡检索/中文子串兜底/方法论目录置前
M core/methodology_kb.py            # format_block/build_block 增加 max_chars 块预算
M pipeline/prompt_injectors_p3b.py  # KB 每类 top-1+snippet150；MKB max_chars=2000
M pipeline/section_writer.py        # P0-1 注入解耦 + P0-2 串行路径 KB/MKB
M pipeline/iron_gate.py             # KbCitationChecksMixin import/MRO/注册
M tests/test_prompt_injectors.py    # 契约 45→47 同步
?? pipeline/checks/kb_citation_mixin.py
?? tests/test_kb_citation_coverage.py
?? tests/test_kb_methodology_wiring.py
```

未触碰（按约定不动）：[CODEX_KB_ACCEPTANCE_20260907.md](D:/Claude/projects/2hao-analyst/docs/CODEX_KB_ACCEPTANCE_20260907.md)、[MASTER_REVIEW_AND_KB_PLAN_20260907.md](D:/Claude/projects/2hao-analyst/docs/MASTER_REVIEW_AND_KB_PLAN_20260907.md)、根目录 0 字节 `kb_fts.db`。

### 5.2 验证结果

```text
# 本会话复核（2026-09-07）
pytest test_kb_citation_coverage + test_prompt_injectors + test_r61_iron_gate_migration → 21 passed
pytest test_kb_methodology_wiring                                             → 16 passed
pytest test_multi_search + test_r51 + test_r58 + test_r56_knowledge_absorption
      + test_methodology_rules                                                → 75 passed
ruff check --select=F821,F601,E9（9 个改动/新增文件）                          → All checks passed
```

说明：含 `run_all()` 的测试会真实调用 LLM provider（异源审计检查），网络可达时 ~28s 完成；网络离线时会被 pytest-timeout 拦下并打印线程栈，需在可达网络下复跑。

---

## 6. 达到"充分调用且可证明"的最小下一步

1. **强检查接进 e2e**：在 [e2e_orchestrator.py](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py:1273) `run_all()` 前收集本报告实际注入的 KB/MKB 条数并调用 `set_kb_injection_counts(kb_count, mkb_count)`，把强检查从"只有测试覆盖"变成"每份真实报告都跑"；
2. **观测漏斗（P1-3）**：输出 retrieved / injected / cited 三段指标进 Gate 报告，让"注入 7 条用 1 条"的退化变成可报警的数值；
3. **MKB 召回兜底**：industry_tags 缺失时按 report_type 走结构化白名单方法论词集（估值/三表勾稽/审计复核等），并对召回做类别过滤防噪声（此前实测"债券估值/评级"文档会混入）；
4. **端到端 before/after 对照**：用新代码重跑一份真实报告，对照正文 `[KB#]`/`[MKB#]` 引用数（验收判据建议：KB 引用 ≥ 注入 × 0.5，MKB > 0）；
5. **提交工作区**：先 `git diff -w` 复核真实改动（已知 CRLF 噪声会让 diff 名义膨胀到数千行）。

---

## 7. 一句话

> **Claude 的收尾修复方向真实、测试属实，且 kb_citation 门禁实际上已接线（比它文档里写的更进一步）；本轮又补上了 KB 中文子串兜底与 MKB 块级预算两个真实缺口。但"充分调用所有知识库方法论用于写报告"仍不能回答"是"：强检查没进 e2e、MKB 在无行业标签时仍会整块为空、且没有任何 post-fix 报告产物证明正文消费提升。代码接近修好，证据尚未闭环。**
