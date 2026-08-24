# R84 全量修复——v0.90 三处根因闭环

**日期**：2026-08-07 ｜ **触发**：油位 v0.90 圆桌评价（对象错位复发：柯力加油站生意写成某制造业商用车车规）
**范围**：委托方实体锚定 + 决策引擎引用 + enrich text 键场景继承

---

## 一、修复清单（4 项全落地）

### P0-1 委托方意图锚定（must_contain + forbidden_swap）✅
- `core/report_planner.py`：
  - `build_report_plan()` 聚合 `must_contain`（必须出现的实体）与 `forbidden_swap`（禁止替换成的场景）到 plan 顶层
  - `serialize_plan()` 注入写作 prompt：「【必须出现的实体/场景】」+「【禁止替换成的场景/叙事】」
- 用法：`--client-questions` 每个问题可带 `must_contain` 数组 + `forbidden_swap` 数组

### P0-2 Gate 关键实体锚定检查 ✅
- `pipeline/checks/coverage_mixin.py`：新增 `_check_entity_anchoring()`
  - 从 client_questions 读 must_contain/forbidden_swap
  - 正文缺失关键实体 或 出现禁止场景 → error 阻断
  - decision_memo 强制；其他类型注入时启用
- `pipeline/iron_gate.py`：注册进 run_all + `IronGate.__init__` 新增 `client_questions` 参数
- `pipeline/scheduler.py`/`e2e_orchestrator.py`：client_questions 接线到 IronGate

### P0-3 Gate 决策引擎数值引用检查 ✅
- `pipeline/checks/coverage_mixin.py`：新增 `_check_decision_engine_citation()`
  - decision_memo 正文必须含：卡位评分（X.X/5）+ 最坏损失金额锚定 + 投入金额
  - 缺失 → error 阻断（禁止 LLM 自编量级）

### P0-4 enrich text 键场景继承回归测试 ✅
- `tests/test_r83_enrich_roundtrip.py`：新增 3b 段
  - 验证 text 键（competition_truth/policy_chain/huahong/jiutong/keli）进入 `_serialize_data` 输出
  - 断言 托肯恒山/防渗改造/危化品/华虹/久通/柯力 必须出现在序列化 prompt

## 二、回归结果

| 测试 | 结果 |
|---|---|
| `test_r84_entity_anchoring.py`（新增） | 12 passed |
| `test_r83_enrich_roundtrip.py`（含 text 键继承） | 10 passed |
| `test_r83_decision_memo.py` | 20 passed |
| `test_r83_decision_engine.py` | 28 passed |
| `test_data_enrichment.py` | 25 passed |
| `test_consistency_engine.py` | 21 passed |
| `test_fp_r55_data_wiring.py` | 6 passed |
| **合计** | **122 passed, 0 failed** |

## 三、v0.91 重跑命令（Marvis 用，已同步 r84 指令）

```bash
cd D:\2hao-analyst
python pipeline/scheduler.py "油位传感器" \
  --type decision_memo \
  --style cicc \
  --enrich-file data/keli_oil_enrich_v086.json \
  --client-questions '[{"q":"油位传感器市场是否值得战略卡位？","must_contain":["华虹","久通","加油站","危化品"],"forbidden_swap":["商用车","车规","汽车油箱"]},{"q":"柯力进入能否快速放量？","must_contain":["久通订单","5000只"],"forbidden_swap":["国四","整车厂"]},{"q":"久通油位业务整合至母公司承接是否可行？","must_contain":["华虹","转移定价"],"forbidden_swap":["商用车"]},{"q":"延伸产业（物位/液位大类）是否值得进入？"}]'
```

## 四、验收（10 项，全部满足才交付）

见 `docs/r84-marvis-execute-oil-v090.md` 验收标准——新增 实体锚定 + 决策引擎引用 两项 Gate 硬检查。

## 五、关键教训

**连续五版（v8/v0.88/v0.89/v0.90）同一类失效的根因**：系统能带数字（fig_* 键），带不进"这是哪门生意"（text 键场景）。R84 三件套闭环：
1. 写作前注入 must_contain/forbidden_swap（委托方是谁/不能写成什么）
2. 写作中引用 DecisionEngine 确定性数值（评分/损失/投入）
3. Gate 后校验实体锚定 + 引擎引用（缺即阻断）
