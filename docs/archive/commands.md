# 1号分析师 V50+ — CLI 命令文档

> **版本**: V50.0 | **日期**: 2026-07-23
> **代码**: `D:\Claude\projects\analysis\1hao-analyst-v50+\V50`
> **入口**: `python cli.py <command> [options]`

---

## 快速开始

```bash
cd D:\Claude\projects\analysis\1hao-analyst-v50+\V50

# 查看所有命令
python cli.py --help

# 查看子命令用法
python cli.py write --help
python cli.py pack --help
```

---

## 命令总览

| 命令 | 功能 | 是否需 API Key | 产出 |
|------|------|---------------|------|
| `write` | 全管线生成报告（研究→数据→论证→写作→验证→导出） | 可选（LLM 行文时需） | .md / .docx / .pdf |
| `pack` | 生成 agent 写作指令包（无行文，仅约束） | 否 | .json 指令包 |
| `hypothesis` | 验证一个投资假说 | 否 | 控制台摘要 |
| `edit` | 分类修改已有报告 | 否 | 修改后的 .md |
| `research` | 生成研究协议（21 个研究任务） | 否 | 控制台 agent 指令 |
| `verify` | 检查已有报告的风格合规性 | 否 | 控制台报告 |
| `report` | 显示可观测性仪表盘 | 否 | 控制台统计 |

---

## 1. `write` — 全管线报告生成

```bash
python cli.py write "<分析指令>" [options]
```

### 参数

| 参数 | 说明 |
|------|------|
| `input` | 分析指令，如"贵州茅台上市公司分析，风格中金" |
| `--signature` | 分析师署名 |
| `--model` | LLM 模型覆盖（仅在 `--llm` 时有效） |
| `--llm` | 启用 LLM 行文引擎（需设置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY） |
| `--verbose, -v` | 详细输出 |

### 输入格式（Type A — 结构化）

```
"<资产>分析，核心判断<判断>，风格<机构>"
```

示例：
```
python cli.py write "贵州茅台分析，核心判断是i茅台直销占比超预期，风格中金"
python cli.py write "宁德时代上市公司深度分析，风格高盛"
python cli.py write "具身智能行业深度分析"
```

### 输入格式（Type C — 兜底）

```
"<资产/行业名称>"
```

示例：
```
python cli.py write "字节跳动非上市分析"
python cli.py write "半导体行业深度"
```

### 管线流程

```
T0 解析指令 → T0.5 假说验证 → T1 知识包（数据+计算）→ T2a 论证骨架 → T2b 行文 → Style Compiler → T3 验证+图表+导出
```

### 输出

| 格式 | 路径 |
|------|------|
| `.md` | `outputs/<asset>_<brief_id>.md` |
| `.docx` | `outputs/<asset>_<brief_id>.docx`（需 V30 库） |
| `.pdf` | `outputs/<asset>_<brief_id>.pdf`（需 V30 库） |
| 图表 | `outputs/charts/<code>_*.png` |

---

## 2. `pack` — Agent 写作指令包（核心功能）

最推荐的 agent 使用方式：系统产出结构化约束，agent 参照写作。

```bash
python cli.py pack "<分析指令>"
```

### 输出 JSON 结构

```json
{
  "brief": {
    "asset": "贵州茅台 600519.SH",
    "report_type": "listed_company",
    "core_thesis": "i茅台直销渠道改革超预期",
    "style_profile": "cicc"
  },
  "scaffold": {
    "title": "贵州茅台深度分析",
    "core_disagreement": {
      "market": "直销占比45%后趋于稳定",
      "our_view": "可突破50%",
      "key_variable": "i茅台GMV增速和渠道效率"
    },
    "sections": [
      {
        "id": "core_disagreement",
        "title": "核心分歧",
        "thesis": "市场认为...我们判断...",
        "counter_thesis": "反方观点...",
        "evidence_ids": ["price", "pe"],
        "required_citations": 2,
        "data_gaps": ["渠道库存数据未公开"]
      }
    ],
    "data_gaps_total": []
  },
  "evidence": [
    {"name": "price", "value": 1300, "unit": "元", "source": "eastmoney"}
  ],
  "style_rules": {
    "conclusion_first": true,
    "forbidden_terms": ["值得注意的是"],
    "min_judgment_density": 1.2,
    "citation_style": "inline"
  },
  "forbidden_patterns": ["SAC", "AI生成"]
}
```

### Agent 使用此包的工作流

```
1. Agent 收到指令包（JSON）
2. 按 scaffold.sections 写正文，每节 thesis + evidence 约束
3. 遵守 style_rules + forbidden_patterns
4. Agent 写完后，用 verify 命令检查
```

---

## 3. `hypothesis` — 假说验证

```bash
python cli.py hypothesis "<假说>"
```

