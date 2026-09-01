# 2hao-analyst 升级工程方案（详细落地版）

**版本**：v1.0 | **日期**：2026-09-02
**定位**：在 UPGRADE_ROADMAP_20260902（规划篇）基础上，把 S1-S7 每个升级项深化为**可执行设计**——文件路径、函数签名、数据结构、验收标准、工作量。
**执行者**：Marvis / 新会话 / 开发者
**前提**：P0-P4 收尾已完成（36 项优化已交付，见 DELIVERY_LOG_20260901）

---

# S1 预测问责闭环（最高优先）

## S1-1 到期自动验证

**现状**：`scripts/verify_predictions.py` 已能回填，但需手动跑；无到期概念。

**设计**：新增 `scripts/prediction_daily.py`，作为每日调度入口：

```python
# scripts/prediction_daily.py
"""每日预测验证调度——到期自动回填 + 状态汇总。"""
def main():
    db = ForwardPicksDB()
    picks = db.load_all()
    # 1. 到期判定：created_at + 12M <= today → 到期待验
    # 2. 对到期 pending 项，用 qlib 净值回填（复用 verify_predictions._latest_nav_for）
    # 3. 输出 output/prediction_daily_<date>.md：今日到期数/已验/跳过
    # 4. 写 learning_data.db 的 improvement_tracking：prediction_verified 事件
```

**调度**：Windows 任务计划程序 或 Claude 定时任务（`cron 0 9 * * *`）。

**验收**：到期预测 100% 自动回填；`prediction_daily_<date>.md` 每日生成。

**工作量**：2h（复用 verify_predictions 的 qlib 读取逻辑）。

---

## S1-2 基准对比（alpha 计算）

**现状**：`verify_predictions.py` 的 benchmark_return 硬编码 0.0（无真实基准）。

**设计**：新增 `core/benchmark_client.py`：

```python
# core/benchmark_client.py
"""基准指数净值——沪深300/中证500，qlib 或 akshare。"""
def get_index_nav(index_code: str, date: str) -> float:
    # 优先 data/qlib_bin/features/sh000300.close（如有）
    # 回退 akshare.stock_zh_index_daily_em(symbol="sh000300")
def get_index_nav_series(index_code: str) -> dict[str, float]:
    # 返回 {date: nav} 供预测窗口对齐
def compute_alpha(pick, index_series) -> float:
    # alpha = actual_return - benchmark_return（同期）
```

**改动**：`verify_predictions.py` 的 benchmark_return 从 0.0 改为 `compute_alpha` 实际值。

**验收**：每条预测的 alpha 是真实超额收益（非 0）。

**工作量**：3h。

---

## S1-3 误差归因

**现状**：预测错只标 hit/miss/partial，无"错在哪"。

**设计**：`ForwardPick` 增加归因字段 + `scripts/prediction_attribution.py`：

```python
# ForwardPick 新增字段（core/forward_picks.py）
attribution: str = ""  # direction_error / magnitude_error / timing_error / key_variable_miss
attribution_note: str = ""

# scripts/prediction_attribution.py
"""对 miss/partial 预测做规则化归因：
- 方向错：actual_return 与 direction 相反
- 幅度错：方向对但 |actual|<|target| 的 50%
- 关键变量错：从 core_thesis/key_variable 提取的指标未兑现
→ 归因标签写回 learning_loop（作为写作规避信号）
"""
def attribute(pick) -> str
def write_back_to_learning(pick):  # 写 learning_data.db improvement_tracking
```

**验收**：miss/partial 预测 100% 带归因标签；标签进入学习库 ≥10 条。

**工作量**：4h。

---

## S1-4 月度命中率报告

**设计**：`scripts/prediction_monthly.py`：

```python
"""聚合月度预测业绩：
- 命中率（hit/总）
- alpha 均值/中位数
- 平均收益/最大回撤
- 按行业/方向/信心分组
输出 output/prediction_monthly_<YYYY-MM>.md
"""
```

**验收**：每月 1 号自动产出，可对外展示。

**工作量**：2h。

---

## S1-5 学习回流

**设计**：`prediction_attribution.attribute` 的产物 → `learning_loop.add_lesson(asset, report_type, "prediction_miss: 关键变量未兑现", "auto")` → 下次同行业写作 `build_lesson_prompt` 自动包含。

**验收**：`grep "prediction_miss" data/learning_data.db` 有记录；新报告 prompt 含"上期预测失败变量"。

**工作量**：1h。

---

# S2 数据实时性

## S2-1 定时增量刷新

**现状**：`scripts/sync_all_data.py` 一键 5 阶段，但全量重跑慢。

