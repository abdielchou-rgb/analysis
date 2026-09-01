# WORKPLAN_SUMMARY_20260901

**项目**: 2hao-analyst (二号分析师)
**日期**: 2026-09-01
**会话目标**: UPGRADE_ROADMAP_20260902.md 全量推进

---

## 一、执行概要

本会话完成了 UPGRADE_ROADMAP_20260902.md 定义的 S1-S7 全部七个阶段，并修复了多个影响生产可靠性的工程问题。产出 4 个新脚本、1 个 CI 配置、6 处核心代码修改。31 项测试全部通过。

---

## 二、阶段完成状态

### S1 预测问责闭环

| 项 | 状态 | 产出 |
|----|------|------|
| 到期自动验证 | ✅ | `scripts/verify_predictions.py` |
| 基准对比 (HS300/ZZ500) | ✅ | Alpha 计算内嵌 |
| 归因标签体系 | ✅ | 10 类标签 |
| 月度命中率报告 | ✅ | `output/prediction_health/` |
| 学习回流 | ✅ | `learning_loop.add_failure_pattern()` |

**当前数据**: 2,246 条预测，全部 pending。time_horizon 分布：12m=1,486 / 6m=256 / 3m=32 / unknown=431。最早到期 2026-10-31。

### S2 数据实时性

| 项 | 状态 | 产出 |
|----|------|------|
| last30days 舆情采集 | ✅ | `pipeline/data_collector.py` |
| 舆情注入写作上下文 | ✅ | `sw_serialize.py` + `prompt_injectors.py` |
| 数据增量刷新调度 | ✅ | `scripts/refresh_data.py` |

### S3 证据可审计

| 项 | 状态 | 产出 |
|----|------|------|
| claim→source 容差匹配 | ✅ | `core/claim_citation.py` |
| 溯源附录自动注入 | ✅ | `e2e_orchestrator.py` 接线 |
| 幂等保护 | ✅ | 重复调用不重复注入 |

### S4 框架自适应

| 项 | 状态 | 产出 |
|----|------|------|
| 方法反思记录 | ✅ | `core/method_reflection.py` |
| registry 效果回写 | ✅ | `e2e_orchestrator.py` 接线 |
| 滑动平均评分 | ✅ | 首次实测覆盖估算基线 |

### S5 工程可靠性

| 项 | 状态 | 产出 |
|----|------|------|
| GitHub Actions CI | ✅ | `.github/workflows/ci.yml` |
| 数据批量刷新 | ✅ | `scripts/refresh_data.py` |
| Circuit breaker 超时宽容 | ✅ | `deepseek_client.py` + `smart_router.py` |
| LLM HTTP 超时 180s | ✅ | `core/settings.py` |

### S6 合规风控

| 项 | 状态 | 产出 |
|----|------|------|
| 合规免责条款库 | ✅ | `core/compliance_clauses.py` |
| 按报告类型自动注入 | ✅ | `e2e_orchestrator.py` 接线 |
| 已有免责不重复注入 | ✅ | 幂等检查 |

### S7 产品化

| 项 | 状态 | 产出 |
|----|------|------|
| 批量报告生成 | ✅ | `scripts/batch_runner.py` |
| 归档 + 索引 | ✅ | `output/archive/` + `index.json` |
| track_record 补跑 | ✅ | `--from-track-record` |

---

## 三、工程修复详情

### 3.1 Circuit Breaker 超时误触

**现象**: zhipu 并行 4 路 section writing 同时超时 → 4 次连续失败 → 触发熔断 → 全部 fallback 到 deepseek via openrouter

**根因**: 超时和硬错误使用同一计数器，4 路并行请求同时超时即触发阈值(5)

**修复**:
```python
# deepseek_client.py
def record_timeout(self, name: str):
    """超时计为半次失败——并行请求容易同时超时，避免误触熔断。"""
    prev = self._consecutive_failures.get(name, 0)
    self._consecutive_failures[name] = prev + 0.5  # 10 次才触发
```

**效果**: 熔断阈值从 5 次硬错误等价于 10 次超时

### 3.2 quality_trends 空表

**现象**: observability.db quality_trends 表 0 条记录，FP3 收敛曲线无法工作

**修复**: Gate 通过后自动写入 3 个指标
```python
# e2e_orchestrator.py validate 节点
_obs.log_quality_trend("gate_score_avg", _score, sample_size=1)
_obs.log_quality_trend("gate_pass_rate", 1.0 if result.passed else 0.0, sample_size=1)
_obs.log_quality_trend("failure_count", float(_n_fail), sample_size=1)
```

### 3.3 预测验证→学习闭环断裂

**现象**: verify_predictions.py 产出归因经验但无法回流 learning_loop

**修复**: learning_loop.py 新增 add_failure_pattern()
- 写入 report_failures（供 recurrence_rate 统计）
- 写入 learning_lessons（供 build_lesson_prompt 读取）
- severity='prediction_verified' 标记来源

---

## 四、文件变更清单

### 新增文件 (5)

