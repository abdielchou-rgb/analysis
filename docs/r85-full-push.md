# R85 全量推进——生成即正确 + 叙事一致性闭环

**日期**：2026-08-07 ｜ **触发**：油位 v0.90 全量工程计划（从"事后拦截"前移到"生成即正确"）

---

## 一、修复清单（7 项全落地）

### 支柱 A：生成层数据锚定（治本）
**A1+A2+A3 合并落地于 `pipeline/section_writer.py` 的 `_call_llm()`**（decision_memo 分支）：
- `[数据锚定-必须引用]`：8 个必须引用的数据点（46亿/166亿/托肯恒山/TDK/华虹/久通/卡位评分/最坏损失），缺失即不合格
- `[数据来源禁令-禁止引入]`：商用车/车规/汽车油箱/国四/整车厂/苏奥传感等 enrich 未提供的叙事禁止写入
- `[执行摘要强制]`：必须含卡位评分+三年投入+最坏损失+执行前提，禁止匿名化委托方

### 支柱 B：叙事一致性门禁（治标）
**B1 `_check_narrative_consistency`**（coverage_mixin）：场景特定关键实体集（加油站/华虹/危化品/托肯恒山/TDK）vs 异质实体集（商用车/车规/国四/整车厂）计数对比，异质 > 关键×1.2 → 判定叙事漂移 error 阻断。**关键改进**：用场景特定词而非行业泛词（油位/液位），避免误判。

**B2 `_check_data_point_citation`**（coverage_mixin）：11 个 enrich 关键数据点验证正文引用，缺失 >3 判定数据继承失败。

**B3 管线指纹**：已存在（`_verify_pipeline_fingerprint`），v0.90 无指纹 → 证实它没走 export_report。无需新造。

### 支柱 C：交付闭环
**C1 `_self_audit.py` 升级**：新增 P1-04 "report content consistency"——扫描最新决策备忘录，验证关键实体 vs 异质实体计数。**v0.90 实测：Total 9 Pass 8 Fail 1**（此前是 8/8 全过却内容全错）。

## 二、回归结果

| 测试 | 结果 |
|---|---|
| `test_r85_narrative.py`（新增） | 9 passed |
| `test_r83_enrich_roundtrip.py` | 10 passed |
| `test_r83_decision_memo.py` | 20 passed |
| `test_r83_decision_engine.py` | 28 passed |
| `test_r84_entity_anchoring.py` | 12 passed |
| 存量确定性（data_enrichment/consistency/fp_*) | 64 passed |
| **合计** | **143 passed, 0 failed** |

## 三、实证验证（新门禁拦下 v0.90）

```
[实体锚定]     FAIL | 缺失关键实体(5): 华虹/加油站/危化品/久通订单/5000只; 出现禁止场景(4): 商用车/车规/国四/整车厂
[决策引擎]     FAIL | 缺卡位评分(X.X/5)
[叙事一致性]   FAIL | 异质实体(59次)超过关键实体(49次)1.2倍——报告在讲另一个行业
[数据点引用]   FAIL | 缺5/11: 华虹/托肯恒山/防渗改造/危化品/卡位评分
[问题覆盖]     PASS | （四个问题都回答了，但答错生意——被叙事一致性补位拦截）
```
**v0.90 在 R85 新门禁下 5 项检查 4 项 FAIL**，证明优化有效。

## 四、v0.91 重跑命令

```bash
cd D:\2hao-analyst
python pipeline/scheduler.py "油位传感器" \
  --type decision_memo \
  --style cicc \
  --enrich-file data/keli_oil_enrich_v086.json \
  --client-questions '[{"q":"油位传感器市场是否值得战略卡位？","must_contain":["华虹","久通","加油站","危化品"],"forbidden_swap":["商用车","车规","汽车油箱"]},{"q":"柯力进入能否快速放量？","must_contain":["久通订单","5000只"],"forbidden_swap":["国四","整车厂"]},{"q":"久通油位业务整合至母公司承接是否可行？","must_contain":["华虹","转移定价"],"forbidden_swap":["商用车"]},{"q":"延伸产业（物位/液位大类）是否值得进入？"}]'
```

## 五、关键教训

**"答对了问题但答错了生意"是门禁的盲区**：问题覆盖检查只验证"答没答"，叙事一致性检查补上"答的是不是对的生意"。生成层（A 支柱）让 enrich 数据成为强制约束，门禁层（B 支柱）拦截叙事漂移，审计层（C 支柱）让 self_audit 与内容一致——三层闭环，从"放养写作+事后拦截"升级为"生成即正确"。
