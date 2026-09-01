# 2hao-analyst 全量升级报告

**日期**: 2026-09-01  
**基线**: UPGRADE_ROADMAP_20260902.md (S1-S7)  
**测试**: 31/31 passing  

---

## 一、升级总览

本次升级目标：将二号分析师从"高设计、低交付"推进到"预测→验证→归因→学习"闭环。七大阶段全部完成。

```
S1 预测问责闭环    ✅  等待首批预测到期
S2 数据实时性      ✅  last30days 舆情注入
S3 证据可审计      ✅  claim→source 容差匹配
S4 框架自适应      ✅  method_reflection 回写
S5 工程可靠性      ✅  CI + 批量刷新
S6 合规风控        ✅  免责条款自动注入
S7 产品化          ✅  批量运行 + 归档
```

---

## 二、各阶段详情

### S1: 预测问责闭环

**文件**: `scripts/verify_predictions.py`

- 到期自动验证：拉取 yfinance 价格 → 判定 hit/miss/partial
- 基准对比：沪深300 (000300.SS) / 中证500 (000905.SS)
- Alpha 计算：实际收益 - 基准收益
- 归因标签：direction_wrong / magnitude_off / timing_off / key_var_missed / black_swan / sector_rotation / policy_shift / earnings_miss / guidance_cut
- 月度报告：`output/prediction_health/monthly_report_<month>.md`

**当前状态**: 2,246 条预测全部 pending。最早到期日 2026-10-31（3m 预测）。

**调度建议**:
```bash
# 每日运行
python scripts/verify_predictions.py

# 批量补跑
python scripts/verify_predictions.py --backfill-default-horizon=90d
```

---

### S2: 数据实时性

**文件**: `pipeline/sw_serialize.py`, `pipeline/prompt_injectors.py`

last30days 舆情信号通过双通道注入报告写作上下文：

1. **sw_serialize.py** — 在 `serialize_chart_data()` 中提取 `fig_recent_news` / `fig_sentiment`，输出为"近30天舆情信号"块
2. **prompt_injectors.py** — 新增 `_inj_sentiment_str()` 注入器，输出结构化 markdown 供 LLM 写作参考

**数据来源**: Hacker News 聚类（无需 API key），有 Brave/Perplexity key 时扩展到 web 搜索。

---

### S3: 证据可审计

**文件**: `core/claim_citation.py`（已有）→ `pipeline/e2e_orchestrator.py`（接线）

- `build_claim_citation_map()`: 扫描正文含数字的句子，与 chart_data 各 fig_* 键数值做 ±0.5% 容差匹配
- `append_citation_appendix()`: 命中表渲染为文末"附录：关键数据溯源"
- 幂等：重复调用不重复注入
- env `REPORT_CITATION_APPENDIX=0` 可关闭

---

### S4: 框架自适应

**文件**: `core/method_reflection.py`（已有）→ `pipeline/e2e_orchestrator.py`（接线）

- Gate 通过后自动调用 `record_reflection()`
- 回写 `data/framework_registry.json` 效果字段（已用次数 / 平均 Gate 分 / 评分）
- 首次实测覆盖估算基线，此后滑动平均
- 反思日志：`data/method_reflection_log.json`（最多 200 条）

---

### S5: 工程可靠性

#### GitHub Actions CI

**文件**: `.github/workflows/ci.yml`

- 触发：push/PR to main
- 步骤：install → test → lint (ruff) → import check
- Python 3.11, ubuntu-latest

#### 数据增量刷新

**文件**: `scripts/refresh_data.py`

12 类数据任务，拓扑排序，依赖感知：

| 任务 | 数据源 | 依赖 |
|------|--------|------|
| financials | akshare | — |
| capital_flow | akshare | financials |
| consensus | akshare | financials |
| events | akshare | — |
| industry | akshare | financials |
| governance | akshare | — |
| pledge | akshare | — |
| earnings_forecast | akshare | financials |
| leading | akshare | — |
| macro | akshare | — |
| us_stocks | yfinance | — |
| qlib | local | — |

```bash
python scripts/refresh_data.py                    # 全部
python scripts/refresh_data.py --only financials  # 单个
python scripts/refresh_data.py --list             # 列出
```

---

### S6: 合规风控

**文件**: `core/compliance_clauses.py`（已有）→ `pipeline/e2e_orchestrator.py`（接线）

按报告类型自动注入合规免责条款：

| 报告类型 | 条款摘要 |
|----------|----------|
| listed_company | 公开信息，不构成投资建议 |
| unlisted_company | 估值假设，信息透明度有限 |
| earnings_notes | 以公司公告为准 |
| industry_deep | 行业预测受多重因素影响 |
| decision_memo | 内部讨论使用，不对外披露 |
| valuation | 多项假设，仅供参考 |

