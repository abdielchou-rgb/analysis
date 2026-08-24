# R74 全量工程计划 v2 — 从审计到执行

> 覆盖 R68-R73 全部审计发现：18 模块静默失败 / 行业非上市接线缺口 / 油位 v6 3 类沉默缺陷 / 4 项系统性缺陷 / 5 缺失维度
> 制作日期：2026-08-05
> 对标：高盛 GS-SUSTAIN / 大摩 Flow Monitor / 桥水 Sustained Failure / Bernstein DES / Kase Short Framework / McKinsey S-Curve

---

## 零、前置状态确认

### 已完成（R68-R72，本次会话）

| R | 内容 | 文件变更 |
|---|------|---------|
| R68 | 18 模块全量审计 | docs/r68-module-audit.md |
| R69 | logger.debug→warning（9处） | section_writer.py |
| R70 | ma/ut/us/_tm 接线（P0全量） | section_writer.py + e2e_orchestrator.py |
| R71 | mr topic_map + di/ex 接线（P1/P2全量） | section_writer.py |
| R72 | ESG注入 + 免责硬拦截 + 催化剂4Q结构 | section_writer.py + content_format_mixin.py |

### 注入变量演进

```
R68: 18 → R70: 24 → R71: 26 → R72: 27
logger.warning: 9 → 15
logger.debug吞异常: 7 → 3
```

---

## 一、缺口全景图（R73 审计综合）

### A. 4 项系统性缺陷

| # | 缺陷 | 严重性 | 根因 | 状态 |
|---|------|--------|------|------|
| A1 | SAC覆盖被游戏化（26/26=关键词命中，14/26=软覆盖） | P0 | Gate用关键词查覆盖→LLM优化指标非深度 | 未修 |
| A2 | 管线修复在手动路径系统失效（排版/免责/图随文） | P0 | 修复只在出口链拦截，prompt层无多重防护 | 部分修(R72) |
| A3 | InfoDesk缺失——系统不知"读者想干什么" | P0 | report_planner缺读者画像+行动问题注入 | 未修 |
| A4 | 跨报告零关联——同赛道标的互不知晓 | P1 | 无 cross_report_synthesis 注入 | 未修 |

### B. 5 项缺失维度

| # | 维度 | 对标 | 状态 |
|---|------|------|------|
| B1 | 做空者视角（Short-Side Check） | Kase Learning Short Framework | 未定义 |
| B2 | 监管合规成本量化 | McKinsey Compliance Economics | 未定义 |
| B3 | 技术替代的非线性加速/减速因子 | McKinsey S-Curve Acceleration | 未定义 |
| B4 | 系统失效状态识别（Sustained Failure Mode） | 桥水 | 未定义 |
| B5 | 资金面四层剥离（hedging/rotation/bottom-up/top-down） | 大摩 Flow Monitor | capital_flow有定义但不加权 |

### C. 3 类已修但需强化

| # | 问题 | 已修 | 剩余缺口 |
|---|------|------|---------|
| C1 | 排版（图堆文末） | R31/R40/Gate layout_quality | md层图表位置检测缺失 |
| C2 | 催化剂日历截断 | R72（4Q结构约束） | 未在Gate中加完整性检查 |
| C3 | 模板句同义重复 | R54（逐字重复检测） | 同义变体不检测 |

---

## 二、工程阶段

### Phase 1：防御纵深（R74a）——让修复在绕过管线时仍生效

**目标**：堵住"修复在手动路径上系统性失效"的漏洞

| 任务 | 文件 | 变更 | 工作量 |
|------|------|------|--------|
| 1.1 md 层图表位置检测 | content_format_mixin.py | 检查 md 文本中 ![fig_xxx] 是否在"附录"标题前出现；若无→FAIL | 1h |
| 1.2 免责声明 prompt 层下沉 | section_writer.py | 在 prompt 末尾加 `[禁止事项] 禁止写"内容由AI生成/仅供参考/AI辅助"` | 0.5h |
| 1.3 免责声明 docs/ 全局审计 | docs/ | 扫描所有 .md 文件，查找 R72 硬拦截的免责声明 pattern | 0.5h |

### Phase 2：度量免疫（R74b）——SAC 覆盖从关键词升级为子要素检查

**目标**：根治 Goodhart 律坍缩——26/26 自评不再能靠关键词空壳通过

