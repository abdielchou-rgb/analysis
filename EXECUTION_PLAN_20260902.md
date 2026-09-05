# 2hao-analyst 审计收尾 · 工程执行计划

**版本**：v1.0
**日期**：2026-09-02
**定位**：AUDIT_20260901_ultra（第一轮全仓审计）+ OPTIMIZATION_DEEP_20260902（第三轮数据契约审计）的**收尾执行计划**。UPGRADE_ENGINEERING_PLAN_20260902 已解决"造机器"（S1-S7 代码就位）；本计划解决"让机器可信"——**在 2026-10-31 首批 3m 预测到期前，把预测数据、验证逻辑、测量层三件事闭环**。
**硬期限**：2026-10-31（首批 3m 预测到期，到期即开始真实验证，届时不能再有"不可证伪"的预测在验）。
**铁律**：无测试不交付；改代码先写失败测试（红）→ 改 → 绿 → 提交。

---

## 一、审计结论（一句话）

> 系统的骨架（数据/计算/门禁/LLM 通道）是真材实料，但**测量-验证链路从未通电**：2018 条预测 0% 带目标价、0% 带证伪条件、验证逻辑判的是"绝对涨跌"而非"相对市场 alpha"。若不修，2026-10-31 首次真实验证将产出"抛硬币级"的无意义结果。

---

## 二、声称 vs 现实（2026-09-02 磁盘实测差异表）

执行计划的第一个任务是**消除下表的每一项差异**。✅=已核实为真；❌=声称已做但代码未落地；⚠️=两处行为不一致。

| # | 声称 | 磁盘实测（证据） | 判定 | 处置 |
|---|---|---|---|---|
| G1 | P0-2 预测契约修复（Prediction 带 falsification，bold_call 提取 target_price+falsification） | `core/tools/track_record.py` Prediction 含 `falsification`（L29）；`core/bold_call_extractor.py` prompt 强制 target_price/falsification（L56-63） | ✅ | 保留；存量回填另计（T1.1） |
| G2 | 根因3 目标价单一化：compute 聚合 primary_target_price | `pipeline/compute_engine.py` **无** primary_target_price；仅 L991 SOTP 单路透传 | ❌ | **待实现**（T4.1） |
| G3 | 锚卡只注入单一目标价 | `pipeline/section_writer.py` `_build_data_anchor_card`（L213）list 取 `[0]`（L243） | ✅ 单值 | 但入口字段多样，需配合 G2 固化契约（T4.2） |
| G4 | 验证用 alpha 判据、基准按风格选、复用 benchmark_client | `scripts/verify_predictions.py` 未 import benchmark_client；自带 `get_benchmark_return()` 且 `max(hs300, zz500)`（L199）；`prediction_daily.py` import `core.benchmark_client`（L40） | ❌ | **改**（T2.1/T2.2）——两脚本行为分裂，先统一 |
| G5 | 到期判定用 time_horizon 解析 | `verify_predictions.is_due(made, horizon_days)`（L88）；`prediction_daily.py` 硬编码 `365天=12M`（L45） | ⚠️ 分裂 | 统一为 is_due + horizon（T2.3） |
| G6 | prediction_daily 支持 dry-run 模拟 | 两脚本均无 argparse、无 --dry-run | ❌ | **补 dry-run**（T3.1） |
| G7 | S4 框架数据驱动 | `core/method_reflection.get_framework_ranking()`（L117）+ `core/framework_injector.inject_framework_rationale()`（L168）存在；`scripts/framework_effectiveness.py` 存在但**从未运行** | ⚠️ 半 | 首次运行聚合（T5.1） |
| G8 | e2e 接线 compliance/claim_citation/HITL/quality_trends | `pipeline/e2e_orchestrator.py` 四处接线均核实（L1023/1042/1142/1208） | ✅ | 保留；写观测断言防回归（T8.1） |
| G9 | S5-1 CI 被 git remote 阻塞 | `git remote -v` → origin 已存在 `github.com/abdielchou-rgb/analysis.git`；`.github/workflows/ci.yml` 存在 | ✅ 已解除 | 提交 + push + 首绿（T8.2） |
| G10 | Web 工作台路由就绪 | `web/app.py`（24.7KB）含 /workbench、/api/batches、/api/review 等 18 路由；需 FastAPI+uvicorn | ⚠️ 未启动过 | 冒烟启动（T7.1） |
| G11 | IronGate 检查数口径 | 历史文档 78/96/99/101 并存 | ⚠️ 治理债 | 以 `run_all` 代码引用数为准文档化（T8.3） |

