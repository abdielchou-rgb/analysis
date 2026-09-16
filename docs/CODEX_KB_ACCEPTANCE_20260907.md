# Codex KB/方法论深度优化 · 完成情况验收报告

**验收日期**：2026-09-07
**验收对象**：codex 针对"知识库/方法论内容无法细颗粒体现到报告正文"的深度优化
**依据文档**：`docs/MASTER_REVIEW_AND_KB_PLAN_20260907.md`（审计+计划，自称"本轮不改代码，改动留待确认后单独执行"）
**验收方式**：磁盘实测 + git 工作区状态 + pytest 回归
**一句话结论**：**P0 三个"必现 bug"修复已在代码中实现且有专项测试（10 绿），但未提交、P1 消费端门禁未做、且引入 2 个测试契约红（45→47 未同步）——完成度约 60%，属"可修复的未完成"，不是"已完成"。**

---

## 一、验收总表

| 计划项 | 文档定位 | 代码现状 | 判定 |
|---|---|---|---|
| P0-1 KB/MKB 注入与 `_tm_str` 总开关解耦 | 必现 bug | `_assemble_data_injection_tail()` 已抽离，`section_writer.py:2665` 调用，KB/MKB 独立展开 | ✅ 已实现 |
| P0-2 串行写作路径补齐 KB/MKB | 必现 bug | `_kb_mkb_for()` + `_kb_mkb_prompt_tail()` 已建，骨架 prompt（L1299）与串行正文（L1709）均注入 | ✅ 已实现 |
| P0-3 检索白名单修正 + 去重 | 必现 bug | `SEARCH_CATEGORY_ALLOWLIST` 纳入 01/08/09；`_relevant_categories()` 单函数去重 | ✅ 已实现 |
| 专项测试 | — | `tests/test_kb_methodology_wiring.py`（232 行，9 测试函数） | ✅ 10 passed |
| P1-1 检索纪律双通道 | P1 | 未见明确改动（diff 无方法论/数据双通道分离） | ⚠️ 未做 |
| P1-2 引用契约 + kb_citation 门禁 | **P1 最关键的消费端不变式** | `pipeline/checks/` 无 kb_citation_mixin；IronGate 无 KB 引用覆盖检查 | ❌ 未做 |
| P1-3 端到端可观测漏斗 | P1 | 无 kb_usage_metrics | ❌ 未做 |
| P2 Evidence-First / 评测集 / 本地分层 | P2 | 未做（属后续） | ⏸ 预期外 |

---

## 二、P0 修复核实（三处均为真修复）

### P0-1 解耦总开关 ✅
- `_assemble_data_injection_tail(_tm_str, ev_str, ..., kb_str, mkb_str)`——KB/MKB 与工具模块块各自独立判空展开，不再被 `if _tm_str` 整体吞掉。
- 专项测试 `test_tail_injects_kb_mkb_when_tool_modules_empty` 直接覆盖"tool_modules 空但 KB/MKB 仍注入"场景。

### P0-2 串行路径补齐 ✅
- `_kb_mkb_for()` 复用与并行路径同一对检索函数 `_inj_kb_str/_inj_mkb_str`（杜绝两套实现），上限对齐（kb 1500/mkb 2000）。
- 两个注入点：骨架 prompt（`_build_skeleton_prompt`，L1299）+ 串行正文（`_build_prompt_v4` 附近 L1709）。
- 专项测试 `test_build_prompt_v4_includes_kb_mkb` / `test_build_skeleton_prompt_includes_kb_mkb` 覆盖。

### P0-3 白名单修正 ✅
- allowlist 现为：01-宏观分析框架、02-行业与公司研究、03-估值与测算、04-回测基线库、07-原始文档提取、**08-四大审计方法论、09-国际投行方法论**（08/09 已纳入，05/06 教学类维持排除）。
- 三段复制粘贴代码收敛为 `_relevant_categories()` 单函数。
- 专项测试 `test_relevant_categories_allow_methodology_dirs` 覆盖。

---

## 三、发现的问题（未完成项，按严重度）

### 🔴 R1：测试契约红——注册表 45→47 未同步（CI 会失败）

- `pipeline/prompt_injectors.py` `INJECTORS` 现 47 项，但 `tests/test_prompt_injectors.py` 硬编码 `len == 45`（两处）。
- 实测：`test_registry_returns_all_contract_keys` 与 `test_broken_data_does_not_crash` **失败**（assert 47 == 45）。
- 根因：新增 2 个注入器键（推测含 engine_ib 相关）后未更新契约测试期望——codex 加功能时漏改守护测试。
- 修复：把两处 `45` 更新为 `47`（先确认 47 是预期值而非多注册了幽灵键）。

### 🔴 R2：改动未提交（工作区 4 个 ` M` + 1 个 `??`）

- `core/knowledge_base.py`、`core/methodology_kb.py`、`pipeline/prompt_injectors_p3b.py`、`pipeline/section_writer.py` 为 ` M`；`tests/test_kb_methodology_wiring.py` 为 `??`。
- 即 codex 的 KB 优化**全部躺在工作区未 commit**——`git log` 无对应提交。
- 风险：与后续并行改动混在一起难回滚；若工作区被清，工作丢失。

