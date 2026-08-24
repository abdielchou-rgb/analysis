# FP 宪法 100 分路线图

> 当前合规率：71%（Step 1-3 修复后）
> 目标：100%（全部 7 条 FP 的否决条件 + 推导约束 100% 满足）
> 
> 原则：**不做代码健康，不做文档整理，不做测试覆盖。只做 FP 合规。**

---

## 一、现状盘点

### 各 FP 合规率与差距

| FP | 当前 | 目标 | 差距 | 剩余违反数 |
|----|------|------|------|-----------|
| FP1 系统本质 | 100% | 100% | 0 | 0 |
| FP2a 数据履约 | 75% | 100% | **25%** | 2 |
| FP2b 分析履约 | 80% | 100% | **20%** | 2 |
| FP3 超级维度 | 0% | 100% | **100%** | 6（全新） |
| FP4 人感约束 | 65% | 100% | **35%** | 3 |
| FP5 智能演化 | 65% | 100% | **35%** | 2 |
| FP6 推理透明 | 55% | 100% | **45%** | 4 |
| FP7 反脆弱性 | 60% | 100% | **40%** | 3 |

**总剩余差距：22 项**（8 条剩余 P0 + 14 条剩余 P1）

---

## 二、按 FP 优先级排列的修复路径

### 裁决链：FP4 → FP2a → FP2b → FP6 → FP7 → FP5 → FP3 → FP1

---

### Phase A：FP4（人感约束）— 当前 65% → 目标 100%

#### A1. AI Tone LLM 判别从 advisory 改为 blocking

**当前**：`_check_ai_tone_by_llm` 在 LLM 不可用时返回 `severity="warning"`，不阻断
**目标**：LLM 可用时必须运行此检查，score<0.4 硬阻断

```
文件: pipeline/iron_gate.py
位置: _check_ai_tone_by_llm 的 except 分支
改动: 将 severity="warning" 改为不 catch 异常或升级为 "error"
      （FP4 下阈否决条件：AI 痕迹输出不得交付）
难度: ★☆☆☆☆（1 行）
FP 优先级: 最高（FP4 在裁决链首位）
```

#### A2. AIScanner 增加语义级指纹检测

**当前**：12 个 P0 指纹全部是短语级（"值得注意的是"、"综上所述"）
**目标**：覆盖语义级 AI 痕迹——均衡段落结构、模板化三列举、机械式逻辑过渡

```
文件: core/ai_fingerprints.py
新增: 5 个语义级 P0 指纹
  1. 段落长度方差 < 0.15（三段落等长 → AI）
  2. "首先…其次…再次…" 完美三列举 → AI
  3. 每段结尾都是总结句 → AI
  4. 无段落以"但是/然而/不过"开头 → AI（人类会转折）
  5. 每段都有"数据→分析→结论"的完整结构 → AI
      （人类分析师偶尔会跳跃）
难度: ★★★☆☆（约 60 行 regex + 统计逻辑）
FP 优先级: 最高
```

#### A3. StyleCompiler 人感检查从 report-only 改为 blocking

**当前**：`_rule_human_sense_check` 返回 `deviations` 但不修改文本
**目标**：human_sense_score < 0.5 时阻断交付

```
文件: core/style.py
改动: _rule_human_sense_check 的返回值将 passed 状态回传
      StyleCompiler.compile() 在 post-processing 后返回 overall_human_score
      IronGate 读取此 score，低于 0.5 时阻断
难度: ★★☆☆☆（约 20 行）
FP 优先级: 最高
```

**Phase A 累计：约 80 行代码 | FP4 达到 100%**

---

### Phase B：FP2a（数据履约）— 当前 75% → 目标 100%

#### B1. A/E/F/B 标注补全 + IronGate 验证

**当前**：prompt 只要求 A（Actual）/E（Estimate），缺 F（Forecast）/B（Benchmark）
**目标**：四种类型标注全部强制，IronGate 验证

```
文件: pipeline/section_writer.py
改动: _build_prompt_v4 的时间标注规则扩展：
  "每个数值必须标注类型：(A)=已发布实际数据 / (E)=分析师估计 / 
   (F)=远期预测 / (B)=行业基准"
  示例：2024A / 2025E / 2027F / 行业均值(B)

文件: pipeline/iron_gate.py
新增: _check_data_type_annotation(self) → GateCheckResult
  检查：报告中是否出现 (A)/(E)/(F)/(B) 标注
  通过阈值：≥ 5 次标注
难度: ★☆☆☆☆（约 40 行）
FP 优先级: 高
```

