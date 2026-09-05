# P0 质量收尾 · 执行方案（2026-09-03）

**版本**：v1.0
**日期**：2026-09-03
**定位**：承接 2026-09-03 总结（docs/WORK_SUMMARY_2026-09-03.md）的 P0 执行篇。该总结交付的框架（A1-D6、C1-C6、dashboard/CLI、68 测试）**代码属实、方向正确**；本方案把 ultrathink 审计发现的**五处假阳性**落成可执行修复——核心一句话：
> **框架全部就位，传感器还没接。** calibration/significance/cohort 是顶级设计，但喂进去的是 pending（2028 条 100% pending）与占位价。若不加真价与诚实标注，10-31 会把"假价格"当"真结果"，产出统计学上漂亮的谎言。

**铁律**：无测试不交付；根因不明不修复；**无真实价格源不得 resolve outcome（FP2a：不编数据）**。

---

## 〇、根因表（每条：证据 → 后果 → 修复）

| # | 问题 | 磁盘证据 | 后果 | 修复任务 |
|---|---|---|---|---|
| R1 | outcome updater 无真实取价 | `scripts/update_outcomes.py` L91-115：`get_price_func=None` 时返回**占位价**；全文无 akshare/yfinance import | resolve_outcome 会把 pending 伪回填成假 hit/miss → 污染 track_record → 校准/MC 全部建立在假结果上 | E1 |
| R2 | MC 对无到期池跑显著性 | track_record 2028 条 100% pending；`core/significance.py` 对空 outcome 池跑 N=10000 | p 值恒 1.0/无意义，dashboard 数字是空转 | E2 |
| R3 | ArgumentEngine 异常被吞 | `pipeline/e2e_orchestrator.py` L393-396：`except Exception → logger.warning + scaffold=None`；根因 `core/models.py` L180-195 曾 `unit=""` raise（B4 已把 unit 可空，但错误路径仍静默） | D1 看不到 argument 失败（scaffold 不在 D1 证据清单 `_node_evidence` L1069-1074）→ 意图层空转 Gate 照过 | E3 |
| R4 | B1 占位符半真 | `_replace_placeholders`（section_writer L213-241）只**警告**残留不阻断；无 post-replace 数值校验 | LLM 自创 `{{xxx}}` 只打日志、不拦 → 占位符泄漏进交付物 | E4 |
| R5 | golden 无数值真值 | `scripts/validate_golden.py` 只有 Jaccard + 结构相似度（L42/58）；7427 份研报是**风格语料非真值集** | golden 治不了"幻觉数字"——只能验证像不像风格，不能验证对不对 | E5 |
| R6 | D3/D4/D5 未接主链 | `e2e_orchestrator.py` 对 retry_policy/idempotent_ledger/hitl_durable **零 import** | 保险库没装进车 | E6 |
| R7 | CI 只有 import 冒烟 | ci.yml 的 Import check 是 `python -c "from ... import ...; print OK"`（L45-53），无 eval/golden 门禁 | "配了 CI"与"CI 守门"是两回事 | E7 |

---

## 一、任务书（P0-1 ~ P0-7）

### P0-1 接真价：update_outcomes 用 akshare（R1 — 最高优先）

**设计**：`scripts/update_outcomes.py` 增加真实取价后端，替换占位价路径。

- 新增 `scripts/price_feeder.py`（或复用 `core/data_service`）：
  ```python
  def get_price(asset: str, date: str, backend: str = "auto") -> float | None:
      """真实收盘价。auto = akshare 优先 → yfinance 回退 → None。
      None 表示"数据不可得"——调用方必须标 data_unavailable，禁止编造。
      """
  ```
- 存储侧改造（`core/tools/track_record.py` + `resolve_outcome`）：
  - 取不到价 → `outcome="unverifiable"`, `outcome_detail="data_unavailable:<asset>@<date>"`（**不许填 hit/miss/partial**）
  - 取到价 → 正常判 alpha/方向（复用 W2 的 `core/prediction_judge.py` 判据）
- **沙箱注意事项**：akshare 在沙箱需先清代理 env（记忆：sandbox-akshare），东财源被墙时用 Sina/腾讯源替代。

**守护测试** `tests/test_price_feeder.py`（红→绿）：
1. 取价成功 → 返回 float >0
2. 后端全失败 → 返回 None（不抛、不编 0.0）
3. resolve_outcome 遇 None → `unverifiable + data_unavailable`，**不改写 outcome**
4. 无 `0.0` 占位价残留在 resolve 路径（grep 断言）

**验收**：跑 `python scripts/update_outcomes.py --dry-run` 输出"到期 N 条，可验证 M 条，data_unavailable K 条"，且 track_record 不被占位价污染。

**工作量**：3h（沙箱网络调试另计 1-2h）。**依赖**：W2 的 prediction_judge 若已存在则复用；否则本任务内建最小判据。

---

### P0-2 MC 只跑真实 outcome（R2）

