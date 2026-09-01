# Golden Samples Population Guide

## Overview
Populate `benchmark/golden/{type}/` with **30 real institutional reports** (6 per type × 5 types) converted from PDF to Markdown.

## annual_reports 语料库（2026-08-29 新增）

与上述 SAC 风格研报样本**用途不同**：这里是**原始事实源**（ground truth corpus），不是分析师报告。

- 位置: `benchmark/golden/annual_reports/*.md`（原始 TXT 备份在 `benchmark/golden_raw/annual_reports/`）
- 规模: 593 份 A 股年报全文，113 家公司 × 2018-2024 七个年度（面板数据）
- 来源: 百度网盘 `【A025】上市公司报告`（UTF-8 TXT，巨潮口径）
- 格式: 每份头部带 frontmatter（`stock_code` / `year` / `orig_file`），正文为年报纯文本
- 入库脚本: `scripts/ingest_annual_reports.py`（幂等，重跑自动跳过已有文件）

用途：
1. **财务证据检验**：listed_company / earnings_notes 生成时的事实核对源（营收/毛利/ROE 等数字与年报原文对账）
2. **同公司跨年回归测试**：同一公司 7 年年报可直接构造时间序列一致性测试
3. **数据采集节点降级源**：akshare 失败时年报文本可作为 fallback 输入

注意：年报 ≠ 分析师报告，**不得**将年报文本直接作为 listed_company 风格 golden 样本（会污染 style calibration）。

## Required Structure

```
benchmark/golden/
├── listed_company/          (6 files)
│   ├── 贵州茅台_cicc.md
│   ├── 宁德时代_gs.md
│   ├── 美的集团_ms.md
│   ├── 工业富联_jpm.md
│   ├── 长江电力_mck.md
│   └── 招商银行_bcg.md
├── industry_deep/           (6 files)
│   ├── 半导体设备_cicc.md
│   ├── AI算力产业链_gs.md
│   ├── 新能源车供应链_ms.md
│   ├── 生物制药CDMO_jpm.md
│   ├── 低空经济_mck.md
│   └── 数据要素_bcg.md
├── unlisted_company/        (6 files)
│   ├── 某AI芯片独角兽_cicc.md
│   ├── 某新能源电池独角兽_gs.md
│   ├── 某生物医药独角兽_ms.md
│   ├── 某机器人独角兽_jpm.md
│   ├── 某量子计算独角兽_mck.md
│   └── 某商业航天独角兽_bcg.md
├── earnings_notes/          (6 files)
│   ├── 贵州茅台_cicc.md
│   ├── 宁德时代_gs.md
│   ├── 美的集团_ms.md
│   ├── 工业富联_jpm.md
│   ├── 长江电力_mck.md
│   └── 招商银行_bcg.md
└── decision_memo/           (6 files)
    ├── 柯力传感油位传感器代工_cicc.md
    ├── 某车企收购激光雷达供应商_gs.md
    ├── 某药企License-in创新药_ms.md
    ├── 某科技巨头投资AI基建_jpm.md
    ├── 某PE收购消费品牌_mck.md
    └── 某主权基金入股半导体_bcg.md
```

## Conversion Requirements

### 1. PDF → Markdown Conversion
Use `mineru` or similar:
```bash
# Install
pip install mineru

# Convert single PDF
mineru -p report.pdf -o output_dir

# Batch convert
for f in *.pdf; do mineru -p "$f" -o "md_output/${f%.pdf}"; done
```

### 2. Required Markdown Structure
Each `.md` must contain these sections (matching SAC dimensions):

#### For `listed_company` (14 dimensions):
```markdown
# 公司名称 深度分析报告

## 核心分歧与投资逻辑
- 市场共识 vs 我们的判断
- 分歧幅度(量化)
- 证伪条件

## 商业模式验证
- 护城河类型评估(品牌/转换成本/网络效应/成本优势)
- 经营杠杆/财务杠杆拆解
- 杜邦驱动类型

## 财务证据检验
- 营收桥接(底部-up + 顶部-down)
- 毛利桥接
- ROE杜邦三层拆解

## 竞争位置确认
- 格林沃德三维(供应/需求/规模经济)
- 反馈回路分析

## 增长可持续性
- 量/价/结构拆分
- TAM约束验证

## 治理检验
- 管理层激励/持股/过往决策

## 估值映射
- DCF(含失败概率/国家风险溢价)
- 可比估值
- 戴维斯双击/双杀
- Kelly赔率

## 催化剂与跟踪
- 3/6/12个月事件时间线

## 证伪与风险
- 至少3条可观察证伪条件
- 均值回归判断
- 系统失效状态

## 资金面与会计穿透
- 北向/公募/两融/大股东增减持
- 收入确认政策/资本化/减值/表外负债
```

#### For `decision_memo` (must answer client questions):
```markdown
# 决策备忘录: 项目名称

## 核心判断 (首页必含)
- 评级/目标价/时间窗口
- 委托方必答问题覆盖清单

## 背景与委托意图
- 客户核心问题清单

## 分析框架 (SAC decision_memo维度)
- 决策门判断(3门2GO)
- 核心分歧
- 市场规模验证
- 竞争格局/卡位
- 生产/运营可行性
- 投入产出/回收期
- 战略衍生价值
- 风险/证伪条件
- 执行路线图
```

### 3. Quality Gates (must pass)
After conversion, each file must pass:
```bash
# Test single file
python -m pytest tests/test_golden_regression.py::test_golden_regression -k "茅台" -v

# Gate thresholds per type:
# listed_company: gate_score >= 0.88
# industry_deep: gate_score >= 0.85
# unlisted_company: gate_score >= 0.82
# earnings_notes: gate_score >= 0.80
# decision_memo: gate_score >= 0.90
```

## Source Access (where to get real reports)

| Source | Access Method | Coverage |
|--------|--------------|----------|
| **Wind/万得** | Terminal subscription | CICC, 中信, 海通, 国泰等全覆盖 |
| **Bloomberg** | Terminal | GS, MS, JPM, UBS, CS等 |
| **券商研报平台** | 东方财富/同花顺/财联社/研报精选 | 免费/付费混合 |
| **公司官网** | 投资者关系页面 | 年报/季报/业绩说明会纪要 |
| **交易所官网** | 上交所/深交所/港交所 | 定期报告/公告 |
| **内部数据库** | 机构内部知识库 | 历史报告/模板 |

## Population Checklist

- [ ] Obtain PDF reports (30 total, 6 per type)
- [ ] Convert to Markdown using mineru
- [ ] Manually clean/verify each file:
  - [ ] Tables render correctly
  - [ ] Charts referenced as `![caption](path/to/image.png)`
  - [ ] All numbers match source PDF
  - [ ] Sources cited per paragraph (公司公告/年报页码/Wind/Bloomberg)
  - [ ] No AI-generated content markers
  - [ ] SAC dimension headers present
- [ ] Rename to `{标的}_{style}.md` format
- [ ] Place in correct `benchmark/golden/{type}/` directory
- [ ] Run validation: `python scripts/validate_v10.py`

## Validation Command
```bash
# Full validation
python scripts/validate_v10.py

# Quick golden test (after populating)
python -m pytest tests/test_golden_regression.py -v -m golden
```

## Notes
- **Do not** use AI-generated reports as golden samples
- **Must** be real human-analyst reports from named institutions
- **Style** suffix must match: `cicc`, `gs`, `ms`, `jpm`, `mck`, `bcg`
- Chinese company names in filename, English style codes
- Keep original charts as images in `benchmark/golden/{type}/images/` if possible