**设计**：`scripts/refresh_daily.py`：

```python
"""每日增量：
- financials.db：只拉最近 N 天新增（按 code 增量 upsert）
- qlib：补最新交易日 close（akshare 或 baostock）
- consensus_estimates：只刷报告期最新
- 输出 data/refresh_log.json 记录每次增量范围
"""
```

**验收**：财务库每日增量 ≤2min；行情补到最新交易日。

**工作量**：5h。

---

## S2-2 财报日历驱动

**设计**：`data/financial_calendar.json`（akshare `stock_financial_report_em` 生成）+ `core/earnings_calendar.py`：

```python
def next_earnings_date(code) -> str | None
def is_earnings_window(code, report) -> bool  # 报告覆盖期内有财报发布
```

**接线**：`data_collector` 采集时若命中财报窗口，`chart_data["fig_earnings_due"] = True`，写作 prompt 注入"注意最新财报"。

**验收**：对 10 只标的能返回下次财报日。

**工作量**：3h。

---

## S2-3 事件驱动更新

**设计**：`data/company_events.db` 已有（35MB），新增 `scripts/event_driver.py`：

```python
"""扫 company_events 近 7 天事件（收购/定增/评级变动）：
- 命中标的的已交付报告 → 标记 data/freshness.db 需刷新
- 输出 output/stale_reports_<date>.md：需刷新报告清单
"""
```

**验收**：事件驱动刷新清单可生成，报告头部标注数据截至日。

**工作量**：3h。

---

## S2-4 舆情真用起来

**现状**：last30days 采集到 `fig_recent_news`/`fig_sentiment`，但报告段未注入。

**设计**：`section_writer` 的 decision_memo 模板加段——"近 30 天动态与情绪"：

```markdown
## 近期市场动态与情绪（last30days）
- 核心事件：{fig_recent_news.headlines}
- 情绪信号：{fig_sentiment.summary}
- 与基本面背离：{fig_sentiment 与 fig_revenue 冲突时标注}
```

**接线**：`data_collector` 已产出 `fig_recent_news` → `section_writer` 注入器（`_build_fig_injection`）加这两个键的映射。

**验收**：决策备忘录含"近 30 天动态"段且数据带来源。

**工作量**：3h。

---

# S3 证据链可审计

## S3-1 claim→source ledger（机器格式）

**现状**：`core/claim_citation.py` 有 `annotate_inline`（[注N]）+ 附录表；来源是数据键非原始 URL。

**设计**：`claim_citation.py` 增加 `render_jsonld_ledger(claims, provenance)`：

```python
def render_jsonld_ledger(claims, provenance) -> str:
    """报告尾附 <script type="application/ld+json">：
    [{"@type":"Claim","claim":"...","source":{"url":..., "excerpt":..., "confidence":...}}]
    来源 URL 从 data_provenance 的 sources 列表匹配数据键。
    """
```

**接线**：`e2e.assemble` 在 append_citation_appendix 后追加 JSON-LD 块。

**验收**：报告含 JSON-LD ledger；每个 claim 带 source URL（有则填，无则标 "unavailable"——符合 FP2a 诚实标注）。

**工作量**：4h。

---

## S3-2 来源可点击

**设计**：`export/exporter.py` 的 docx 转换，把 `[注N]` 渲染为超链接（指向来源 URL）：

```python
# exporter.to_docx 处理 [注N] → 超链接 run
def _add_hyperlink(paragraph, url, text):
    # python-docx 超链接实现
```

**验收**：docx 中 [注N] 可点击跳转来源 URL（有 URL 时）。

**工作量**：3h。

---

## S3-3 信号背离标注

**设计**：`core/signal_divergence.py`：

```python
def detect_divergence(fig_sentiment, fig_revenue, fig_valuation) -> list[dict]:
    """舆情情绪 vs 基本面趋势背离：
    - 情绪强负面 但 营收正增长 → 背离
    - 情绪正面 但 资金流出 → 背离
    返回 [{signal_a, signal_b, type: "sentiment_fundamental"|"sentiment_flow"}]
    """
```

**接线**：`compute` 节点跑完，`divergence` 注入 prompt 与报告"风险"段。

**验收**：报告在背离时自动标注"信号背离"。

**工作量**：4h。

---

## S3-4 证伪追踪

**设计**：`scripts/falsification_tracker.py`：

```python
"""提取报告 Bold Call 的 falsification conditions（已结构化）：
- 到期检查关键变量（如"毛利率跌破34%"→ 拉最新毛利率）
- 输出 output/falsification_check_<date>.md：每条件 满足/未满足/待查
"""
```

**验收**：对已交付报告能检查证伪条件是否触发。

