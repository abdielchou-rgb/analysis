# SSOT + 单写路径 + 门禁分层 · 执行方案

**日期**：2026-09-07
**依据**：ultrathink 顶级解法调研（SSOT/cortex-x、Zod ADR、Strangler Fig、Layer-Don't-Choose、LLM-judge-is-not-oracle、Hypothesis round-trip）
**一句话**：把 2hao 从"两套 schema 各写各的、两个门禁各判各的"收成——**一个 store of record、一条写路径、一个门禁事实源、一个不可被覆盖的确定性层**。
**铁律**：无测试不交付；改动经 ruff correctness gate + 回归全绿。

---

## 〇、四条原则 → 落到 2hao 的哪一处

| 顶级原则 | 出处 | 2hao 落点 |
|---|---|---|
| SSOT：一个字段只有一个权威位置，"Can two systems claim to be right about the same field?" = 拒 | cortex-x ssot / Zod ADR | `Prediction` dataclass 是唯一 store of record；`update_outcomes.py` 裸 dict 直写必须收编 |
| round-trip 不变量 `deserialize(serialize(x))==x` | Hypothesis / TU Delft | 任意 Prediction serialize→deserialize 恒等测试；schema 演进即红 |
| Strangler Fig：facade→shadow→canary→decommission | Microsoft / Fowler | `irongate_v2` 从"第二个门禁"降为 advisor，由 run_all facade 决定 |
| Layer-Don't-Choose：确定性层在前，LLM-judge 只处理余量且不可覆盖门禁 | futureagi / PROCTOR | run_all(确定性/规则, fail-closed)=门；v2(LLM 5层)=报告性 advisor；judge 分数永不直接放行 |

---

## 一、改动任务书

### T1 单写路径：`update_outcomes` 收编进 `TrackRecordManager`（P0，最高优先）

**问题**：`scripts/update_outcomes.py` 的 `load_track_record/save_track_record` 是**第二条裸 dict 写路径**，绕过 dataclass schema。SSOT 原则：`core/tools/track_record.py` 是唯一 store of record，任何外部写入必须经其门面。

**设计**：
- `core/tools/track_record.py` 新增门面方法：
  ```python
  def apply_resolved(self, predictions: list[dict]) -> int:
      """把 resolve 结果(dict)写回 dataclass 并落盘。校验：未知键丢弃+告警；outcome∈词表。"""
  def load_for_update(self) -> list[dict]:  # 读为 dict 视图(含 expiry_date 派生)
  ```
- `scripts/update_outcomes.py`：删 `save_track_record` 直写；改为 `TrackRecordManager(storage_path).apply_resolved(updated)`。
- `check_expired` 移入 `TrackRecordManager` 或保留纯函数但不再承担写盘职责。

**守护测试**：`test_update_outcomes_goes_through_manager`——monkeypatch `get_price_func`，断言 resolve 后文件经 dataclass 写回且 alpha/bench/return_pct/resolved_at 保留；`track_record.json` 无裸 dict 残留键。

**验收**：grep `json.dump(data, ...track_record` 无裸写；唯一写路径 = `TrackRecordManager._save`。

### T2 round-trip 恒等测试（P0）

**设计**：`tests/test_roundtrip_invariant.py`——用 Hypothesis `from_type(Prediction)` 或穷举字段组合，断言：
```python
def roundtrip(p: Prediction) -> Prediction:
    raw = json.loads(TrackRecordManager(...).dump(p))   # 经 dataclass 序列化
    return Prediction(**{k: raw[k] for k in Prediction.__dataclass_fields__ if k in raw})
assert roundtrip(p) == p  # 全字段恒等
```
- 覆盖：空字段/None/全字段填满/含 resolve 四键/含新 schema 键(应告警丢弃而非崩)。

**验收**：schema 增加任一字段后若 `_load`/`_save` 未同步 → 测试红。

### T3 门禁分层裁定：run_all=门，v2=advisor（P1）

**问题**：`iron_gate._run_irongate_v2_checks` 把 v2 各层 append 为 `severity="error" if score<0.5 else "warning"`，与 run_all 的 error-mean 门禁**并行**——两个引擎都可能以 error 身份 block，构成双事实源。

**裁定（Strangler Fig + Layer-Don't-Choose）**：
- **run_all（101 项确定性/规则 + error-mean 0.78 fail-closed）= 唯一门禁**。
- **v2（5 层 LLM）降为 advisor**：severity 恒为 `warning`（永不 error），分数进 report card 供人看、不进 passed 判定。理由：LLM 判断是 advisor 不是 oracle，不可覆盖确定性门禁（PROCTOR 五护栏精神）；未来如要启用 v2 作门，走 shadow→golden 对比达标后由产品决策提升。

**守护测试**：`test_v2_is_advisory_not_gate`——mock IronGateV2 返回全 0 分 layer，断言 Gate `passed` 不受 v2 error 影响；report card 含 v2 分数。

**验收**：v2 不再产生 error-severity check；`passed` 只由 run_all error-mean 决定。

### T4 schema 派生 + 文档单一源（P1，衔接 R4）

- `harness/generate_docs.py` 已从 iron_gate.py 读阈值（R4 完成）；补：`Prediction` 字段清单由 dataclass 派生写入 PIPELINE_FACTS（若存在该节）。
- 不手写第二份 schema；所有 `prediction["x"]=` 写入键由 `test_resolve_write_keys_are_on_dataclass` 守（已完成）。

---

## 二、执行顺序与验收

```
T1(单写路径) → T2(round-trip) → T3(门禁分层) → T4(派生核对)
每步红→绿 + ruff correctness gate
```

**DoD**：
- [ ] `update_outcomes` 不再裸写 JSON；唯一写路径 = TrackRecordManager
- [ ] round-trip 恒等测试绿；加字段不加同步 → 红
- [ ] v2 降 advisor（无 error severity）；Gate passed 只由 run_all 决定
- [ ] ruff correctness gate 绿；回归全绿
