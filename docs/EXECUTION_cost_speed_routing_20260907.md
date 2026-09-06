# 成本/速度/路由决策 · 执行报告（如实版）

**日期**：2026-09-07
**依据**：`docs/DECISION_cost_speed_routing_20260907.md` 落地项
**重要前提**：全量执行前对 e2e 主循环做了代码级侦察，发现**决策清单里的大部分机制其实已经在代码中存在**（stall / semantic early-stop / circuit-break / best_so_far / 局部修订 / checkpoint / data 缓存）。因此本报告如实区分「已存在 / 本次改动 / 不应盲改」三档，避免为改而改引入回归。

---

## 一、侦察结论：决策清单的真实落地状态

| 决策项 | 代码现状（实测） | 判定 |
|---|---|---|
| ① Gate 过线为主闸 + 两轮提升停止 | e2e L2243 `result.passed and ig_passed → return`；已有 best_so_far（L2360）、semantic early-stop（相似度>0.90 即停，L2393）、STALL 连续3轮同失败终止（L2316）、circuit-break 同失败项 N 次转全量重写（L2330） | ✅ **已存在且更细** |
| ② 计算层 data-hash 缓存 | data 节点有 `_data_cached` 复用（L220）；compute/chart/enrich/cross_validate **无** hash 缓存，attempt 轮确会重跑 | ⚠️ **真缺口**（本次未盲改，见 §三） |
| ③ 开 `LLM_RESPONSE_CACHE=1` | settings `llm_response_cache()` 默认关；deepseek_client L325 注释**明确警告**："写作修订循环依赖同 prompt 不同轮的采样差异，全局开启会破坏 repair/STALL 语义" | ❌ **危险建议，否决全局开** |
| ④ 本地短任务路由 | route_policy 已支持 `NODE_PROVIDER_<节点>` env 覆盖 + extract 走 openrouter；本地 ollama 自动探测已注册 | ✅ 代码已就绪（配置问题） |
| ⑤ 调研节点分级 | 需先跑真实 [PROFILE] 才能分级 | 方法论，未到代码 |
| ⑥ provider 冲突修复（SSOT） | route_policy L25 注释"opencode_go 已损坏"与 smart_router（priority=1 免费主力）、deepseek_client 注释**矛盾** | ✅ **本次修复** |
| ⑦ 先 profile 再动刀 | — | 方法论，前置 |

**核心发现**：e2e 写改循环的收敛机制（stall/early-stop/circuit-break/best_so_far）**比决策文档设想的更完善**——这份决策记录的"慢的根因"判断部分基于过时代码印象。真正能安全落地的只有 SSOT 注释修复；其余要么已存在、要么需要真实运行验证、要么是危险建议。

---

## 二、本次实际改动

| 文件 | 改动 | 验证 |
|---|---|---|
| `pipeline/route_policy.py` | 修正 L25 过时注释：从"opencode_go 已损坏，写作切 zhipu"改为指向 smart_router 为事实源、说明质量红线节点显式 pin deepseek 的**真实理由**（付费保底，非损坏）；各节点行内注释同步去"429 兜底"误导 | py_compile OK；`resolve_provider` 实测：write/merge/revise/gate_review/skeleton→deepseek、extract→openrouter、fallback→opencode_go（符合 smart_router priority=1） |

**无测试新增**：本改动是纯注释纠偏 + 路由行为本已正确（实测确认），不改变任何运行时行为，故不加行为测试——加测试反而是测"注释没写错"，无价值。守卫由既有 `test_route` 类（若存在）覆盖。

---

## 三、明确不做 / 不建议盲改的项（含理由）

1. **❌ 全局开 `LLM_RESPONSE_CACHE=1`（决策③）**——deepseek_client 源码注释已给出反对理由：修订循环依赖轮间采样差异，全局缓存会返回同一份失败输出，**破坏 repair/STALL 语义，可能造成死循环**。正确姿势是仅对**确定性短任务**（extract/分类/标题）选择性开，且需 profile 确认哪些节点 prompt 完全确定后再配 `LLM_RESPONSE_CACHE=1` + 节点级白名单——**不能全局开**。
2. **⚠️ 计算层 data-hash 缓存（决策②）**——是真缺口，但改 compute/chart/enrich/cross_validate 四处 + attempt 循环属**核心管线大改**，且本环境无真实 LLM key、无法端到端验证；盲改违反"无测试不交付、无根因不修复"。正确路径：先在真实环境跑一版 [PROFILE] 确认 compute 重跑确实是 top 耗时（决策⑦），再针对性加 hash 缓存并配回归测试。
3. **重写停止策略（决策①）**——已存在且比文档设想更细（stall 看"失败项不变"、early-stop 看"内容不变"、circuit-break 看"单失败项修不好"、regression 看"分数退化"）；不需要再加一层"两轮提升<ε"，那会与既有机制重叠。

---

## 四、剩余可执行路径（需真实环境）

1. **跑一版 [PROFILE] 真实报告** → 确认 attempt 轮耗时分布（决策⑦，一切的前提）。
2. profile 证实 compute 重跑是瓶颈后 → 加 **data-hash 增量缓存**（chart/compute/enrich 按 collected_data hash 跳过），配回归测试。
3. 若确需本地短任务 → 配 `NODE_PROVIDER_EXTRACT=ollama_local` + 小样本对比 Gate 失败率（决策④，配置非代码）。
4. 调研节点分级（决策⑤）→ 在真实调研任务上区分"开放探索 vs 有限提取"，再定 Kimi/DeepSeek 分工。

---

## 五、结论

**全量执行遇阻的原因是：决策文档基于部分过时的代码印象写成——e2e 实际已有完善的收敛机制，且"全局开响应缓存"是与源码注释直接冲突的危险建议。** 本次如实落地了唯一安全项（route_policy SSOT 注释纠偏），并明确拒绝了两项高风险/危险改动，把真正需要做的事（data-hash 缓存）正确挂到 profile 之后。

这不是"没执行"，而是**执行前做了侦察、避免把已经存在的机制重造一遍、避免采纳会破坏管线的建议**——与本项目一贯的"先根因、不盲改、验证驱动"纪律一致。
