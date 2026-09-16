# 二号分析师 · KB/方法论"充分调用"全量推进执行报告

> 日期：2026-09-07
> 依据：[CODEX_SELF_AUDIT_20260907.md](D:/Claude/projects/2hao-analyst/docs/CODEX_SELF_AUDIT_20260907.md) §6 最小下一步
> 范围：知识库/方法论"检索→注入→正文消费→门禁防回退"链路闭环
> 验证方式：真实库只读探针 + pytest 回归 + ruff + 无网络 e2e 夹具

---

## 0. 一句话结论

**§6 的 1-3 已实现并附回归测试；第 4 项"真实报告 before/after 对照"未硬跑（单份 5-15 分钟且消耗 LLM 额度，用真实库探针 + 无网络 e2e mock 夹具覆盖了运行时接线）；第 5 项 git 提交按既有约定不做。**

全量推进过程中发现并修复了一个**上一轮自己埋下的真 Bug**：P1-3 观测写入块连同 `context["report_text"] = text` 被误缩进到 `except RuntimeError` 内 `raise` 之后，成为不可达死代码——若不加审计，强检查将永远只跑弱检查，而文档却声称已接线。

---

## 1. 完成度对照（§6 五项）

| §6 项 | 内容 | 状态 | 证据 |
|---|---|---|---|
| 1 | 强检查接进 e2e | ✅ 完成（含修 Bug） | [e2e_orchestrator.py](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py:27) 抽取 `_record_kb_injection_metrics`，[L810](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py:810) 在成功路径调用；validate 在 [L1290](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py:1290) 读 context → `set_kb_injection_counts` → `run_all()` |
| 2 | 观测漏斗 retrieved/injected/cited | ✅ 部分完成 | injected 为**截断后实际注入条数**（`_count_injection_blocks` 与写作 `[:1500]/[:2000]` 同口径，防虚报）；Gate 报告 check details 含"注入KB/MKB、正文KB标记、方法论词、覆盖率"；**retrieved（截断前命中数）未单独跟踪**，见 §5 |
| 3 | MKB 无标签兜底 + 噪声过滤 | ✅ 完成 | [methodology_kb.py](D:/Claude/projects/2hao-analyst/core/methodology_kb.py:42) `_TYPE_FALLBACK_TERMS`、[L21](D:/Claude/projects/2hao-analyst/core/methodology_kb.py:21) `_NOISE_TITLE_TERMS`、类别惩罚；真实库探针见 §4 |
| 4 | 端到端 before/after 真实报告 | ⚠️ 未硬跑 | 单份 5-15 分钟 + LLM 成本；无网络 e2e 夹具 mock LLM 已走通真实 write_sections 成功路径（6 passed） |
| 5 | 提交工作区 | ⛔ 按约定不做 | 不 git add/commit/branch/PR；改动保留在工作区 |

---

## 2. 关键发现：上一轮接线是死代码（必须记录）

上一轮在 [e2e_orchestrator.py](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py) 的 `write_sections` 中追加 P1-3 观测写入时，把代码块放进了 `except RuntimeError` 处理器内、**第二个 `raise` 之后**：

```python
except RuntimeError as e:
    ...
    raise
    context["report_text"] = text      # ← 死代码（上一轮误缩进）
    context["kb_injection_metrics"] = {...}  # ← 死代码：永远不执行
```

后果：`kb_injection_metrics` 恒为空 → validate 的 `set_kb_injection_counts(0, 0)` → 每份真实报告门禁都只走弱检查，"注入 7 条只用 1 条"的退化永远不报警。

**为何审计时容易被漏掉**：`git diff -w` 忽略纯空白变化，把"整块被缩进进 except"显示成上下文而非改动；只有逐行核对缩进 + AST 检查才能发现。

**修复**：抽出模块级小函数 [_record_kb_injection_metrics](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py:27)，在 `try/except RuntimeError` 之后的成功路径调用（[L807-810](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py:807)），并把 `context["report_text"] = text` 恢复到 HEAD 原本的正确位置。

---

## 3. 本次改动清单（相对上一轮新增）

| 文件 | 改动 | 作用 |
|---|---|---|
| [pipeline/e2e_orchestrator.py](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py:27) | 新增 `_record_kb_injection_metrics` + 成功路径调用；修复 except 死代码缩进 | 强检查真正进入每份报告的门禁 |
| [tests/test_kb_full_push_telemetry.py](D:/Claude/projects/2hao-analyst/tests/test_kb_full_push_telemetry.py) | +2 测试（共 9） | helper 功能回归 + **AST 结构回归**（防"观测调用再被插进 except 死区"） |
| [tests/test_kb_methodology_wiring.py](D:/Claude/projects/2hao-analyst/tests/test_kb_methodology_wiring.py) | 清理 3 处 F401 | ruff 默认规则全绿 |

