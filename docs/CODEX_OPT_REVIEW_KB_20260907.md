# 二号分析师 · 四条 KB 观测/召回优化建议·评估备忘录

> 日期：2026-09-07
> 性质：审慎评估（不直接实施）。基于代码事实逐条判断"有没有道理、该怎么做、何时做"
> 关联：[CODEX_KB_FULL_PUSH_20260907.md](D:/Claude/projects/2hao-analyst/docs/CODEX_KB_FULL_PUSH_20260907.md)（已闭环部分）

---

## 0. 结论速览

| 建议 | 判断 | 优先级 | 前置条件 |
|---|---|---|---|
| 1. 补 retrieved 段指标 | ✅ 合理且便宜 | P1 | 先定"retrieved"口径 |
| 2. 行业标签推断层 | ✅ 方向极对，**实现要改** | P0 | 先接上游已有行业字段，名称推断只做离线兜底 |
| 3. citation coverage 按类型调权 | ⚠️ 方向对，当前是拍数字 | P2 | 先对齐 injected 语义，再用语料定阈值 |
| 4. 达标自动升级 error | ⚠️ 有设计风险 | P3 | 先做"引用质量代理 + 人工复核"，机制后置 |

一句话：**2 和 1 可以直接落地；3 和 4 现在缺的不是参数，是"计数语义对齐 + 真实语料 + 抗游戏化"，过早做反而会把系统锁进 false confidence。**

---

## 1. 评估口径

四条建议都围绕自审链路"检索 → 注入 → 正文消费 → 门禁防回退"。评估时核对了真实代码，三个事实作为后续判断的公共前提：

1. 强检查计数语义目前**不对称**：[kb_citation_mixin.py](D:/Claude/projects/2hao-analyst/pipeline/checks/kb_citation_mixin.py:60) 中 injected = 单段 prompt 块内条数（KB 7 + MKB 5），cited = 整篇正文 `[KBn]` 标记出现次数。分母是"一段 prompt"，分子是"全文"。
2. "正文消费"目前只数**字符串标记**（`[KB1]`/`[MKB1]`/方法论词），不验证标记附近是否真的用了对应内容——存在表面引用被游戏化的空间。
3. 管线里**已有多处上游行业信号**，但 MKB 注入器只读 `biz_model.industry_tags` 一个来源，其他字段被忽略（见建议 2）。

---

## 2. 建议 1：补 retrieved 段指标 —— 合理且便宜，建议做

### 判断
合理。当前三段漏斗只有 injected（截断后条数）与 cited（正文引用）能观测，**"检索到底命中多少"没有落点**，两类退化只能靠人工探针发现：

- 检索空召回：retrieved = 0，但 injected 恒 0，门禁弱检查只报"正文无痕迹"，看不到根因在检索侧；
- 注入预算切尾：retrieved > injected 时，说明写作侧截断丢内容，但现有强检查不会暴露。

### 落地方式
`_inj_kb_str` / `_inj_mkb_str` 是 ctx 驱动的注入器（[prompt_injectors_p3b.py](D:/Claude/projects/2hao-analyst/pipeline/prompt_injectors_p3b.py:103)），把命中数写进 `ctx` 或作为伴随返回值即可，不动调用链。口径建议：

- KB retrieved = `search_balanced` 返回前各目录候选池命中数（per_category=1 时通常恒 7，重点观察的是"某目录 0 命中"）；
- MKB retrieved = 打分后进入排名、未被 max_items/max_chars 丢弃前的条数（能暴露"召回 20 条只注入 5 条"的截断）。

### 边界
retrieved 的价值在**诊断**，不在用户可见的 Gate 报告正文。先接进日志/context，等有真实语料再决定是否进 Gate 展示，避免指标噪音淹没判断。

---

## 3. 建议 2：行业标签推断层 —— 方向极对，但实现应换成"接上游字段"

### 判断
"无 industry_tags 时 MKB 检索不到行业方法论"是真实盲区（上一轮审计已实证：茅台/宁德无标签 → 空块，修复后靠通用兜底词）。但**第一优先不是从资产名推断行业，而是把管线已有的行业信号接进来**：

- [data_collector.py](D:/Claude/projects/2hao-analyst/pipeline/data_collector.py:1310) 已用 akshare 找到股票所属行业板块；
- [data_enrichment.py](D:/Claude/projects/2hao-analyst/pipeline/data_enrichment.py:256) 已把 `industry_tags` 放进 `chart_data`；
- [data_feeds_node.py](D:/Claude/projects/2hao-analyst/pipeline/data_feeds_node.py:74) 已按 `biz.industry_tags[0]` 驱动资讯/板块数据；
- 而 MKB 注入器 [_inj_mkb_str](D:/Claude/projects/2hao-analyst/pipeline/prompt_injectors_p3b.py:142) 只读 `data_context.biz_model.industry_tags`，`chart_data.industry_tags` / `universe_summary.industry` 都没进 MKB 关键词。

真实管线上茅台大概率本就有"白酒"标签，只是没传到 MKB 注入这一步——**先修传输，再谈推断**。

### 正确实现顺序
1. 字段回退链：`biz_model.industry_tags` → `chart_data.industry_tags` → `universe_summary.industry`，三者都空才走兜底；
2. 兜底用**静态别名表**（茅台→白酒/消费），映射明确、可审计、放在噪声过滤同一层；
3. 不用 LLM 推断：贵、慢、多一个失败点，且"猜错行业 → 召回错误方法论"比空召回更隐蔽。

