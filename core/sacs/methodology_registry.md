# 1号分析师 V50 方法论注册表
#
# 定位: 记录每个方法论条目的状态、来源、V50 实现方式
# 版本: V50.0 / 2026-07-21
# 更新规则: 新增方法论在此注册，不消耗主版本号（用 V50.x 标记）

---

## 注册表

### 已迁移为 SAC（active）

| ID | 名称 | 来源 | V50 实现 | 优先级 | 门禁 |
|----|------|------|---------|--------|------|
| sac_earnings_notes | 上市公司财报点评 | V24 writer_agent public_company 框架 | sac + T2 逐节生成 | P0 | SAC Gate |
| sac_industry_deep | 行业深度研究 | V24 researcher_agent 11维框架 + Serenity 9步工作流 | sac + 谋篇双引擎 | P0 | SAC Gate |
| sac_listed_company | 上市公司深度分析 | V24 writer_agent + financial_analyst 整合 | sac + 8阶写框架 | P0 | SAC Gate |
| sac_unlisted_company | 非上市企业分析 | V24 writer_agent 8层框架（已重建） | sac + 天眼查数据源 | P0 | SAC Gate |

### 已迁移为计算引擎（active）

| ID | 名称 | 来源 | V50 实现 | 优先级 | 门禁 |
|----|------|------|---------|--------|------|
| compute_revenue_bridge | 收入桥 | V30 L2 revenue_bridge.py | T1 compute_engine | P0 | Numeric Gate |
| compute_margin_bridge | 毛利桥 | V30 L2 margin_bridge.py | T1 compute_engine | P0 | Numeric Gate |
| compute_expense_bridge | 费用桥 | V30 L2 expense_bridge.py | T1 compute_engine | P0 | Numeric Gate |
| compute_profit_quality | 利润质量 | V30 L2 profit_quality.py | T1 compute_engine | P0 | Numeric Gate |
| compute_working_capital | 营运资本 | V30 L2 working_capital.py | T1 compute_engine | P0 | Numeric Gate |
| compute_cash_flow | 现金流质量 | V30 L2 cash_flow.py | T1 compute_engine | P0 | Numeric Gate |
| compute_roe_decomp | ROE/ROIC 拆解 | V30 L2 roe_decomp.py | T1 compute_engine | P0 | Numeric Gate |
| compute_peer_compare | 同业对标 | V30 L2 peer_compare.py | T1 compute_engine | P0 | Numeric Gate |
| compute_dcf | DCF 估值 | V30 L2 dcf.py | T1 compute_engine（WACC/beta透明化） | P0 | Numeric Gate |
| compute_comparable | 可比公司估值 | V30 L2 comparable.py | T1 compute_engine | P0 | Numeric Gate |
| compute_three_gate | 三闸门质量评级 | V34 tools/quality_gate.py | T1 compute_engine（从V34迁移） | P0 | Numeric Gate |
| compute_scenario | 情景分析 | V50 新增 | T1 compute_engine | P0 | Numeric Gate |

### 已迁移为风格指南（active）

| ID | 名称 | 来源 | V50 实现 | 优先级 |
|----|------|------|---------|--------|
| style_goldman_sachs | 高盛风格 | D:\深度研究报告原始文档 | T1 styles/goldman_sachs.yaml | P0 |
| style_cicc | 中金风格 | D:\深度研究报告原始文档 | T1 styles/cicc.yaml | P0 |
| style_citic | 中信风格 | D:\深度研究报告原始文档 | T1 styles/citic.yaml（P1） | P1 |
| style_mckinsey | 麦肯锡风格 | D:\深度研究报告原始文档 | T1 styles/mckinsey.yaml（P1） | P1 |

### 已迁移为 Bluebook 模式（active—逐步填充）

| ID | 名称 | 来源 | V50 实现 | 优先级 |
|----|------|------|---------|--------|
| bb_structure_ib | 投行报告结构模式 | D:\深度研究报告原始文档\A_国际投行 | bluebook/structure_patterns/ | P1 |
| bb_structure_consulting | 咨询报告结构模式 | D:\深度研究报告原始文档\C_战略咨询 | bluebook/structure_patterns/ | P1 |
| bb_structure_big4 | 四大报告结构模式 | D:\深度研究报告原始文档\D_四大会计 | bluebook/structure_patterns/ | P1 |
| bb_thinking_serenity | Serenity 推理链模式 | muxuu 生态 | bluebook/thinking_patterns/ | P0 |

### 已迁移为圆桌审计（active）

| ID | 名称 | 来源 | V50 实现 | 优先级 |
|----|------|------|---------|--------|
| audit_roundtable | AI污染圆桌审计 | V24 Auditor 多机构审查 + muxuu Phase4 | T3 roundtable_audit/ | P0 |
| audit_evidence_ledger | 证据账本 | V24 Auditor evidence_ledger | T3 roundtable_audit/ | P0 |

### 已迁移为测试体系（P1）

| ID | 名称 | 来源 | V50 实现 | 优先级 |
|----|------|------|---------|--------|
| test_functional | 功能测试集 | muxuu Phase4 启发 | T3 tests/functional/ | P1 |
| test_style | 风格测试集 | muxuu Phase4 启发 | T3 tests/style/ | P1 |
| test_backtest | 历史回测 | 圆桌讨论共识 | T3 tests/backtest/ | P1 |

### 由 T0 输入接口承接

| V24/Router 能力 | 状态说明 |
|----------------|---------|
| 范式路由（6类范式） | T0→T2 谋篇时根据 report_type + style_profile 自动匹配，不再作为独立的"路由"步骤 |
| 范式选择 rationale | 不写入报告。T0 内部记录选择理由，作为版本记录的辅助信息 |

### 由 T2 写作引擎承接

| V24/Writer 能力 | V50 承接方式 |
|----------------|------------|
| "判断在前，证据在后" | T2 行文强制顺序约束 |
| "读者只有20分钟" | T2 谋篇的篇幅控制 + T3 Turing Gate 的"信息密度"检查 |
| 格式硬要求（目录/图表目录/编号引用） | T3 图表引擎 + 导出器自动生成 |
| "你只输出主报告正文" | T3 SAC Gate 阻断方法论术语泄露 |

### 已裁撤（不再需要）

| 原模块 | 裁撤理由 |
|--------|---------|
| V24 Reviewer Agent | 功能分解到 T2 精修（分类修改）+ T3 SAC Gate + T3 Turing Gate |
| V24 Auditor Agent | 升级为 AI 污染圆桌审计 + 证据账本 |
| V30 orchestator/run.py | 被 T0→T1→T2→T3 管线替代 |
| V30 fill_template.py | 被 T2 三阶段引擎替代 |
| V34 web_server.py | 暂不纳入 V50 P0，单列评估 |