**工作量**：4h。

---

# S4 框架自适应

## S4-1 框架有效性统计

**现状**：`method_reflection_log.json` 186 条（method_reflection.record_reflection），但未聚合。

**设计**：`scripts/framework_effectiveness.py`：

```python
"""聚合 method_reflection_log：
- 每框架：用了多少次 / 平均 Gate 分 / 通过率
- 对比：用该框架 vs 不用（同报告类型）的 Gate 分差
输出 output/framework_effectiveness_<date>.md
"""
```

**验收**：框架效果表可生成，有"用 vs 不用"对照。

**工作量**：2h。

---

## S4-2 动态权重

**设计**：`core/method_reflection.py` 的 `get_framework_ranking(report_type)`：

```python
"""按实测效果排序框架：效果 = 平均 Gate 分 × 通过率 × 使用量加权
供 section_writer._build_framework_injection 按排序注入（替代规则化排序）。
"""
```

**接线**：`_build_framework_injection` 的"ROE>15→quality"规则改为调 `get_framework_ranking`。

**验收**：框架注入顺序来自实测而非规则。

**工作量**：3h。

---

## S4-3 框架选择可解释

**设计**：`analysis_plan` 增加 `framework_rationale` 字段 + 报告开头注入：

```markdown
> 本报告选用【{framework}】框架（依据：同行业此前 N 份报告用此框架 Gate 通过率 Y%，高于全量均值 Z%）。
```

**验收**：报告开头附数据驱动的选框架依据。

**工作量**：2h。

---

# S5 工程可靠性

## S5-1 CI/CD 通电

**现状**：git 已提交（51ebbaf），`git remote` 为空。

**设计**：
1. `.github/workflows/ci.yml` 已存在但需修：依赖分级 `requirements-ci.txt`（pytest+轻量）
2. `git remote add origin <url>` → push
3. CI job：单元测试（跳过 network/e2e）+ golden eval + 覆盖率门槛 35%→50%

**验收**：GitHub Actions 每次 PR 全绿。

**工作量**：3h（需用户提供 remote URL）。

---

## S5-2 数据层三栈合一

**现状**：DataCollectorV5 已接 data_backends 缓存/熔断（部分）；data/ 旧平台零引用。

**设计**：
1. 全网络路径走 `_network_phase`（完成度审计：grep 裸 akshare/tavily 调用）
2. `data/` 旧平台 → `legacy/data_platform/`

**验收**：采集无绕过缓存的路径；旧平台代码全归档。

**工作量**：4h。

---

## S5-3 节点级 checkpoint

**现状**：`write_checkpoint.py` SQLite 断点续跑（只覆盖写改循环层）。

**设计**：`agent_graph.py` 节点执行后写 checkpoint（node_id + output hash），恢复时跳过已完成节点：

```python
# agent_graph.py
def _checkpoint_key(node_id, context) -> str:
    return f"{node_id}:{hash(context.get('final_text', ''))[:8]}"
# 执行前查 checkpoint → 有则复用输出，无则执行
```

**验收**：崩溃后重跑跳过已完成节点。

**工作量**：6h。

---

## S5-4 类型化 PipelineContext

**现状**：裸 dict + 双键兜底（`context.get("collected_data", context.get("data_context", {}))`）。

**设计**：`core/pipeline_context.py`：

```python
@dataclass
class PipelineContext:
    asset: str
    report_type: str
    style: str = "cicc"
    collected_data: dict = field(default_factory=dict)
    chart_data: dict = field(default_factory=dict)
    compute_results: dict = field(default_factory=dict)
    final_text: str = ""
    gate_result: dict = field(default_factory=dict)
    # ... ~30 显式字段
    def get(self, key, default=None):  # 兼容既有访问
```

**接线**：e2e 节点签名改 `def node(ctx: PipelineContext)`（渐进，先包一层）。

**验收**：核心节点用类型化字段；无新双键兜底。

**工作量**：8h。

---

## S5-5 observability 防锁落地

**现状**：`core/metrics.py` 的 `_write()`/`_fallback_db_path()` 已写（未提交——受 index.lock 影响）。

**动作**：
1. Windows 侧删 `.git/index.lock`
2. 提交 `core/metrics.py`
3. 验证：跑一次管线 → `quality_trends` +1；确认主库锁释放后直写主库

**验收**：quality_trends 连续 7 天有数据（主库或副本）。

**工作量**：1h + 观测期。

---

# S6 合规风控

## S6-1 评级变更追踪

**设计**：`scripts/rating_tracker.py`：

```python
"""对比历史报告评级（data/ratings_history.json）：
- 同标的评级变化 → 输出 output/rating_changes_<date>.md + 变更说明模板
"""
```