assemble 阶段自动注入，已有免责不重复注入。

---

### S7: 产品化

**文件**: `scripts/batch_runner.py`

```bash
# 指定标的
python scripts/batch_runner.py --assets "宁德时代,比亚迪,中芯国际" --type listed_company

# 从 track_record 补跑
python scripts/batch_runner.py --from-track-record

# 配置文件
python scripts/batch_runner.py --config batch_config.json
```

归档结构：
```
output/archive/
  20260901_193000_宁德时代/
    宁德时代_深度研究.docx
    宁德时代_深度研究.md
    meta.json
  index.json  ← 全局索引
```

---

## 三、关键工程修复

### 3.1 Circuit Breaker 超时宽容

**问题**: zhipu 并行 4 路 section writing 同时超时 → 4 次连续失败 → 触发熔断 → 全部 fallback 到 deepseek

**修复**:
- `core/deepseek_client.py`: 新增 `record_timeout()` — 超时计为 0.5 次失败
- `core/smart_router.py`: 新增 `_record_timeout()` + `record_timeout()`
- 效果：10 次连续超时才触发熔断（原来 =5 次）

### 3.2 LLM HTTP 超时

**文件**: `core/settings.py`

- 默认 90s → 180s（zhipu 大 prompt 需要更长时间）

### 3.3 quality_trends 写入

**问题**: observability.db 的 quality_trends 表 0 条记录，FP3 收敛曲线无法工作

**修复**: `pipeline/e2e_orchestrator.py` validate 节点后自动写入：
- `gate_score_avg` — 本次 Gate 均分
- `gate_pass_rate` — 本次是否通过 (1.0/0.0)
- `failure_count` — 本次失败项数

### 3.4 预测→学习闭环

**文件**: `pipeline/learning_loop.py`

新增 `add_failure_pattern()` 方法：
- 写入 `report_failures`（供 recurrence_rate 统计）
- 写入 `learning_lessons`（供 build_lesson_prompt 读取）
- verify_predictions.py 的归因经验可直接回流

---

## 四、文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `scripts/verify_predictions.py` | 新增 | 预测自动验证 |
| `scripts/refresh_data.py` | 新增 | 数据增量刷新调度 |
| `scripts/batch_runner.py` | 新增 | 批量运行 + 归档 |
| `.github/workflows/ci.yml` | 新增 | GitHub Actions CI |
| `pipeline/sw_serialize.py` | 修改 | last30days 舆情注入 |
| `pipeline/prompt_injectors.py` | 修改 | sentiment_str 注入器 |
| `pipeline/e2e_orchestrator.py` | 修改 | quality_trends + compliance + claim citation |
| `pipeline/learning_loop.py` | 修改 | add_failure_pattern() |
| `core/deepseek_client.py` | 修改 | record_timeout() |
| `core/smart_router.py` | 修改 | _record_timeout() |
| `core/settings.py` | 修改 | LLM_HTTP_TIMEOUT 180s |
| `output/prediction_health/PREDICTION_SYSTEM_STATUS.md` | 新增 | 预测系统状态报告 |

---

## 五、待观察项

| 项 | 时间窗口 | 说明 |
|----|----------|------|
| 预测验证闭环首次运行 | 2026-10-31 | 首批 3m 预测到期 |
| zhipu 稳定性 | 持续 | circuit breaker 宽容后不再误触，但延迟仍需监控 |
| CI 首次通过 | push 后 | 需 GitHub remote 可达 |
| batch_runner 并行 | 待实现 | 当前串行，LLM 限流下并行收益有限 |

---

## 六、架构现状

```
main.py (入口)
  └→ E2EOrchestratorV2
       ├→ preflight_check
       ├→ data collection (akshare + Tavily + yfinance + last30days)
       ├→ data_stager (9 engine, 3 backend)
       ├→ chart generation (15+ charts)
       ├→ compute pipeline (DCF + 可比 + 场景)
       ├→ section_writer (SAC 3段式, zhipu/deepseek)
       ├→ StyleCompiler (AIGC 去指纹)
       ├→ IronGate (101 checks)
       ├→ claim_citation (数据溯源附录)
       ├→ compliance_clauses (合规免责)
       ├→ method_reflection (框架效果回写)
       ├→ quality_trends (收敛趋势)
       └→ export (DOCX)

验证闭环:
  verify_predictions.py (每日)
    → track_record.json → yfinance 价格 → hit/miss/partial
    → 归因标签 → learning_loop.add_failure_pattern()
    → auto_apply_lessons → 下次报告自动规避

数据刷新:
  refresh_data.py (定时)
    → 12 类 sync_*.py → financials.db / capital_flow.db / ...
```
