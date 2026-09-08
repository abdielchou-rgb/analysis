# 2hao-analyst 工作总结 — 2026-09-07

## 本次会话完成的工作

### 1. 知识保留率审计与修复

**问题**：24 个引擎方法论注入器在真实管线上 100% 空转——引擎算了但报告从未引用。

**根因**：`e2e_orchestrator.py` 的 `write_sections` 节点只把 `collected_data` 传给 `section_writer`，但 `compute_results` 在 context 顶层，未并入 `collected_data`。

**修复**（commit `3160714`）：
- `engine_bridge.py`：`current_price` 从 `0.0` 改为 `None`（pydantic 校验 `gt=0` 不允许 0.0）
- `e2e_orchestrator.py`：`write_sections` 把顶层 `compute_results` 并入 `_write_dc`
- `e2e_orchestrator.py`：scenario anchor 从 `None` 改为 `None or 0.0`（`base_price` 非 Optional）

**验证**：engine_ib ok，fair_value=1571.39，IronGate 0.85，172 tests passing。

### 2. Codex KB 审查集成

**问题**：Codex 代码审查发现 P0 级行业标签不统一、P1 MKB retrieved 指标缺失。

**修复**（commit `78379e4`）：
- `prompt_injectors_p3b.py`：新增 `_industry_tags_for()` 统一回退链（biz_model → chart_data → universe_summary → 空）
- `section_writer.py`：P1-3 注入观测从 except 内移到成功路径
- `e2e_orchestrator.py`：`_record_kb_injection_metrics` 确保异常后仍记录

**验证**：224 tests passing。

### 3. KB Retrieved 间隙闭环

**问题**：KB/MKB 检索到但注入量为零时，Gate 只跑弱检查。

**修复**（commit `5a6b97e`）：
- `prompt_injectors_p3b.py`：`_inj_kb_str` / `_inj_mkb_str` 注入前记录 `kb_retrieved_count` / `mkb_retrieved_count`
- `section_writer.py`：双通道诊断日志（写作侧实测注入条数 vs 注入器检索条数）

**验证**：224 tests passing。

### 4. Pipeline 加速分析

产出 7 份分析文档，从原始 10-cut 分析逐步迭代到 Cache-Revised 版本：

| 文档 | 核心结论 |
|---|---|
| `PIPELINE_ACCELERATION_ANALYSIS_20260907.md` | 原始 10-cut：131s→59s，54.9% 提速 |
| `PIPELINE_ACCELERATION_HONEST_ASSESSMENT_20260907.md` | 诚实评估：真正"加速"的只有 P0-1a 超时 |
| `PIPELINE_ACCELERATION_UPGRADED_20260907.md` | 升级 5-cut：分层超时+稳定前缀+级联熔断 |
| `PIPELINE_ACCELERATION_BEYOND_UPGRADED_20260907.md` | Prompt caching 是 ROI 最高的优化 |
| `PIPELINE_ACCELERATION_CACHE_REVISED_20260907.md` | DeepSeek 缓存经济学修正（strict prefix match，30-120x） |
| `PIPELINE_ACCELERATION_BEYOND_CACHE_REVISED_20260907.md` | 三种缓存持久化路径 + 交错扇出 |
| `QUALITY_SPEED_MASTER_20260907.md` | 质量-速度双层框架 |

### 5. P0-1a：research_planner 超时

**问题**：6 路并行 LLM 调用无独立超时，单维度卡死拖死整轮。

**修复**（commit `e63375f`）：
- `core/deepseek_client.py`：`call_llm` / `call_deepseek` 新增 `timeout` 参数（向后兼容）
- `pipeline/research_planner.py`：`_llm_generate_questions` 30s 超时 + `fallback_count` 观测

### 6. P0-2a：子步骤 Profiling

**修复**（commit `e63375f`）：
- `section_writer.py`：`[SELF-HEAL][PROFILE]` timing + recovered/failed 计数
- `e2e_orchestrator.py`：`[VALIDATE][PROFILE]` breakdown（pre_gate/iron_gate/intent_gate）
- `e2e_orchestrator.py`：`[DATA][PROFILE]` breakdown（primary/fallback）
- `e2e_orchestrator.py`：`[RECORD][PROFILE]` breakdown（import/bold_calls）

### 7. P0-3：确定性节点墙钟预算

**修复**（commit `e63375f`）：
- `core/settings.py`：新增 `data_node_budget_s()`、`validate_node_budget_s()`、`record_node_budget_s()`
- `pipeline/agent_graph.py`：`AgentGraph.run()` 新增 `node_timeout_s` 参数，`ThreadPoolExecutor` + `future.result(timeout)`
- `pipeline/e2e_orchestrator.py`：data / validate / record_results 节点传入 `timeout_s`

### 8. Evidence-Grounded Writing + Delta-Only Rewrite（本次核心交付）

**问题**：报告质量的真正来源是 planning + evidence grounding，不是后置门禁。当前 writer 拿到全量 KB 盲注，rewrite 时把全文 20K 发给 LLM 重写。

**方案**：web 研究驱动（EVIREPORT / WebWeaver / DualGraph / Deep-Reporter），零语义风险实现。

**修改文件**：

| 文件 | 改动 |
|---|---|
| `pipeline/research_planner.py` | 新增 `_DIM_MKB_KEYWORDS`（20 个维度→关键词映射）、`_build_dim_kb_map()`（为每个维度预检索 MKB 条目）；`plan()` 输出新增 `dim_kb_map` |
| `pipeline/section_writer.py` | `write()` 读取 `_dim_kb_map`；新增 `_mkb_for_group()` 方法（按组维度过滤 MKB）；`_write_group` 用过滤后的 `_group_mkb` 替代全局 `mkb_str` |
| `pipeline/e2e_orchestrator.py` | `research_plan` 节点把 `dim_kb_map` 写入 `collected_data`；`rewrite_sections` 新增 Delta-Only Rewrite（提取失败维度→查 KB→精准注入）；新增 `_locate_failed_dims()` 和 `_build_dim_kb_hints()` |
| `tests/test_evidence_grounded.py` | 新建 11 个测试用例 |

**工作原理**：
```
planner: dim_kb_map = {valuation: [MKB条目A,B], risk: [MKB条目C]}
         ↓ 注入 collected_data
writer:  每组只注入该组维度对应的 MKB 条目（不再全量盲注）
         ↓ Gate 检查
rewriter: 失败维度 → 查 dim_kb_map → 只给该维度的 KB 条目作为重写证据
```

**验证**：11 新测试 + 27 已有测试全部通过，3 个模块导入正常。

---

## 当前状态

- 所有修改未提交（3 modified + 2 new files in test, 1 new test file）
- 已有测试全通过（pre-existing test_r78_data_contract.py import error 不是本次引入）
- `kb_fts.db` 是运行时生成的 FTS 索引，不纳入提交

## 下一步

1. 提交 Evidence-Grounded Writing + Delta-Only Rewrite
2. 集成 smoke test：跑一次完整 e2e pipeline 验证端到端效果
3. 考虑 B-track 加速：cascade 反转（草稿降档）+ 交错扇出缓存命中
4. 考虑质量门升级：方法论应用深度检查（框架间交叉验证）
