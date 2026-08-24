# 2号分析师 — Agent强制管线法典

> 版本: V1.2 | 2026-07-31
> 定位: 在agent上运行的超级智能化中文分析师系统
> 宪法: docs/FP1-FP7-超级智能法则.md（必须先读）
> LLM: Multi-Provider（默认 DeepSeek，自动降级 通义/OpenRouter/SiliconFlow）
> 模型: deepseek-chat (写作) / deepseek-reasoner (深度推理)

---

## 零、不可违反的原则

1. **Multi-Provider LLM 可用** — 默认 DeepSeek；provider 失败自动切换（通义/OpenRouter/SiliconFlow），不可全挂时禁止编造数据
2. **数据零编造** — 每个数据点必须有真实来源
3. **FP4图灵测试** — 资深分析师分辨不出人机
4. **排版必须精美** — 字体一致、表格不溢出、图片不溢出
5. **图表必须丰富** — 密度、准确性、专业性缺一不可

---

## 一、Multi-Provider LLM 使用

`python
# 统一API入口 (OpenAI兼容格式)
import requests

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# 报告写作: deepseek-chat (temperature=0.3, 精准)
# 深度推理: deepseek-reasoner (temperature=0.2, 深度思考)

headers = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json",
}

response = requests.post(
    f"{DEEPSEEK_BASE_URL}/chat/completions",
    headers=headers,
    json={
        "model": "deepseek-chat",  # 或 deepseek-reasoner
        "messages": [
            {"role": "system", "content": "你是一位资深分析师..."},
            {"role": "user", "content": "请撰写深度分析报告..."}
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    }
)
`

**提示词格式要求:**
- System Prompt: 角色设定（资深分析师、具体机构风格）
- User Prompt: SAC框架 + 数据 + 图表路径 + 写作要求
- 禁止在System Prompt中暴露内部方法论标签

---

## 二、5步强制管线

### Step 1: 读SAC和Writing Charter

`python
from writing_charter import generate_writing_charter
charter = generate_writing_charter(asset_name, report_type="industry_deep")
`

**验收**: SAC全部维度必须覆盖，遗漏=不合格。

### Step 2: 数据采集（必须使用真实数据）

`python
# 方式A: 超级爬虫（推荐）
from data.super_crawler import SuperCrawler
crawler = SuperCrawler()
data = crawler.collect_all("标的名称", 
    dimensions=["financial", "news", "industry", "policy", "macro", "competitor"])

# 方式B: 专项采集
from pipeline.data_collector import DataCollector
collector = DataCollector()
data = collector.collect(asset, report_type)
`

**规则**:
- ❌ 不能编造数据
- ✅ 每个数据点必须标注来源（"数据来源：公司公告/akshare/Crawl4AI"）
- ✅ 多源冲突时使用 DataCredibilityEngine 做交叉验证
- ✅ 数据获取失败时使用降级方案，标注"数据局限性"

**数据可信度检查**:
`python
from core.data_credibility import DataCredibilityEngine, DataPoint
credibility = DataCredibilityEngine()
points = [
    DataPoint("revenue_2025", 1500, "亿", "公司公告", confidence=0.9),
    DataPoint("revenue_2025", 1480, "亿", "Wind", confidence=0.85),
]
validated = credibility.cross_validate(points)
`

### Step 3: 计算管线

`python
from pipeline.compute_engine import ComputeEngine
engine = ComputeEngine()
results = engine.compute(data)
`

**计算包括**: 三桥(营收/利润率/费用) + DCF + 可比(PE/PB/PS) + SOTP + 情景分析 + 敏感性
**规则**: 计算与生成分离。LLM不能修改计算结果。

### Step 4: 图表生成（必须丰富专业）

`python
from pipeline.chart_runner import ChartRunner
runner = ChartRunner(style="cicc")
charts = runner.generate_all(results, report_type)
`

**最少图表数量**:

| 报告类型 | 图表 | 表格 | 说明 |
|---------|------|------|------|
| 行业深度 | >= 5张 | >= 3个 | 市场规模+竞争格局+增长对比+盈利对比+估值 |
| 上市公司 | >= 5张 | >= 3个 | 营收趋势+利润率+DCF敏感性+可比估值+情景 |
| 非上市公司 | >= 4张 | >= 2个 | 单位经济+融资历史+竞争定位+估值三角 |
| 财报点评 | >= 2张 | >= 1个 | 超预期分析+分部穿透 |

