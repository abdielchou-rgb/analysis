---
name: 2hao-training
description: 二号分析师训练模式 — Agent直接调用2hao-analyst各模块写报告。触发词：'训练模式'、'training mode'、'用Agent直接写报告'、'调用2hao模块'、'直接写报告'。
license: MIT
metadata:
  author: 2hao-analyst团队
  version: "2.0"
---

# 二号分析师训练模式 (2hao-training)

Turn your agent into a SAC-driven report writer by directly calling 2hao-analyst modules.

这个 Skill 把 opencode 变成一个直接调用 2hao-analyst 各模块的报告写作引擎。它不是替代分析师——它是分析师的直接工具：你告诉它标的和类型，它按 SAC 框架顺序调用各模块，逐步生成报告。

---

## 核心原则

1. **按 SAC 框架顺序执行。** 必须按 数据采集 → 计算 → 图表 → 写作 → 校验 → 导出 顺序执行，不能跳过任何模块。
2. **计算和写作分离。** 数字来自确定性计算（akshare/yfinance/DCF），LLM 只负责叙述。
3. **质量门禁不可绕过。** IronGate 78项检查，0.55阈值，未通过不交付。

---

## 触发条件

当用户提出以下请求时激活：
- `训练模式写一份（某公司）的分析`
- `training mode 跑一下（某标的）的管线`
- `用Agent直接写（某行业）的深度研究`
- `调用2hao模块生成（某公司）的研究报告`
- `直接写报告`

**关键区别：**
- 性能模式（默认）：调用 `main.py` 一键运行，黑盒
- 训练模式（本 skill）：Agent 逐步调用各模块，白盒，可观察每步结果

---

## 工作流程

### 步骤 1：解析用户意图

从用户输入中提取：
- **标的 (asset)**：公司名或股票代码（必需）
- **报告类型 (report_type)**：见下表（默认 industry_deep）
- **风格 (style)**：见下表（默认 cicc）

| 报告类型 | 参数值 | 说明 |
|----------|--------|------|
| 行业深度 | `industry_deep` | 产业链分析、市场规模、竞争格局 |
| 上市公司 | `listed_company` | 财务穿透、估值、投资建议 |
| 非上市企业 | `unlisted_company` | 尽调、商业模式、退出路径 |
| 业绩快评 | `earnings_notes` | 财报点评、业绩概览、估值更新 |

| 风格 | 参数值 | 说明 |
|------|--------|------|
| 中金 | `cicc` | "我们认为"、正式学术 |
| 高盛 | `gs` | 英文术语、数据密度 |
| 中信 | `ms` | 简洁直给、结论先行 |
| 麦肯锡 | `mck` | MECE、金字塔结构 |
| BCG | `bcg` | 战略视角、长期主义 |
| 摩根大通 | `jpm` | 保守稳健、风险优先 |

### 步骤 2：读取 SAC 框架

```python
# 读取 SAC 维度关键词
import yaml
from pathlib import Path

sac_file = Path("core/sacs") / f"sac_{report_type}.yaml"
with open(sac_file, "r", encoding="utf-8") as f:
    sac_data = yaml.safe_load(f)

# 获取维度关键词
dim_keywords = {}
for dim in sac_data.get("required_dimensions", []):
    if isinstance(dim, dict) and dim.get("id"):
        dim_keywords[dim["id"]] = dim.get("keywords", [])
```

### 步骤 3：数据采集

```python
# 直接调用 data_collector
from pipeline.data_collector import DataCollector

collector = DataCollector()
data = collector.collect(asset, report_type)
```

### 步骤 4：计算管线

```python
# 直接调用 compute_engine
from pipeline.compute_engine import ComputeEngine

engine = ComputeEngine()
results = engine.compute(data)
```

### 步骤 5：图表生成

```python
# 直接调用 chart_runner
from pipeline.chart_runner import ChartRunner

runner = ChartRunner(style=style)
charts = runner.generate_all(results, report_type)
```

### 步骤 6：SAC 写作

```python
# 直接调用 section_writer
from pipeline.section_writer import SectionWriter

writer = SectionWriter(
    asset=asset,
    report_type=report_type,
    style=style,
    sac_data=sac_data,
    collected_data=data,
    compute_results=results,
    charts=charts
)
report_text = writer.write()
```

### 步骤 7：Iron Gate 校验

```python
# 直接调用 iron_gate
from pipeline.iron_gate import IronGate

gate = IronGate.from_text(report_text, report_type, style, asset=asset)
gate_result = gate.run_all()

if not gate_result.passed:
    # 返回修改建议，重新写作
    print(gate.get_feedback(gate_result))
else:
    # 导出报告
    from export.report_gate import ReportGate
    report_gate = ReportGate(report_text, gate_result)
    report_gate.export(output_dir)
```

---

## 模块调用顺序

```
1. 读取 SAC 框架 → 获取维度关键词
2. data_collector.py → 采集数据
3. compute_engine.py → 运行计算
4. chart_runner.py → 生成图表
5. section_writer.py → SAC 写作
6. iron_gate.py → 质量校验
7. style_compiler.py → 去AI化
8. report_gate.py → 导出
```

**铁律：必须按顺序执行，不能跳过任何模块。**

---

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

---

## 常见问题

### Q: 训练模式和性能模式有什么区别？
A:
- 性能模式：调用 `main.py` 一键运行，黑盒，速度快
- 训练模式：Agent 逐步调用各模块，白盒，可观察每步结果，适合调试和学习

### Q: 训练模式需要什么环境？
A:
- Python 3.10+
- 2hao-analyst 项目依赖（requirements.txt）
- DEEPSEEK_API_KEY 或 OPENROUTER_API_KEY

### Q: 训练模式如何处理错误？
A:
- 每个模块返回错误时，Agent 会分析原因并尝试修复
- 如果无法修复，返回错误信息给用户
- 可以重试或切换到性能模式

### Q: 训练模式支持哪些报告类型？
A:
- 行业深度（industry_deep）
- 上市公司（listed_company）
- 非上市企业（unlisted_company）
- 业绩快评（earnings_notes）

---

## 风险与边界

- 本 Skill 提供研究报告生成服务。所有输出仅供参考，不构成投资建议。
- 涉及具体买卖建议时，标注"本研究不构成投资建议"。
- 分析师需要对报告内容承担最终责任。
