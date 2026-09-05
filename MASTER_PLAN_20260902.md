# 2hao-analyst 全项目主工程计划（Master Plan）

**版本**：v1.0
**日期**：2026-09-02
**定位**：本仓唯一执行依据。整合 P0-P4 交付（DELIVERY_LOG_20260901）、S1-S7 建设（UPGRADE_ROADMAP/ENGINEERING_PLAN）、三轮审计结论（AUDIT_20260901_ultra / OPTIMIZATION_DEEP_20260902）与磁盘实测差异，形成一份**可直接照做的任务级计划**。
**取代**：EXECUTION_PLAN_20260902.md（并入 W1-W6 相应任务，其 G 差异表在本文件 §2.4 以复核后口径重列）。
**执行者**：Claude / Marvis / 开发者。**硬期限**：2026-10-31（首批 3m 预测到期，开始真实验证）。
**铁律**：无测试不交付；改代码先写失败测试（红）→ 改 → 绿 → 提交；根因不明不修复。

---

## 1. 执行摘要

系统骨架（数据/计算/门禁/LLM 通道）是**真材实料**；P0-P4 已把测量层、学习库、指纹、失败归因等"机制通电"，S1-S7 已把预测验证、数据刷新、证据链、合规、Web 的**代码搭好**。但磁盘实测证明两件事未闭环：

1. **预测数据不可证伪**——track_record.json 2028 条预测中仅 5 条带 target_price / falsification（0.25%），100% pending；
2. **S1-S7 大量"已创建、未运行、未通电"**，且 `verify_predictions` 与 `prediction_daily` 两套验证逻辑分裂（绝对涨跌 vs alpha、max 基准偏置、365 天硬编码 vs horizon 解析）。

**主计划主线**：W1 预测数据契约 → W2 验证逻辑投研化 → W3 目标价单一化 → W4 S1-S7 通电冒烟 → W5 测量/CI/治理 → W6 校准口径 → W7 数据/证据/合规接线 → W8 产品化 → W9 **10-31 冲刺** → W10 中长线。

---

## 2. 现状基线（2026-09-02 磁盘实测）

### 2.1 规模与资产

| 维度 | 实测 | 证据 |
|---|---|---|
| 代码 | core/pipeline/scripts/export 约 11 万行（不含 .venv/legacy） | AUDIT_20260901 |
| 测试 | ~110 测试文件 / 约 660 用例函数（含非纯单测文件） | tests/ 扫描 |
| LLM | 7 provider + 熔断 + 限流 + 回退 + agent 落盘兜底 | core/deepseek_client.py |
| 门禁 | IronGate run_all 引用 99~101 项检查（口径见 W5.4） | pipeline/iron_gate.py |
| 数据 | financials.db 669MB / kb_fts 422MB / company_events 35MB | data/ |
| 失败学习 | learning_data.db 19640 条真实失败记录 | P4-0 triage 已聚类 |
| 预测 | **track_record.json：2028 条，100% pending** | 见 §2.2 |
| git | 49+ commit；origin=`github.com/abdielchou-rgb/analysis.git` 已配（CI 阻塞解除） | git remote -v |

### 2.2 预测资产基线（本次实测，计划锚点）

`core/data/forward_picks/track_record.json`（dict：analyst_name / predictions / last_updated，2026-09-02 18:57 更新）：

| 维度 | 数值 | 判定 |
|---|---|---|
| 总条数 | 2028 | — |
| direction | bullish 1309 / bearish 337 / neutral 377 / **脏值 5**（长期看多·估值重估预期·催化剂事件·行业格局变化·政策驱动增长） | 🟡 需清洗 |
| 带 target_price | **5（0.25%）** | 🔴 致命 |
| 带 falsification | **5（0.25%）** | 🔴 致命 |
| outcome | pending 2028（100%） | 🔴 |
| time_horizon | 2028 全有 | ✅ |

> ⚠️ **存在三套预测存储需归一**：`ForwardPicksDB`（core/forward_picks.py，历史 12 条，DELIVERY_LOG 口径）、`data/forward_picks/forward_picks.csv`（legacy）、`track_record.json`（现行主库）。口径分裂是审计数字 12/2018/2246/2028 打架的根因（见 W1.1）。

### 2.3 架构快照

