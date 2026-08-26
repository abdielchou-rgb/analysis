# 二号分析师 (2hao-analyst) 项目分析与代码审核报告

> 审核日期：2026-07-30
> 项目版本：V1.0.0
> 审核范围：全量源码（18个核心文件）

---

## 一、项目概述

**二号分析师**是一个 AI 驱动的深度研究报告生成系统，基于 **SAC 因果链框架**（So What → Argument → Conclusion），自动生成符合国际顶级投行标准的上市公司、行业及非上市公司深度研究报告。

| 属性 | 值 |
|------|-----|
| 项目名称 | `2hao-analyst` |
| 版本 | V1.0.0（代码架构为 V51/V57 级别） |
| 许可证 | MIT |
| Python 版本 | >=3.10 |
| LLM 后端 | DeepSeek API（唯一允许的 LLM） |
| 核心方法论 | SAC 因果链框架 |

---

## 二、项目目录结构

```
D:\2hao-analyst\
├── main.py                          # 主入口点
├── workflow.py                      # V51 管线编排器（全量集成版）
├── pyproject.toml                   # 项目构建配置
├── requirements.txt                 # Python 依赖
├── README.md / SKILL.md / AGENTS.md / CLAUDE.md
│
├── core/                            # 核心引擎层
│   ├── models.py                    # 全局数据模型
│   ├── deepseek_client.py           # DeepSeek API 封装（多Provider+断路器）
│   ├── sacs/                        # SAC 分析框架定义
│   │   ├── __init__.py              # SACLoader 统一加载器
│   │   ├── sac_listed_company.yaml  # 上市公司14维SAC框架
│   │   ├── sac_industry_deep.yaml   # 行业深度研究SAC框架
│   │   ├── sac_unlisted_company.yaml
│   │   ├── sac_earnings_notes.yaml
│   │   └── methodology_registry.yaml
│   ├── compute/                     # 计算引擎（确定性Python，零LLM参与）
│   │   ├── pipeline.py              # L2计算层调度入口
│   │   ├── financial/               # 财务计算（收入桥/毛利桥/费用桥/DCF）
│   │   ├── valuation/               # 估值模块（DCF/可比/情景/SOTP）
│   │   └── quality_gate/            # 数值门禁
│   ├── styles/                      # 机构风格指纹库（中金/高盛/麦肯锡/摩根/BCG/中信）
│   ├── enforcer/                    # 约束执行器（Schema+Checklist）
│   ├── quality_scorer.py            # 8维质量评分器
│   ├── fp_scorer.py                 # FP4图灵测试评分
│   ├── ai_fingerprints.py           # AI指纹扫描
│   ├── human_signal_injector.py     # 人感信号注入
│   ├── hypothesis_verifier.py       # 假说验证器
│   ├── chart_engine.py              # 图表引擎
│   ├── argument.py / style.py / prose.py  # 论证/风格/文体引擎
│   ├── conviction.py                # 信念矩阵
│   ├── evidence_chain.py            # 证据链
│   └── ...                          # 其他核心模块
│
├── pipeline/                        # 核心管线层
│   ├── e2e_orchestrator.py          # E2E端到端编排器（AgentGraph状态机）
│   ├── scheduler.py                 # 强制管线入口（唯一合规入口）
│   ├── write_revise_loop.py         # 写→评→改循环
│   ├── section_writer.py            # SAC框架驱动的章节写作器
│   ├── iron_gate.py                 # Iron Gate 不可绕过的最终校验闸门
│   ├── agent_graph.py               # 轻量级状态机引擎（拓扑排序+依赖检查）
│   ├── step_manager.py              # 步骤管理器（强制顺序执行）
│   ├── data_pipeline.py             # 并行数据采集管线（断路器模式）
│   ├── chart_pipeline.py            # 图表生成管线
│   ├── format_sheriff.py            # 格式预检
│   └── ...                          # 其他管线模块
│
├── data/                            # 数据采集层
│   ├── super_crawler.py             # 超级数据采集引擎
│   ├── akshare_connector.py         # akshare连接器（A股数据）
│   ├── east_money_connector.py      # 东方财富连接器
│   ├── yfinance_engine.py           # yfinance引擎（美股数据）
│   └── ...                          # 其他数据源
│
├── export/                          # 输出层
│   ├── report_gate.py               # 唯一输出入口+强制阻断
│   ├── integrated_exporter.py       # 集成导出器（md/docx/pptx一站式）
│   ├── docx_exporter.py / pdf_exporter.py / pptx_exporter.py
│   ├── visual_gate.py               # 视觉质量门禁
│   └── ...                          # 其他导出模块
│
├── prompts/                         # 外部化 Prompt 库
│   ├── system/                      # 角色设定（中金/高盛/麦肯锡风格）
│   ├── writing/                     # 写作 Prompt（各章节模板）
│   └── quality/                     # 质量评分标准
│
├── tests/                           # 测试
├── docs/                            # 文档
├── benchmark/                       # 基准与校准
└── output/                          # 输出目录
```