| 任务 | 文件 | 变更 | 工作量 |
|------|------|------|--------|
| 2.1 定义 SAC 各维度的必需子要素 | core/sacs/*.yaml | 为每个维度加 `required_sub_elements: [...]` 字段（如 capital_market: [DCF, comparable, sensitivity, cross_validation, davis_doubleplay, kelly_odds, mean_reversion]） | 2h |
| 2.2 Gate 子要素覆盖率检查 | checks/coverage_mixin.py | 新增 `_check_sub_element_coverage()` ——用结构性正则逐个查子要素 | 2h |
| 2.3 per-industry 维度权重矩阵 | data/industry_dimension_weights.json | 为 20+ 行业定义维度权重（半导体 geopolitics=8/10, 油位=3/10） | 1h |
| 2.4 analyst_planner 接入权重 | core/analyst_planner.py | plan() 产出时注入 `dimension_weights`，让 section_writer 知道哪些维度应该多写 | 1h |

### Phase 3：InfoDesk 层（R74c）——系统知道"读者想干什么"

**目标**：报告不再是教科书式行业罗列，而是有读者画像、有行动问题的投资建议

| 任务 | 文件 | 变更 | 工作量 |
|------|------|------|--------|
| 3.1 report_planner 加读者画像 | core/report_planner.py | `build_report_plan()` 新增 `reader_profile`（机构/个人/长线/短线）+ `action_questions`（最多3个） | 1h |
| 3.2 section_writer 注入 reader_profile | section_writer.py | dim-parallel 组 prompt 加 `## 读者画像与行动问题` 段 | 0.5h |
| 3.3 investable_standouts 维度加强 | sac_industry_deep.yaml | 该维度 sub_questions 加"仓位建议%/退出条件/与同赛道标的替代关系" | 0.5h |

### Phase 4：跨报告关联（R74d）——同一赛道的报告彼此知晓

**目标**：油位 v6 写川仪 28.60 时，能引用柯力 v5 的判断做对照

| 任务 | 文件 | 变更 | 工作量 |
|------|------|------|--------|
| 4.1 report_cache 增强 | core/report_cache.py | 新增 `get_same_sector_reports()` ——查同行业/同赛道的历史报告摘要 | 1h |
| 4.2 section_writer 注入跨报告 context | section_writer.py | 在 prompt 加 `## 同赛道历史判断（标的/评级/目标价/核心分歧）` 段 | 1h |
| 4.3 组合替代关系提示 | core/report_planner.py | 若同赛道有多个标的报告，自动生成"替代/互补/资金分流"判断提示 | 0.5h |

### Phase 5：5 项缺失维度（R74e）——新建维度 + 注入

**目标**：对标国际大行，补齐做空者视角/合规成本/替代因子/系统失效/资金流四层

| 任务 | 文件 | 对标 | 工作量 |
|------|------|------|--------|
| 5.1 short_check 维度 + 注入 | sac_*.yaml + section_writer.py（`ss_str`） | Kase Short Framework —— "从做空者视角审视这份报告：新市场/新产品/新会计/新管理层/新资本结构" | 2h |
| 5.2 compliance_cost 维度 + 注入 | sac_industry_deep.yaml + section_writer.py（`cc_str`） | McKinsey Compliance Economics —— 认证/许可/合规的持续成本对新进入者的壁垒效应 | 1.5h |
| 5.3 substitution_acceleration 子维度 | sac_industry_deep.yaml → technology 维度加 sub_question（"什么变量会让替代在2027年突然加速2倍？什么会减速？"） | McKinsey S-Curve —— 触发因子列表 + 非线性替代概率 | 1h |
| 5.4 sustained_failure_mode 升级 | sac_*.yaml → falsification 维度改名为 falsification_and_failure_modes → 加"当前宏观环境下的系统失效状态" | Bridgewater —— 与 macro_ctx 联动 | 1h |
| 5.5 capital_flow 四层剥离 | core/compute/capital_flow_decompose.py → 新建 compute 模块 | Morgan Stanley Flow Monitor —— hedging/rotation/bottom-up/top-down | 2h |

### Phase 6：反方论证强度量化（R74f）

**目标**：Gate 不止查"有没有反方观点"，还查"反方观点对主判断的威胁够不够强"

| 任务 | 文件 | 对标 | 工作量 |
|------|------|------|--------|
| 6.1 IronGate DES 评分 | checks/analysis_mixin.py → `_check_counterargument_strength()` | Bernstein DES —— 反方论证越强主判断仍成立→报告可信度越高 | 2h |
| 6.2 模板句同义去重升级 | checks/content_format_mixin.py → `_check_semantic_repeat` 从逐字→同义 | R54 升级——embedding-based 同义检测（本地 sentence-transformers） | 2h |

---

## 三、执行优先级矩阵

```
                    高影响
                      │
     Phase 1 ─────────┼───────── Phase 3
     (防御纵深)       │         (InfoDesk)
                      │
     Phase 2 ─────────┤
     (度量免疫)       │
                      │
   ───────────────────┼──────────────────
                      │
     Phase 6          │         Phase 4
     (反方强度)       │         (跨报告)
                      │
     Phase 5          │
     (5维缺失)        │
                      │
                    低影响
    低工作量 ←──────────────────→ 高工作量
```

**执行顺序**：Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 6 → Phase 5
（防御纵深优先——不先堵住手动路径的漏洞，后面修的都是建在沙滩上的城堡）

---

## 四、首批执行（Phase 1+2，立即开始）

以下 6 个文件变更将在本会话内完成：

| 序号 | Phase | 文件 | 行估计 |
|------|-------|------|--------|
| 1 | 1 | content_format_mixin.py · md图表位置检测 | +25 |
| 2 | 1 | section_writer.py · prompt层禁免责声明 | +8 |
| 3 | 2 | sac_industry_deep.yaml · sub_elements 字段 | +40 |
| 4 | 2 | sac_listed_company.yaml · sub_elements 字段 | +30 |
| 5 | 2 | sac_unlisted_company.yaml · sub_elements 字段 | +25 |
| 6 | 2 | checks/coverage_mixin.py · 子要素覆盖率 | +60 |
| 7 | 1 | iron_gate.py · 接线 sub_element 检查 | +1 |

## 五、Phase 1+2 执行结果（R74a/b，已完成）

| 序号 | 文件 | 变更 |
|------|------|------|
| 1.1 | checks/content_format_mixin.py | md 层图表位置检测（附录前是否有 ![](fig_xxx)） |
| 1.2 | section_writer.py | dim-parallel prompt + merge prompt 双点注入"禁止AI免责" |
| 2.1 | sac_industry_deep.yaml | 4 维度新增 required_sub_elements（elasticity/capital_market/consolidation/esg） |
| 2.2 | checks/coverage_mixin.py | 新建 `_check_sub_element_coverage()` ——正则逐个查子要素，阈值70% |
| 2.4 | iron_gate.py | 子要素覆盖接入 Gate 检查队列 |

语法全过（ast.parse OK），SACLoader 正确读取 required_sub_elements 字段。
