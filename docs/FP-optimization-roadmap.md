# 2hao-analyst FP 宪法优化路线图

> 基于 FP1-FP7 v3.0 的反思与优化计划
> 综合评分：78% (32个维度 25/7 ✅/⚠️/❌)
> 生成日期：2026-07-30

---

## 一、当前状态诊断

### 已完成的工程（不应回退）

- SAC 框架：4种报告类型，逻辑链5-20步 ✅
- IronGate：34项检查，L1-L6全透明 ✅
- StyleCompiler：9条规则(含strip_ai_preamble) ✅
- 低熵锚点prompt重构 ✅
- Gate回馈机制(fail_counter→hot→prompt) ✅
- Universal零依赖采集器 ✅
- 12个方法论框架 ✅
- PE/VC 5维度增强 ✅
- 三级降级体系(L1/L2/L3) ✅
- Cross_validate修复+DataCredibility接入 ✅
- AIScanner 12P0+5语义指纹 ✅
- SectionWriter 8个注入方法 ✅

### 系统的结构性问题（不可忽略）

| 问题 | 影响 | 根因 |
|------|------|------|
| akshare/yfinance 装不上 | 管线不能独立运行 | 网络环境限制,非代码问题 |
| A/E/F/B LLM执行率低 | FP2a合规检查失败 | LLM注意力分散(新prompt已解决) |
| FP3 记忆维度数据空洞 | 跨报告一致性为空 | 只跑了1份报告,无历史数据 |
| FP3 协作维度=0 | debate协议未被调用 | 优先级低,未实现 |
| learning_loop DB有结构无记录 | 演化机制无数据 | 只跑通一次,无持续运行 |
| compute_engine功能完整但数据依赖性高 | 分析深度依赖外部数据 | 需要akshare等数据源 |
| 报告包含"指令。"开场白 | 专业形象差 | StyleCompiler 9条规则覆盖 ✅ 已修复 |

---

## 二、依FP裁决链的优化优先级

裁决链：**FP4 → FP2a → FP2b → FP6 → FP7 → FP5 → FP3 → FP1**

### Phase 1: FP4 人感约束巩固（当前90%→98%）

#### 1.1 验证低熵prompt的真实合规率提升

当前已完成：system prompt重构 + 规则3分组 + hot failure回馈。需要真实跑一份报告验证LLM对(A)(E)(F)(B)、表格、章节编号的执行率。

```
验证方法: 跑1次柯力传感管线,检查输出
  - 是否以"一、"开头而非"指令。" → StyleCompiler检查
  - (A)(E)(F)(B)标注出现次数 → IronGate data_type_annotation
  - 表格数量≥3 → IronGate table_density
预计: 1小时,1次LLM调用
```

#### 1.2 AI Tone LLM判别激活

`_check_ai_tone_by_llm` 存在但被 circuit breaker 阻断(DeepSeek连续失败后_mark circuit broken)。需要重置circuit breaker或用Qwen。

```
修复: core/deepseek_client.py 重置circuit breaker或添加--no-circuit-breaker模式
预计: 15分钟
```

### Phase 2: FP2a 数据履约强化（当前85%→95%）

#### 2.1 装akshare

根本解决方案不是修fallback——是装akshare。当前环境pip install超时。建议：
- 使用预编译wheel: `pip install akshare --no-deps --only-binary :all:`
- 或使用国内镜像: `pip install akshare -i https://pypi.doubanio.com/simple`
- 或下载wheel后离线安装

```
预计: 30分钟(取决于网络)
```

#### 2.2 cross_validate实际数据验证

cross_validate节点从collected_data读取financials，但当前financials来自Tavily+DeepSeek提取,不是结构化数据。需要验证：
- financials是否被正确传递到cross_validate
- 交叉验证结果是否被写入data_context供writer使用
- DataCredibility评分是否可用

### Phase 3: FP7 反脆弱性（当前75%→90%）

#### 3.1 Multi-provider实际激活