### 🟡 R3：真实报告产物未见提升（需重跑才见效）

- `output/贵州茅台_cicc.md` 与 `_gate_check.md` 仍是 **KB 引用 1 处 / MKB 0 处**（文档审计时的旧值）。
- 原因：修复在**注入侧**，已生成的报告是修复前产物；需用新代码重跑报告才能验证"正文 KB/MKB 体现率"是否真的提升。当前**没有端到端证据**证明 P0 修复实际改变了正文行为。

### 🟡 R4：P1-2 引用契约门禁缺失（文档自认"最关键的消费端不变式"）

- 文档 P1-2 明确提出"注入非空 → 正文引用 ≥ 一定比例 → 否则告警/阻断"，但代码中无 `kb_citation_mixin`、无 `[KB#]` 覆盖率检查。
- **后果**：即使 P0 修复让 KB 注入成功，仍无门禁保证 LLM 真的在正文用了它——"注入成功 ≠ 消费成功"的盲区仍在。这是整套优化里防止回退的最后一环，未做意味着**无法证明"修好了且不回退"**。

### 🟡 R5：section_writer diff 巨大但真实改动小（噪声掩盖）

- 工作区 diff：section_writer.py 名义 +7374/-（numstat 3732/3642），但 `git diff -w`（忽略空白）后仅 **+108/-18**。
- 说明大量 diff 是行尾空白/重排噪声，真实逻辑改动集中在 KB/MKB 注入点。建议提交前做 `git diff -w` 审查 + 避免空白噪声污染（可配 `.gitattributes` 或统一行尾）。

---

## 四、验证记录

```text
# KB 专项测试（10 用例全绿）
pytest tests/test_kb_methodology_wiring.py → 10 passed

# KB 相关邻域测试（49 passed, 2 failed —— 2 个失败是 45→47 契约未同步）
pytest test_kb_methodology_wiring + test_methodology_rules
     + test_prompt_injectors + test_prompt_injection_redteam
     → 2 failed (test_prompt_injectors 契约), 49 passed

# git 状态（未提交）
 M core/knowledge_base.py  M core/methodology_kb.py
 M pipeline/prompt_injectors_p3b.py  M pipeline/section_writer.py
 ?? tests/test_kb_methodology_wiring.py

# allowlist（08/09 已纳入）
SEARCH_CATEGORY_ALLOWLIST = (01-宏观…02-行业…03-估值…04-回测…07-原始…08-四大审计…09-国际投行)
```

---

## 五、完成度评估

| 维度 | 完成度 | 说明 |
|---|---|---|
| P0 注入三硬伤修复 | ✅ 100% | 代码 + 专项测试全绿 |
| 专项测试 | ✅ 100% | test_kb_methodology_wiring 10 绿 |
| 测试回归无红 | ❌ | 2 个 prompt_injectors 契约红（45→47） |
| 提交入库 | ❌ | 4 M + 1 ?? 全在工作区 |
| P1 消费端门禁 | ❌ 0% | kb_citation / 观测漏斗均未做 |
| 端到端正文验证 | ❌ | 报告产物为旧逻辑，无重跑证据 |

**总完成度 ≈ 60%**：P0（修复注入侧）做完且有测试，但 P1（保证消费 + 防回退）没做，改动未提交、测试契约未同步——**处于"可验收前一步"，不是"已完成"。**

---

## 六、建议的收尾动作（按序）

1. **修复测试契约红**：确认注册表 47 键是预期值 → 更新 `test_prompt_injectors.py` 两处 `45→47`（先 diff 确认新增的 2 个注入器不是幽灵键）。
2. **全量回归**：跑 `pytest tests/test_prompt_injectors.py tests/test_kb_methodology_wiring.py` 确认绿。
3. **补 P1-2 最小版**：加 `[KB#]`/`[MKB#]` 引用覆盖检查（注入非空时正文回指比例，warning 起步）——这是防回退的关键，工作量 ~半天。
4. **提交**：对 5 个文件 `git add` + 语义化 commit（`feat(kb): methodology KB injection decoupled from tool_modules + serial-path KB/MKB + allowlist fix`），提交前用 `git diff -w` 复核真实改动。
5. **端到端验证**：重跑一份真实报告，确认正文 `[KB]` 引用数 > 修复前（1 处），作为 P0 生效的证据。
6. **P1-3 观测漏斗**（可选下轮）：输出 kb_retrieved/injected/cited 指标进 Gate 报告。

---

## 七、一句话验收结论

> **codex 把计划里的 P0 三处"必现 bug"真正修了（注入解耦 + 串行补齐 + 白名单修正），专项测试也写了且绿——这是真干活，不是纸面计划。但活没干完：P1 的"消费端引用门禁"（防回退的关键一环）没做、改动全在工作区未提交、还把 prompt_injectors 的契约测试弄红了（45→47 未同步）。当前状态是"60% 完成、可快速收尾"，距离"验收通过、证明 KB 方法论细颗粒落地"还差：同步测试 + 提交 + 补引用门禁 + 重跑一份报告拿到正文引用数提升的证据。**
