# 2号分析师 Claude升级版 审计报告

审计日期：2026-07-28
审计范围：Claude对2号分析师的升级后，编码健康度、架构一致性、模块完整性、管线连接性

---

## 一、Claude升级概览

### 观察到的主要升级

| 领域 | Claude升级 | 评估 |
|------|-----------|------|
| LLM Provider | 新增 core/llm_provider.py 多Provider切换层(DeepSeek/OpenAI/Ollama，自动回退) | [OK] 解决模型锁定风险 |
| DeepSeek客户端 | core/deepseek_client.py 接入 llm_provider | [OK] 统一调用路径 |
| 评分引擎 | pipeline/agent_loop.py ScoreEngine(8维评分+DeepSeek补充) | [OK] 评分能力增强 |
| 学习回路 | pipeline/learning_loop.py(EditLearn+TemporalVerifier+ForwardPicks+Calibration) | [OK] 完整 |
| 数据采集 | data_collector_v5.py 使用 Tavily SDK | [OK] 简化但有效 |
| 段落写作 | section_writer.py 三段式写作+SAC驱动分段 | [OK] 结构合理 |
| 最终门禁 | finalize.py(AI指纹+人感+质量+IronGate+导出+格式验证) | [WARN] 未接入write_revise_loop |
| 工具集 | tools/ 新增12个分析工具 | [OK] 丰富 |

---

## 二、管线完整性审计

### 核心管线流

main.py -> WriteReviseLoop.run -> Phase1:DataCollectorV5 -> Phase1.5:ComputeEngine -> Phase2:ChartPlanner/ChartEngine -> Phase3-5:写评改循环 -> SectionWriter x3段 -> FormatSheriff -> IronGate 16项检查 -> [通过? Yes->Export:MD+DOCX / No->写循环]

### 各组件状态

| 组件 | 文件 | 接入 | 评估 |
|------|------|------|------|
| 入口 | main.py | [OK] argparse | 良好 |
| 编排器 | write_revise_loop.py | [OK] 核心引擎 | 良好 |
| 数据采集 | data_collector_v5.py | [OK] Phase1 | [WARN] 仅Tavily+yfinance+akshare |
| 财务计算 | compute_engine.py | [OK] Phase1.5 | 良好 |
| 图表规划 | chart_planner.py -> core/chart_engine.py | [OK] Phase2 | [OK] |
| 段落写作 | section_writer.py | [OK] 写作循环 | [OK] SAC驱动 |
| 格式检查 | format_sheriff.py | [OK] Gate前 | [OK] |
| 质量门禁 | iron_gate.py | [OK] 16项检查 | [OK] |
| 概率检查 | probabilistic_deep_check.py | [OK] | [OK] |
| 学习回路 | learning_loop.py | [OK] before/after | [OK] |
| 导出 | report_writer.export() | [OK] MD+DOCX | [WARN] DOCX质量依赖pandoc |
| 最终门禁 | finalize.py | [NO] 未接入 | 独立文件 |

---

## 三、编码与架构质量审计

### [OK] 优点

1. 模块化良好 - pipeline/core/compute/data/export分层清晰
2. SAC驱动 - 分析框架从YAML加载，不硬编码
3. 学习回路完整 - EditLearn+TemporalVerifier+ForwardPicks+CalibrationDashboard全接入
4. 16项Iron Gate检查 - 覆盖内容体积/AI指纹/人感/SAC维度/图表密度/数据追溯/格式/说服力架构等
5. LLM Provider解耦 - 支持DeepSeek/OpenAI/Ollama自动回退
6. Python语法通过 - 13个关键文件全部编译通过

### [WARN] 问题与风险

#### P0: 必须修复

1. finalize.py未接入主管线 - 有完整的AI指纹检查+人感注入+质量评分+导出流程，但write_revise_loop完全不调用它。

2. core/cross_validator.py导入但未调用 - report_writer.py导入了CrossValidator，但从未调用任何方法。

3. core/data_provenance.py简化版丢失功能 - 原来的EvidenceChain集成丢失，没有图表数据溯源能力。

#### P1: 功能性缺陷

4. SAC YAML的chart_config缺失 - 3/4的SAC YAML文件没有chart_config节。虽然SACLoader有硬编码回退，但YAML不再是单一事实源。

5. data_collector.py(V1)编码残留 - 功能被V5替代，应考虑清理。

6. 50+ patches文件 - patches/目录下有大量一次性修复脚本，系统经历了大量热修复，架构不够稳健。

7. V30 heritage模块已复制但不被管线调用 - harvard_framework.py/evidence_ladder.py/multi_institution_review.py已复制但没有任何代码调用。

#### P2: 架构问题

8. workflow.py vs 简化管线并行 - V51全量编排器和简化管线同时存在，架构分裂。

9. 309个.py文件维护负担大 - 含大量实验性/一次性/废弃文件。

10. 文档未更新 - docs/目录设计文档可能未反映Claude升级。

---

## 四、与First Principle的对标

| 原则 | 当前实现 | 评估 |
|------|---------|------|
| FP1: 客户是人类 | section_writer清理AI指纹/agent_loop评分人感信号 | [OK] |
| FP2: 数据零错误 | DataCollectorV5有数据质量阻断检查 | [WARN] 仅Tavily为主/cross_validator未调用 |
| FP3: SAC驱动 | SACLoader统一加载 | [OK] YAML驱动 |
| FP4: 没有裸页 | ChartPlanner+Iron Gate最小图表数 | [OK] |
| FP5: 确定性门禁 | Iron Gate 16项+FormatSheriff | [OK] |
| FP6: 学习回路 | LearningLoop完整 | [OK] |
| FP7: 多模型 | core/chart_engine多风格 | [WARN] 估值模型存在但LLM可能失败 |

---

## 五、总结与评分

**总评分：85/100**（相比上次审计82/100 +3分）

| 维度 | 评分 | 变化 | 说明 |
|------|------|------|------|
| 编码健康度 | 95/100 | +15 | 全部Python语法通过 |
| 管线完整性 | 90/100 | +10 | ComputeEngine接入 |
| SAC框架 | 85/100 | +5 | YAML驱动但有chart_config缺失 |
| 学习回路 | 90/100 | 0 | 完整但CalibrationDashboard简化 |
| 数据层 | 70/100 | -5 | 仅Tavily为主/policy/CVC/卫星未激活 |
| 导出层 | 85/100 | 0 | MD+DOCX稳定 |
| 架构一致性 | 75/100 | -5 | workflow.py与write_revise_loop并行 |
| 文档/测试 | 65/100 | 0 | 测试存在但文档未更新 |
| 终极门禁 | 60/100 | -20 | finalize.py未接入主管线 |

**关键建议：**
1. 最紧急：将finalize.py的AI指纹检查+人感检测+质量评分集成到write_revise_loop中
2. 次紧急：激活cross_validator，在导出前做多源数据交叉验证
3. 完善数据源：将data/目录下的policy_crawler/satellite_engine/cvc_engine集成到DataCollectorV5
4. 清理代码：归档patches/和output_X目录，减少维护负担
5. 恢复Heritage框架管线化：将HarvardFramework注入行业分析报告的writing_prompt