---

## 三、执行主线（P0→P2，对应第三轮审计 A-E 主线）

每条主线给：目标 / 改动点 / 验收 / 守护测试 / 工作量。**优先级依据**：没有数据契约（A），验证逻辑（B）和校准（C）全部无意义；所以 A→B→C 严格串行，D/E 可并行。

### 主线 A — 预测数据契约（最高优先）

**目标**：让存量与新增预测都"可证伪、可校准"。第三轮审计实测：2018 条预测，0% 带 target_price、0% 带 falsification、100% pending。

| 任务 | 内容 | 改动文件 | 验收 | 守护测试 | 工作量 |
|---|---|---|---|---|---|
| **A1 存量 backfill** | 从已交付报告（output/ 报告含目标价如 38.50/260/27.50/52.00 元）反提取 target_price+falsification，回填 track_record；提取不到则标 `unverifiable=True` 剔除出命中率分母 | `scripts/backfill_predictions.py`（新）、`core/tools/track_record.py` | 回填后带 target_price 比例 >0；unverifiable 清单可导出 | `test_backfill_predictions.py`：mock 报告→提取→回填→unverifiable 分支 | 4h |
| **A2 方向标签白名单** | direction 现含"长期看多/催化剂事件"等非方向值；白名单 bullish/bearish/neutral，非法值移入 reason | `core/bold_call_extractor.py` | 提取后 direction ∈ 白名单 100% | 现有 `test_prediction_contract.py` 扩展非法值用例 | 1h |
| **A3 neutral 不可验证标记** | neutral（约 372 条）设 `verifiable=False`，不计命中率分母 | `core/tools/track_record.py` + `verify_predictions.py` | neutral 不进命中率统计 | 同上 | 1h |

**A 线验收**：新增预测 100% 带 target_price+falsification+干净 direction；存量回填或标注 unverifiable 完毕。

### 主线 B — 验证逻辑投研化

**目标**：验证"相对市场的判断"，不是"绝对涨跌"。

| 任务 | 内容 | 改动文件 | 验收 | 守护测试 | 工作量 |
|---|---|---|---|---|---|
| **B1 alpha 判据统一** | hit/miss/partial 改以 alpha（超额收益）判定，阈值 ±2% | `scripts/verify_predictions.py`（判据）、`scripts/prediction_daily.py`（同步） | 两脚本对同一条预测输出一致 outcome | `test_s1_prediction.py` 扩展：构造大盘跌10%标的跌3%用例 → 必须 hit | 2h |
| **B2 基准修正** | 弃 `max(hs300,zz500)`，按市值风格选基准；统一走 `core/benchmark_client.py`（data/qlib_bin 优先→akshare 回退） | `scripts/verify_predictions.py` | 无 max() 残留；verify 与 prediction_daily 同一函数出基准 | grep 断言 + mock 风格选择单测 | 2h |
| **B3 复权** | entry/exit 用复权价，防除权失真 | `core/benchmark_client.py` + 验证取价处 | 取价统一 auto_adjust 路径 | 单测除权样例 | 1h |
| **B4 到期逻辑统一** | prediction_daily 弃硬编码 365d，复用 is_due(horizon) | `scripts/prediction_daily.py` | 两脚本 is_due 一致 | 现有 is_due 用例迁移 | 1h |

**B 线验收**：验证结果能回答"系统相对市场是否创造 alpha"；prediction_daily 与 verify_predictions 行为一致（消灭 G4/G5）。

### 主线 C — 置信度校准（就绪，等数据）

