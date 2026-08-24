# 开发者指南 — 1号分析师 V51

## 快速开始

```bash
cd D:\Claude\projects\analysis\1hao-analyst-v51
python main.py write "贵州茅台分析"
```

## 目录结构

```
1hao-analyst-v51/
├── main.py            # CLI 入口 — python main.py write "xxx"
├── workflow.py        # 管线编排 — T0→T1→T2a→Style→T3
├── core/              # 方法论核心
│   ├── models.py      # 所有数据模型 (WritingBrief/KnowledgePackage/Deliverable/...)
│   ├── protocol.py    # SAC → Research Protocol + Devil's Advocate
│   ├── argument.py    # 论证引擎 — 从 SAC 生成 ArgumentScaffold
│   ├── style.py       # Style Compiler — 3 条确定性规则
│   ├── verify.py      # SAC Gate + 图表引擎
│   ├── edit.py        # 修改引擎 — 6 类分类修改
│   ├── learn.py       # 修改学习回路 — EditCase → T2a
│   ├── input.py       # 输入解析 — 类型A/B/C
│   ├── report.py      # 报告生成器（模板填充/LLM 回退）
│   ├── llm_client.py  # LLM 多后端客户端（Claude/GPT/DeepSeek）
│   ├── metrics.py     # 可观测性 — LLM 日志/validate 历史/质量趋势
│   ├── plugin.py      # 插件 SDK — SAC/风格/数据源三种插件
│   ├── sacs/          # SAC 方法论文档 (4 个 YAML)
│   ├── styles/        # 风格配置 (7 家机构)
│   └── ...
├── data/              # 数据层
│   ├── engine.py      # DataPipeline — EastMoney+K线+Cache
│   ├── verifier.py    # 假说验证 — T0.5
│   ├── orchestrator.py# 知识编排 — SAC 加载 + 数据加载 + 计算桥接
│   └── akshare_connector.py
├── compute/           # 财务计算 (V30 桥接)
│   ├── __init__.py    # ComputeEngine — V50+→V30 adapter
│   └── V30_compute/   # 外部 V30 计算引擎
│   └── V30_tools/     # 外部 V30 导出器/图表
├── export/            # 导出器
│   ├── __init__.py    # ExportAdapter — .md+.docx+.pdf
│   └── expandable_report.py  # 展开式 HTML
├── tests/             # 测试 + 回测
│   ├── run_all.py     # 全量测试 (49 tests)
│   ├── test_e2e.py    # 端到端测试 (19 tests)
│   ├── test_sac_gate.py
│   ├── test_schema.py
│   ├── test_style_compiler.py
│   ├── test_regression.py  # V22 基准回归
│   ├── benchmark_full.py   # FinRpt 5 维回测对标
│   └── compare_with_benchmarks.py
├── docs/              # 文档
│   ├── README.md      # 入口文档
│   ├── CHANGELOG.md   # 版本历史
│   └── commands.md    # CLI 命令文档
└── SKILL.md           # Cowork/Codex Skill 入口
```

## 核心数据流

```
main.py:write
  → V51Orchestrator.run(user_input)
    1. V51Input.parse(input) → WritingBrief
    2. KnowledgeOrchestrator.build(brief) → KnowledgePackage
    3. FinancialHistoryEngine.fetch(code) → 添加财务历史数据
    4. ComputeEngine.compute(brief, data) → FinancialSummary (可选)
    5. ArgumentEngine.design(brief, kp) → ArgumentScaffold
    6. scaffold + kp → 报告文本（模板/LLM）
    7. StyleCompiler.compile(report, profile) → 风格化文本
    8. V51Verify.deliver(compiled, brief, scaffold, kp) → Deliverable
    9. ExportAdapter.export_all(deliverable) → .md/.docx/.pdf
```

## 测试

```bash
# 全量编译检查 + 测试
python tests/run_all.py

# 端到端
python tests/test_e2e.py

# 回测对标（需要 benchmark/ 下有真实研报文本）
python tests/benchmark_full.py
```

## 扩展

### 新增 SAC

在 `core/sacs/` 下创建 YAML 文件，模型层自动加载。

### 新增风格

在 `core/styles/` 下创建 YAML，并在 `core/styles/profiles.py` 注册。

### 新增数据源

继承 `DataPipeline` 基类，实现 `fetch()` 方法。

## 构建状态

- Python: 3.10+
- 依赖: 零（核心模块使用标准库）
- 可选: akshare, baostock, openai, python-docx
- 测试: 49 passed, 0 failed (run_all)