```
意图输入 → E2EOrchestratorV2 双路径：
  批量/标准：preflight → data_collect(akshare/yfinance/last30days)
             → chart_gen(15+) → compute(DCF/可比/情景/SOTP 真实数值)
             → section_writer(SAC+30注入器, zhipu/deepseek)
             → StyleCompiler(去AIGC指纹) → IronGate(门禁)
             → claim_citation(溯源) → compliance(合规) → method_reflection(回写)
             → human-in-loop(decision_memo) → export(DOCX/PDF)
  深度/高险：workbench 混合（web/app.py 提交 → scheduler 子进程）
异步闭环：prediction_daily/verify_predictions(到期验证→归因→learning_loop)
          refresh_data(12类sync) → event_driver → 报告刷新提醒
```

### 2.4 已交付能力（P0-P4 36 项 + S1-S7）——按 DELIVERY_LOG_20260901 / WORK_SUMMARY_20260902 登记

| 阶段 | 状态 | 关键产出 |
|---|---|---|
| P0 止血 | ✅ | 指纹 hash 绑定(fail-closed)、占位符/硬编码清零、28 脚本归档、gate_failure_triage |
| P1 通电 | ✅ | quality_trends 写入、learning_loop 真实现(复发率 26.1%)、test_compute_math 17、红测清零 |
| P2 收敛 | ✅ | 失败模式聚类修复、Gate 阈值用 golden 校准、learning 三段注入、learning_health |
| P3 能力 | ✅ | last30days 桥接、claim 溯源骨架、verify_predictions 首回填 12 条(命中42%) |
| P4 治理 | ✅ | R 规则注册表(101 中 28 登记)、文档单一事实源、巨石拆解第一步 |
| S1 预测闭环 | 🟡 代码就位未通电 | prediction_daily / attribution / monthly / benchmark_client |
| S2 数据实时 | 🟡 代码就位未通电 | refresh_data / earnings_calendar / event_driver / 舆情注入缺口 |
| S3 证据链 | 🟡 骨架已接未验证 | claim_citation JSON-LD / docx 超链接 / signal_divergence / falsification_tracker |
| S4 框架自适应 | 🟡 函数就位未首跑 | framework_effectiveness / get_framework_ranking / inject_framework_rationale |
| S5 工程可靠 | 🟡 部分 | PipelineContext / checkpoint / ci.yml(未首绿) / data 三栈未合一 |
| S6 合规风控 | 🟡 代码就位 | rating_tracker / target_price_reminder / compliance_clauses(已接线) / sensitive_info_scan |
| S7 产品化 | 🟡 代码就位 | web/app.py(18 路由未启动) / run_reports batch / cost_panel / HITL(已接线) |

### 2.5 复核后的差异表（修正 EXECUTION_PLAN 的 G 表；引用前查磁盘）

| ID | 事项 | 实测 | 处置（对应任务） |
|---|---|---|---|
| G1 | 预测契约字段(Prediction.falsification+bold_call 提取) | ✅ core/tools/track_record.py L29 + core/bold_call_extractor.py prompt 强制 | 保留；存量回填 W1.2 |
| G2 | compute 目标价单一化 | 🔴 compute_engine 无 primary_target_price（仅 L991 SOTP 透传） | **W3.1** |
| G3 | 锚卡单目标价 | ✅ section_writer `_build_data_anchor_card` list 取 [0] | 配合 W3.2 固化契约 |
| G4 | 验证用 alpha / 风格基准 / 复用 benchmark_client | 🔴 verify_predictions 自带 `get_benchmark_return` `max(hs300,zz500)`(L199)；benchmark_client 内 `get_best_benchmark_return` 同为 max 偏置 | **W2.3/W2.7** |
| G5 | 到期逻辑 | ⚠️ verify `is_due(made,horizon)` vs prediction_daily 硬编码 365 天(L45) | **W2.5** |
| G6 | dry-run | 🔴 两脚本无 argparse | **W4.1** |
| G7 | S4 数据驱动 | ⚠️ ranking/rationale 函数就位，framework_effectiveness 从未运行 | **W4.3** |
| G8 | e2e 接线 compliance/citation/HITL/quality_trends | ✅ e2e L1023/1042/1142/1208 核实 | 观测断言 W5.1 |
| G9 | CI remote | ✅ origin 已存在（DELIVERY_LOG 后新增） | **W5.2** push 首绿 |
| G10 | Web 路由 | ✅ web/app.py 18 路由存在未启动 | **W4.4/W8** |
| G11 | 指纹洞（EXECUTION_PLAN 曾列待办） | ✅ **已被 P0-1 修复**（DELIVERY_LOG：hash+资产名校验+fail-closed, 7 测试） | 回归确认 W5.5 |
| G12 | 门禁/文档口径 | ⚠️ 历史 78/96/99/101 并存；P4-2 已统一为 101 | **W5.4** 再校验 |