**设计**：`core/significance.py` 两个 MC 函数入口加**有效性前置**：

```python
def _require_valid_outcomes(predictions) -> int:
    valid = [p for p in predictions if p.get("outcome") in ("hit", "miss", "partial")]
    if len(valid) < 20:
        raise InsufficientOutcomes(f"有效 outcome 仅 {len(valid)} 条（阈值 20）——先接真价并等待到期")
```

- dashboard `--significance` 捕获该异常 → 输出"数据不足，跳过显著性"而非假 p 值。
- 到期池不足时**空跑模板**，把 MC 的 N=10000 能力留给 P0-6 的真验证。

**守护测试** `test_significance_guard.py`：
1. 全 pending 池 → 抛 InsufficientOutcomes（不产出 p 值）
2. 20+ 真实 outcome 池 → 正常出 p/percentile
3. dashboard 捕获后 exit code 非 0 但输出人类可读说明

**验收**：任何 dashboard 输出里不会再出现"对空池算出的 0.0000 p 值"。
**工作量**：1h。

---

### P0-3 修 ArgumentEngine 洞（R3 — 让 D1 真正生效）

**设计**：三件套。

1. **抛异常给编排器**：`e2e_orchestrator.py` `argument_engine` 节点把
   ```python
   except Exception as e:
       logger.warning(...); context["scaffold"] = None
   ```
   改为**按证据契约处理**：scaffold 是设计内必需（对 decision_memo / 机构长报告）时记录失败证据 `context["node_errors"]["argument"] = str(e)` 并**传播**；仅在非必需报告类型允许降级并显式标注。
   - 根因再确认：`core/models.py` B4 已把 `unit` 可空——`DataPoint` 构建不再因空 unit 抛错；但 `WritingBrief(asset=...)` 用 `context.get("asset","")` 可能仍为空串触发其他必填校验。**先跑一次真实 e2e 复现，确认当前失败点再改**（无根因调查不修复）。
2. **扩 D1 证据清单**：`_node_evidence`（e2e L1069-1074）加 `"argument": ["scaffold"]`，缺失即 block（warning 级对意图层不够）。
3. **graph 层 fail-closed**：e2e 图定义 L2549-2550 的 `required: False, severity: warning` 参数表改为——对声明"argument 必需"的报告类型 `required: True, severity: error`。

**守护测试** `test_argument_node_contract.py`（红→绿）：
1. ArgumentEngine 抛错 → e2e 整链显式失败（gate_result.passed=False）
2. scaffold 缺失 → D1 拦截（不再 warning 放行）
3. 非必需报告类型 → 允许降级但带标注

**验收**：argument 节点失败不再静默；意图层空转会被 Gate 拦。
**工作量**：2h + 复现调查 1h。

---

### P0-4 B1 占位符补强（R4）

**设计**：
1. **残留即阻断**：`_replace_placeholders` 检测到 `{{[a-z_]+}}` 残留 → 不是 warning，而是返回标记让上游进入**重写或失败**；在 `content_format_mixin._check_placeholder_xxx`（L115）把残余占位符从 warning 提为 error。
2. **post-replace 数值校验**：替换后扫描正文，出现 `{{` 即记 failure。

**守护测试** `test_placeholder_hard_block.py`：
1. LLM 自创 `{{pe_ratio}}` → 替换阶段检测 → 触发重写（或 Gate error）
2. 正常 `{{tp_primary}}` → 替换为 compute 值 → 无残留
3. 无 compute 值时 `{{tp_primary}}` 不替换也不静默——标记 unverifiable

**验收**：占位符不可能泄漏到 docx 交付物（Gate 前被拦）。
**工作量**：1.5h。

---

### P0-5 golden 数值真值（R5）

**设计**：在现有"风格语料"golden 之外，新增**机检数值真值集**：

- 新 `benchmark/golden_numeric/*.json`（首批 30-50 条，从真实交付报告 + compute 产物提取）：
  ```json
  {
    "asset": "宁德时代", "report_id": "...", "field": "target_price",
    "canonical": 260.0, "source": "compute_primary_target_price",
    "allow_report_values": [260.0], "tolerance": 0.01
  }
  ```
- `scripts/validate_golden.py` 扩展 `--numeric`：对报告正文提取 target_price/关键财务数值，与 canonical 比对，超 tolerance 即红。
- 注意：**这是治"幻觉数字"的真值锚**——现有 Jaccard 风格相似度只治"像不像风格"，继续保留但不算质量分。

**守护测试** `test_golden_numeric.py`：
1. 报告含 canonical 值 → pass
2. 报告写 310（偏离 260 >1%）→ fail
3. 报告无该字段值 → 标 unverifiable（不 fail，不编造）

**验收**：`validate_golden.py --numeric` 能拦下"目标价 38.40 无来源"这类硬伤。
**工作量**：3h（首批标注 + 代码）。

---

### P0-6 MC 真验证彩排（R1+R2 之后才有效）

