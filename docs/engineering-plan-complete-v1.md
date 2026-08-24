# 2hao 全量补齐工程计划（V1.0 完备版）

> 版本：2026-08-02 | 目标：覆盖所有已识别缺口 + 参考顶级打法（投行/券商/四大/咨询/学术/对冲基金）
> 原则：第一性原理（FP1-FP7）+ 反馈闭环优先 + 真实约束适配

---

## 〇、总览：缺口全景图

### A. 已完成（19 项，不重复）
资产解析层(R26)、数据口径层(R28)、Gate一致性(R28)、写作规划(R28)、催化剂日历(R23)、多空表(R23)、非上市反向定价(R23)、瓶颈引擎(R20-22)、反向DCF(R23)、事实质量四刀(R28)、5个skill(R29)、工程计划7模块、综合同步脚本(R25)、财务字段扩展(R27)、指数成分支持(R27)、柯力回归用例(R26)、语义充足性(R26)、生成护栏(R26)、Gate收敛(R26)。

### B. 已识别未完成（4 项，本次补进计划）
| # | 缺口 | 现状 | 根因 |
|---|---|---|---|
| B1 | 排版问题 | PPTX 0图(21图全缺)、DOCX 56空段 | pptx_exporter 图表嵌入链路没生效 |
| B2 | 行业数据 | 传感器/仪器仪表/工控 3 行业缺失 | Marvis 命令给了未执行 |
| B3 | 财务明细 | 柯力 balance 仍 6 字段 | 沪深300+中证1000 方案做了未跑 |
| B4 | 预测验证 | 137 条 pending 0 验证 | 双轨未打通 |

### C. 新发现（本次调研爆出，最严重）
| # | 缺口 | 现状 | 严重性 |
|---|---|---|---|
| C1 | **预测记录质量垃圾** | 137 条预测全是 neutral、0 条有有效目标价 | 🔴 致命 |
| C2 | FP5 空转 | 宪法要求"预测追踪+准确率统计"，实测从未运转 | 🔴 致命 |
| C3 | 输出多样性 | 只出 md/docx，无 HTML（排版中立解） | 🟡 |

---

## 一、第一性原理框架

### 反馈闭环是一切的基础
```
预测 → 记录(质量) → 到期 → 验证(实际价) → 评分 → 校准 → 下次更准
                ↑____________________________|
```
**C1+C2 说明：2hao 记录的都是垃圾预测(neutral/无目标价)，且从不验证。** 这不是"缺验证"，是"从记录环节就是坏的"。必须先修记录质量，再激活验证。

### 对齐的 FP
- FP5 智能演化 ← B4+C1+C2（预测闭环）
- FP2a 数据履约 ← B2+B3（数据完整性）
- FP7 反脆弱 ← B4（从失败学习）
- FP4 人感/排版 ← B1（交付质量）

---

## 二、完备工程计划（9 大模块）

### 模块 1【P0】预测闭环修复 + 激活（B4+C1+C2，最致命）

**问题拆解**：
- 记录质量：`ForwardPick.append` 不校验 → 137 条 neutral 垃圾入库
- 双轨不通：`ForwardPicksDB`(csv) vs `TrackRecordManager`(json)
- 验证没跑：`PredictionValidator` 读 json，csv 的预测永不验证

**步骤**：
| 步 | 动作 | 文件 |
|---|---|---|
| 1a | 记录质量门槛：direction≠neutral、base_target>0、conviction 非空，否则拒绝 | `core/forward_picks.py` append |
| 1b | 清理存量：137 条 neutral/无目标价 → 标记 invalid，不参与统计 | 同上 |
| 1c | 统一数据源：Validator 读 csv+json 合并 | `core/prediction_validator.py` |
| 1d | 过期判定 + 离线价格验证（fig_qlib_price 优先） | 同上 |
| 1e | 验证回流 CognitiveBaseline（校准） | `core/forward_picks.py` |
| 1f | CLI：`scripts/validate_predictions.py` | 新增 |
| 1g | 测试：`tests/test_prediction_loop.py` | 新增 |

**成功标准**：新预测质量达标；存量清理；过期预测开始 hit/miss；命中率可读。

### 模块 2【P0】目标价追踪台账（对标投行考核）
- 2a: `data/forward_picks/target_tracker.csv` 目标价/到期价/误差
- 2b: 12个月到期判定 + 误差分级(<5%命中/<15%接近/>15%miss)
- 2c: 按标的/行业聚合 → 分析师能力档案
- 2d: 档案回流 prompt（"我过去对该类标的目标价命中率X%"）
- 文件: `core/target_tracker.py`(新), `core/cognitive_baseline.py`

### 模块 3【P1】排版修复（B1，交付质量）
**问题**：pptx_exporter 有关键词匹配嵌入逻辑，但柯力 0 图。根因可能是 chart_paths 传参或匹配失效。