---

## 三、核心架构：5步强制管线

所有报告生成必须经过以下5步，**不可跳过任何步骤**：

```
Step 1: 读SAC框架 + Writing Charter
    ↓
Step 2: 数据采集（Tavily/akshare/Crawl4AI/yfinance，并行+断路器）
    ↓
Step 3: 计算管线（收入桥+毛利桥+费用桥+DCF+可比估值+情景分析，零LLM参与）
    ↓
Step 4: 图表生成（matplotlib，专业排版，中文字体）
    ↓
Step 5: 写作循环（DeepSeek API写初稿 → ScoreEngine评分 → 评分<0.9则修复重写 → 循环）
    ↓
Iron Gate: 不可绕过的最终校验（7维评分，不合格不导出）
    ↓
Export: MD → DOCX / PDF / PPTX（多格式导出）
```

### 3.1 三条执行路径

| 路径 | 入口 | 驱动方式 | 特点 |
|------|------|----------|------|
| E2E编排器 | `pipeline/e2e_orchestrator.py` | AgentGraph 状态机 | 拓扑排序执行，硬失败模式，`main.py` 使用 |
| WriteReviseLoop | `pipeline/scheduler.py` | StepManager 强制顺序 | 写→评→改循环，"唯一合规入口" |
| V51编排器 | `workflow.py` | 全量集成 | 假说验证+交叉验证+信念矩阵+人感注入等 |

### 3.2 三层门禁体系

| 层级 | 组件 | 职责 |
|------|------|------|
| L1 | FormatSheriff | 格式预检（prompt泄露、空标记、来源覆盖率） |
| L2 | VisualGate | 视觉质量（图表密度、排版一致性） |
| L3 | IronGate | 内容质量（SAC覆盖率≥70%、数据可追溯、人感检测、22+项检查） |

### 3.3 八维评分体系

| 维度 | 权重 | 说明 |
|------|------|------|
| AIGC指纹 | 15% | AI痕迹越少越好 |
| 人感 | 10% | 资深分析师语气 |
| 质量 | 20% | 论证深度+数据质量+可读性 |
| SAC覆盖 | 15% | SAC维度覆盖度 |
| 图表密度 | 15% | 图表数量和分布 |
| 数据可追溯 | 10% | 有来源标注 |
| 排版一致性 | 5% | 无问题 |
| 说服力架构 | 10% | 有叙事弧线 |

**综合评分 ≥ 0.9 才能进入 Iron Gate，不合格报告不会导出。**

### 3.4 支持的报告类型与风格

**4种报告类型**：`industry_deep`（行业深度）、`listed_company`（上市公司）、`unlisted_company`（非上市公司）、`earnings_notes`（财报点评）

**6+种机构风格**：`cicc`（中金）、`goldman_sachs`（高盛）、`mckinsey`（麦肯锡）、`morgan_stanley`（摩根士丹利）、`bcg`（BCG）、`citic`（中信）

---

## 四、关键设计原则

| # | 原则 | 说明 |
|---|------|------|
| 1 | 只有 DeepSeek API 可用 | 不能使用 OpenAI/Claude/其他 API |
| 2 | 数据零编造 | 每个数据点必须有真实来源 |
| 3 | FP4 图灵测试 | 资深分析师分辨不出人机 |
| 4 | MD 是唯一真源 | 所有格式从 MD 转换生成 |
| 5 | Iron Gate 不可绕过 | 不存在"跳过 Gate"的模式 |
| 6 | Agent 只管调度，不准亲自写 | 必须通过 pipeline 执行 |
| 7 | StepManager 步骤不可跳过 | 架构级阻断 |
| 8 | 迭代退化禁止 | 回归基线检测，任何维度下降超 0.10 则阻断 |
| 9 | 假数据阻断 | 数据源不可用时如实告知，不编造 |

---

## 五、代码审核报告

