# 1hao-analyst-v51

智能化分析师系统 — 在 AI Agent 上运行的研报写作系统。输入分析指令，产出机构级研究报告。方法论驱动，去 AI 化，多风格，可对标。

## 快速开始

```bash
python main.py write "贵州茅台分析，核心判断是直销占比超预期，风格中金"
```

不需要 API Key，不需要联网，不需要数据源。

## 系统能力

- **3 类报告**: 行业深度分析(12维MECE+Serenity9步) / 上市公司深度(9阶) / 非上市企业分析(9阶+数据声明)
- **7 种机构风格**: 中金/高盛/摩根士丹利/麦肯锡/波士顿咨询/中信/学术论文
- **去 AI 化**: 3条Style Compiler规则(去套话/结论先行/判断密度) + Devil's Advocate自纠错
- **回测对标**: FinRpt 5维评分体系(Clarity/Depth/Data/Logic/Objectivity)
- **财务引擎**: 收入桥/毛利桥/费用桥/DCF/三情景/可比SOTP(通过V30桥接)
- **多格式导出**: .md / .docx / .pdf / 展开式HTML

## 目录

```
core/      方法论核心(SAC/论证/Style Compiler/校验/修改学习)
data/      数据管线(EastMoney行情/akshare财务/假说验证)
compute/   财务计算引擎(V30桥接)
export/    导出器
tests/     测试+回测对标
docs/      文档
```

## 快速命令

```bash
python main.py write "贵州茅台分析"          # 全管线生成报告
python main.py pack "宁德时代"                # Agent写作指令包
python tests/run_all.py                      # 全量测试(49通过)
python tests/benchmark_full.py               # 回测对标
```

## License

MIT
