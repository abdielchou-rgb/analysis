# 二号分析师 (Analyst No.2)

> 最后更新: 2026-07-30 | 更新方式: 手动（与 SAC YAML 对齐）
> 架构基线: E2EOrchestratorV2 + IronGate + StyleCompiler

---

## 项目定位

AI 驱动的深度研究报告生成引擎。基于 SAC（Structural Analysis Framework）因果链分析框架，对标 CICC、Goldman Sachs、McKinsey 等顶级机构的研究报告质量。

## 分析框架 (SAC)

SAC 定义在 `core/sacs/*.yaml` 中，每种报告类型独立一套：

| 报告类型 | 文件 | 核心维度 |
|----------|------|----------|
| listed_company | sac_listed_company.yaml | 14维：决策门→核心分歧→商业模式→财务验证→竞争→增长→治理ESG→估值→催化剂→证伪→母子公司→资金面→Bold Call→风险 |
| industry_deep | sac_industry_deep.yaml | 12维：产业定义→市场规模→增长驱动→技术路线→竞争格局→供应链→政策→盈利→风险→趋势→Bold Call→投资建议 |
| unlisted_company | sac_unlisted_company.yaml | 11维：商业模式→市场验证→增长→团队→财务→估值→竞争→风险→退出→Bold Call→建议 |
| earnings_notes | sac_earnings_notes.yaml | 7维：业绩概览→收入分析→利润分析→业务分拆→指引→估值→评级 |

## 管线架构

```
scheduler.py / main.py (入口)
  └→ E2EOrchestratorV2
       ├→ preflight_check (运行环境验证)
       ├→ data collection (akshare + Tavily + yfinance)
       ├→ chart generation (ChartEngine + placeholder fallback)
       ├→ compute pipeline (DCF + 可比 + 场景 + SOTP)
       ├→ section_writer (SAC 3段式 DeepSeek 写作)
       ├→ StyleCompiler (8条确定性规则去AI化)
       ├→ IronGate (101项注册检查，0.55阈值——以 pipeline/iron_gate.py 注册表为准，实时数见 docs/PIPELINE_FACTS.md)
       └→ export (DOCX + VisualGate + 门禁)
```

## 质量红线

| 规则 | 阈值 | 违反后果 |
|------|------|----------|
| SAC 维度覆盖率 | ≥70% | IronGate 阻断 |
| 数据来源标注率 | ≥30% | IronGate 阻断 |
| 图表数量 | ≥5 | IronGate 阻断 |
| 表格数量 | ≥3 | IronGate 阻断 |
| AIGC 指纹 | 0个P0 | StyleCompiler 自动移除 |
| 个人叙事 | 禁止 | IronGate 阻断 |
| 系统指令泄露 | 禁止 | StyleCompiler 自动移除 |
| So What 链 | 每段必须有 | IronGate 报告 |
| 目标价+评级+催化剂 | 必须包含 | IronGate 报告 |

## 环境依赖

| 依赖 | 用途 | 安装方式 |
|------|------|----------|
| DEEPSEEK_API_KEY | 主 LLM 后端 | .env |
| TAVILY_API_KEY | 网络搜索 | .env (可选) |
| python >=3.10 | 运行环境 | pip install -r requirements.txt |
| akshare | A股数据 | pip install akshare |
| playwright | 网页抓取 | pip install playwright && playwright install |

## 多 Provider 支持

实际代码支持多 LLM Provider（`core/deepseek_client.py` ProviderRegistry；原 `run_direct.py` 已移除）：
- DeepSeek Direct（最高优先级）
- 阿里云 Qwen（OpenAI 兼容接口）
- OpenRouter（多模型网关）

优先级按 0→1→2 递减，失败时自动 fallback。

## 已知限制

1. 数据采集依赖外部 API（Tavily / akshare / yfinance），网络异常时降级
2. PDF 导出依赖 fpdf2，复杂排版（图表混排、自定义字体）有限
3. IronGate 101项注册检查中一部分是 heuristic 判定（非 LLM 评估）
4. 版本管理目前手动，CLAUDE.md 需与 harness/pipeline_contract.py 同步