---

## 3. WBS 工作分解（W1-W10，任务级）

图例：状态 = 🔴未动 / 🟡部分 / 🔵进行中 / 🟢完成。工时 = 按 2026-09-02 上下文的人时估计。依赖列引用任务 ID。

---

### W1 预测数据契约（最高优先，串行前提）

**目标**：让每条预测"可证伪、可校准、可问责"。基线：2028 条中仅 5 条带 target_price/falsification。

| ID | 任务 | 改动文件 / 设计要点 | 守护测试（红→绿） | 验收 | 工时 | 依赖 |
|---|---|---|---|---|---|---|
| W1.1 | **预测存储归一** | 盘清三套存储：`ForwardPicksDB`(core/forward_picks.py) / `forward_picks.csv` / `track_record.json`；定 `track_record.json` 为唯一事实源，写迁移+只读兼容层（禁止新代码写 CSV/旧库） | `test_prediction_stores.py`：写一条→三处一致 or 旧处只读 | 单一写路径；审计口径从 12/2018/2246/2028 收敛为一个数 | 3h | — |
| W1.2 | **存量 backfill** | 新 `scripts/backfill_predictions.py`：从 output/ 已交付报告（含"目标价 XX 元"）正则+LLM 双确认提取 target_price/falsification 回填；提取不到标 `verifiable=False` | `test_backfill_predictions.py`：mock 报告→提取/兜底两分支 | 回填后覆盖率 >0.25%；unverifiable 清单可导出 | 5h | W1.1 |
| W1.3 | **方向白名单** | `core/bold_call_extractor.py` 写时白名单 bullish/bearish/neutral；脏 5 条（长期看多…）归 reason；存量清洗脚本 | `test_prediction_contract.py` 扩展脏值用例 | direction 100% ∈ 白名单 | 1.5h | W1.1 |
| W1.4 | **neutral 不可验证** | 377 条 neutral 标 `verifiable=False`（不进命中率分母）；保留区间预测扩展位 | 同上 | neutral 不计分母，月度口径含剔除说明 | 1h | W1.3 |
| W1.5 | **写入契约校验** | `core/tools/track_record.py` `register_prediction()` 增加 schema 校验：direction∈白名单、target_price/falsification 缺失告警（extractor 或 reason 必填）；新增字段 `verifiable: bool`、`judge_ver: int` | `test_prediction_contract.py` 5→10 用例 | 非法写入被拒/降级，写入日志可见 | 2h | W1.3 |

**W1 验收（里程碑 M1）**：新增预测 100% 携带契约；存量 backfill 或标注 unverifiable；单存储口径。

---

### W2 验证逻辑投研化

**目标**：验证"相对市场的判断（alpha）"，不是绝对涨跌；消灭两脚本分裂。