**步骤**：
| 步 | 动作 | 文件 |
|---|---|---|
| 3a | 调试 PPTX 链路：确认 chart_paths 是否传入、关键词匹配为何失败 | `export/pptx_exporter.py` |
| 3b | 修复：按章节标题匹配图表，兜底全部图表依次嵌入 | 同上 |
| 3c | DOCX 空段落清洗：导出前删空 `<w:p>` | `export/docx_exporter.py` |
| 3d | HTML 导出：内嵌图表 base64 + 表格 + TOC（排版中立解） | `export/html_exporter.py`(新) |
| 3e | 测试：`tests/test_export_quality.py`（PPTX含图、DOCX无空段、HTML完整） | 新增 |

**成功标准**：柯力四件套 PPTX 含 21 图、DOCX 无空段、HTML 可打开。

### 模块 4【P1】行业数据补齐（B2）
- Marvis 执行：industry_chain 加传感器/仪器仪表/工控；penetration 加传感器条目；drivers 加传感器 key
- 命令已给：`docs/marvis-data-backfill-20260802.md` §2
- 验证：`resolve_asset('柯力传感') → load_industry_chain` 非空

### 模块 5【P1】财务明细执行（B3）
- Marvis 执行：`python scripts/sync_akshare_financials.py --index 000300 --workers 4` + `--index 000852`
- 验证：柯力 balance 字段从 6 → 20+（含应收/存货/商誉/研发）

### 模块 6【P1】三表勾稽验证（对标四大）
- 6a: `core/three_statement_audit.py`(新) 规则引擎（资产=负债+权益等）
- 6b: Gate `_check_balance_sheet_audit` 不平衡阻断
- 6c: 依赖模块5的财务明细

### 模块 7【P1】预期差引擎（对标券商）
- 7a: consensus 扩充 300 只
- 7b: 业绩预告/快报同步 `scripts/sync_earnings_forecast.py`(新)
- 7c: `core/earnings_surprise.py`(新) 预告 vs 一致预期 → 超/低于预期

### 模块 8【P1】估值锚统一 + 反向DCF深化（对标投行/New Constructs）
- 8a: `core/valuation_crosscheck.py`(新) 多方法交叉验证
- 8b: 反向 DCF 隐含 FCF margin 反推 `core/data_caliber.py`
- 8c: 复用 R28 `_check_rating_target_consistency`

### 模块 9【P2】预测 vs 基准检验 + 对标矩阵（对标学术/咨询）
- 9a: 基准=均值回归，2hao 预测超额准确率 `core/prediction_validator.py`
- 9b: `core/peer_matrix.py`(新) 标的 vs 行业基准逐项对比

---

## 三、依赖关系与执行顺序

```
模块1(预测闭环) ← 最高优先，C1+C2 致命
  ├→ 模块2(目标价追踪)
  └→ 模块9a(基准检验)
模块3(排版) ← 独立，交付质量
模块4(行业数据) ─┐
模块5(财务明细) ─┴→ 模块6(三表勾稽)
模块7(预期差) ← 独立
模块8(估值锚) ← 依赖 R28
模块9b(对标矩阵) ← 依赖 global_leaders
```

**执行顺序（并行三线）**：
- **线 A（智能演化）**：模块1 → 模块2 → 模块9a
- **线 B（交付质量）**：模块3 → 模块4 → 模块5
- **线 C（方法论深化）**：模块6 → 模块7 → 模块8 → 模块9b

## 四、真实约束适配

| 约束 | 适配 |
|---|---|
| VM 无 akshare | 模块4/5/7a 由 Marvis 用户机执行；模块1-3/6/8 逻辑用 VM 现有数据 |
| 单 provider DeepSeek | 验证/评分/勾稽用确定性规则（不依赖 LLM） |
| bash 45s 上限 | 长验证拆小步；验证 CLI 分批跑 |
| 上下文约束 | 长任务用 2hao-context-guard checkpoint |
| 数据质量（C1） | 模块1 先清垃圾预测，再谈验证 |

## 五、成功标准（整体）

柯力传感完整报告：
1. 预测有质量（direction/target/conviction 齐全）→ 记录 ✅
2. 12个月后自动验证 → 命中率/误差可查 ✅
3. PPTX 含 21 图、DOCX 无空段、HTML 可打开 ✅
4. 传感器行业数据可读（chain/penetration/drivers）✅
5. 三表勾稽通过 ✅
6. 预期差信号明确 ✅
7. 估值锚统一（无 PE 矛盾）✅
8. 对标矩阵完整 ✅

## 六、验收测试

```
tests/test_prediction_loop.py   # 模块1
tests/test_target_tracker.py    # 模块2
tests/test_export_quality.py    # 模块3
tests/test_three_statement_audit.py  # 模块6
tests/test_earnings_surprise.py # 模块7
tests/test_valuation_crosscheck.py   # 模块8
tests/test_peer_matrix.py       # 模块9b
```
+ 现有 59 项回归全过

---

**一句话**：这份计划覆盖了 A(已完成19项) + B(4项遗漏) + C(新发现2项致命)——共 9 大模块，三线并行。最优先的是**模块1**：修预测记录质量(137条垃圾) + 激活验证闭环，因为这是 FP5 智能演化的地基，也是 2hao 从"会造报告"到"会验报告"的分水岭。