**图表质量要求**:
- 图表必须在正文中引用，不能全部塞在末尾
- 每个图表必须有: 标题 + 编号 + 数据来源脚注 + 单位标注
- 图表要有上下文分析（不是简单放图，要分析图表的含义）
- 使用 
unner.generate_data_table() 生成规范表格

**排版要求**:
- 图表大小一致（宽度不超过正文宽度）
- 表格不溢出（每列不超过30字符）
- 字体统一（中文宋体，英文Times New Roman）

### Step 5: 写作循环（核心 — 由Agent亲自执行）

`python
from pipeline.agent_loop import ScoreEngine, ReportFixer

score_engine = ScoreEngine(use_deepseek=True)  # 启用DeepSeek辅助评分
fixer = ReportFixer()

# 写初稿（使用DeepSeek API）
report = call_deepseek(system_prompt, user_prompt)

# 评分
score = score_engine.score(report)
feedback = score_engine.get_feedback(score)
print(feedback)

# 如果评分<0.9，修复后重新评分
while score["overall"] < 0.9:
    report = fixer.fix(report, feedback)
    score = score_engine.score(report)
    feedback = score_engine.get_feedback(score)
    # Agent分析失败原因→针对性修改→重新评分

# 评分>=0.9 → 提交Iron Gate
`

## 评分体系

ScoreEngine 8维评分:

| 维度 | 权重 | 说明 | 检测方式 |
|------|------|------|---------|
| AIGC指纹 | 15% | AI痕迹越少越好 | AIScanner |
| 人感 | 10% | 资深分析师语气 | HumanSenseDetector |
| 质量 | 20% | 论证深度+数据质量+可读性 | QualityScorer |
| SAC覆盖 | 15% | SAC维度覆盖度 | 正则统计 |
| 图表密度 | 15% | 图表数量和分布 | 正则统计 |
| 数据可追溯 | 10% | 有来源 | 正则检查 |
| 排版一致性 | 5% | 无问题 | FormatProfessionalizer |
| 说服力架构 | 10% | 有弧线 | 关键词检测 |

**综合评分 >= 0.9 才能进入Iron Gate。**

---

## 三、Iron Gate（不可绕过的最终校验）

`python
from pipeline.iron_gate import IronGate

gate = IronGate(output_path, report_type, style)
gate_report = gate.run_all()

if not gate_report.passed:
    print(gate.get_feedback(gate_report))
    # 必须回到写作循环！
else:
    gate.export_final(output_dir)
`

**Iron Gate是不可绕过的。** 不存在"跳过Gate"的模式。

### Iron Gate校验项:
1. AIGC指纹 < 15%
2. 人感评分 >= 0.7
3. 质量评分 >= 0.8
4. SAC维度覆盖 >= 80%
5. 图表密度达标
6. 数据可追溯（有来源标注）
7. 格式一致（字体统一、无溢出）
8. 禁止模式（无内部方法论标签）
9. 说服力架构完整

---

## 四、排版标准

### 字体规范
| 机构 | 中文 | 英文 | 正文字号 |
|------|------|------|---------|
| 中金/CICC | 宋体 | Times New Roman | 10.5pt |
| 高盛/GS | 宋体 | Times New Roman | 10pt |
| 摩根/MS | 宋体 | Times New Roman | 10pt |
| 麦肯锡 | 微软雅黑 | Arial | 10pt |
| BCG | 微软雅黑 | Arial | 10pt |

### 禁止的排版问题
- ❌ **加粗滥用** — 加粗字符不超过段落长度的10%
- ❌ **字体大小不一致** — 全文统一字号
- ❌ **表格溢出** — 每列不超过30个字符
- ❌ **图片溢出** — 图片宽度不超过正文
- ❌ **图片在末尾堆砌** — 图表必须在对应的分析文本附近

### 必须包含的排版元素
- ✅ 页眉（报告标题+机构名称）
- ✅ 页脚（页码+日期）
- ✅ 免责声明
- ✅ 数据来源标注（每个图/表底部）
- ✅ 图表编号（图1/图2/表1/表2）

---

## 五、外部工具集成（MCP 生态）

2号分析师已接入以下 MCP 工具，Agent 在对应阶段必须使用：

### 5.1 Tavily — Step 2 数据采集阶段（推荐优先使用）

Tavily 是 AI 专用搜索引擎，返回结构化结果（来源+日期+摘要+相关性评分）。