| ID | 任务 | 改动文件 / 设计要点 | 守护测试（红→绿） | 验收 | 工时 | 依赖 |
|---|---|---|---|---|---|---|
| W2.1 | **判定模块抽取** | 新 `core/prediction_judge.py`：`judge_outcome(actual_return, direction, alpha, target_price=None) -> tuple[str,str]`；从 verify_predictions 抽离，杜绝双份逻辑 | `test_prediction_judge.py`（自 W2.2 起红） | verify 与 daily 同函数出 outcome | 2h | W1 |
| W2.2 | **alpha 判据** | hit=alpha>+2% / miss=alpha<-2% / partial=中间；构造"大盘-10%、标的-3%"用例必须 hit | `test_s1_prediction.py` 扩展 | 判据切到 alpha 且用例绿 | 1.5h | W2.1 |
| W2.3 | **风格基准** | benchmark_client 新增 `select_benchmark(asset_style) -> index_code`（小盘→zz500 / 大盘→hs300 / 港股美股另行）；弃 `get_best_benchmark_return` 的 max 偏置与 verify 本地副本 | `test_benchmark_style.py`：风格→指数映射 + 无 max 残留 grep | alpha=实际-风格基准；无 `max(hs300,zz500)` | 2.5h | W2.1 |
| W2.4 | **复权统一** | 取价统一 `auto_adjust=True`（benchmark_client 已是），verify 的 entry/exit 改走 `core/benchmark_client.get_index_nav` + yfinance 复权；除权样例测试 | `test_adjusted_price.py` | 除权样例不产生虚假跳空 alpha | 1.5h | W2.3 |
| W2.5 | **到期逻辑统一** | prediction_daily 弃硬编码 365d，复用 `is_due(made_date, parse_time_horizon(horizon))` | 现有 is_due 用例迁移+参数化 | 两脚本对同一 created_at/horizon 判同一天到期 | 1h | W2.1 |
| W2.6 | **daily 收敛到 judge** | prediction_daily 改调 `prediction_judge` + `select_benchmark`，删本地判定副本 | `test_s1_prediction.py` 同步 | 行为一致单测 | 1h | W2.2/2.3/2.5 |
| W2.7 | **verify 收敛到 judge** | verify_predictions 删 `get_benchmark_return`/`verify_prediction` 判定体，改 import judge+benchmark | 全绿回归 | 双脚本共享同一判定代码路径 | 1h | W2.6 |

**W2 验收（里程碑 M2）**：verify_predictions 与 prediction_daily 代码级同源；alpha 判据生效；无 max 偏置。

---

### W3 目标价单一化（G2/G3）

| ID | 任务 | 改动文件 / 设计要点 | 守护测试 | 验收 | 工时 | 依赖 |
|---|---|---|---|---|---|---|
| W3.1 | **compute 聚合 primary_target_price** | `pipeline/compute_engine.py` 结果组装处聚合：优先级 DCF fair_value > SOTP target_price > scenario base_price（各来源仍保留明细供溯源）；context 注入 `primary_target_price` | `test_compute_math.py` 扩展聚合优先级用例 | 单值产出，明细可溯源 | 3h | — |
| W3.2 | **锚卡只读单值** | `section_writer._build_data_anchor_card` 只注入 `primary_target_price`；删 `data_context.get("target_prices")` list 分支（防止多个目标价进 prompt） | `test_anchor_single_price.py`：context 带多价→prompt 只见单值 | prompt/正文单一目标价 | 1.5h | W3.1 |
| W3.3 | **Gate 断言** | `rating_target_consistency` / `cross_section_consistency` 已存在；补一条确定性断言"正文目标价出现次数 ≤1（除引用/附录）" | `test_exit_quality_gates.py` 扩展 | 多目标价报告被 Gate 拦 | 1h | W3.2 |

**W3 验收**：同一报告不再出现 260/320/380/420 多目标价。

---

### W4 S1-S7 通电冒烟（"已创建未运行"首次跑通）

| ID | 任务 | 命令（预期） | 守护测试 | 验收 | 工时 |
|---|---|---|---|---|---|
| W4.1 | prediction_daily dry-run | 先加 argparse `--dry-run/--horizon/--limit`，跑 `python scripts/prediction_daily.py --dry-run --limit 5` | `test_s1_prediction.py`：dry-run 不写库 | 模拟到期→回填+alpha 报告样例，不污染真库 | 2h |
| W4.2 | refresh_data 增量 | `python scripts/refresh_data.py --only financials --dry-run` → 真跑小批量 | 无（运维） | dry-run 不写库；真跑后 financials.db 当日时间戳 | 2h |
| W4.3 | framework_effectiveness 首跑 | 补输出路径后 `python scripts/framework_effectiveness.py` | `test_s4_framework.py` 已有 7 | `output/framework_effectiveness_*.md` 非空，含"用 vs 不用"对照 | 1h |
| W4.4 | web/app.py 冒烟 | `pip install fastapi uvicorn`；`cd web && python app.py` | `test_s7_productization.py` 已有 6 | `/health` 200；`/api/batches` 返 JSON | 1h |
| W4.5 | falsification_tracker 首跑 | `python scripts/falsification_tracker.py` | 现有用例 | `output/falsification_check_*.md` 生成 | 1h |
| W4.6 | cost_panel 首跑 | `python scripts/cost_panel.py` | — | `output/cost_panel_*.md` 生成 | 0.5h |

