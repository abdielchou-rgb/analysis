# 2hao-analyst 优化计划

## 根因分析

跨报告失败统计显示: 8份报告,58次失败,14个唯一失败项。

### Tier 1: 环境限制(不可通过修改2hao代码解决)

| 失败项 | 频率 | 根因 |
|--------|------|------|
| 图表密度 0/5 | 8/8 | ChartEngine未接入export管线 |
| chart_analysis_quality 0 | 8/8 | 同上 |
| data_traceability <0.1 | 8/8 | akshare未安装,来源格式不统一 |

这3项占24/58=41%的失败次数。不是代码bug——是环境配置问题:
- 装akshare → 结构化财务数据可用 → traceability从0.05到0.6+
- ChartEngine接入export管线 → 图表密度从0到5

### Tier 2: omission约束衰减(可通过代码自动补全)

| 失败项 | 频率 | 根因 |
|--------|------|------|
| so_what_chain | 8/8 | LLM在prompt中看到"每段必须有SoWhat"但没执行 |
| so_what_per_judgment | 8/8 | 同上,每个判断句缺少结论 |
| explicit_conclusion | 5/8 | 报告开头缺少评级/目标价/核心判断 |

这3项占21/58=36%的失败次数。核心原因是LLM的"不作为约束衰减"——
格式指令(禁止评分、禁止Markdown)执行率高,结构指令(必须有SoWhat)执行率低。
解决方案:在StyleCompiler中做自动补全——从正文中提取信息插入。

### Tier 3: SAC维度执行完整度(需强化prompt)

| 失败项 | 频率 | 根因 |
|--------|------|------|
| dcf_sensitivity | 4/8 | SAC在prompt中定义了但LLM未执行完整 |
| 决策门判断 | 2/8 | 同上 |

这2项占6/58=10%的失败次数。P2格式强制约束已经注入prompt,
但LLM仍然选择性执行。需要在StyleCompiler中增加dcf_sensitivity自动补全。

## 优化方案

### Phase 0: 装akshare(30分钟)
无需写代码。效果: data_traceability从0.05→0.6+,IronGate平均分提升约0.05。

### Phase 1: StyleCompiler自动补全SoWhat链(60行,1小时)
当前inject_conclusion和inject_decision_gate已完成。
新增_rule_inject_so_what: 从正文中提取判断句,在每个判断句末尾
自动追加"因此我们建议..."结论。

### Phase 2: StyleCompiler自动补全DCF敏感性(40行,30分钟)
从正文中提取估值相关信息,如果没有DCF敏感性矩阵则用模板补全。
对"dcf_sensitivity"失败项直接修复。

### Phase 3: ChartEngine接入export管线(30分钟)
在scheduler.py的export步骤中调用ChartEngine生成图表,
再通过exporter嵌入DOCX。解决"图表密度0/5"问题。

## 预期效果

| 阶段 | 修复项 | IronGate提升 | 代码量 |
|------|--------|-------------|--------|
| Phase 0 | data_traceability | +0.05 | 1行(安装) |
| Phase 1 | so_what链 | +0.04 | 60行 |
| Phase 2 | dcf_sensitivity | +0.02 | 40行 |
| Phase 3 | 图表密度 | +0.05 | 30行 |
| **合计** | **核心5项** | **+0.16(0.747→0.907)** | **~131行** |

## 不做的事

- 改prompt: 已试过5+次,每次改善幅度递减
- 扩IronGate: 35项已覆盖FP2a/2b/4/6
- 加新框架: 12个已达到认知上限
- 数据积累: learning_loop空不是代码问题