**验收**：评级变更可追踪、可输出说明。

**工作量**：3h。

---

## S6-2 目标价到期提醒

**设计**：`scripts/target_price_reminder.py`：

```python
"""扫 forward_picks + 报告，目标价 12M 到期：
- 到期前 30/7 天提醒
- 输出 output/target_price_due_<date>.md
"""
```

**验收**：目标价到期提醒可生成。

**工作量**：2h。

---

## S6-3 免责合规自动生成

**设计**：`core/compliance_clauses.py`：

```python
CLAUSES = {
    "listed_company": "本报告基于公开信息，不构成投资建议...",
    "unlisted_company": "本报告基于尽调/公开资料，估值存在不确定性...",
    "decision_memo": "本备忘录为内部决策参考，非对外披露...",
}
def get_clause(report_type) -> str
```

**接线**：export 前自动附加（替换现在 LLM 生成的免责——R42 已删 AI 免责，这是合规免责）。

**验收**：每报告自动附对应类型合规条款。

**工作量**：2h。

---

## S6-4 敏感信息检测

**设计**：`scripts/sensitive_info_scan.py`：

```python
"""发布前扫描：
- 未公开财报数据 / 内幕信号 / 未公告并购
- 关键词表 + 数据源交叉（是否来自公开渠道）
- 命中 → 标注"需人工复核"
"""
```

**验收**：高险报告发布前过敏感扫描。

**工作量**：4h。

---

# S7 产品化

## S7-1 Web 工作台

**现状**：`web/app.py` 存在。审计其路由是否可提交任务/看进度/下载报告。

**设计**：
1. 路由：`POST /tasks`（提交标的+类型）→ `GET /tasks/<id>`（进度）→ `GET /reports/<id>.docx`（下载）
2. 后端把任务投到 `scheduler.py`（子进程），进度写 `data/task_progress.json`
3. 前端轮询进度条

**验收**：Web 可提交/监控/下载。

**工作量**：1-2 天。

---

## S7-2 批量编排

**设计**：`scripts/run_reports.py` 增强：多标的并行，每标独立熔断（data_backends _CIRCUIT per-source），失败标的自动降级不影响批次。

**验收**：批量 N 标的一个失败不阻塞其余。

**工作量**：4h。

---

## S7-3 成本面板

**设计**：`scripts/cost_panel.py`：

```python
"""聚合 ObservabilityDB.cost_audit：
- 每报告 token/成本/耗时
- 按模块/通道分布
- 输出 output/cost_panel_<date>.md + 成本超支告警
"""
```

**验收**：成本面板可生成，单报告成本可查。

**工作量**：2h。

---

## S7-4 人机协作

**设计**：`workbench_executor` 强化：人工审核点（decision_memo 强制）+ 修订追踪（谁改了什么）+ 用户反馈回写 learning_loop。

**验收**：高险报告必经人工审核；修订与反馈入库。

**工作量**：6h。

---

# 执行顺序与工作量汇总

| 阶段 | 子项 | 工作量 | 优先级 |
|---|---|---|---|
| S1 预测闭环 | S1-1~5 | 12h | ★★★★★ |
| S2 数据实时 | S2-1~4 | 14h | ★★★★ |
| S3 证据可审计 | S3-1~4 | 15h | ★★★★ |
| S4 框架自适应 | S4-1~3 | 7h | ★★★ |
| S5 工程可靠 | S5-1~5 | 22h | ★★★ |
| S6 合规风控 | S6-1~4 | 11h | ★★★ |
| S7 产品化 | S7-1~4 | 2-3 天 | ★★ |
| **合计** | 27 子项 | **约 5-6 人周** | |

**建议执行批次**：
- **批次 1（本周）**：S1 全部（预测闭环价值证明）+ S5-5（防锁落地）
- **批次 2（次周）**：S2 全部（数据实时）+ S3-1/3-2（证据可审计第一步）
- **批次 3（第 3 周）**：S3-3/3-4 + S4 全部（框架自适应）
- **批次 4（第 4 周起）**：S5-1~4 + S6 全部（工程可靠+合规）
- **批次 5（第 5-6 周）**：S7 全部（产品化）

---

# 每条验收以测试守护

每个子项交付时，写对应 `tests/test_<subitem>.py`，例如：
- S1-1 → `test_prediction_daily.py`
- S3-1 → `test_claim_jsonld.py`
- S4-2 → `test_framework_ranking.py`
- S5-4 → `test_pipeline_context.py`

**铁律**：无测试不交付；改代码先写失败测试（红）→ 改（绿）→ 提交。
