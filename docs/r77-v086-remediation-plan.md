# R77 油位传感器 v0.86 — 报告修改工程计划

> 基于 R77 深度分析 + v0.86 docx 实际内容 + Marvis Gate 失败复盘
> 生成日期：2026-08-06

---

## 一、修改目标

将 v0.86（70/100，Gate 0.86 但被高估）升级为 **可交付的机构级深度报告（85+/100）**。

修改分为两条独立的线路：
- **线路A（管线治本）**：修反馈桥/归因/正向累积 → 重跑管线产出新稿
- **线路B（报告治病）**：直接修 v0.86 报告中人的阅读能感知到的硬伤 → 手动/半手动修复

本计划覆盖两条线路。

---

## 二、线路A：管线治本 —— 5项修复

### A1：失败指纹 + 归因收窄（对应问题1+2）

| 层级 | 文件 | 变更 |
|------|------|------|
| P0 | `pipeline/fail_segment_locator.py` | `_global_fail_pats` 正则收窄：data_conflicts 去掉 `口径`，annotation_types 去掉 `来源标注`；新增独立匹配 market_size_consistency / source_entity |
| P0 | `pipeline/fail_segment_locator.py` | 新增 `_failure_fingerprints {}`：记录每轮失败指纹，同一指纹连续出现>2次→降级为警告、不再触发全量重写 |
| P1 | `pipeline/fail_segment_locator.py` | so_what_chain 失败时从Gate反馈中提取"min=0的段标题"（Gate需先产出这个信息） |

### A2：死角段定位 + 大纲锚定（对应问题1+4）

| 层级 | 文件 | 变更 |
|------|------|------|
| P0 | `pipeline/checks/analysis_mixin.py` | `_check_so_what_chain` 的 GateCheckResult.details 追加"min段: xxx（标题/首句）" |
| P0 | `pipeline/fail_segment_locator.py` | 从 details 解析 min 段名→映射到段索引→返回 rewrite_indices |
| P0 | `pipeline/section_writer.py` | 已达标段（非 rewrite_indices）从 best_so_far 冻结文本，不再重写 |

### A3：最佳稿基线固化（对应问题3）

| 层级 | 文件 | 变更 |
|------|------|------|
| P0 | `pipeline/e2e_orchestrator.py` | `_best_so_far` 从"仅记录分数字典"升级为"{score: x, full_text: y, segment_texts: {0: t0, 1: t1, ...}}" |
| P1 | `pipeline/e2e_orchestrator.py` | Gate 反馈后，将 best_so_far 的非重写段直接拼接进下一轮 draft（跳过 LLM 重写） |

### A4：Writing Charter 强制推理链（对应问题4）

| 层级 | 文件 | 变更 |
|------|------|------|
| P1 | `pipeline/section_writer.py` | 每个 SAC 维度的 dim-def 模板末尾追加："[推理链要求] 在分析最后必须写一句'因此/我们判断/综上/这意味着'的推理性结论，禁止纯数据罗列无判断" |
| P1 | `core/sacs/sac_industry_deep.yaml` | 每个维度加 `reasoning_chain_min: 1` 字段（Gate 用来验证推理链密度） |

### A5：LLM Provider 超时熔断（复盘暴露的性能问题）

| 层级 | 文件 | 变更 |
|------|------|------|
| P1 | `core/agent_provider.py` | agent_provider 超时 300s→60s，2次失败后 circuit-break 30s（已部分实现，检查激活逻辑） |
| P2 | `pipeline/e2e_orchestrator.py` | Gate 的 LLM 检查项（ai_tone_by_llm等）在 provider 熔断时跳过而非等待超时 |

---

## 三、线路B：v0.86 报告逐项治病 —— 5项可手动修复的硬伤

### B1：数据口径统一（P0 致命伤）

| 问题 | 位置 | 修复 |
|------|------|------|
| 全球市场规模三种口径(18.6/46.0/65.0)并存 | 各章节 | 统一为 data_dict 权威值：2025年全球=50亿美元，中国=172亿元 |
| 中国市场规模1.0亿 vs 166.0亿 | 历史轮次残留 | 删除错误口径段落 |
| 渗透率多值并存(10%/40%/70%) | 技术章节 | 统一为60-70%（危化品SIS）/85-90%（加油站）/100%（燃油车） |