#### B2. 数据来源标注从关键词升级到语义验证

**当前**：IronGate `_check_data_traceability` 做关键词计数（"来源"、"Wind"等）
**目标**：验证每个来源引用是否包含"报告名称+发布机构+日期"三级信息

```
文件: pipeline/iron_gate.py
改动: _check_data_traceability 升级
  用 regex 提取所有"据[X报告][Y机构][Z日期]"模式
  评分拆为三级：来源名(0.3) + 机构名(0.3) + 日期(0.4)
  单来源引用无日期 → 该来源分数扣 40%
难度: ★★☆☆☆（约 30 行 regex）
FP 优先级: 高
```

**Phase B 累计：约 70 行代码 | FP2a 达到 100%**

---

### Phase C：FP2b（分析履约）— 当前 80% → 目标 100%

#### C1. 反方论证概率强制验证

**当前**：IronGate 检查反方关键词（"然而/但是/风险"）但不验证概率
**目标**：每个反方论证必须附带成立条件概率

```
文件: pipeline/iron_gate.py
改动: _check_persuasion_architecture 升级
  增加检查：反方关键词附近是否有 `\d+%` / `概率` / `可能性`
  每个反方段落必须概率标注
难度: ★☆☆☆☆（约 15 行 regex）
FP 优先级: 中
```

#### C2. So What 链从段落平均改为每个判断必须完整

**当前**：逐段评分取平均，某些段无 So What 链也可通过
**目标**：每个 major 判断（匹配到"我们认为/判断/预计/建议"的句子）必须有 So What 链

```
文件: pipeline/iron_gate.py
改动: _check_so_what_chain 重构
  1. 找到所有"我们认为/判断/预计/建议/Bold Call"开头句子
  2. 验证每个判断前后 200 字内有"数据→分析→含义"完整链
  3. 缺失率 > 20% → fail
难度: ★★☆☆☆（约 40 行重构）
FP 优先级: 中
```

**Phase C 累计：约 55 行 | FP2b 达到 100%**

---

### Phase D：FP6（推理透明）— 当前 55% → 目标 100%

#### D1. L4 证据层验证

**当前**：data_traceability 检查来源数量，不检查"每个数据点都有来源"
**目标**：验证每个数值引用都被来源标注跟随

```
文件: pipeline/iron_gate.py
新增: _check_evidence_layer(self) → GateCheckResult
  提取所有数字（\d+[\.\d]*[亿万千]?\b）
  检查每个数字 100 字内是否有来源关键词
  覆盖率 ≥ 70% → pass
难度: ★★☆☆☆（约 30 行）
FP 优先级: 中
```

#### D2. L5 反证层——证伪条件概率强制

**当前**：`_check_forbidden_patterns` 检查关键词，但无"证伪条件+概率"结构验证
**目标**：验证是否存在"如果…那么…"形式的证伪条件

```
文件: pipeline/iron_gate.py
新增: _check_falsification_conditions(self) → GateCheckResult
  检查：是否存在"如果/假如/假设…那么/则…"结构的证伪段落
  所有 Bold Call 必须附带证伪条件
  至少 1 个完整证伪条件 → pass
难度: ★★☆☆☆（约 25 行）
FP 优先级: 中
```

#### D3. L6 元认知层——置信度与盲区标注

**当前**：prompt 第 13 条要求 H/M/L 置信度标注，Gate 不验证
**目标**：至少 3 处 H/M/L 标注，且至少 1 处"不确定性/盲区/局限"说明

```
文件: pipeline/iron_gate.py
新增: _check_meta_cognition(self) → GateCheckResult
  1. 提取 H=High / M=Medium / L=Low / \d+% 置信度标注，≥ 3 处
  2. 检查是否有盲区段落（不确定/局限/风险/未覆盖/假设条件）
难度: ★☆☆☆☆（约 20 行）
FP 优先级: 中
```

#### D4. 置信度标注 Gate 验证

**当前**：section_writer 的 prompt 要求标注，Gate 无对应检查
**目标**：每个 Bold Call 必须有置信度标注