| 任务 | 内容 | 改动文件 | 验收 | 守护测试 | 工作量 |
|---|---|---|---|---|---|
| **C1 分桶校准器** | 按 confidence 分桶统计实际命中率 vs 声称置信度 → Brier score + 校准曲线数据 | `scripts/calibration_report.py`（新） | 空数据可跑出空模板；有 mock 到期数据可出曲线 | `test_calibration.py`：mock 分桶 | 3h |
| **C2 校准反馈** | 高估桶（0.7 实际 0.5）→ learning_loop 写"收敛置信度" | C1 接线 `learning_loop.add_failure_pattern` | 触发条件有单测 | 同上 | 1h |

**C 线验收**：首批到期后可立即产出校准曲线（代码就绪 + mock 测试绿）。

### 主线 D — 三套命中率 + 随机基线

| 任务 | 内容 | 改动文件 | 验收 | 守护测试 | 工作量 |
|---|---|---|---|---|---|
| **D1 三套口径** | 月度报告同时输出：方向命中率（参照）/ alpha 命中率（价值）/ 目标价命中率（最严） | `scripts/prediction_monthly.py` | 报告含三表 | `test_s1_prediction.py` 扩展 | 2h |
| **D2 随机基线对照** | 同池随机方向 50% 作下界；alpha 命中率 >55% 才算有效 | D1 内嵌 | 报告含随机基线行 | 同上 | 1h |

### 主线 E — 预测错误反哺（依赖 A/B 完成后才有意义）

| 任务 | 内容 | 改动文件 | 验收 | 守护测试 | 工作量 |
|---|---|---|---|---|---|
| **E1 错题卡** | 每条 miss/partial → 错题卡（依据/结果/关键变量/偏差假设）→ learning_data.db | `scripts/prediction_attribution.py` 增强 | 错题卡 ≥10（mock） | 现有归因测试扩展 | 2h |

---

## 四、通电冒烟（S1-S7 "已创建未运行"脚本首次跑通）

审计会话识别的四个待验优先级——**全部是"代码在、没跑过"**，先跑通再谈增强：

| 任务 | 命令（预期） | 验收 | 工作量 |
|---|---|---|---|
| **T3.1 预测闭环 dry-run** | `python scripts/prediction_daily.py --dry-run`（**先补 --dry-run 参数**，G6） | 模拟"到期"预测 → 回填 + alpha 报告可出，不写真实库 | 2h |
| **T6.1 数据增量刷新** | `python scripts/refresh_data.py --only financials --dry-run` 后接真实小批量 | financials.db 有当日写入时间戳；dry-run 不写库 | 2h |
| **T7.1 Web 冒烟** | `pip install fastapi uvicorn` 后 `cd web && python app.py` | `/health` 200；`/api/batches` 返回 JSON | 1h |
| **T5.1 框架有效性首跑** | `python scripts/framework_effectiveness.py`（先补默认输出路径） | `output/framework_effectiveness_*.md` 非空 | 1h |

**冒烟纪律**：任何脚本首次运行报错 → 走 2hao-root-cause 四阶段（先根因，不盲修）；报错即"文档声称闭环但实际没闭环"的证据，回写本计划差异表。

---

## 五、测量层与 CI（让"收敛"第一次可观测）

| 任务 | 内容 | 改动文件 | 验收 | 工作量 |
|---|---|---|---|---|
| **T8.1 观测断言** | e2e 三处 quality_trends 写入（gate_score_avg/pass_rate/failure_count）加存在性测试，防回归 | `tests/` 新增 | 跑一次 gate → quality_trends +1 | 2h |
| **T8.2 CI 首绿** | 修 ci.yml 依赖分级（requirements-ci.txt：pytest+轻量，跳过 network/e2e）→ commit → push origin → Actions 全绿 | `.github/workflows/ci.yml`、`requirements-ci.txt` | PR/主分支绿；G9 已解除阻塞 | 3h |
| **T8.3 口径收敛** | IronGate 检查数、测试数、来源标注率统一到"代码事实 + 自动生成"（README/PIPELINE_FACTS 改为引用 `run_all` 计数） | `docs/`、`harness/generate_docs.py` | 文档口径=代码口径（消 G11） | 2h |
| **T8.4 红测清零** | 复跑全量定向套件，修残留红测（上次审计 lastfailed 7 项） | tests/ | `pytest` 定向套件全绿 | 2h |
| **T8.5 指纹洞** | `_verify_pipeline_fingerprint` 三绕过洞：指纹与正文 hash 绑定、校验归属、解析失败拒绝 | `pipeline/` | 跨资产复用指纹被拦 | 2h |

