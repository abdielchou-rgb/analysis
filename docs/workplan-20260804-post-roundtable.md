# 2号分析师 后续工作计划（2026-08-04 起）

> 基于圆桌讨论结论：三个维度（覆盖意识→从 checklist 到 awareness、方法选择→从规则到数据驱动、失败保护→从被动修复到主动自愈）
> P0 = 沙箱/用户机本周可完成 | P1 = 需累积运行数据 | P2 = 需架构调整+R68看齐

## 一、立即可做（P0，本周）

### 1. R68 接线验收 + 回归修复
- 跑 `scripts/check_wiring.py` 确认 coverage_mixin + universe_build 接线率
- 修复报告提到的 3 个 assertion drift：
  - `test_r55_llm_verification.py`：文件读取路径更新到 `pipeline/checks/llm_checks_mixin.py`
  - `test_e2e_keli.py::test_locate_failed_segments_types`：断言更新到 R66 新行为（charts 全段局部重写不再 return None）
- 确认 IronGate 69 检查全部接线（67 + 2 coverage = 69）

### 2. 覆盖意识从 checklist → staleness detection
- `universe_build.py` 加 `staleness_check`：unlisted_players.json 最后更新时间 > 90 天 → 标记 `recommend_action: "stale_refresh"`
- `brand_entity_mapping.json` 同逻辑
- IronGate 新增 warning 级检查：报告涉及的行业在 unlisted_players 里缺条目 → 提示"底座可能漏行业"
- 对齐 R68 的 `coverage_rate < 0.7` 阈值接入 FP5 回测校准（当前硬编码改从 registry 读）

### 3. 方法选择从规则 → 初代数据驱动
- `framework_registry.json` 效果字段清空"初始基线"标记——当前 7 个框架的"已用次数/平均Gate分"全是估算值
- `method_reflection` 接入 e2e 出口：报告完成后若 analysis_plan 存在且 Gate 通过，自动调用 `record_reflection`
- scheduler 的 data_sufficiency_hint 从 gaps.json 自动读的路径已有（R65补），确认在 training 模式真实数据流能走通

### 4. 失败保护的 chaos 注射（首例）
- 执行一次人工 fault injection：关闭 DeepSeek → 验证 agent_provider 质量护栏拦截坏响应 → 记录结果
- 验证 best-so-far 回滚：模拟 attempt3 Gate 分低于 attempt1 → 确认回滚到 attempt1 稿
- 两种场景都只读不破坏（用 dry-run 模式 + 日志验证）

---

## 二、中等范围（P1，需累积运行数据）

### 5. 方法选择双轨并行——产真实方案数据
- 跑 3-5 份不同行业报告（气体传感器/柯力传感/思必驰/恒瑞医药/腾讯控股），每份让 planner 产出 analysis_plan
- 收集 {标的, 数据充足度, 选用的框架, Gate分数} → 回写 registry 效果字段
- 跑完后看：哪个框架组合对哪个行业类型 Gate 分最高、planner 的规则选择 vs 实际效果偏差
- 目标：registry 效果数据从估算 → 实测，planner 下次选框架有真实依据而非规则

### 6. 覆盖意识动态发现——首例"从报告中反向发现"
- 跑一份气体传感器报告（数据底座已有），抽查报告中提到的公司名 vs unlisted_players.json
- 若出现"底座没收录但报告引用"的公司 → 生成 `_suggested_players.json`（建议补充清单）
- 不自动回写（人工确认），但建立发现→建议的链路

### 7. FP7a chaos engineering 常态化
- 写 `scripts/chaos_inject.py`：随机断掉数据源/LLM provider/图表生成 → 管线是否正常降级
- 每跑 10 份报告触发一次自动 chaos（可在 e2e 末尾加概率触发器）
- 目标：不等柯力事故，主动制造小错误验证保护层

---

## 三、长期架构（P2，跨 R69-R74）

### 8. 三缺一的第四维度：预测闭环验证
- forward_picks 12 条已入库（2026-08-03），2027-08-04 到期可验证
- 在此之前：不能等一年才验证——**加 3M/6M 短周期预测**（快速反馈）
- `analyze_short_term_signals`：从现有宏观/资金面数据生成 3 月内可验证信号（如"北向资金对恒瑞增持 vs 减持方向"）
- 目标：不等一年，三个月内验证一批短周期判断，让 FP5 演化有数据转起来

### 9. Universe Building 扩展——从静态到动态
- 当前只覆盖 industry_deep → 扩展 listed_company（用的品牌映射做 group affiliation 校验）
- `_infer_missing_from_report`：报告写完后，用 LLM 提取文中公司名 → 与 unlisted_players + brand_mapping 对比 → 生成待补充清单
- 对接 Marvis 做定期采集（定时调度刷新 unlisted_players.json）

### 10. 方法选择全面数据驱动
- 条件满足时（registry 跑过 20+ 份报告，每个框架用过 ≥3 次），planner 从硬编码规则切换为 RL 策略（选框架组合最大化预期 Gate 分）
- 这个阶段当前不急，但架构口子 R65 已经打开——只用把 `select_frameworks` 的规则引擎换成一个从 registry 学习的函数

---

## 四、近期行动清单（可直接执行，沙箱做）

| 序号 | 动作 | 预期产出 | 估时 |
|---|---|---|---|
| 1 | R68 接线验收 + 3 assertion drift 修复 | check_wiring 覆盖 coverage_mixin | 0.5h |
| 2 | universe_build staleness_check 实现 | >90天自动 stale 标记 | 0.5h |
| 3 | framework_registry 效果字段校准（清估算标记） | 7 框架效果字段加 `_baseline: estimated` 标记 | 0.2h |
| 4 | method_reflection 接入 e2e 出口 | 报告完成自动记录框架效果 | 0.5h |
| 5 | chaos injection 首例（手动 dry-run） | 验证质量护栏 + best-so-far 回滚 | 0.3h |
| 6 | 跑一份气体传感器报告（含新 coverage check） | Gate 通过 + analysis_plan 生效 + coverage check PASS | 用户机 |
| 7 | 回归测试全量 | r65-r68 全部绿 | 用户机 |

---

## 五、一句话总结

圆桌承认"三个维度是刚打开的方向，不是已完成的事"。工作计划不是补丁堆，而是沿着这三个方向稳步推进的工程路线：让覆盖从 checklist 变成 awareness（staleness detection）、让方法从规则变成数据驱动（跑报告积累效果数据）、让失败保护从被动变成主动（chaos injection）。原则是每一步都解决真实问题而非虚构问题。

[查看圆桌讨论完整分析](computer://D:\2hao-analyst\docs\r68-marvis-upgrade-think.md)