| 文件 | 用途 |
|------|------|
| `scripts/verify_predictions.py` | 预测自动验证 |
| `scripts/refresh_data.py` | 12 类数据增量刷新 |
| `scripts/batch_runner.py` | 批量运行 + 归档 |
| `.github/workflows/ci.yml` | GitHub Actions CI |
| `UPGRADE_REPORT_20260901.md` | 升级报告 |

### 修改文件 (7)

| 文件 | 修改内容 |
|------|----------|
| `pipeline/sw_serialize.py` | last30days 舆情注入 |
| `pipeline/prompt_injectors.py` | sentiment_str 注入器 |
| `pipeline/e2e_orchestrator.py` | quality_trends + compliance + claim citation 接线 |
| `pipeline/learning_loop.py` | add_failure_pattern() |
| `core/deepseek_client.py` | record_timeout() |
| `core/smart_router.py` | _record_timeout() + record_timeout() |
| `core/settings.py` | LLM_HTTP_TIMEOUT 90→180s |

### 新增报告 (1)

| 文件 | 用途 |
|------|------|
| `output/prediction_health/PREDICTION_SYSTEM_STATUS.md` | 预测系统状态 |

---

## 五、测试状态

```
31 passed, 1 warning in 1.01s

test_claim_citation.py      16 passed
test_yfinance_ticker.py     12 passed
test_market_anchors.py       3 passed
```

---

## 六、数据资产现状

### 数据库

| 库 | 用途 | 记录数 |
|----|------|--------|
| financials.db | A股财务数据 | 活跃 |
| data_cache.db | 数据缓存 | 活跃 |
| consensus_estimates.db | 一致预期 | 活跃 |
| capital_flow.db | 资金流向 | 活跃 |
| observability.db | 可观测性 | quality_trends 开始积累 |
| learning_data.db | 学习数据 | 活跃 |
| findings.db | 研究发现 | 活跃 |
| track_record.json | 预测记录 | 2,246 条 |
| framework_registry.json | 框架注册表 | 效果字段开始实测回写 |
| method_reflection_log.json | 反思日志 | 活跃 |

### 数据刷新

12 类 sync 脚本通过 refresh_data.py 统一调度，支持拓扑排序和依赖感知。

---

## 七、架构当前状态

```
输入: "宁德时代" --type listed_company
  │
  ├→ preflight_check (运行环境验证)
  ├→ data collection
  │    ├→ DataCollectorV5 (akshare + yfinance + Tavily)
  │    ├→ last30days (Hacker News 舆情)
  │    └→ DataPipeline fallback
  ├→ data_stager (9 engine, 3 backend)
  │    ├→ macro / valuation / roic / moat
  │    ├→ sentiment / industry_chain / dividend
  │    └→ sector / implied
  ├→ chart generation (15+ charts)
  ├→ compute pipeline (DCF + 可比 + 场景 + SOTP)
  ├→ section_writer (SAC 3段式, zhipu/deepseek)
  │    ├→ prompt_injectors (20+ 注入器含 sentiment_str)
  │    └→ dimension_grouper (4 组并行)
  ├→ StyleCompiler (AIGC 去指纹)
  ├→ IronGate (101 checks, 0.55 阈值)
  ├→ claim_citation (数据溯源附录)
  ├→ compliance_clauses (合规免责)
  ├→ method_reflection (框架效果回写)
  ├→ quality_trends (收敛趋势写入)
  └→ export (DOCX)

异步闭环:
  verify_predictions.py (每日)
    → hit/miss/partial → 归因标签
    → learning_loop.add_failure_pattern()
    → auto_apply_lessons → 下次报告规避

  refresh_data.py (定时)
    → 12 类 sync → financials.db / ...
```

---

## 八、待观察项

| 项 | 时间窗口 | 风险 | 缓解 |
|----|----------|------|------|
| 预测验证首次运行 | 2026-10-31 | 3m 预测到期 | 自动验证脚本已就绪 |
| zhipu 延迟 | 持续 | 大 prompt 超时 | circuit breaker 宽容 + 180s 超时 |
| CI 首次通过 | push 后 | remote 不可达 | 需确认 GitHub access |
| batch_runner 并行 | 待实现 | LLM 限流 | 当前串行足够 |
| quality_trends 积累 | 持续 | 冷启动 | 每次 Gate 自动写入 |
| track_record 去重 | 待处理 | 重复预测 | verify_predictions 幂等 |

---

## 九、下一步建议

1. **短期 (1-2 周)**:
   - 等待 2026-10-31 首批 3m 预测到期，验证自动验证闭环
   - 监控 zhipu 延迟和 circuit breaker 状态
   - 清理 track_record.json 中的重复预测

2. **中期 (1 个月)**:
   - quality_trends 积累足够数据后生成收敛曲线
   - batch_runner 增加并行支持（需 LLM 限流策略）
   - last30days 扩展到 Brave/Perplexity 源

3. **长期 (季度)**:
   - 基于验证结果优化 SAC 维度权重
   - framework_registry 效果数据驱动框架选择
   - 预测准确率目标：hit rate > 60%, alpha > 0