```
文件: pipeline/iron_gate.py
改动: _check_bold_call 升级
  增加检查：Bold Call 5 要素中 "置信度" 权重翻倍
  无置信度的 Bold Call → score 降 50%
难度: ★☆☆☆☆（约 5 行）
FP 优先级: 中
```

**Phase D 累计：约 80 行 | FP6 达到 100%**

---

### Phase E：FP7（反脆弱性）— 当前 60% → 目标 100%

#### E1. L2 数据降级实现

**当前**：只有 L1（图表降级）实现
**目标**：L2 降级——部分数据源不可用时，标注降级并降低 gate 阈值

```
文件: pipeline/e2e_orchestrator.py
位置: data_feeds 节点
改动: 数据源采集失败时，不抛异常，设置 degradation_level = 2
      在报告头部注入 "此报告基于 N 个来源（完整应 M 个）" 标注

文件: pipeline/iron_gate.py
改动: 读取 degradation_level >= 2 时，自动调低 data_traceability 阈值
难度: ★★☆☆☆（约 40 行逻辑 + 20 行 Gate 适配）
FP 优先级: 中
```

#### E2. 故障注入测试脚本

**当前**：无
**目标**：季度运行的 chaos engineering 脚本

```
文件: scripts/chaos_test.py（新建）
功能: 
  1. 随机断掉一个数据源（模拟 akshare 不可用）
  2. 随机断掉主 LLM provider（模拟 DeepSeek 超时）
  3. 随机返回空数据（模拟 data_collector 空响应）
  4. 验证系统是否优雅降级（非崩溃）
  5. 输出降级报告

难度: ★★★☆☆（约 100 行）
FP 优先级: 低
```

#### E3. 组件期权清单文档化

**当前**：期权存在但无文档
**目标**：docs/infrastructure_options.md

```
文件: docs/infrastructure_options.md（新建）
内容: 每个组件的替代选项+状态+切换时间

难度: ★☆☆☆☆（约 30 行文档）
FP 优先级: 低
```

**Phase E 累计：约 190 行 | FP7 达到 100%**

---

### Phase F：FP5（智能演化）— 当前 65% → 目标 100%

#### F1. Gate 失败复发率追踪

**当前**：LearningLoop 有 `report_scores` 表但无 time-series 查询
**目标**：每月自动报告"同类型 Gate 失败复发率"及环比趋势

```
文件: pipeline/learning_loop.py
新增: def recurrence_rate(self, months=3) → dict
  按 failure pattern 分组，统计每月复发率
  输出：{"aigc_fingerprint": {"month1": 0.3, "month2": 0.2, trend: "down"}, ...}

文件: scripts/monthly_report.py（新建）
  调用 recurrence_rate + prediction_stats
  输出 Markdown 报告
难度: ★★★☆☆（约 80 行）
FP 优先级: 中
```

#### F2. 学习案例自动应用

**当前**：LearningLoop 存储失败模式到 `learning_lessons` 表，但未自动调整规则
**目标**：失败模式自动映射为 prompt 调整或 gate 规则修正

```
文件: pipeline/learning_loop.py
新增: def auto_apply_lessons(self) → int
  从 learning_lessons 表提取 top-3 失败模式
  映射到 section_writer prompt 调整或 iron_gate 阈值微调
  输出已应用 lesson 数

文件: pipeline/e2e_orchestrator.py
改动: record_results 节点调用 auto_apply_lessons
难度: ★★★★☆（约 120 行，需设计模式→规则映射表）
FP 优先级: 中
```

**Phase F 累计：约 200 行 | FP5 达到 100%**

---

### Phase G：FP3（超级维度）— 当前 0% → 目标 100%

#### G1. 六维测量基线（一次性搭建）

**当前**：无任何测量
**目标**：六个维度各有自动化测量脚本