**使用场景**：
- 搜索行业新闻、政策变化、竞争对手动态
- 获取最新市场数据和行业趋势
- 验证和补充 akshare 不覆盖的实时信息

**使用方式**：
```
在 Step 2 数据采集过程中，调用 tavily_search 工具
搜索关键词建议："{标的} 行业分析 2026" / "{标的} 最新动态"
```

**与 crawl4ai 的关系**：Tavily 返回结构化搜索结果（更快、更精确），crawl4ai 抓取整页内容（更深入但更慢）。优先用 Tavily，需要深入全文时用 crawl4ai。

### 5.2 Playwright MCP — Step 2 数据采集阶段（深度网页操作）

**使用场景**：
- 抓取需要 JS 渲染的动态网页数据
- 操作需要登录的行业付费报告网站
- 访问官网获取最新产品参数/财务数据

**使用方式**：
```
当 crawl4ai 无法抓取目标页面（JS 渲染/需登录/动态内容）时，
使用 playwright_mcp 工具打开浏览器获取数据
```

### 5.3 akshare-mcp — Step 2 数据采集（A 股金融数据全覆盖）

akshare-mcp 提供 A 股实时行情、历史 K 线、财务报表、估值指标、板块全景、宏观经济等金融数据。和 `data_collector.py` 中内联的 akshare 使用同一数据源，但通过 MCP 协议可直接在写作时按需调用。

**使用场景**：
- 获取个股实时行情和历史 K 线
- 查询财务报表（利润表/资产负债表/现金流量表）
- 查询财务指标（ROE/ROIC/毛利率趋势）
- 查询估值数据（PE/PB/PS 历史分位）
- 查询板块行情和行业涨跌榜
- 查询宏观经济指标（GDP/CPI/PMI）
- 查询实时财经新闻

**使用方式**：
```
在写作时如果需要具体的金融数据，直接调用 akshare 相关工具。
例如：查询贵州茅台的财务数据、查询白酒板块行情等。
```

**与 data_collector 的关系**：data_collector 自动化采集时已通过内联 akshare 获取数据。此 MCP 版本供 agent 在写作过程中按需补充查询。

### 5.4 Composio — Step 6 报告分发阶段

Composio 提供 800+ 外部服务连接器。报告通过 Iron Gate 后，按需分发：

**使用场景**：
- `composio_github`：把报告提交到 GitHub 仓库
- `composio_gmail`：把报告发送给订阅者
- `composio_slack`：把报告推送到团队频道（使用前先 `composio add slack`）

**使用方式**：
```
Iron Gate 通过后，在 _step_export 中或之后调用 Composio 工具做分发：
1. 报告保存为 md/docx 后 → Composio Slack 发送通知
2. 报告通过 Gate → Composio GitHub 提交
3. 最终定稿 → Composio Gmail 发送
```

### 5.4 selfMCP — 工具自发现（后台运行）

selfMCP 运行时自动检测当前 MCP Server 列表，发现缺少工具时尝试自动安装。
此工具在后台工作，不需要手动调用。

### 5.5 数据兜底协议（agent 补充数据 — 桥接节点）

当主数据链路数据不足（`needs_agent=true`）时，agent 允许补充数据，但必须回流管线：

**流程：**
```
① 快速检查缺口（不写报告，秒级）：
   python pipeline/scheduler.py "标的" --type listed_company --data-check-only
   → 看 data_sufficiency / output/<标的>_gaps.json
   → needs_agent=true = 核心财务数据（营收/净利趋势）不足

② 用 WebSearch / WebFetch / akshare-MCP / 本地库补数据
   → 生成 enrich-file JSON（schema 见 pipeline/data_enrichment.py 顶部）
   → 自动模板: python scripts/agent_backfill.py template "标的" --out enrich.json

③ python pipeline/scheduler.py "标的" --type listed_company \
     --enrich-file enrich.json
   → 数据进入 collected_data → compute → write → Iron Gate

一键自动版：python scripts/agent_backfill.py auto "标的"
  （检查缺口 → 提示补什么 → 生成模板）
```

**enrich-file 最小示例：**
```json
{
  "asset": "标的",
  "generated_by": "agent",
  "generated_at": "2026-07-31T00:00:00+08:00",
  "items": [
    {"type": "fig_data", "key": "fig_revenue_trend",
     "data": {"2023": 120.5, "2024": 145.0, "2025": 170.2},
     "source": "公司公告 2026-03", "confidence": 0.9, "unit": "亿元"},
    {"type": "news", "items": ["新闻1", "新闻2"],
     "source": "WebSearch: 标的最新动态", "confidence": 0.8}
  ]
}
```

