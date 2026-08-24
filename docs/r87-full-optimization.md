# R87 全量优化——enrich 可信度治理 + 场景锁定 + 数值统一

**日期**：2026-08-07 ｜ **触发**：油位 v1.0 圆桌（enrich v086 含幻觉，门禁锚定不可靠数据源）

---

## 一、修复清单（5 项全落地）

### P0-1 enrich 数据源可信度治理 ✅
- 新建 `data/keli_oil_enrich_v087_corrected.json`（R87 修正版），修正 enrich v086 幻觉：
  - 磁致伸缩丝：TDK垄断(幻觉) → **爱知制钢/VAC主导**(正确)
  - 政策：2019防渗改造62%(幻觉) → **2015水十条**+东部近100%/全国5-8%未完成(正确)
  - 华虹：主营物位/液位(幻觉) → **主业矿山物联网**，油位产能需新建(正确)
  - 竞争：KROHNE纳入竞争观察但非全球前五(前五=VEGA/Siemens/E+H/Emerson/Yokogawa)
  - 每项加 `source_level`（verified/corrected/unverified）

### P0-2 Gate 数据源可信度检查 ✅
- `coverage_mixin._check_source_reliability()`：报告沿用已知幻觉值（TDK/2019防渗/华虹产线）→ FAIL；采用修正值 → PASS
- 实测：沿用幻觉 FAIL / 修正值 PASS
- 注册进 iron_gate.run_all

### P0-3 场景锚定锁定加油站/危化品 ✅
- r86 命令更新：must_contain 加"防渗改造/SIS"，forbidden_swap 加"工程机械/IATF16949"
- enrich 文件路径改 v087_corrected

### P0-4 决策数值单一来源 ✅
- DecisionEngine `calculate_investment` 口径对齐 v1.1：华虹1.22亿=股权投资非沉没；运营投入上限约1850-2450万；最坏损失约1700万≈净利5%
- 修正 1.22 提取正则（`([\d.]+)\s*亿\s*增持`）
- tech_route 卡脖子改爱知制钢/VAC
- 回归测试断言更新为新口径

### P1-5 更新 Marvis 指令 ✅
- r84/r86 指令 enrich 路径改 v087_corrected，同步到 Marvis/output/reports/

## 二、回归结果

| 测试 | 结果 |
|---|---|
| test_r85_narrative | 9 passed |
| test_r83_decision_engine | 28 passed |
| test_r83_decision_memo | 20 passed |
| test_r83_enrich_roundtrip | 10 passed |
| test_r84_entity_anchoring | 12 passed |
| test_data_enrichment | 25 passed |
| test_consistency_engine | 21 passed |
| fp_* (r55/source/valuation) | 18 passed |
| enforcer/format_sheriff | 全过 |
| **合计** | **147 passed, 0 failed** |

## 三、v1.1 重跑命令

```bash
cd D:\2hao-analyst
python pipeline/scheduler.py "油位传感器" \
  --type decision_memo \
  --style cicc \
  --enrich-file data/keli_oil_enrich_v087_corrected.json \
  --client-questions '[{"q":"油位传感器市场是否值得战略卡位？","must_contain":["华虹","久通","加油站","危化品","防渗改造","SIS"],"forbidden_swap":["商用车","车规","汽车油箱","工程机械"]},{"q":"柯力进入能否快速放量？","must_contain":["久通订单","5000只"],"forbidden_swap":["国四","整车厂","IATF16949"]},{"q":"久通油位业务整合至母公司承接是否可行？","must_contain":["华虹","转移定价"],"forbidden_swap":["商用车"]},{"q":"延伸产业（物位/液位大类）是否值得进入？"}]'
```

## 四、关键教训

**门禁的输入（enrich）需要独立可信度治理**。R83-R85 把门禁越修越严，但"Garbage In Garbage Out"在门禁层体现：enrich 含幻觉时，门禁会放行错误的锚定、拦下正确的修正。R87 三件套：
1. enrich 数据来源分级（verified/corrected/unverified）
2. Gate 校验报告是否沿用已知幻觉值（沿用→FAIL，修正→PASS）
3. 决策数值单一来源（引擎口径与报告一致）
