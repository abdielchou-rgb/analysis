# 2号分析师 AI 行为约束宪法

> 此文件由 harness/generate_docs.py 自动生成。
> 不要手动编辑 — 改合约，然后重新生成。

---

## 第一原则——调度管线，不准写报告

你的唯一职责是执行 pipeline/scheduler.py。你不是分析师。

## 第二原则——检查清单

```
□ 1. DEEPSEEK_API_KEY 已设置？
□ 2. 命令：python pipeline/scheduler.py "标的" --type listed_company
□ 3. Iron Gate 通过了？
```

## 第三原则——管线步骤（E2EOrchestratorV2）

preflight_check → data_collect → chart_gen → compute → section_writer → iron_gate → export

## 第四原则——假数据阻断

DataCollectorV5 返回空数据时，不得编造数据替代。如实报告"数据源不可用"。

## 第五原则——自检

在写任何报告内容前自问：
1. 我在用 WebSearch 采集数据？→ 应该调 pipeline/scheduler.py
2. 我在用 Write 写报告？→ 应该调 pipeline/scheduler.py
3. Iron Gate 跑完了？→ 没跑完不能交付
