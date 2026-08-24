# R78 剩余大工作量项推进

> Phase 1.1/1.5/2.3/3.4/3.1 全量落地
> 日期：2026-08-05

## Phase 1.1 数据契约 JSON Schema
- 新建 core/data_contract.py：enrich_file/chart_data 结构校验
- ALLOWED_FIG_KEYS 从 data_enrichment 导入（单一事实源）
- enrich_node 接入校验：结构漂移早暴露（实测抓到 enrich_oil 7 项白名单不一致 → 修复后剩 1 项真实空数据）
- 新增 test_r78_data_contract.py（5 项）

## Phase 1.5 golden dataset
- tests/golden/ 3 份真实报告样本
- golden_check.py 确定性断言（篇幅/结构/判断密度/数据密度/反方/无AI免责）
- 接入 pytest：test_r78_golden.py（3 项），3 样本全 PASS

## Phase 2.3 写改循环 checkpoint
- 新建 pipeline/write_checkpoint.py：SQLite checkpoint（7 天 TTL）
- e2e run() 接入：循环开头恢复、每轮结束保存、成功清除
- 中断后续跑不重头（配合 scheduler retry）
- 新增 test_r78_checkpoint.py（3 项）

## Phase 3.4 scheduler 排队服务
- scripts/run_reports.py 已有并发（R48）；补 --retry 失败重试
- 重试借助 checkpoint 续跑（Phase 2.3）

## Phase 3.1 拆分上帝模块
- section_writer._serialize_data（129 行）抽到 pipeline/sw_serialize.py
- 主文件保留转发（resume_driver 外部调用兼容）
- section_writer 2202 → 2076 行（首拆，行为零变化）
- 更新 test_r66 断言指向新模块

## 回归
69 pytest 全绿

## 累计（R77+R78 全量推进）
- Gate 71 项（+行业底座缺口）
- 新增模块：sw_serialize/data_contract/write_checkpoint/short_term_signals
- 新增测试：r77×4 + r78×4 + golden = 约 40 项

---

## 追加推进（2026-08-05）

### 数据契约 → financials.db
- core/data_contract.py 加 check_financials_coverage
- 抓到真实问题：cashflow 覆盖 0.0 → 实为字段命名不同（OCF/ICF/FCF 而非 netCashFlow），修正后全库覆盖 1.0
- 教训：契约校验先看实际数据再定义期望，避免命名误报

### e2e_orchestrator 拆分
- _locate_failed_segments（103 行）抽到 pipeline/fail_segment_locator.py，主文件转发
- e2e_orchestrator 1697 → 1594 行
- 更新 test_r66 断言指向新模块

### 轻量级 trace_id
- e2e __init__ 生成 uuid，注入 context + 成功返回
- 一次运行一个可追溯 ID，跨环节定位问题（为未来 OpenTelemetry 打底）

### CI/CD 骨架
- （未做：需用户确认 git 初始化后才有意义）