### 5.1 P0 级 — 必须立即修复

#### 1. 硬编码 API Key 泄露

- **文件**：`pipeline/data_pipeline.py:87`
- **问题**：Tavily API Key 硬编码在源代码中作为默认值
- **风险**：代码推送到公开仓库时 Key 将泄露
- **建议**：移除默认值，仅从环境变量读取，缺失时抛异常

```python
# 当前（危险）
key = os.environ.get("TAVILY_API_KEY", "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")

# 建议
key = os.environ.get("TAVILY_API_KEY")
if not key:
    raise RuntimeError("TAVILY_API_KEY 环境变量未设置")
```

#### 2. IronGate 构造参数不匹配（运行时 BUG）

- **文件**：`pipeline/write_revise_loop.py:125`
- **问题**：`IronGate(self.report_type)` 缺少必需的 `report_path` 参数
- **影响**：`report_path` 被赋值为 `report_type` 字符串，后续 `Path(report_path)` 指向不存在的路径
- **建议**：补全 `report_path` 参数

```python
# 当前（BUG）
gate = IronGate(self.report_type)

# 建议
gate = IronGate(report_path=self.output_path, report_type=self.report_type)
```

#### 3. MAX_ITERATIONS=1 使写-评-改循环名存实亡

- **文件**：`pipeline/write_revise_loop.py:28`
- **问题**：`MAX_ITERATIONS = 1` 意味着只执行一次，永远不会进入修订循环
- **建议**：改为 ≥3

```python
# 当前
MAX_ITERATIONS = 1

# 建议
MAX_ITERATIONS = 3
```

#### 4. _per_section 潜在无限递归

- **文件**：`core/quality_scorer.py:212`
- **问题**：`_per_section` 内调 `self.score()`，`score()` 又调 `_per_section()`，形成递归且无深度限制
- **建议**：添加递归深度参数，超过阈值时停止递归

```python
def _per_section(self, text: str, depth: int = 0) -> dict:
    if depth >= 2:  # 最多递归2层
        return {}
    ...
    scores = self.score(body, _depth=depth + 1) if body else QualityScore()
```

#### 5. 硬编码 Windows 绝对路径

- **文件**：`pipeline/e2e_orchestrator.py:8`
- **问题**：`Path(r"D:\2hao-analyst")` 导致代码无法在其他机器或操作系统上运行
- **建议**：使用相对路径推导

```python
# 当前
_ROOT = Path(r"D:\2hao-analyst")

# 建议
_ROOT = Path(__file__).resolve().parent.parent
```

---

### 5.2 P1 级 — 高优先级修复

#### 6. 裸 `except: pass` 泛滥（5处）

- **文件**：`iron_gate.py:107,136,193`、`e2e_orchestrator.py:263`、`chart_pipeline.py:66`、`data_pipeline.py:188`
- **问题**：吞掉所有异常（包括 `KeyboardInterrupt`、`SystemExit`）
- **建议**：改为 `except Exception as e:` 并至少 `logger.warning`

```python
# 当前（危险）
except:
    pass

# 建议
except Exception as e:
    logger.warning(f"检查异常: {e}")
```

#### 7. 假数据注入

- **文件**：`pipeline/data_pipeline.py:191`、`pipeline/chart_pipeline.py:247`
- **问题**：无数据时生成假的市场规模数据 / 使用 `np.random` 生成图表，违反"无假数据"原则
- **建议**：明确标注为"示意数据"或拒绝生成

```python
# data_pipeline.py — 当前（违反原则）
cd["market_size"] = {"labels": ["2022", "2023", "2024", "2025E", "2026E"], "values": [100, 125, 158, 198, 245]}

# 建议
cd["market_size"] = {"labels": [], "values": [], "note": "数据源不可用，需人工补充"}
```

#### 8. `__import__("re")` 反模式

- **文件**：`core/deepseek_client.py:200`
- **问题**：使用 `__import__` 内联导入，严重反模式
- **建议**：改为文件顶部 `import re`

```python
# 当前
json_match = __import__("re").search(r"\{.*\}", content, __import__("re").DOTALL)

# 建议
import re  # 顶部

json_match = re.search(r"\{.*\}", content, re.DOTALL)
```

#### 9. SACLoader `_parse_yaml_simple` 中 `raw` 可能未定义

- **文件**：`core/sacs/__init__.py:63-66`
- **问题**：`ImportError` 时 `raw` 可能未赋值就进入 `except` 块
- **建议**：将 `raw = f.read()` 移到 `try` 之前，或要求 `pyyaml` 为必需依赖

