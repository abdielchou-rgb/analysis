# 2号分析师 架构与运维手册（按需读取）

> 本文件是 2hao-analyst CLAUDE.md 的详细扩展，仅在需要深入理解架构、排查故障、或执行数据兜底时读取。CLAUDE.md 只保留每轮必加载的核心规则。

## 1. 三层架构强制（2026-07-31）

```
层1 能力约束（不可能绕过）：
  AgentProvider 已注册进 ProviderRegistry（priority=-1，最高优先级）
  → LLM 主执行走 call_llm 优先落队列，agent 以 provider 身份响应，不直接写报告
  → 强制 Marvis 主执行（2026-08-01 用户决策），DeepSeek 降级为兜底
  → agent 启动响应: python scripts/agent_llm_responder.py watch

层2 自动兜底（不用自觉）：
  LLM 挂 → call_llm 自动切 agent_provider（落盘队列→agent响应→回管线）
  数据缺 → enrich 写 backlog → TTL 超时自动升级 escalated
  → python scripts/agent_backlog.py list 检查升级项

层3 审计追踪（全程可查）：
  出口指纹 pipeline_fingerprint.json → export_report 校验，无指纹拒绝导出
  血缘 lineage.json → 记录 数据源→enrich→compute→write→gate 五层
```

**硬拦截清单：**
```
拦截1（出口指纹）：export_report 校验 pipeline_fingerprint.json
  → 只有 E2EOrchestratorV2 完整跑完才写指纹
  → 绕过管线直接生成的 MD/DOCX 无指纹 → GateBlockedError 拒绝导出

拦截2（待办队列）：data/backlog/<asset>_task.json
  → 管线数据不足时自动写待办，启动时必须先检查
  → python scripts/agent_backlog.py list

拦截3（FP7d 宪法）：Agent 兜底是补充输入，不是替代管线
  → 兜底数据/文本必须回流管线，直接写正文 = 输出无效

拦截4（LLM兜底通道）：agent 以 provider 身份响应，不直接产出
  → python scripts/agent_llm_responder.py watch / respond <id> --content "正文"
```

## 2. 数据兜底协议（第〇原则 桥接节点）

数据不够时，可以补充数据，但必须通过桥接节点回流：

```
① 快速检查缺口（不写报告，秒级）：
   python pipeline/scheduler.py "标的" --type listed_company --data-check-only
   → 看 data_sufficiency / needs_agent / output/<标的>_gaps.json

② 用 WebSearch/WebFetch/akshare-MCP 等补数据 → 写 enrich-file JSON
   格式见 pipeline/data_enrichment.py 顶部 schema。
   硬性合规：每条数据必须带 source 字段，否则被桥接层拒绝。
   自动生成模板：python scripts/agent_backfill.py template "标的" --out enrich.json

③ 重跑管线注入补充数据：
   python pipeline/scheduler.py "标的" --type listed_company --enrich-file enrich.json
   或 python scripts/agent_backfill.py run "标的" --enrich-file enrich.json

一键自动版：python scripts/agent_backfill.py auto "标的"
```

**合规边界（FP2 数据零编造）：**
- 补充的每个数据点必须有来源（公司公告/年报/WebSearch 结果等）
- 无 source 的数据点会被 `pipeline/data_enrichment.py` 拦截
- agent 补充数据会在报告尾部生成「数据补充来源」附录，供 Iron Gate 追溯
- 桥接层只接受白名单内的 fig_* 键
- 禁止把补充数据直接写进正文

## 3. 实际管线步骤

`pipeline/e2e_orchestrator.py`（E2EOrchestratorV2）定义强制管线步骤：

```
preflight_check → data_collect → enrich(充足性检查+本地/agent兜底) → chart_gen → compute → section_writer → iron_gate → export
```

21 节点图（AgentGraph）：
```
preflight → biz_macro → data_feeds
                                  ↘
data ─→ enrich ─→ scarcity / cross_validate / argument / compute / charts
                                  ↘                      ↘          ↘
                                    write_sections → style → assemble → template → validate → critic → compliance → export_docx
```

每个节点有 `output_contract` 类型/子键校验，error 级违例阻断节点（2026-08-01 修复）。

## 4. 数据兜底桥接节点

`pipeline/data_enrichment.py` 是 agent 兜底数据的统一入口，在 data 之后自动运行：
1. DataSufficiencyChecker 判定数据充足性
2. LocalBackfill 从本地库（financials.db/qlib/历史报告）兜底
3. AgentEnricher 把 --enrich-file 的 agent 数据 merge 回 collected_data

## 5. 故障排查速查

| 症状 | 排查 | 修复 |
|---|---|---|
| preflight 慢/卡死 | RuntimeGate.check_all 全量语法编译 | `scripts/run_e2e_light.py` 跳过编译直接驱动管线 |
| LLM 不可用 | DeepSeek 网络/代理问题 | 确认 key、绕过代理；或走 L3 agent 兜底 |
| data_feeds 卡 | assets/reports 103个PDF扫描 | 确认网络；无网络时该节点较慢但最终返回 |
| 契约不阻断 | 检查 agent_graph.py output_contract | 已修复，error 级会阻断 |
| 报告无指纹 | export_report 拒绝 | 只有 E2EOrchestratorV2 完整跑完才写指纹 |

## 6. 已知修复记录（2026-08-01）

- `core/deepseek_client.py`：AgentProvider 接线修复（原未 import，LLM 兜底断线）
- `pipeline/agent_graph.py`：契约校验覆盖 bug 修复（validation_issues 被覆盖）
- `pipeline/data_feeds_node.py`：feeds 产出 merge 进 collected_data（原断线）
- `pipeline/e2e_orchestrator.py`：重试间数据缓存（原每轮重采网络）
- `scripts/sync_financials.py`：增量跳过按表独立（原只看 profit，balance/cashflow 3%）
- `scripts/run_e2e_light.py`：轻量启动器（受限环境跳过慢 preflight 编译）
