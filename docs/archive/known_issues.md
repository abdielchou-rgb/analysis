# 2号分析师 · 已知问题清单

> 本文件汇总所有审计（V51/V60/V70/圆桌讨论）发现的已知问题。
> 每次审计后更新。每次修复后标记状态。
> 格式：`[ID] 文件:行号 | 描述 | 首次发现 | 状态 | 验证方式`

---

## P0 — 必须修复

| ID | 位置 | 描述 | 首次发现 | 状态 | 验证方式 |
|----|------|------|---------|:----:|---------|
| P0-01 | sacs/__init__.py:65 | `raw`变量在except块外引用 | V51 | ❓ 待验证 | 运行SAC加载 |
| P0-02 | compute_engine.py:~126 | `NotImplementedError`可能被触发 | V51 | ❓ 待验证 | 运行计算管线 |
| P0-03 | 多个文件 | `id`覆盖内置函数 | V51 | ❓ 待验证 | grep "def id\|= id\b" |
| P0-04 | fp_scorer.py vs ai_fingerprints.py | AI指纹列表DRY违反 | V51 | ❓ 待验证 | 检查两文件一致性 |
| P0-05 | write_revise_loop.py:275 | `_export_with_warning()`可绕过IronGate | V51 | ❓ 待验证 | 审查导出路径 |

## P1 — 高优先级

| ID | 位置 | 描述 | 首次发现 | 状态 |
|----|------|------|---------|:----:|
| P1-01 | data_collector.py/v2/v3/v4/v5 | 5个旧数据采集器共存 | V60 | ❓ 待清理 |
| P1-02 | pipeline/export双入口 | E2EOrchestratorV2 + WriteReviseLoop | V51 | ❓ 待合并 |
| P1-03 | heritage_integrator.py | 空壳模块已拔管但文件仍在 | V51 | ⚠️ 已拔管，文件保留 |
| P1-04 | workflow.py | 旧入口，与E2EOrchestrator共存 | V51 | ❓ 待标记deprecated |
| P1-05 | LearningLoop | 机制到位但数据库为空 | V51 | ❓ 需回填数据 |

## P2 — 建议修复

| ID | 位置 | 描述 | 首次发现 | 状态 |
|----|------|------|---------|:----:|
| P2-01 | — | 缺少scope mode分层 | Marvis | ❌ 未开始 |
| P2-02 | — | 缺少eval体系 | Marvis | ❌ 未开始 |
| P2-03 | — | 缺少CI/CD | V51 | ❌ 未开始 |
| P2-04 | — | 缺少Dockerfile | V51 | ❌ 未开始 |

## 已修复

| ID | 描述 | 修复版本 | 验证方式 |
|----|------|---------|---------|
| P0-F01 | `_extract_chart_data`假数据 | V70+P0P2 | 代码审查 |
| P0-F02 | `_ROOT`路径文字字符串 | V70+P0P2 | 审查e2e_orchestrator.py:8 |
| P0-F03 | `__import__`反模式(6处) | V70+P0P2 | grep零结果 |
| P0-F04 | 硬编码API key(3处) | V70+P0P2 | grep零结果 |
| P0-F05 | E2E字符串检查(main.py:61) | V60 | 代码审查 |
| P0-F06 | `ReportType.__members__` BUG | V70+P0P2 | 代码审查 |
| P0-F07 | `dir()`变量检查(chart_engine.py) | V70+P0P2 | 代码审查 |
| P0-F08 | Heritage拔管 | V70+P0P2 | 审查compute_engine.py |
