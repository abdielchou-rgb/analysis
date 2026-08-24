# 2hao-analyst SDD 规格说明书

> **Specification-Driven Development**
> 此文件是代码和文档的共同父级。修改规格 → 重新生成代码 + 文档。
> 生成器：`harness/generate_docs.py`
> 更新日期：2026-07-30

---

## 1. 系统定位

| 属性 | 值 |
|------|-----|
| 系统名 | 二号分析师 (Analyst No.2) |
| 核心能力 | AI 驱动的深度研究报告生成 |
| 对标质量 | CICC / Goldman Sachs / McKinsey / BCG 机构级 |
| 输出格式 | Markdown → DOCX / PDF / PPTX |
| 宪法文件 | CLAUDE.md (约束 AI Agent 行为) |
| 版本锚点 | V80+ / pyproject.toml v0.1.0 |

---

## 2. 管线合约

### 2.1 唯一入口

```python
# scheduler.py (v2) / main.py — 二选一，同一后端
pipeline.scheduler.schedule(asset, report_type, style, output_dir, time_anchor)
main.run_pipeline(asset, report_type, style, output_dir, time_anchor)
# 都调用 pipeline.e2e_orchestrator.E2EOrchestratorV2
```

### 2.2 管线步骤

| # | 步骤 | 模块 | 输出 | 合约 |
|---|------|------|------|------|
| 0 | preflight | `E2ENodes.preflight_check` | runtime health | 每个依赖可用 |
| 1 | data | `DataCollectorV5` | financials, sources | 不编造数据 |
| 2 | charts | `ChartRunner` / `ChartPipeline` | chart_paths | ≥5 charts |
| 3 | compute | `compute_engine` | compute_results | 确定性计算 |
| 4 | write | `SectionWriter` (SAC 3段) | report_text | ≥3000 chars |
| 5 | gate | `IronGate` (24项) | gate_result | score ≥ 0.55 |
| 6 | export | `report_gate` → `exporter` | docx / pdf / pptx | 通过 gate |

### 2.3 环境要求

| 环境变量 | 用途 | 必须 |
|----------|------|------|
| `DEEPSEEK_API_KEY` | 主 LLM 后端 | ✅ |
| `TAVILY_API_KEY` | 网络搜索采集 | 可选 |
| `ALIYUN_API_KEY` | 阿里云 Qwen（备用） | 可选 |
| `OPENROUTER_API_KEY` | 多模型网关 | 可选 |

---

## 3. 数据契约

### 3.1 SAC 框架文件

| 文件 | 用途 | 维度数 |
|------|------|--------|
| `core/sacs/sac_listed_company.yaml` | 上市公司分析 | 14 |
| `core/sacs/sac_industry_deep.yaml` | 行业深度研究 | 12 |
| `core/sacs/sac_unlisted_company.yaml` | 非上市公司分析 | 11 |
| `core/sacs/sac_earnings_notes.yaml` | 业绩点评 | 7 |

### 3.2 数据零容忍规则 (FP2)

1. 不允许编造数据点
2. 不允许在没有来源的情况下给出数字
3. 不允许用 "AI 生成的合理估计" 冒充真实数据
4. 数据源不可用时，报告失败而不是编造
5. 每个数值必须标注 Actual(A) 或 Estimate(E) 或 Forecast(F)

---

## 4. 质量契约

### 4.1 IronGate 24 项检查

| 类别 | 检查项 | 权重 | 阻断 |
|------|--------|------|------|
| 结构 | content_volume | 1.0 | ✅ |
| 结构 | content_density | 0.7 | ❌ |
| 结构 | section_continuity | 0.5 | ❌ |
| AI 痕迹 | aigc_fingerprint | 1.0 | ✅ |
| AI 痕迹 | human_sense | 0.5 | ❌ |
| AI 痕迹 | personal_narrative | 0.8 | ✅ |
| AI 痕迹 | markdown_artifacts | 0.6 | ❌ |
| 框架 | sac_coverage | 0.8 | ✅ |
| 框架 | forbidden_patterns | 0.8 | ✅ |
| 框架 | table_density | 0.5 | ❌ |
| 数据 | data_traceability | 0.8 | ✅ |
| 数据 | data_fidelity | 0.8 | ✅ |
| 数据 | placeholder_charts | 0.6 | ❌ |
| 图表 | chart_density | 0.6 | ❌ |
| 图表 | chart_analysis_quality | 0.5 | ❌ |
| 逻辑 | persuasion_architecture | 0.6 | ❌ |
| 逻辑 | so_what_chain | 0.8 | ✅ |
| 逻辑 | decision_gate | 0.5 | ❌ |
| 逻辑 | bold_call | 0.7 | ❌ |
| 逻辑 | moat_analysis | 0.5 | ❌ |
| 格式 | format_consistency | 0.5 | ❌ |
| 估值 | dcf_sensitivity | 0.5 | ❌ |
| 估值 | multi_model | 0.5 | ❌ |
| 表 | table_quality_md | 0.4 | ❌ |

**计算公式**: `overall_score = sum(weights) / sum(max_possible)`
**阈值**: `min_score = 0.55` (gates_config.yaml)

### 4.2 风格编译器 (StyleCompiler) 8 规则

| 规则 | 作用 | 阻断 |
|------|------|------|
| conclusion_first | 结论先行，数据随后 | 修改 |
| remove_ai_patterns | 清除 AI 套话 | 修改 |
| anti_ai_fingerprint | P0 自动移除 + P1 警告 | 修改+报告 |
| human_sense_check | 人感指标检测 | 报告 |
| strip_aigc_metadata | 切除 AIGC 元数据 | 修改 |
| ensure_judgment_density | 判断密度评分 | 报告 |
| remove_methodology_tags | 切除内部方法论标签 | 修改 |
| check_protocol_bans | 检查禁令遵守 | 报告 |

---

## 5. 规格 ↔ 代码 ↔ 文档映射

| 规格文件 | 驱动代码 | 生成文档 |
|----------|----------|----------|
| `harness/pipeline_contract.py` | `pipeline/*.py`, `main.py` | `CLAUDE.md` |
| `core/sacs/*.yaml` | `core/protocol.py`, `pipeline/section_writer.py` | `AGENTS.md` |
| `export/gates_config.yaml` | `pipeline/iron_gate.py`, `export/report_gate.py` | `SKILL.md` |

### 同步规则

1. 修改 `pipeline_contract.py` 或 `gates_config.yaml` 后 → 运行 `python -m harness.generate_docs`
2. 修改 SAC YAML 后 → 无需手动同步（section_writer 直接读取）
3. CLAUDE.md 若与 `generate_claude_md()` 输出不一致 → pre-commit 会阻断