---

## 六、执行顺序与里程碑

```
里程碑 M0（基线，半天）   T8.4 + 差异表 G1-G11 复核，冻结基线
里程碑 M1（契约，1-2天）  主线 A 全量（A1-A3）——可证伪前提
里程碑 M2（判据，1天）    主线 B 全量（B1-B4）——消灭绝对涨跌判定
里程碑 M3（通电，1天）    T3.1 + T6.1 + T5.1 + T7.1 四冒烟全过
里程碑 M4（测量，1-2天）  T8.1/T8.2/T8.3/T8.5 + 主线 C 就绪
里程碑 M5（口径，1天）    主线 D/E + 月度模板 + 随机基线
────────────────────────────────────────────
硬期限 2026-10-31        首批 3m 到期 → 跑第一次真实验证
```

批次依赖：**M1→M2 严格串行**（数据不合格时验证逻辑改对了也没用）；M3 的四个冒烟彼此独立、可并行；M4/M5 与 M3 可重叠。合计约 **5-8 人日**，不含等待数据积累。

---

## 七、风险与回滚

| 风险 | 概率 | 影响 | 缓解 / 回滚 |
|---|---|---|---|
| backfill 提取目标价误伤（把分析师展望当 target_price） | 中 | 污染存量契约 | 提取走"目标价 XXX 元"正则 + LLM 双确认；人工抽检 20 条；unverifiable 兜底 |
| verify 判定改 alpha 后历史 pending 语义变化 | 中 | 报告口径混乱 | 判定版本号入 outcome 记录（`judge_ver=2`），可回溯 |
| 两脚本统一引入回归 | 中 | 调度断裂 | B 线每步先写失败测试；prediction_daily 与 verify 共享 `core/prediction_judge.py` 单函数，杜绝双份逻辑 |
| refresh_data 真实拉取触发 akshare 超时/风控 | 高 | 阻塞 M3 | 先 --dry-run + 单标的试点；失败不重试循环（记日志回写） |
| CI push 后依赖装不上（crawl4ai/playwright） | 中 | CI 红 | ci.yml 分 job：轻量单测 job 先行，重型依赖 job 标注 continue-on-error |
| 到期日临近但 data 拉不到净值 | 低 | 无法验证 | benchmark_client 已含 qlib/akshare 双路回退；仍失败则标 `data_unavailable` 诚实空跑 |

**通用回滚**：每任务独立 commit（语义化前缀 `fix(prediction):` 等）；主线 A/B 各自 revert 不影响 S1-S7 其余代码。

---

## 八、Definition of Done（全部勾选才算收尾）

- [ ] 差异表 G1-G11 全消（每项关闭都留磁盘证据）
- [ ] 存量预测 100% 带 target_price+falsification，或标 unverifiable
- [ ] verify_predictions 与 prediction_daily 行为一致、alpha 判据生效、无 max() 基准
- [ ] 四冒烟（dry-run/refresh/web/framework）各产出第一份真实产物
- [ ] 定向测试套件全绿；CI 首绿；quality_trends 连续积累
- [ ] 本计划每条验收都有对应守护测试（红→绿）

---

## 附：与既有文档的关系

| 文档 | 关系 |
|---|---|
| AUDIT_20260901_ultra.md | 第一轮全仓审计（差距识别）——本计划是其 P0-P2 的收尾执行 |
| OPTIMIZATION_DEEP_20260902.md | 第三轮数据契约审计（A-E 主线）——本计划将其落为可执行任务 |
| UPGRADE_ENGINEERING_PLAN_20260902.md | S1-S7 建设方案——本计划不再重复建设，只做"通电+纠偏" |
| DELIVERY_LOG_20260901.md / WORK_SUMMARY_20260902.md | 交付记录——完成一项在本计划打勾并回写 |