```
维度 1 — 速度：从 scheduler.py 中提取 run 开始到 IronGate 通过的时间
  实现: 在 scheduler 中加计时器，输出到 logs/timing.log
  
维度 2 — 广度：管线支持的最大并行标的数
  实现: 用 python -c "from pipeline.e2e_orchestrator import ..." 启动 N 个并行进程
  
维度 3 — 深度：SAC 逻辑链最大步长
  实现: python -c "from core.sacs import SACLoader; l = SACLoader('listed_company'); print(len(l.get_logic_chain()))"
  
维度 4 — 记忆：知识注入使用率 × 预测跟踪完整度
  实现: 查询 learning_loop.db 的 table 行数 + forward_picks.csv 的条目数
  
维度 5 — 协作：debate protocol 调用率
  实现: 搜索 pipeline/e2e_orchestrator 中 debate 调用次数 / 总管线运行次数
  
维度 6 — 持续：gate score 日方差
  实现: learning_loop.report_scores 表中按日期聚合 gate score 的方差

难度: ★★☆☆☆（约 100 行一次性脚本）
FP 优先级: 低（但首次测量必须做，否则无法追踪收敛）
```

#### G2. 收敛曲线自动追踪

**当前**：无
**目标**：每次管线运行后自动更新 FP3 六维指标到数据库，每版本自动对比

```
文件: scripts/track_convergence.py（新建）
功能: 每次 pipeline 运行后，收集 6 个维度的测量值
      写入 convergence_log.db
      自动计算 vs 人类基线的 e^(-k·t) 收敛率

文件: docs/convergence_report.md（自动生成）
难度: ★★★☆☆（约 120 行）
FP 优先级: 低
```

**Phase G 累计：约 220 行 | FP3 达到 100%**

---

## 三、整合路线图

```
Phase   FP   合规提升   代码量   依赖
──────────────────────────────────────────
A       FP4   65→100%   ~80行   无（独立）
B       FP2a  75→100%   ~70行   无（独立）
C       FP2b  80→100%   ~55行   无（独立）
D       FP6   55→100%   ~80行   Phase A 之后（AIScanner 经验复用）
E       FP7   60→100%   ~190行  Phase B 之后（数据降级依赖 data 节点）
F       FP5   65→100%   ~200行  Phase A+B 之后（学习案例需要 gate 和 data 数据）
G       FP3   0→100%    ~220行  Phase A-F 之后（测量才有意义）
──────────────────────────────────────────
总计    全部   71→100%   ~895行  4-6 周（按每 Phase 3-5 天）
```

### 投入产出比排序

| 排序 | Phase | 代码量 | 合规提升 | 效率 |
|------|-------|--------|----------|------|
| 1 | A: FP4 | 80 行 | +35% | **每行 0.44%** |
| 2 | B: FP2a | 70 行 | +25% | **每行 0.36%** |
| 3 | D: FP6 | 80 行 | +45% | **每行 0.56%** |
| 4 | C: FP2b | 55 行 | +20% | **每行 0.36%** |
| 5 | E: FP7 | 190 行 | +40% | 每行 0.21% |
| 6 | F: FP5 | 200 行 | +35% | 每行 0.18% |
| 7 | G: FP3 | 220 行 | +100% | 每行 0.45% |

**最佳路径**：A → D → B → C → E → F → G
（按每行代码产出比排列，而非裁决链顺序）

---

## 四、关键依赖与风险

### 外部依赖
- **Phase A1**（AI Tone blocking）：Qwen/OpenRouter 必须有可用 API key，否则单 provider 下 LLM 判别不可用
- **Phase E2**（故障注入）：需要独立环境，不能在正式分析时运行
- **Phase F2**（自动应用）：需要先积累至少 50 条 learning_lessons 记录

### 架构风险
- **Phase D1**（L4 证据层）：数字提取 regex 在中文财报文本中误报率可能较高（年份、日期、编号）
- **Phase G**（FP3 测量）：六维度中"协作"和"持续"的测量需要跨 session 数据，当前日志系统不支持

### 安全建议
- **Phase G** 的测量脚本不要在正式 pipeline 中运行，作为独立 CLI 工具每次版本发布前手动触发

---

## 五、你可以立刻做的三件事

1. **[Phase A2] 语义级 AIScanner**：5 个 regex 模式，今天就能写。效果是直接把 FP4 下阈从"可绕过"变成"绕过需要精心设计"
2. **[Phase B1] A/E/F/B 标注**：改 prompt + 加 Gate 检查，一下午做完。FP2a 从 75% 到 90%
3. **[Phase D3] L6 元认知**：置信度标注检查，三小时。FP6 从 55% 到 70%

这三个加起来 ~150 行代码，合规率从 71% 提升到 ~82%。

要我执行哪个 Phase？