#### 10. `ReportType.__members__` 检查逻辑错误

- **文件**：`core/models.py:94`
- **问题**：`__members__` 返回枚举名（如 `EARNINGS_NOTES`），而 `rt` 是枚举值（如 `earnings_notes`），条件永远为 `False`
- **建议**：使用 `ReportType(rt)` 的 `value` 属性检查，或使用 `_value2member_map_`

```python
# 当前（永远False）
report_type = ReportType(rt) if rt in ReportType.__members__ else ReportType.LISTED_COMPANY

# 建议
report_type = ReportType(rt) if rt in ReportType._value2member_map_ else ReportType.LISTED_COMPANY
```

#### 11. API Key 获取逻辑冗余

- **文件**：`core/deepseek_client.py:83-86`
- **问题**：`or` 两边调用同一个环境变量，第二句完全冗余
- **建议**：简化为 `os.environ.get("DEEPSEEK_API_KEY", "")`

---

### 5.3 P2 级 — 架构改进建议

#### 12. 断路器实现重复

- **文件**：`core/deepseek_client.py`、`pipeline/data_pipeline.py`
- **问题**：两套断路器实现，逻辑不同（前者基于连续失败次数，后者基于时间窗口重置）
- **建议**：统一为单一断路器实现，提取到 `core/circuit_breaker.py`

#### 13. `workflow.py` 的 `run` 方法 320 行

- **文件**：`workflow.py:61-387`
- **问题**：严重违反单一职责原则
- **建议**：拆分为 `_collect_data`、`_verify_hypothesis`、`_run_compute`、`_compile_style`、`_score_quality`、`_check_gates`、`_export` 等私有方法

#### 14. `sys.path` 修改泛滥

- **文件**：几乎所有文件
- **问题**：每个文件都手动 `sys.path.insert(0, str(_ROOT))`，表明项目未正确安装为包
- **建议**：使用 `pip install -e .` 可编辑安装替代运行时修改

#### 15. 关键词/阈值硬编码

- **文件**：`quality_scorer.py`、`iron_gate.py`、`sacs/__init__.py`
- **问题**：大量硬编码阈值（如 `0.9`、`0.5`、`5`）和关键词列表
- **建议**：从 YAML 配置或校准文件加载，保持 SAC 文件作为"单一事实源"

#### 16. DRY 违规：AI 指纹列表重复

- **文件**：`core/fp_scorer.py:6-11`、`core/ai_fingerprints.py`
- **问题**：两处定义 AI 指纹列表，内容不一致
- **建议**：统一到 `ai_fingerprints.py` 单一模块，其他模块引用

#### 17. 路径管理不一致

- **文件**：`e2e_orchestrator.py`（硬编码绝对路径）、`chart_pipeline.py`（`_ROOT` 指向 `pipeline/`）、其他文件（`parent.parent`）
- **建议**：统一为 `Path(__file__).resolve().parent.parent` 方式

#### 18. 中英文检查名混用

- **文件**：`pipeline/iron_gate.py`
- **问题**：`"内容体积"` vs `"placeholder_charts"` 命名不一致
- **建议**：统一为英文标识符，中文仅用于用户可见的显示名

#### 19. StepManager 被跳过标记

- **文件**：`pipeline/write_revise_loop.py:118-119`
- **问题**：直接 `mark_done("section2_write")` 而未实际执行，使 StepManager 形同虚设
- **建议**：要么实际执行，要么从 STEPS 列表中移除这些步骤

#### 20. 动态添加私有属性

- **文件**：`workflow.py:71,213-214`
- **问题**：`brief._learning_findings = ...` 运行时给 dataclass 动态添加属性，破坏类型安全
- **建议**：在 `WritingBrief` 中正式声明这些字段

#### 21. 拓扑排序性能问题

- **文件**：`pipeline/agent_graph.py:131-147`
- **问题**：`list.pop(0)` 是 O(n) 操作；内层循环遍历所有节点，总复杂度 O(V²)
- **建议**：使用 `collections.deque.popleft()` + 邻接表优化到 O(V+E)

#### 22. 图表管线重复导入 matplotlib

- **文件**：`pipeline/chart_pipeline.py:238-411`
- **问题**：每个图表方法都重复 `import matplotlib` 和 `matplotlib.use("Agg")`
- **建议**：在模块级别导入一次，`matplotlib.use()` 只调用一次