scheduler.py已注册Qwen+OpenRouter,但需要验证:
- ALIYUN_API_KEY和OPENROUTER_API_KEY在.env中是否存在
- circuit breaker机制是否正常工作
- provider信用分是否更新

#### 3.2 故障注入自动化

chaos_test.py已创建但未集成到CI。pre-commit中集成:
```
pre-commit run → python scripts/chaos_test.py → 随机断数据源验证系统不崩
```

### Phase 4: FP5 智能演化（当前60%→80%）

#### 4.1 跑10份不同行业报告

FP5的核心缺口不是代码——是数据。learning_loop DB是空的,recurrence_rate无数据,ForwardPicksDB无记录。需要run pipeline多次积累:
```
标的示例:
  1. 柯力传感(传感器)      2. 宁德时代(电池)
  3. 中芯国际(半导体)      4. 贵州茅台(消费)
  5. 腾讯控股(互联网)      6. 比亚迪(汽车)
  7. 药明康德(医药)        8. 海螺水泥(建材)
  9. 东方财富(金融)        10. 汇川技术(工控)
```
每份报告完成后自动记录到learning_loop → 3个月后可做recurrence分析。

#### 4.2 hot failure回馈机制的完整闭环

当前: IronGate标记hot failure → section_writer在prompt中注入[⚠️上次评审未通过]
完成: hot failure积累到learning_lessons表 → auto_apply_lessons方法读取 → 自动调整prompt规则顺序

```
代码行数: ~30行
工作量: 1小时
```

### Phase 5: FP3 超级维度（当前50%→70%）

#### 5.1 D5协作——debate协议

FP3中协作维度当前为0。最小可行实现：
- 在section_writer.write()的Bold Call段落前增加2次额外LLM调用:
  1. bull agent: 写Bold Call论证(200字)
  2. bear agent: 写反方论证(200字)
  3. judge agent: 综合双方输出Bold Call(200字)

```
代码行数: ~60行(新增_build_debate_section方法)
额外时间: ~60s/报告(2次LLM调用)
工作量: 2小时
```

#### 5.2 D4记忆——跨报告引用的数据填充

report_cache.get_related_judgments()需要数据库有数据。Phase 4.1跑10份报告后自动填充。

---

## 三、长期方向（不紧急但重要）

### 架构层面

| 方向 | 价值 | 前置条件 |
|------|------|----------|
| 从单LLM调用→多agent协作(debate) | 分析深度质变 | Phase 5.1完成 |
| Gate score时序追踪+可视化 | 知道系统在变好还是变坏 | 跑10份报告积累数据 |
| A/E/F/B标注LLM执行率从0→100% | FP2a合规 | 低熵prompt+hot failure回馈 |
| 跨报告一致性网络 | 从单报告到知识网络 | report_cache积累数据 |
| 预编译akshare+playwright Docker镜像 | 零配置部署 | 独立于代码迭代 |

### 内容层面

| 方向 | 价值 | 工作量 |
|------|------|--------|
| 100+公司基准率数据库 | PE/VC分析真正可用 | 持续 |
| 行业级对标数据库 | 估值分位精度 | 持续 |
| 历史预测→真实结果→Bold Call准确率 | FP5闭环 | 持续 |

---

## 四、我的建议

当前2hao-analyst的状态是一个"功能完整、质量门禁齐全、但没上过路"的系统。78%的FP合规率反映的不是能力缺失——是**数据空洞**（DB没数据所以记忆/演化/协作维度测不了）。

下一步最该做的是：

**第1优先级：跑10份报告。** 不做任何新功能。每天早上一份，收集gate score、失败模式、LLM执行率。10份之后你就有能力判断哪些是代码问题（需要修），哪些是LLM行为问题（需要prompt调整），哪些是数据问题（需要积累）。

**第2优先级：把akshare装好。** 这个环境限制卡住了数据管线的独立性。

**第3优先级：debate协议。** 多agent协作是FP3协作维度的核心，也是让分析深度从"单LLM写三段"变成"多LLM辩论后综合"的关键升级。

整个系统的建设成本已经付了，现在只需要**用的成本**——让它做事，然后修做出来的问题。
