---
name: 2hao-performance
description: 二号分析师性能模式 — 调度管线，OpenRouter优先，DeepSeek兜底。触发词：'性能模式'、'performance mode'、'跑管线'、'E2E测试'、'生成研究报告'。
license: MIT
metadata:
  author: 2hao-analyst团队
  version: "2.0"
---

# 二号分析师性能模式 (2hao-performance)

Turn your agent into a SAC-driven report generator by scheduling the E2E pipeline.

这个 Skill 把 opencode 变成一个自动化研究报告生成引擎。它不是替代分析师——它是分析师的生产管线：你告诉它标的和类型，它自动完成数据采集、SAC维度写作、IronGate质量校验、导出。

---

## 核心原则

1. **管线是唯一入口。** 所有报告必须通过 `main.py` 生成，不手动拼装。
2. **计算和写作分离。** 数字来自确定性计算（akshare/yfinance/DCF），LLM 只负责叙述。
3. **质量门禁不可绕过。** IronGate 78项检查，0.55阈值，未通过不交付。

---

## 触发条件

当用户提出以下请求时激活：
- `性能模式写一份（某公司）的分析`
- `performance mode 跑一下（某标的）的管线`
- `跑管线`、`E2E测试`
- `生成（某公司）的研究报告`

**关键区别：**
- 性能模式（本 skill）：调用 `main.py` 一键运行，黑盒
- 训练模式：Agent 逐步调用各模块，白盒，可观察每步结果

---

## LLM 策略

**性能模式**：LLM 主通道走 OpenRouter（`.env` 现有 OPENROUTER_API_KEY）；OpenRouter 不可用 → 降级 DeepSeek

### Provider 优先级

| 模式 | 第一优先 | 第二优先 | 说明 |
|------|----------|----------|------|
| 性能模式 | OpenRouter | DeepSeek | OpenRouter 多模型网关，速度快 |
| 训练模式 | DeepSeek | OpenRouter | DeepSeek 推理能力强，适合深度分析 |

---

## 工作流程

### 步骤 1：解析用户意图

从用户输入中提取：
- **标的 (asset)**：公司名或股票代码（必需）
- **报告类型 (report_type)**：见下表（默认 industry_deep）
- **风格 (style)**：见下表（默认 cicc）
- **输出目录 (output_dir)**：默认 output

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

### 步骤 2：构造命令

```bash
cd D:\Claude\projects\2hao-analyst
& ".venv\Scripts\python.exe" -u main.py "<标的>" --type <报告类型> --style <风格> --output <输出目录>
```

**示例：**
```bash
# 宁德时代业绩快评（CICC风格）
& ".venv\Scripts\python.exe" -u main.py "宁德时代" --type earnings_notes --style cicc --output output

# 半导体行业深度研究
& ".venv\Scripts\python.exe" -u main.py "半导体" --type industry_deep --style cicc --output output

# 非上市企业尽调
& ".venv\Scripts\python.exe" -u main.py "字节跳动" --type unlisted_company --style mck --output output
```

### 步骤 3：执行管线

运行命令并等待完成。管线执行时间：
- `earnings_notes`：约 8-12 分钟（单轮）
- `industry_deep`：约 15-20 分钟（单轮）
- `listed_company`：约 15-20 分钟（单轮）
- `unlisted_company`：约 10-15 分钟（单轮）

**环境变量（已配置在 .env 中）：**
- `OPENROUTER_API_KEY`：主 LLM 后端（性能模式优先）
- `DEEPSEEK_API_KEY`：兜底 LLM 后端
- `TAVILY_API_KEY`：网络搜索（可选，有速率限制）
- `MAX_ATTEMPTS`：最大重试轮数（默认 3）

### 步骤 4：汇报结果

管线完成后，向用户汇报：
1. **Gate 状态**：通过/阻断 + 分数
2. **输出文件**：MD 和 DOCX 路径
3. **关键指标**：SAC 覆盖率、图表数量、表格数量
4. **如有阻断**：列出失败的检查项和原因

---

## 管线流程图

```
用户输入 (标的 + 类型 + 风格)
        ↓
   [1] Harness 验证（语法/导入链/P0扫描）
        ↓
   [2] 数据采集（akshare + Tavily + yfinance）
        ↓
   [3] 图表生成（ChartEngine + placeholder fallback）
        ↓
   [4] 计算管线（DCF + 可比 + 场景 + SOTP）
        ↓
   [5] SAC 写作（SectionWriter × 3段式 DeepSeek）
        ↓
   [6] StyleCompiler（8条确定性规则去AI化）
        ↓
   [7] IronGate（78项注册检查，0.55阈值）
        ↓
   [8] 导出（MD + DOCX + VisualGate）
```

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

### Q: 管线运行失败怎么办？
A: 检查日志 `logs/` 目录。常见原因：
- API 密钥过期：检查 `.env` 文件
- 网络超时：重试或检查代理设置
- Gate 阻断：查看具体检查项，修复报告内容后重试

### Q: 如何加速运行？
A: 设置环境变量：
```bash
$env:MAX_ATTEMPTS='1'  # 只跑1轮，约8-12分钟
```

### Q: 如何查看详细的 Gate 检查结果？
A: 管线运行后会在 `output/` 目录生成 `*_gate_report.json`

### Q: 支持哪些股票市场？
A: 主要支持 A 股（akshare），部分支持港股/美股（yfinance）

---

## 风险与边界

- 本 Skill 提供研究报告生成服务。所有输出仅供参考，不构成投资建议。
- 涉及具体买卖建议时，标注"本研究不构成投资建议"。
- 分析师需要对报告内容承担最终责任。
