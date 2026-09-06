# P0-1 修复报告：research_planner LLM 预算熔断

**日期**：2026-09-07
**依据**：`docs/PROFILE_BOTTLENECK_ANALYSIS_20260907.md`（424 行真实日志：research_planner 中位 155s / p90 1219s，为第一瓶颈）
**验证口径**：ruff correctness gate + pytest（新增 6 用例）+ 回归 53 passed

---

## 一、根因

`pipeline/research_planner.py` `question_tree_v2` 用 `ThreadPoolExecutor(max_workers=6)` 并行调 deepseek 为各维度生成研究问题，但**没有任何共享时间预算**——6 路并行下若 deepseek 慢/超时，每维度独立等待、最坏累计可达 1219s（20 分钟）。且 `e2e_orchestrator.py` 两处注释写"零 LLM"，与实现严重不符（掩盖了这里有 LLM 调用的事实）。

---

## 二、改动

| 文件 | 改动 |
|---|---|
| `pipeline/research_planner.py` | `question_tree_v2` 新增 `llm_budget_s` 共享总预算：`wait(FIRST_COMPLETED)` 有界等待循环，预算耗尽即 break、未完成维度回落 v1 模板；`_process_dim` 对 LLM 异常加 try/except 防御；`pool.shutdown(wait=False)` 关键修正（避免 `with` 的 wait=True 让熔断形同虚设）；结果按原 dims 顺序确定性输出 |
| `core/settings.py` | 新增 `research_llm_budget_s()`（env `RESEARCH_LLM_BUDGET_S`，默认 45s，下限 5s） |
| `pipeline/e2e_orchestrator.py` | 两处"零 LLM"假注释纠偏（L478 节点 docstring + L2122 图注册注释）→ 明示"LLM 生成 + 共享预算 + 模板回退" |
| `tests/test_research_planner_budget.py` | **新增** 6 用例 |

**行为语义**：每轮 research_planner 的 LLM 问题生成总耗时被硬性限制在 ~`llm_budget_s`（默认 45s）；超时未完成的维度自动用 v1 模板补齐，**不丢维度、不崩管线**。有 key 时正常走 LLM；无 key / `use_llm=False` 全模板（原有 fallback 保留）。

---

## 三、守护测试（6 个，全绿）

| 用例 | 断言 |
|---|---|
| `test_no_key_goes_template` | 无 DEEPSEEK_API_KEY → 全模板、不触发 LLM、维度顺序确定 |
| `test_use_llm_false_goes_template` | `use_llm=False` → 模板且含有效问题 |
| `test_budget_elapsed_falls_back_template` | 慢 LLM(10s) + 预算 0.1s → **耗时 <8s 快速返回**、4 维齐全、无 LLM 源 |
| `test_llm_success_kept` | LLM 正常 → source=llm、问题保留 |
| `test_llm_failure_falls_back_template` | LLM 抛异常 → 回落模板、不崩 |
| `test_settings_budget_available` | `research_llm_budget_s() ≥ 5.0` |

---

## 四、验证

```
ruff --select=F821,F601,E9 (core pipeline web export scripts harness) → All checks passed
pytest test_research_planner_budget + test_deep_audit_fixes + test_ssot_single_writer
     + test_outcome_vocab_unified + test_prediction_contract → 53 passed, 0 failed
```

---

## 五、预期收益与后续

- **预期**：每轮端到端省 ~100-150s（research_planner 中位 155s → 预算上限 45s + 模板补齐），消除 20 分钟级最坏情形。
- **后续 P0-2**：write_sections 段级 profile（定位单段最慢 + 自愈重试热点）——真实第二瓶颈（107s 中位 / max 2502s），需要段级耗时日志，待真实环境跑一版后实施。
- 配置：可用 `RESEARCH_LLM_BUDGET_S` 调预算；默认 45s 是保守起点，profile 后可视真实分布下调。

---

## 六、一句话

真实 profile 数据驱动：**research_planner 的 155s 中位/20min 极值来自"每维度独立无限等 LLM、无共享预算"，本轮加 45s 总预算熔断 + 模板兜底，并修正两处掩盖真相的"零 LLM"注释**——先证伪假设、再对症下药，而不是给 1.5s 的 charts 写缓存。