上一轮已完成、本次审计复核并实测的改动（未重复提交给代码库）：

- [section_writer.py](D:/Claude/projects/2hao-analyst/pipeline/section_writer.py:167) `_count_injection_blocks`（与截断同口径）；[L228](D:/Claude/projects/2hao-analyst/pipeline/section_writer.py:228) `_kb_mkb_for` 记录 metrics；并行路径 [L2489](D:/Claude/projects/2hao-analyst/pipeline/section_writer.py:2489) 同步统计
- [methodology_kb.py](D:/Claude/projects/2hao-analyst/core/methodology_kb.py:147) `select_entries` 支持 `filter_noise` + 类别惩罚；[L207](D:/Claude/projects/2hao-analyst/core/methodology_kb.py:207) `build_block` 块级预算
- [prompt_injectors_p3b.py](D:/Claude/projects/2hao-analyst/pipeline/prompt_injectors_p3b.py) `_inj_mkb_str` 无标签兜底走 `_TYPE_FALLBACK_TERMS` + `filter_noise`

---

## 4. 验证证据

### 4.1 pytest 回归（全绿）

```text
tests/test_kb_full_push_telemetry.py                     → 9 passed
tests/test_kb_methodology_wiring.py + test_prompt_injectors.py
  + test_kb_citation_coverage.py + test_r61_iron_gate_migration.py → 37 passed
tests/test_multi_search.py + test_r51 + test_r58 + test_r56_knowledge_absorption
  + test_methodology_rules.py                            → 75 passed
tests/test_e2e_no_network.py + test_export_gate_reuse.py → 6 passed（真实 e2e 节点 mock LLM）
---------------------------------------------------------
合计 127 passed
```

另：依赖 e2e/section_writer 的 14 个历史测试文件 `--collect-only` 103 项收集无 import/签名断裂。

### 4.2 ruff

```text
ruff check（默认规则 + F821/F601/E9）对 11 个改动/新增文件 → All checks passed
```

### 4.3 真实库只读探针（2026-09-07）

贵州茅台 / listed_company / 无行业标签：

```text
KB 注入：1319 字 ≤ 1500，7 个来源全部命中（块首 = 四大审计方法论/国际投行方法论/宏观分析框架）
MKB 兜底：1761 字 ≤ 2000，5 条整条命中（DCF 非上市/寿险估值思辨/互联网公司估值/传媒估值/风投估值）
噪声扫描：债券/利率/央行/缩表/基金持仓/流动性观察 → 0 命中
writer metrics：_kb_injection_metrics = {"kb_count": 7, "mkb_count": 5}
```

修复前同一场景（自审报告 §4.3）：**茅台/宁德无标签 → MKB 整块为空**；噪声实证 `backtest_gold` 的"债券估值/基金持仓"曾混入。

---

## 5. 诚实口径：完成度边界

1. **强检查 severity 仍为 `warning`**（可报警、不阻断），与计划"warning 起步"一致；若基线稳定后可把 [kb_citation_mixin.py](D:/Claude/projects/2hao-analyst/pipeline/checks/kb_citation_mixin.py) 调用方 mode 切 `error`。
2. **"retrieved"段未单独成指标**：当前 injected = 截断后可见 `[KBn]/[MKBn]` 计数，能防"块尾被切却虚报"；检索命中总数（注入前）不落 Gate 报告。若要完整三段漏斗，需在 `_inj_kb_str/_inj_mkb_str` 返回命中数。
3. **未跑真实报告 before/after**：无 post-fix 产物仍成立。代码层条件已具备（接线 + 计数 + 门禁细节都真跑过），只差一次 5-15 分钟的实跑。
4. 05-Excel / 06-PPT 目录按设计排除（沿用自审报告 §4.4 口径），"调用所有知识库"字面仍不成立。
5. 兜底 5 条是**估值/财务方法论通用弹药**（宁缺毋滥），与个股特异性无关；这是设计取舍，不是缺陷。

---

## 6. 一句话

> **§6 推进完成：强检查接线被证实上一轮是死代码并已修复（AST 回归钉死）；MKB 无标签兜底 + 噪声过滤经真实库探针确认从"空块/噪声"变成 5 条干净估值方法论；127 项测试与 ruff 全绿。仍欠的只有一次真实报告重跑做 before/after 产物证据。**
