# 2hao-analyst 后续工作计划

> 日期: 2026-07-31
> 基于 FP1-FP7 v3.0 宪法

---

## 裁决链

FP4 → FP2a → FP2b → FP6 → FP7 → FP5 → FP3 → FP1

优先修接近完成的高位维度,再处理需要累积数据的低位维度。

---

## Phase 0: 跑通完整管线(FP7-反脆弱性)

**当前**: ENFORCE_GATE已部署,export_report已验证通过,但图表引擎和akshare未接入。

| 任务 | 工作量 | 验证 |
|------|--------|------|
| 安装akshare+tavily+matplotlib | 30min | pip install,DataPipeline可获取结构化财务数据 |
| ChartEngine接入出口管线 | 30min | to_docx(chart_paths=chart_paths)传递图表参数 |
| 跑1份完整报告 | 10min | python scheduler.py "标的" --enforce-gate |

**完成标志**: 一份报告同时有(a)结构化财务数据 (b)5张图表嵌入正文 (c)通过IronGate+VisualGate

---

## Phase 1: 协作维度(FP3-D5)

**当前**: D5=0,debate协议未激活。这是FP3中最容易突破的维度。

| 任务 | 代码量 | 效果 |
|------|--------|------|
| Bold Call辩论 | ~80行 | bull agent写看多→bear agent写看空→judge综合 |
| 估值辩论 | ~60行 | 高估vs低估两张场景 |
| 加入IronGate | ~20行 | 检查conflicting_opinions是否存在 |

**完成标志**: IronGate新增debate_resolution检查,报告中同时存在可识别的看多和看空论证。

---

## Phase 2: 数据积累(FP5-智能演化+FP3-D4记忆)

**当前**: learning_loop DB空,ForwardPicks空,report_cache空。

**唯一解法**: 跑报告。

| 策略 | 频率 | 目标 |
|------|------|------|
| 每周跑2-3份报告 | 持续 | 3个月后learning_loop有~30条记录 |
| 记录每份gate score | 每次 | FP3-D6持续维度开始可测 |
| 记录bold call | 每次 | 到期后可验证预测准确率 |

不需要写代码。只需要跑。

---

## Phase 3: 剪枝(FP1-系统本质)

**当前**: ~72K行代码,~329个.py文件,其中~35%不在管线上。

| 任务 | 效果 |
|------|------|
| compute/V30_compute/ → archive (14K行) | 减少20%代码量 |
| 废弃的pipeline节点(content_enforcer等) | 减少5%代码量 |
| core/中未接入的孤儿模块标记 | 降低理解成本 |

**完成标志**: 可维护代码量从72K降至~50K。

---

## 不建议做的事

| 事项 | 原因 |
|------|------|
| 再写新框架 | 已有12个,超过了7±2的认知上限 |
| 再扩IronGate | 35项已覆盖FP2a/2b/4/6,继续扩张边际效益递减 |
| 再改prompt | P0+P2已从prompt和code两层加固 |
| DB schema设计 | 当前learning_loop schema够用,缺的是数据不是设计 |

---

## 优先级总结

```
本周: Phase 0 — 装akshare+调ChartEngine,跑1份完整报告
本月: Phase 1 — debate协议80行代码
持续: Phase 2 — 每周2-3份报告
整理: Phase 3 — 剪枝,从72K→50K
```