#### 23. 日志格式不一致

- **问题**：部分使用 `logger.info("%s", var)`（正确），部分使用 `logger.info(f"...{var}")`（不推荐），部分使用 `print()`
- **建议**：统一使用 `logger.info("...%s", var)` 延迟格式化方式

#### 24. 正则表达式误匹配

- **文件**：`core/ai_fingerprints.py:42`
- **问题**：`[某种意义上]` 是字符类，匹配"某/种/意/义/上"中任意一个字符，而非完整短语
- **建议**：改为 `(?:某种意义上)?`

---

## 六、修复优先级总览

| 优先级 | 编号 | 问题 | 文件 | 行号 |
|--------|------|------|------|------|
| **P0** | 1 | 硬编码 API Key 泄露 | data_pipeline.py | 87 |
| **P0** | 2 | IronGate 构造参数不匹配 | write_revise_loop.py | 125 |
| **P0** | 3 | MAX_ITERATIONS=1 使循环失效 | write_revise_loop.py | 28 |
| **P0** | 4 | _per_section 无限递归 | quality_scorer.py | 212 |
| **P0** | 5 | 硬编码绝对路径 | e2e_orchestrator.py | 8 |
| **P1** | 6 | 裸 except:pass（5处） | 多文件 | - |
| **P1** | 7 | 假数据注入 | data_pipeline.py, chart_pipeline.py | - |
| **P1** | 8 | __import__ 反模式 | deepseek_client.py | 200 |
| **P1** | 9 | SACLoader raw 未定义 BUG | sacs/__init__.py | 63-66 |
| **P1** | 10 | ReportType.__members__ 检查错误 | models.py | 94 |
| **P1** | 11 | API Key 获取逻辑冗余 | deepseek_client.py | 83-86 |
| **P2** | 12 | 断路器实现重复 | deepseek_client.py, data_pipeline.py | - |
| **P2** | 13 | workflow.py run 方法 320 行 | workflow.py | 61-387 |
| **P2** | 14 | sys.path 修改泛滥 | 几乎所有文件 | - |
| **P2** | 15 | 关键词/阈值硬编码 | 多文件 | - |
| **P2** | 16 | AI 指纹列表重复 | fp_scorer.py, ai_fingerprints.py | - |
| **P2** | 17 | 路径管理不一致 | 多文件 | - |
| **P2** | 18 | 中英文检查名混用 | iron_gate.py | - |
| **P2** | 19 | StepManager 被跳过标记 | write_revise_loop.py | 118-119 |
| **P2** | 20 | 动态添加私有属性 | workflow.py | 71 |
| **P2** | 21 | 拓扑排序性能 | agent_graph.py | 131-147 |
| **P2** | 22 | matplotlib 重复导入 | chart_pipeline.py | 238-411 |
| **P2** | 23 | 日志格式不一致 | 多文件 | - |
| **P2** | 24 | 正则表达式误匹配 | ai_fingerprints.py | 42 |

---

## 七、总体评价

### 优势

- **架构设计水准高**：SAC 因果链框架、5步强制管线、三层门禁、8维评分、Iron Gate 不可绕过等设计理念非常专业
- **方法论扎实**：SAC 框架用 YAML 定义、代码检查执行，实现了"框架即代码"的纪律
- **质量内建**：从数据采集到最终导出，每一步都有门禁，不合格不放行
- **风格系统完善**：6+种机构风格指纹库，Prompt 外部化管理
- **容错设计**：断路器、多Provider、自动降级、学习循环

### 不足

- **工程质量与架构设计存在明显落差**：硬编码路径/Key、裸 except、假数据注入、参数不匹配等 P0 问题需要优先修复
- **DRY 违规较多**：断路器、AI 指纹、关键词列表等在多处重复定义且内容不一致
- **类型安全不足**：大量函数缺少类型标注，动态添加属性破坏 dataclass 约束
- **配置管理薄弱**：阈值、路径、模型名等硬编码在源码中，难以调优

### 建议路线

1. **第一阶段**（紧急）：修复 5 个 P0 问题，确保系统在非开发环境下可运行
2. **第二阶段**（重要）：修复 6 个 P1 问题，消除安全隐患和运行时 BUG
3. **第三阶段**（重构）：逐步解决 P2 架构问题，提升代码质量和可维护性
4. **第四阶段**（增强）：添加完整的类型标注、统一配置管理、补充测试覆盖率