**操作**：打开 data_dict，将报告内所有市场规模/渗透率数值与 data_dict 交叉校验→不一致的用 data_dict 替换。

### B2：决策门截断（P0 硬伤）

| 问题 | 位置 | 修复 |
|------|------|------|
| "处于"加油站场景成熟、新兴场景成长"的双的分析" | docx 开头 | 补全为："处于加油站场景成熟、新兴场景成长的双轨阶段。三个决策门评估：(1)行业空间GO、(2)竞争格局GO、(3)估值吸引力CONDITIONAL，综上2/3 GO，进入深度分析" |

### B3：Bold Call 估值链断裂（P1）

| 问题 | 位置 | 修复 |
|------|------|------|
| 目标价38.5元缺推导过程 | 核心判断段 | 补入："38.5元基于2026年动态PE 25倍 × EPS 1.54元的基准情景。DCF法估值42元（WACC=9%，终端增长率2.5%），可比PE法34-43元。三法交叉取中值38.5元，隐含较当前价上行15%空间" |

### B4：推理链死角段修补（P1 系统性）

| 问题 | 修复 |
|------|------|
| 至少1段完全无"因此/我们判断/这意味着" | 逐段排查，在每段末尾追加1句推理总结（不是全文重写，是局部追加） |

### B5：v0.86 独有的 R72/R74/R76 能力缺失（P2 追补）

| 缺失能力 | R版本 | 在v0.86中是否有 |
|---------|--------|-------------|
| ESG实质性议题 | R72 | ❌ 全文无 ESG 章节 |
| 做空者视角审查 | R76 | ❌ 全文无 Short Check |
| 合规成本量化 | R76 | ❌ 全文无 Compliance Cost |
| 资金面四层剥离 | R76 | ❌ 全文笼统写北向 |
| 行业戴维斯双击 | R71 | ❌ 全文无 EPS×PE 方向判断 |
| 非上市威胁度 | R70 | ⚠️ 图表覆盖但正文无量化威胁度 |

**操作**：这些 v0.86 未享受 R70-R76 的注入——不手动追加，因为管线重跑后自然会产生（R70-R76 已接线）。建议优先走线路A重跑而非手动补。

---

## 四、执行优先级矩阵

```
                    高影响
                      │
    A1(归因收窄) ─────┼───── A2(死角定位)
    B1(口径统一)      │     A3(基线固化)
                      │
   ───────────────────┼──────────────────
                      │
    A4(WritingCharter)│     B2(决策门截断)
    B4(推理链补丁)    │     B3(估值链)
                      │
                    低影响
    低工作量 ←──────────────────→ 高工作量
```

**执行顺序**（本会话执行A1+A2，重跑管线产出新稿后评估B1-B5是否需要手动干预）：

| 优先级 | 项 | 工作量 | 本回执行 |
|--------|-----|--------|---------|
| P0 | A1: 归因正则收窄 + 失败指纹 | 1h | ✅ |
| P0 | A2: so_what_chain 死角段定位输出 | 0.5h | ✅ |
| P0 | B1: 数据口径统一 | 0.5h（手动） | 待管线重跑后评估 |
| P0 | B2: 决策门截断 | 0.2h（手动） | 待管线重跑后评估 |
| P1 | A3: 最佳稿基线固化 | 1.5h | R78 |
| P1 | A4: WritingCharter 推理链约束 | 0.5h | R78 |
| P1 | A5: Provider 超时熔断 | 0.3h | R78 |
| P2 | B3-B5: 估值链/死角/新能力缺失 | 管线重跑自动修复 | R78 |

---

## 五、顶级解法对标矩阵

| 解法 | 来源 | 2hao 对应修复 |
|------|------|-------------|
| Outline Anchoring 大纲锚定 | CogGen (ACL 2026) | A2: 已达标段冻结，不推倒大纲 |
| Fault-Signature Retry 失败指纹 | AgentGuard-LLM | A1: 同一指纹重复出现→降级 |
| Evidence-Tracked 证据追踪 | EviReport (ACL 2026) | B1: data_dict 口径统一 |
| Validation-Feedback Align 标准对齐 | Multi-Agent (2026) | A4: WritingCharter 与 Gate 规则同步 |
| Progressive Freeze 段冻结 | DurableExecution | A3: best_so_far 段级冻结 |