### 示例

```
python cli.py hypothesis "茅台直销占比能突破50%吗？"
python cli.py hypothesis "宁德时代PE合理区间？"
python cli.py hypothesis "比亚迪2024年净利润能否超过400亿？"
```

### 输出

```
Hypothesis: 茅台直销占比能突破50%吗？
Confidence: medium
Supporting evidence: 1  Opposing evidence: 0
Data gaps: 1
  - consensus data unavailable

Price: 1305, 20d: +2.3%, YTD: +12.1%
52wk range: 1050 - 1420
```

---

## 4. `edit` — 分类修改

```bash
python cli.py edit "<修改指令>" --file <报告路径> [--output <输出路径>] [--edit-type <类型>]
```

### 修改类型

| `--edit-type` | 适用场景 | 动作 |
|---------------|---------|------|
| `weak_evidence` | "证据不够充分" | 回查 T1 找更强证据 |
| `biased_judgment` | "太激进/太保守" | 调整判断词强度 |
| `logic_gap` | "这里缺一步" | 标记逻辑断裂点 |
| `style_mismatch` | "不是我们家的写法" | 调用 Style Compiler |
| `structure` | "放错位置" | 段落移动标记 |
| `verbose` | "太啰嗦" | 段落压缩 |

如不指定 `--edit-type`，系统自动识别。

### 示例

```
python cli.py edit "证据不够充分" --file outputs/茅台分析.md --output outputs/茅台分析_v2.md
python cli.py edit "太激进了" --file outputs/报告.md --edit-type biased_judgment
```

---

## 5. `research` — 研究协议

```bash
python cli.py research "<研究主题>"
```

输出 21 个研究任务（Serenity 9 步 + 12 维 MECE），agent 按此执行研究。

### 示例

```
python cli.py research "贵州茅台上市公司深度分析"
```

输出包含：
- 9 个 Serenity 工作流步骤
- 12 个 MECE 维度（深度模式）或 9 个（上市公司模式）
- 写作指令（含禁止项/位置约束/风格要求）

---

## 6. `verify` — 风格合规性检查

```bash
python cli.py verify --file <报告路径> [--sac <SAC_ID>] [--style <风格ID>]
```

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--file` | 必填 | 报告 markdown 文件路径 |
| `--sac` | `sac_listed_company` | 检查的 SAC ID |
| `--style` | 空（仅检测基础规则） | 风格 profile ID |

### 输出

```
=== Style Compiler Report ===
Rules applied: 3/10
Deviations: 2
  - conclusion_first: flip
  - sentence_length: split long sentence (135 chars)

Style compliance: PASS
```

---

## 7. `report` — 可观测性

```bash
python cli.py report
```

### 输出

```
=== V50+ Observability Report ===
LLM Usage Today:  {'calls': 12, 'total_tokens': 45321, ...}
Quality Summary:  {'pass_rate': '91.7%', ...}
Validate Trend:   [{'day': '2026-07-22', 'pass_rate': 85.0}, ...]
```

---

## 集成指引（Agent 使用）

### 作为 Skill 调用

```
/1hao-analyst 贵州茅台上市公司分析，风格中金
/1hao-analyst hypothesis 茅台PE合理区间？
```

### Python API

```python
import sys
sys.path.insert(0, r"D:\Claude\projects\analysis\1hao-analyst-v50+\V50")

from run_v50 import V50PlusOrchestrator

orc = V50PlusOrchestrator()

# 方式 1：全管线
result = orc.run("贵州茅台分析，核心判断直销占比超预期")
print(result.report_md[:500])

# 方式 2：假说验证
hv_result = orc.run_hypothesis("茅台直销占比能突破50%吗？", "600519")
print(hv_result["summary"])

# 方式 3：研究协议
brief_text = orc.prepare_research("贵州茅台行业深度分析")
print(brief_text)
```

---

## 数据依赖

| 数据 | 来源 | 是否需要安装 | 是否需要 API Key |
|------|------|-------------|-----------------|
| 实时行情 | EastMoney HTTP API | 否 | 否 |
| K 线 | 腾讯财经 HTTP API | 否 | 否 |
| 财务历史 | akshare | `pip install akshare` | 否 |
| 一致预期 | akshare | `pip install akshare` | 否 |
| 新闻/公告 | crawl4ai / trafilatura | `pip install crawl4ai trafilatura` | 否 |
| 估值计算 | V30 计算引擎 | 需 akshare 数据 | 否 |

---

## 测试

```bash
# 全量测试
python tests/run_all.py

# 端到端测试
python tests/test_e2e.py

# 风格编译器测试
python tests/test_style_compiler.py

# SAC 门禁测试
python tests/test_sac_gate.py

# Schema 测试
python tests/test_schema.py
```

预期：**全部通过，0 失败**。