**冒烟纪律**：任何脚本首跑报错 → 2hao-root-cause 四阶段；报错即"文档声称闭环但未闭环"的证据，回写 §2.5。

---

### W5 测量层 / CI / 治理

| ID | 任务 | 改动文件 / 要点 | 守护测试 | 验收 | 工时 | 依赖 |
|---|---|---|---|---|---|---|
| W5.1 | quality_trends 观测断言 | e2e 三处写入加存在性测试；`scripts/learning_health.py` 已可出周趋势 | `test_observability_wiring.py` 扩展 | 每次 Gate→quality_trends +1；连续 7 天有数 | 2h | — |
| W5.2 | CI 首绿 | `requirements-ci.txt`(pytest+轻量) 分级依赖；ci.yml 拆 job（轻量先行，crawl4ai/playwright 标 continue-on-error）；commit→push origin | — | Actions 主分支/PR 绿 | 3h | G9 已解除 |
| W5.3 | 红测清零+覆盖率基线 | 全量定向跑，修残留红测；`coverage_baseline.json` 更新，核心计算模块门槛 50%→80%(W10 续) | pytest 全绿 | 定向套件 0 红；覆盖率报告入库 | 3h | — |
| W5.4 | 口径收敛 | 以 `run_all` 代码引用数为准，`harness/generate_docs.py` 重新生成 README/PIPELINE_FACTS/AGENTS；R 规则登记 73 条人工归因分批 | — | 文档口径=代码口径 | 2h+跟踪 | P4-2 续 |
| W5.5 | 指纹回归确认 | P0-1 已交付（hash+归属+fail-closed）；复跑 `test_fingerprint_bypass.py` 7 用例并补跨资产复用拦截断言 | test_fingerprint_bypass | 全绿即关闭 G11 | 1h | — |
| W5.6 | 巨石拆解续 | Strangler Fig：`analysis_mixin`→checks/、`section_writer` 注入器外移；每步 golden diff 为验收（不改变输出） | `test_numeric_chain_extract.py` 模式复制 | 文件行数下降且输出 diff=0 | 分步 | P4-3 续 |

---

### W6 校准 / 口径 / 反哺

| ID | 任务 | 改动文件 / 要点 | 守护测试 | 验收 | 工时 | 依赖 |
|---|---|---|---|---|---|---|
| W6.1 | 分桶校准器 | 新 `scripts/calibration_report.py`：confidence 分桶(0.4-0.9)→实际命中率 vs 声称→Brier；空数据出空模板 | `test_calibration.py`：mock 到期 | 首批到期后立即出校准曲线 | 3h | W1/W2 |
| W6.2 | 三套命中率+随机基线 | prediction_monthly 输出 方向(参照)/alpha(价值)/目标价(最严) + 随机 50% 下界；alpha 命中率>55% 才算有效 | `test_s1_prediction.py` 扩展 | 月度报告三表+基线行 | 2.5h | W2/W6.1 |
| W6.3 | 错题本回流 | prediction_attribution 增强：miss/partial→错题卡(依据/结果/关键变量/偏差)→learning_data.db | 现有归因测试扩展 | mock 下错题卡 ≥10 且回流可见 | 2.5h | W2 |
| W6.4 | 校准反馈 | 高估桶(0.7 实际 0.5)→`learning_loop.add_failure_pattern` 收敛置信度 | `test_learning_loop_real.py` 扩展 | 触发条件有单测 | 1h | W6.1 |

---

### W7 数据实时 / 证据链 / 合规接线（S2/S3/S6 收尾）