**合规红线：**
- 每条数据必须有 `source` 字段，无来源 → 桥接层拒绝
- 只接受白名单 fig_* 键（防污染图表管线）
- agent 补充数据自动生成「数据补充来源」附录，Iron Gate 可追溯
- 严禁把搜索/抓取结果直接拼进正文

---

## 六、新增工具索引

| 工具 | 路径 | 用途 |
|------|------|------|
| DeepSeek Client | core/deepseek_client.py | DeepSeek API统一封装 |
| Super Crawler | data/super_crawler.py | 超级数据采集引擎 |
| Data Credibility | core/data_credibility.py | 多源交叉验证+可信度评分 |
| Format Professionalizer | export/format_professionalizer.py | 专业排版引擎 |
| **DataEnrichment** | pipeline/data_enrichment.py | 数据兜底桥接：充足性检查+本地兜底+agent数据回流 |
| **Tavily MCP** | Claude Desktop MCP | AI 专用搜索（Step 2 数据采集优先使用） |
| **akshare-mcp** | Claude Desktop MCP | A 股金融数据（Step 2 按需查询） |
| **Playwright MCP** | Claude Desktop MCP | 网页交互式数据采集（Step 2 深度数据） |
| **Composio MCP** | Claude Desktop MCP | 报告分发推送（Step 6 完成后推送） |
| **selfMCP** | Claude Desktop MCP | MCP 工具自动发现与安装 |

---

## 六、FP4检验

**问自己**: 这篇报告如果拿给中金的分析师看，他能看出是AI写的吗？

判断标准:
1. 语言自然吗？有没有AI常见的套话？
2. 数据都有来源吗？能不能点对点追溯？
3. 排版专业吗？和真实研报放一起能分出来吗？
4. 论证深刻吗？有反方论证吗？有So What链吗？

**如果有人能看出是AI → 不合格，必须重写。**

---

## 八、强制管线规则——不可绕过

### 规则1：所有输出必须经过IronGate
- 禁止绕过IronGate直接输出DOCX/PDF/PPTX
- 禁止使用pandoc无校验转换
- 禁止使用python-docx手动拼接代替管线
- 唯一合规路径：Data→Compute→MD→IronGate→Export

### 规则2：内容密度门禁
- MD正文必须≥8000字（行业深度）/≥6000字（上市公司）/≥5000字（非上市公司）
- DOCX内容字数不得低于MD字数的70%
- 图表必须嵌入正文对应位置，禁止堆叠在文末
- 不满足以上条件→禁止导出

### 规则3：ContentEnforcer执行检查
- 每次导出前自动调用 ContentEnforcer.assert_pipeline_complete()
- 检查步骤标记文件确认管线完整
- 检查失败→返回错误信息，不执行导出

### 规则4：MD是唯一真源
- 所有格式（DOCX/PDF/PPTX）都必须从MD转换生成
- 禁止直接修改DOCX内容（只允许通过修改MD再转换来更新）
- MD→DOCX转换时必须保留全部内容，不得删减

---
## 七、完整执行示例（PowerShell）

`powershell
# 1. 设置DeepSeek API
 = os.environ.get("DEEPSEEK_API_KEY", "")

# 2. 读SAC
 = python -c "from writing_charter import generate_writing_charter; import json; print(json.dumps(generate_writing_charter('test', 'industry_deep'), ensure_ascii=False))" | ConvertFrom-Json

# 3. 采集数据
 = python -m data.super_crawler "新能源汽车" --dimensions financial industry policy macro

# 4. 计算管线
 = python -m pipeline.compute_engine --input data.json --type industry_deep

# 5. 生成图表
 = python -m pipeline.chart_runner --input results.json --type industry_deep --style cicc

# 6. 写作循环（由Agent执行）
#   - 用DeepSeek API写初稿
#   - 调ScoreEngine评分
#   - 评分<0.9→分析失败→改写→重新评分
#   - 评分>=0.9→提交Iron Gate

# 7. Iron Gate
 = python -m pipeline.iron_gate report.md --type industry_deep --style cicc
# 未通过→回到步骤6
`

---

### Prompts目录索引

所有写作prompt已外部化到 prompts/ 目录，详见 prompts/INDEX.md。
Agent在写作前必须加载对应的prompt文件。
**这是法典，不是参考指南。违反任何一条规则的输出都是不合格的。**
