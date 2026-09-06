# P0-2 修复报告：write_sections 段级耗时 profile

**日期**：2026-09-07
**依据**：`docs/PROFILE_BOTTLENECK_ANALYSIS_20260907.md`（真实日志：write_sections 中位 107s / max 2502s，为第二瓶颈）
**验证口径**：ruff correctness gate + pytest（新增 4 用例）+ 相关回归 60 passed

---

## 一、改动内容（纯增量观测，不改写行为）

`pipeline/section_writer.py` `_write_dimension_parallel`（默认写路径）加**组级耗时计时**：

1. **单组计时**：`_write_group` 起始 `perf_counter`，完成时 `_group_times[gname] = ...` 并打日志
   `[DIM-PARALLEL][PROFILE] 组 X 写完: 12.3s (1832字)`。
2. **组级汇总**：全部组写完输出 `[DIM-PARALLEL][PROFILE] 组级总耗时 Xs | 最慢组: A=120s, B=80s, ...`（top5）。
3. **慢段告警**：最慢组 ≥ `SLOW_GROUP_THRESHOLD_S`（默认 30s）→ warning"慢段候选, 下轮可对该组降档/换 provider"。
4. 模块级 `from time import perf_counter as _perf_counter`。

`core/settings.py` 新增 `slow_group_threshold_s()`（env `SLOW_GROUP_THRESHOLD_S`，默认 30s，下限 5s）。

**不改行为**：不缓存、不改 provider、不跳过任何组——只让"哪个段慢"第一次可见。真实 PROFILE 只能告诉我们 write_sections 整体慢；要定位**是哪一组**拖到 107s/2502s，必须组级计时。这是 P0-2 的全部目的——为后续"慢段降档"提供数据。

---

## 二、守护测试（4 个，全绿）

| 用例 | 断言 |
|---|---|
| `test_slow_group_threshold_default` | settings 默认 30s |
| `test_slow_group_threshold_env_override` | env `SLOW_GROUP_THRESHOLD_S=12` → 12s |
| `test_section_writer_group_timing_injected` | 源码含 4 处计时注入点（总起点/单组/汇总/完成日志），防误删 |
| `test_section_writer_imports_clean` | 模块可导入（改动不破坏加载） |
| `test_merge_timing_injected`（P0-2b） | merge 调用处含计时起点 + `[EDITOR][PROFILE] merge 耗时` + ≥15s 告警 |

---

## 三、验证

```
ruff --select=F821,F601,E9 pipeline/section_writer.py core/settings.py → All checks passed
pytest test_write_sections_profile + test_research_planner_budget + test_deep_audit_fixes
     + test_ssot_single_writer + test_r53_deep_fix + test_engineering_plan
     → 60 passed, 0 failed
```

---

## 四、下一步（需真实环境）

P0-2 的**观测已就位**，但"哪个组最慢"需要一次真实运行才能回答。建议在真实 API key 环境跑一份报告后：
1. 读 `[DIM-PARALLEL][PROFILE] 组级总耗时` 行 → 得到最慢组名 + 耗时。
2. 对最慢组（≥30s 告警触发）做**降档**：组级 provider 覆盖（该组走本地/免费草稿 → deepseek 精修），或降低该组 `max_tokens`/简化 prompt。
3. 若组级看不出问题（所有组都快但总时长仍高），再查 **merge 编辑**耗时（`_editor_merge`）——那是维度并行之后又一个串行段。

配置杠杆已就绪：`SLOW_GROUP_THRESHOLD_S` 可调告警阈值；后续"慢段降档"可复用 route_policy 的 `NODE_PROVIDER_*` 或新增 `GROUP_PROVIDER_<组名>` 覆盖。

---

## 五、一句话

**write_sections 的段级 profile 已注入——现在每一组写完都会上报耗时、汇总打印最慢组、≥30s 告警"慢段候选"。观测是定位"哪个组拖到 107s/2502s"的前提；下一步在真实环境跑一版，读 `[DIM-PARALLEL][PROFILE]` 行，对最慢组做降档。**
