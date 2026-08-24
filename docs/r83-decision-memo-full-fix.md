# R83 全面修复——七层根因全量落地

**日期**：2026-08-07 ｜ **触发**：油位 v0.89 圆桌诊断（对象错位 + 数据回流失效 + 交付核验复发）
**深度**：七层根因全修（用户指定）｜ **回归**：新测试 28 项全绿 + 存量确定性测试全绿

---

## 一、修复清单（7 项）

### P0-1 委托方问题清单注入机制 ✅
- `core/report_planner.py`：新增 `client_questions` 参数；`build_report_plan()` 把委托方必答问题合并进 questions 顶层（critical=True, client=True）；`serialize_plan()` 输出"【委托方必答问题】"高亮段
- `pipeline/scheduler.py`：`schedule()` 新增 `client_questions` 参数 + `--client-questions` CLI
- `pipeline/e2e_orchestrator.py`：`E2EOrchestratorV2.__init__` 新增参数 + context/data_context 双注入
- `pipeline/section_writer.py`：`write()` 从 data_context 读取 client_questions，注入写作 prompt

### P0-2 enrich 回流链路回归测试 ✅
- `tests/test_r83_enrich_roundtrip.py`（8 项）：AgentEnricher merge → 序列化 → R89 清理器 → **权威锚点比对拦截 4 倍错差**
- 验证 R85/R87 市场规模权威锚点机制：正文 12.8亿 vs enrich 锚点 46亿 → Gate `_check_market_size_consistency` FAIL

### P0-3 新报告类型 decision_memo ✅
- `core/sacs/sac_decision_memo.yaml`：新 SAC（9 逻辑链 + 12 维度 + 6 图），强制"执行摘要/行业真相/禀赋匹配/路径决策/财务测算/最坏损失/执行路线图"，禁评级目标价
- `core/sacs/__init__.py`：注册 SAC 映射 + `_AUTHORITATIVE_MIN` + `get_section_structure`
- `pipeline/scheduler.py`/`check_env.py`：CLI choices + 环境自检注册
- `pipeline/chart_assembler.py`/`chart_pipeline.py`：decision_memo 图表模板（轻量 6 图）
- `pipeline/iron_gate.py`：min_charts=4/min_tables=3/min_chars=6000
- `pipeline/checks/data_quality_mixin.py`：非 listed 类型自动跳过评级-目标价检查（decision_memo 天然受益）

### P1-4 写作计划结构化进 framework_registry ✅
- `data/framework_registry.json`：新增 `decision_memo` 框架条目（适用条件/映射SAC/注入方式），analyst_planner 自动路由

### P1-5 Gate 新增委托方问题覆盖率检查 ✅
- `pipeline/checks/coverage_mixin.py`：`_check_client_questions_coverage()`——从 report_planner 加载问题清单，按主题词（2字二元组）+ 结论信号判定；decision_memo 强制启用，缺答即阻断（error）
- `pipeline/iron_gate.py`：注册进 run_all

### P1-6 交付核验回归加固 ✅
- `export/visual_gate.py`：新增 `enrich_source_leak` error 检查（AGENT_ENRICH_SOURCES 残留即阻断）；`hard_fail_issues` 增加 enrich_source_leak/charts_not_embedded/duplicate_source_appendix；decision_memo 加入图片/标题阈值

### P2-7 SAC 报告用途标签 ✅
- `core/sacs/__init__.py`：`_REPORT_PURPOSE`（investor/board）+ `get_report_purpose()`——decision_memo=board，其余=investor

---

## 二、回归结果

| 测试 | 结果 |
|---|---|
| `tests/test_r83_enrich_roundtrip.py` | 8 passed |
| `tests/test_r83_decision_memo.py` | 20 passed |
| `tests/test_data_enrichment.py` | 25 passed |
| `tests/test_consistency_engine.py` | 21 passed |
| `tests/test_fp_r55_data_wiring.py` | 6 passed |
| `tests/test_fp_source_multi_dim.py` | 5 passed |
| `tests/test_fp_valuation_gate.py` | 7 passed |
| `tests/test_enforcer.py` | 全过 |
| `tests/test_format_sheriff_table_fix.py` | 4 passed |
| `tests/test_completeness_scan.py` | 6 passed |
| **合计（新增+确定性）** | **110 passed** |

已知非阻断：`test_fact_quality` 2 项失败为沙箱文件写权限限制（`Operation not permitted: output/_toc_regression.docx`），非代码回归，用户机可正常通过。

---

## 三、使用方式（v0.90 决策备忘录）

```bash
cd D:\2hao-analyst
python pipeline/scheduler.py "油位传感器" \
  --type decision_memo \
  --enrich-file data/keli_oil_enrich_v086.json \
  --client-questions '[{"q":"油位传感器市场是否值得战略卡位？"},{"q":"柯力进入能否快速放量？"},{"q":"久通油位业务整合至母公司承接是否可行？"},{"q":"延伸产业（物位/液位大类）是否值得进入？"}]'
```

产出自动带：委托方必答问题注入 prompt → 执行摘要/行业真相/禀赋匹配/路径决策/最坏损失/路线图章节 → IronGate 委托方问题覆盖率检查 → VisualGate 防 enrich 泄漏/图表缺失。

---

## 四、后续待办（P3）

- 写作计划 r82 文档→framework_registry 条目的**自动化转换工具**（当前为手动建条目）
- `decision_memo` 与 `--client-questions` 的端到端管线实测（需 DeepSeek key + 网络）
- 外部委托方问题清单 schema 校验（JSON 结构容错）