### 风险
名称→行业别名表只能覆盖少数知名标的，覆盖不了"兴业银行"这类多义词与冷门股。别名表要克制，宁可漏不可错——错误行业标签污染的不只是 MKB，还会扩散到同文件里其余四个读 `industry_tags` 的注入器（[L211](D:/Claude/projects/2hao-analyst/pipeline/prompt_injectors_p3b.py:211)、[L240](D:/Claude/projects/2hao-analyst/pipeline/prompt_injectors_p3b.py:240)、[L272](D:/Claude/projects/2hao-analyst/pipeline/prompt_injectors_p3b.py:272)、[L371](D:/Claude/projects/2hao-analyst/pipeline/prompt_injectors_p3b.py:371)）。

---

## 4. 建议 3：citation coverage 按报告类型调权 —— 方向对，但现在是拍数字

### 判断
"不同类型引用强度不同"直觉成立（earnings_notes 7 维短报告确实不该和 industry_deep 同标尺），但 0.3/0.6 这类数字现在**没有依据**，因为两个前置问题没解决：

1. **计数语义不对齐**：injected 是单段 prompt 块的条数（约 12），cited 是全文标记数。当前强检查等价于"正文约 6 个 `[KB]` 标记"（[kb_citation_mixin.py](D:/Claude/projects/2hao-analyst/pipeline/checks/kb_citation_mixin.py:63)），很多真实报告其实偏严。分母分子统一前，调 0.3 还是 0.6 都是在错标尺上打补丁。
2. **类型差异应先体现在注入内容**：[_inj_kb_str](D:/Claude/projects/2hao-analyst/pipeline/prompt_injectors_p3b.py:103) 对每种 report_type 都塞同一套 7 类目录 + "估值"。earnings_notes 该做的是按"业绩点评"主题收窄注入、少注入，而不是"注入同样多但要求低一点"。

### 建议做法
- 先定义 injected = **全报告唯一注入条数**（同一 KB 块被多个段落重复注入只算一次），再讨论阈值；
- 收集 2-3 份真实报告语料，按"实际引用分布"定分位阈值，而不是现在拍死；
- 若坚持先落地，阈值应作为**配置项**暴露，并同时输出类型 + 阈值 + 通过率日志，为后续语料校准留数据。

---

## 5. 建议 4：达标自动升级 error —— 有设计风险，建议缓行

### 判断
机制本身不复杂，但**被升级的指标可以被表面满足**：强检查数的是正文里 `[KBn]`/`[MKBn]` 字符串与独立方法论词，LLM 完全可以在不消费内容的情况下撒标记（写"[KB1]框架"却没用其方法）通过计数。连续 N 份 ≥0.7 就自动 error，等于把"表面引用率"当质量真值，还可能让系统长期处在"高通过率但低真引用"的假健康态。

### 若要做的三道闸
1. **引用质量代理**：`[KBn]` 附近出现方法论词/方法名，或引用段落主题与注入块有文本重叠——先让"引用"不等于"标记出现"；
2. **人工复核**：升级 error 会开始阻断报告，错判代价大，自动升档前至少复核一批样本；
3. **滞回与降级路径**：连续失败回退 warning，避免单次波动误锁档位。

---

## 6. 交叉发现：三个被四条建议共同暴露的隐藏问题

1. **cited 的计数对象是"标记出现次数"，不是"唯一引用"**——同一 `[KB1]` 在 5 个段落出现会让覆盖率虚高；建议改为"正文中不同 KB/MKB id 的集合大小"。
2. **重复注入未被计入语义**：串行/并行路径对每个段落都注入同一 KB/MKB 块，但 metrics 记录的是"最后一段的块内条数"；这会稀释"真正喂给模型的内容量"与"报告消费量"之间的对应关系。
3. **行业信号断裂是系统性问题**：不只 MKB，同文件四个注入器都只认 `biz_model.industry_tags`，上游 `chart_data`/`universe_summary` 的行业字段属于"算出来了但没送达"。修建议 2 时应顺带统一成一个 `_industry_tags_for(ctx)` 工具函数。

---

## 7. 推荐路线

| 阶段 | 内容 | 完成条件 |
|---|---|---|
| P0 | 行业字段回退链 + 统一 `_industry_tags_for(ctx)` + 静态别名离线兜底 | 真实库探针：无 biz_model 但有 chart_data 的标的，MKB 召回行业方法论而非通用兜底词 |
| P1 | retrieved 漏斗（注入器命中数进 ctx/日志） | 探针能区分"空召回 0"与"截断 retrieved>injected" |
| P2 | injected 语义对齐为全报告唯一条数；基于 2-3 份真实语料定类型阈值（配置化） | 语料报告强检查通过率分布有记录可查 |
| P3 | 引用质量代理 → 人工复核 → 自动升级 error（含滞回） | 表面标记案例被质量代理拦截，样本人工复核通过 |

---

## 8. 诚实口径

- 本备忘是**评估不是实施**；代码事实基于 2026-09-07 工作区快照。
- P2/P3 都依赖真实报告语料，当前没有 post-fix 产物（[CODEX_KB_FULL_PUSH_20260907.md](D:/Claude/projects/2hao-analyst/docs/CODEX_KB_FULL_PUSH_20260907.md) §5 已如实标注），所以"阈值 0.3/0.6"无法被验证，只能作为待校准初值。
- 别名表/回退链若实现，需保留"宁缺毋滥"原则并在报告里说明召回来源，避免把启发式结果伪装成数据结论。

---

## 9. 一句话

> **四条建议全都有价值，但成熟度不同：接上游行业字段（建议 2 的改版）是当下最高杠杆的一步，retrieved 漏斗（建议 1）顺手可做；按类型调权（3）要等计数语义对齐和真实语料，自动升级 error（4）要在引用质量代理成熟之后——否则我们只是在给一个可被表面满足的指标装自动门。**
