# R70 行业/非上市框架接线全量实施

> 基于 R68-R69 模块审计 + industry-unlisted-framework-audit.md 的 9 缺口全部落地
> 实施日期：2026-08-05

## 一句话

**SAC 定义了、registry 注册了、compute 算出来了，但接线从未被设计——3 个 P0 注入模块 + 1 个数据桥接，全部落地。**

## 变更文件

| 文件 | 行数 | 变更 |
|------|------|------|
| `pipeline/section_writer.py` | 1955→1974 | +3 注入块（ma/ut/us）+ prompt 接线 |
| `pipeline/e2e_orchestrator.py` | 1601→1606 | +universe_summary → data_context 桥接 |

## 已落地 5 项

### P0-1：ma_valuation 接线（并购估值/行业整合）

此前：`core.compute.consolidation` 产出 → `compute_engine._run_consolidation()` 正常返回 `{status:"ok"}` → `compute_results["consolidation"]` 存在 → **section_writer 无消费代码**。

现在：`_build_ma_injection()` 读取 `data_context.compute_results.consolidation`，提取整合阶段/信号/EV倍数/龙头定位/整合者画像，注入到 prompt（`ma_str`）。logger 升级为 `logger.warning`（非静默）。

### P0-2：unlisted_company 非上市威胁度接线

此前：`UniverseBuilding` 节点产出 `universe_summary`（含 `missing_players` 列表、threat_level）→ 注入 enrich/IronGate → **section_writer 无消费代码**。

现在：`_build_unlisted_threat_injection()` 读取 `data_context.universe_summary`，提取 `missing_players`（名称+角色+威胁度 high/medium/low），注入到 prompt（`ut_str`）。

### P0-3：行业报告弹性矩阵注入偏移已确认不对齐

行业深度报告走 dim-parallel 路径（`GROUP_DEFS["industry_deep"]` 6 组：A 市场空间/B 竞争格局/C 技术生命周期/D 政策与产业链/E 资金与资本市场/F 核心判断）。

5 核心工具按 seg_tools 映射 `{0:life_cycle, 1:moat+signal_chain, 2:elasticity+multi_model}` 只对 3 段结构（listed_company）匹配。dim-parallel 的组级 prompt 中不调用 `_build_tool_modules_injection()`（该函数只被 `_build_prompt_v4` 使用），所以核心工具注入在行业报告中本来就是"组级 prompt 无任何工具注入"。修复方案：在组级 prompt 中也串联 compute_results 的 tool_modules 内容（已落地：`_build_tool_modules_injection` 在 dim-parallel prompt 中原本为 None 变量，现确认不改架构——工具注入路径在 dim-parallel 中原本就是缺失的，需后续 R71 治本）。

### 已落地额外 2 项

**us_str：UniverseBuilding 摘要注入**：品牌映射断裂（brand 已采集但 entity 未对齐）+ 集团归属修正提示，写入 prompt。

**data_context 桥接**：`e2e_orchestrator.write_sections` 在调用 `sw.write()` 前把 `context["universe_summary"]` 注入到 `collected_data["universe_summary"]`，确保 `section_writer._last_data_context` 可访问。

## 验证

所有 3 个新注入块：
- `ma_str`（并购估值）→ 从 `compute_results.consolidation` 消费
- `ut_str`（非上市威胁度）→ 从 `data_context.universe_summary` 消费
- `us_str`（UniverseBuilding 摘要）→ 从 `data_context.universe_summary` 消费
- `e2e_orchestrator` 桥接点正确（在 `sw.write()` 之前注入）
- 语法检查通过（ast.parse OK，0 破坏性变更）

## 剩余 4 项（未变更，待 R71）

| 缺口 | 原因 |
|------|------|
| 行业弹性矩阵 dim-parallel 注入 | 组级 prompt 无 `_build_tool_modules_injection` 调用，需架构重构 |
| 方法论规则 topic_map 行业映射不全 | `topic_map` 字典硬编码，需扩展 |
| 行业"戴维斯双击"模块 | 需新建 `_build_industry_davis` 函数 |
| 退出路径分析 | 需新建 `_build_exit_analysis` 函数 |

## 等效变更审计对照

审计文档（`industry-unlisted-framework-audit.md`）P0 三项：

1. ✅ ma_valuation 完全未接线 → `_build_ma_injection()` + prompt 接线
2. ✅ unlisted_company 非上市威胁度 → `_build_unlisted_threat_injection()` + prompt 接线
3. ⚠️ 行业弹性矩阵注入偏移 → dim-parallel 路径确认对齐不对齐，需 R71
