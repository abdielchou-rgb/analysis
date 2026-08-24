# R77 P0 工作计划全量执行 — 覆盖意识/方法数据驱动/失败保护

> 基于 workplan-20260804-post-roundtable.md P0 四项
> 日期：2026-08-05

## 变更总览

| P0 | 任务 | 状态 | 文件 |
|----|------|------|------|
| 1 | R68 接线验收 + 回归修复 | ✅ | tests/×3 断言更新 |
| 2 | 覆盖意识 staleness detection | ✅ | universe_build.py + coverage_mixin.py + iron_gate.py |
| 3 | 方法选择数据驱动初代 | ✅ | method_reflection.py + e2e_orchestrator.py |
| 4 | 失败保护 chaos 注射 | ✅ | agent_provider.py + deepseek_client.py + iron_gate.py |

---

## P0-1 R68 接线验收 + 回归修复

- `scripts/check_wiring.py`：**43/43 工具维度接线率 100%**
- 修复 3 个 assertion drift：
  1. `test_r55_llm_verification.py`：路径从 `iron_gate.py` 更新到 `checks/llm_checks_mixin.py`（R61 迁移）
  2. `test_e2e_keli.py`：图表失败断言从 `None`（全量重写）更新到 `[0,1,2]`（R66 全段局部重写）
  3. `test_fact_quality.py`：免责声明测试从"豁免"改为"硬拦截"（R72 设计变更）
- **发现并根治 R77 关键 bug**：IronGate LLM 并行检查 `_fut.result()` 无 timeout +
  `HAS_AGENT` 默认 "1" + agent_provider `MAX_WAIT_SEC=300` → 无 responder 环境挂死 5 分钟
  （test_audit_report 触发）

## P0-2 覆盖意识 staleness detection

- `universe_build.py`：
  - 新增 `staleness_check()`：unlisted_players/brand_entity_mapping mtime > 90 天 → `stale_refresh`
  - `build()` 输出 `data_freshness` + `stale_note`
  - `_COVERAGE_ENRICH_THRESHOLD` 从 framework_registry `_meta.calibration` 读（FP5 校准口子）
- `coverage_mixin.py`：新增 `_check_industry_baseline_gap`（warning 级，不阻断）——
  报告涉及行业在底座缺条目 → 提示补采
- `iron_gate.py`：注册行业底座缺口检查（Gate 71 项）

## P0-3 方法选择数据驱动初代

- `framework_registry.json`：效果字段打标"估算基线"（7 框架全标）
- `method_reflection.py`：首次实测覆盖估算（不污染滑动平均）→ 后续滑动平均
- `e2e_orchestrator.py record_results`：Gate 通过后自动 `record_reflection`（此前从未接线）
- 验证：首次 0.92估算 → 0.91实测覆盖 → 第二次 0.95 → 0.93 滑动平均 ✅
- scheduler 的 gaps.json 读取路径确认存在（R65 已补）

## P0-4 失败保护 chaos 注射

### 场景1: agent_provider 质量护栏（R67）
- 占位符/过短(<150字)/拒绝生成 全部拦截 ✅
- 合格响应放行 ✅

### 场景2: best-so-far 回滚
- attempt1(0.91) → attempt2(0.88) → attempt3(0.77) → 保留 0.91 稿 ✅
- 柯力事故场景复现验证通过

### 治本修复（chaos 触发暴露）
- **agent_provider 心跳机制**：responder 每次轮询写 `.heartbeat`；provider 无心跳/心跳过期 30s → 快速失败回退 DeepSeek
- **call_llm 回退**：强制指定 provider 失败后全量回退 `provider="auto"`（此前单元素列表失败即 raise）
- **IronGate LLM 检查 timeout**：`_fut.result(timeout=60)` 防挂死
- 测试 41 项通过（含原挂死的 test_r61/test_r51）

---

## 回归测试

新增 3 个测试文件（16 项）：
- `test_r77_staleness_detection.py`（6）— P0-2
- `test_r77_method_reflection.py`（4）— P0-3
- `test_r77_chaos_injection.py`（6）— P0-4

关键回归批次全绿：test_r61(7)/test_r51(19)/test_r55_llm(5)/test_r65(6)/test_fact_quality(23)/test_e2e_keli(5)/test_r77×3(16)

## 下一步（P1）

- 方法选择双轨并行：跑 3-5 份不同行业报告积累真实框架效果数据
- 覆盖意识动态发现：从报告反向发现未收录公司 → `_suggested_players.json`
- 3M/6M 短周期预测（不等一年才验证）