| ID | 任务 | 改动文件 / 要点 | 守护测试 | 验收 | 工时 | 依赖 |
|---|---|---|---|---|---|---|
| W7.1 | **舆情注入缺口** | last30days 已装已采（fig_recent_news/fig_sentiment）；S2-4 声称注入但实际缺——decision_memo 模板加"近 30 天动态与情绪"段+`_build_fig_injection` 映射 | `test_s3_evidence.py` 扩展 | decision_memo 含该段且带来源 | 3h | — |
| W7.2 | claim JSON-LD+docx 超链接 | 复核 render_jsonld_ledger/build_footnote_url_map/`_add_hyperlink` 真实接线；跑通一份报告见 [注N] 可点 | `test_claim_citation.py` 16 保持绿 + 1 端到端 | docx [注N]→URL 超链接 | 2h | — |
| W7.3 | signal_divergence 接线 | compute 节点跑完注入 divergence→"风险"段 | `test_signal_divergence.py`(新) | 背离自动标注 | 2h | — |
| W7.4 | 财报/事件驱动定时 | earnings_calendar 对 10 标返回下次财报日；event_driver 出 stale_reports 清单 | 现有用例 | 清单可生成 | 2h | W4.2 |
| W7.5 | 合规风控首跑+定时 | rating_tracker/target_price_reminder 首跑出 md；sensitive_info_scan 挂出口 | — | 三件产物可生成 | 2h | — |
| W7.6 | 事件→refresh 闭环 | event_driver 命中→freshness.db 标记→下一轮 refresh_data 自动含该标的 | — | 端到端事件刷新链路演示 | 2h | W7.4 |

---

### W8 产品化（S7）

| ID | 任务 | 要点 | 验收 | 工时 | 依赖 |
|---|---|---|---|---|---|
| W8.1 | Web 提交→scheduler 子进程 | `/api/batches` POST 投递到真实 scheduler.py 子进程（非 mock）；进度写 data/batches/ | Web 提交一条→真实出报告 | 4h | W4.4 |
| W8.2 | 批量并行+熔断隔离 | run_reports 多标的并行，单标失败不阻塞批次（data_backends 熔断隔离） | N 标一个失败其余完成 | 4h | — |
| W8.3 | HITL 复核 | /api/review/{id}/approve\|reject 与 e2e decision_memo 门禁端到端 | 高险报告不经审核无法导出 | 2h | W8.1 |
| W8.4 | 成本面板+归档 | cost_panel 接入真实 cost_audit；Web 展示 | 面板可查单报告成本 | 2h | W4.6 |

---

### W9 10-31 冲刺（硬期限专项）

| ID | 任务 | 要点 | 验收 | 工时 | 依赖 |
|---|---|---|---|---|---|
| W9.1 | **到期模拟演练** | 造 5 条"昨日到期"的 mock 预测（带 target/falsification）→ 全链路 dry-run：到期判定→净值回填→alpha 判据→归因→learning 回流 | 模拟产出完整验证报告，无人工介入 | 3h | W1-W6 |
| W9.2 | **定时任务启用** | 用 schedule 工具/cron 注册：prediction_daily（每日）+ refresh_data（每日）+ prediction_monthly（每月 1 日） | 定时任务列表可见可手动触发 | 0.5h | W9.1 |
| W9.3 | 到期前数据补位 | 对 2026-10-31 到期 3m 池（32 条 time_horizon=3m）确保有净值源与报告关联 | 到期池 100% 可验证或诚实标注 data_unavailable | 1h | W4.2 |
| W9.4 | 首次真实验证 | 10-31 当天跑首次真实验证→发布第一份"命中率+alpha+校准"业绩报告 | 业绩报告可对外；复盘入 W10 | — | W9.1-9.3 |

---

### W10 中长线（季度，不在硬期限前承诺）

| 优先级 | 主题 | 说明 |
|---|---|---|
| 高 | 数据深度 | 港股/美股覆盖、一致预期实时化、TAM/份额少依赖搜索；决定分析深度上限 |
| 高 | claim 级全文引用 | 从"来源标注率"升级为逐论断可点击（STORM 级），FP2a 落地抓手 |
| 中 | LLM 网关 | LiteLLM/Instructor 级：JSON-schema 强约束、token 计数、响应缓存 |
| 中 | 注入防御纵深 | dual-LLM 隔离 + 系统性红队（spotlighting 已做，需纵深） |
| 中 | 计算核心覆盖率 80% | run_dcf/run_comparable 边界/敏感性独立测试 |
| 低 | 巨石彻底拆解 | section_writer/e2e 以 Strangler Fig 继续 |
| 低 | batch 并行限流 | 需要 LLM 限流策略成熟后开启 |

---

## 4. 依赖与执行顺序