**设计**：等 P0-1 接真价后，造 **5 条"昨日到期 + 带目标价"的 mock 预测**，全链路 dry-run：
到期判定 → 真实取价（若沙箱网络可用）或 mock 价 → alpha 判据 → MC N=10000 → 归因 → 输出 dashboard。

**验收**：`dashboard --significance --update-outcomes` 全链路出**带真数字**的报告（哪怕 mock 价也走真实判定代码路径）。
**工作量**：2h。**依赖**：P0-1/P0-2/P0-7。

---

### P0-7 把"装了没接"的接上（R6+R7）

**设计**：
1. **D3 接线**：`e2e_orchestrator.py` 对 LLM 调用点（deepseek_client/zhipu 调用）接入 `RetryPolicy.classify_error` → 声明式重试替换手写 try/except 循环（限流→退避、超长→压缩上下文、不可重试→立刻失败）。
2. **D4 接线**：e2e 写 DB/导出 docx 前先 `IdempotentLedger.record_pending`，崩溃后 `recover_incomplete()`；export 节点加幂等键（job_id+asset+type）。
3. **D5 接线**：`export_docx` 的 HITL 门（decision_memo 读 data/reviews）接 `core/hitl_durable.py`——审批请求持久化 → 崩溃后 `resume_after_approval()` 从 export 续跑（替换现在"读文件判断"的半实现）。
4. **CI 真门禁**：ci.yml 加 job：跑 `validate_golden.py --numeric`（新）+ `dashboard --significance` 冒烟 + **delta 门**（对 golden_numeric 全绿才过）；`update_outcomes --dry-run` 不放 CI（需真网络）。
5. **B1 自动填充位置确认**：`_replace_placeholders` 的调用点在 section_writer L1086/1106/2570（per-section 与 assemble 路径都有）——补一条 assemble 后置校验（L2570 后）确认无残留才放行到 export。

**守护测试** `test_wiring_to_e2e.py`（新，红→绿）：
1. 模拟 LLM 429 → RetryPolicy 退避后成功（不写手写循环）
2. 导出前崩溃 → 台账 recover → 不重复导出
3. approval 请求在"重启"后仍可 resume
4. assemble 后含 `{{` → 出口被拦

**验收**：D3/D4/D5 不再是孤立库；CI 首次真正守门（numeric golden 全绿才绿）。
**工作量**：4h。

---

## 二、执行顺序

```
P0-1 接真价（3h）───────┐
P0-3 修 argument 洞（3h） │   ← 三者独立，可并行
P0-5 golden 数值（3h）───┘
        │
P0-2 MC 前置（1h，依赖 P0-1 的 outcome 语义）
P0-4 占位符硬拦（1.5h，依赖 P0-5 思路）
        │
P0-7 接线 + CI 门禁（4h，依赖 P0-1/3/4/5）
P0-6 MC 彩排（2h，依赖全部）
─────────────────────────
合计 ≈ 13h + 网络调试 ≈ 1.5 人日
```

**批次建议**：今天做 P0-1 + P0-3 + P0-5（并行三线程），明天 P0-2/4/7/6。每任务独立 commit，语义前缀（`fix(price)` / `fix(argument)` / `feat(golden-numeric)`）。

---

## 三、Definition of Done

- [ ] **P0-1**：update_outcomes 无占位价路径；取不到价 → `unverifiable/data_unavailable`，track_record 不被污染
- [ ] **P0-2**：全 pending 池跑 MC → 明确报"数据不足"，绝不产假 p 值
- [ ] **P0-3**：argument 失败 → 整链显式失败；scaffold 进 D1 证据清单；graph 参数表 fail-closed
- [ ] **P0-4**：残留占位符 Gate error（不是 warning）；占位符不可能进 docx
- [ ] **P0-5**：`validate_golden.py --numeric` 可拦"无来源目标价/数值偏离"
- [ ] **P0-6**：mock 到期彩排全链路出真数字报告
- [ ] **P0-7**：D3/D4/D5 进 e2e 主链；CI 含 numeric golden 门禁
- [ ] 全部守护测试红→绿；git 提交带语义前缀

**不做**（留到下轮）：N=10000 对真池调优、golden 扩充、dashboard HTML、MC 阈值细化——等 P0 真价闭环后再做才有意义。

---

## 四、与文档关系

| 文档 | 关系 |
|---|---|
| docs/WORK_SUMMARY_2026-09-03.md | 本方案是它的 P0 执行篇（它交付框架，本方案接传感器） |
| ULTRA_OPTIMIZATION_ROADMAP_20260902.md | A/B/C/D 主线的落地子集（A1/D1/B1/golden/MC 已有雏形，本方案补真价与接线） |
| MASTER_PLAN_20260902.md | 本方案的 P0-1 对应其 W1.2（backfill 前置条件）；P0-3 对应 W5 系修复 |
| EXECUTION_PLAN_20260902.md | 已被 MASTER_PLAN 取代，不再引用 |