```
M0 基线(0.5d)   W5.3 红测清零 + §2.5 复核
M1 契约(1.5d)   W1.1→W1.2→W1.3/1.4/1.5     ← 串行，全局前提
M2 判据(1d)     W2.1→W2.2/2.3/2.5→W2.6/2.7  ← 依赖 M1
M3 通电(1d)     W3.1/3.2/3.3 + W4.1-4.6    ← W4 各任务可并行
M4 测量(1-2d)   W5.1/5.2/5.4/5.5 + W6.1     ← 可提前重叠
M5 口径(1d)     W6.2/6.3/6.4 + W7.x
M6 产品(1-2d)   W8.x                        ← 依赖 M3 的 W4.4
M7 冲刺(1d)     W9.1→W9.2→W9.3→(10-31)W9.4
────────────────────────────────────────
硬期限 2026-10-31
```

批次依赖：**M1→M2 严格串行**；M4/M5 与 M3 可重叠；W7 大多依赖 M3 的通电经验但可提前做接线。合计 M0-M7 ≈ **8-12 人日**（不含 W10 与数据等待）。

---

## 5. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 / 回滚 |
|---|---|---|---|
| backfill 提取误伤（把展望价当 target_price） | 中 | 污染契约 | 正则+LLM 双确认；人工抽检 20 条；unverifiable 兜底；改动全在 track_record.json（1.2MB）可整体 revert |
| 三套存储归一破坏读路径 | 中 | 报表/调度断裂 | 先加只读兼容层再切写路径；W1.1 有独立测试守护 |
| alpha 判据改后历史 pending 语义变化 | 中 | 口径混乱 | outcome 记录带 `judge_ver=2`；可回溯旧判据结果 |
| refresh_data 真实拉取触发 akshare 超时/风控 | 高 | 阻塞 M3 | 先 dry-run+单标的试点；失败记日志不循环重试（尊重熔断） |
| CI push 后依赖装不上 | 中 | CI 红 | ci.yml 分 job + continue-on-error 重依赖；轻量单测 job 先行 |
| 10-31 净值源不可达 | 低 | 无法真实验证 | benchmark_client 双路回退（qlib/akshare→yfinance）；仍失败标 data_unavailable 诚实空跑 |
| 2028 条人工归因 R 规则耗时 | 中 | W5.4 拖延 | 分批：先登记高引用 top10，其余按"使用即登记"渐进 |

**通用纪律**：任务独立 commit，语义前缀（`fix(prediction):` / `feat(compute):`）；W1/W2/W3 各自 revert 不影响其余；**根因不明不修复**，禁止为绿而绿的补丁。

---

## 6. Definition of Done（全部勾选才算主计划收尾）

- [ ] W1：单存储；新预测 100% 契约；存量 backfill 或 unverifiable
- [ ] W2：verify 与 daily 代码同源、alpha 判据生效、无 max 偏置
- [ ] W3：compute 出 primary_target_price；正文单一目标价
- [ ] W4：六冒烟各产第一份真实产物
- [ ] W5：定向套件全绿、CI 首绿、quality_trends 连续积累、口径=代码
- [ ] W6：三套命中率+随机基线+错题本就绪（等数据）
- [ ] W7/W8：舆情注入、JSON-LD/超链接、事件刷新、Web 真实出报告
- [ ] W9：模拟演练通过；定时任务启用；10-31 首次真实验证出业绩报告

---

## 7. 文档关系与索引（本计划取代的散落文档）

| 文档 | 关系 | 状态 |
|---|---|---|
| AUDIT_20260901_ultra.md | 差距识别（十大差距/断裂点） | 已并入 §1/§2/WBS |
| DELIVERY_LOG_20260901.md | P0-P4 交付记录 | 基线（§2.3），不再重复执行 |
| UPGRADE_ROADMAP_20260902.md | S1-S7 规划 | 并入 W4-W8 |
| UPGRADE_ENGINEERING_PLAN_20260902.md | S1-S7 详细设计 | 执行时按任务引用其设计细节 |
| OPTIMIZATION_DEEP_20260902.md | 第三轮审计 A-E | 并入 W1/W2/W6 |
| EXECUTION_PLAN_20260902.md | 审计收尾执行计划 | **被本文件取代**（差异表修订为 §2.5） |
| WORK_SUMMARY / WORKPLAN_SUMMARY | 阶段记录 | 历史存档 |
| 2hao 行为约束宪法 CLAUDE.md | 铁律来源 | 持续遵守（调度管线/不编数据/门禁通过才交付） |
