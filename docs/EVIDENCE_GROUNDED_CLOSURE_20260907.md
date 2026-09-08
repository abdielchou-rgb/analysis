# Evidence-Grounded Writing + Delta-Only Rewrite — 交付闭环

**日期**：2026-09-07
**性质**：`QUALITY_SPEED_MASTER_20260907.md` 质量层门禁④（方法论应用深度）的**首阶段实现**——从"后置门禁检查"升级到"前置证据整合"。

---

## 一、解决了什么问题

| 问题 | 根因 | 后果 |
|---|---|---|
| MKB 全量盲注 | `_inj_mkb_str` 一次性检索 8 条，不分维度，全部塞进每组 prompt | 估值组拿到 ESG 条目，ESG 组拿到 DCF 条目——证据错配 |
| Rewrite 全文重写 | `rewrite_sections` 把 20K 全文 + 审稿意见发给 LLM | LLM 改了不该改的段、丢了数据标注、长度失控 |
| 无法追踪 KB→正文映射 | `dim_kb_map` 不存在 | Gate 检查"引用覆盖"只能做统计，不能做归因 |

---

## 二、改了什么

### 2.1 research_planner.py（+57 行）

```
_DIM_MKB_KEYWORDS = {
    "valuation_assessment": ["估值", "DCF", "PE", "可比"],
    "financial_analysis": ["财务分析", "估值", "盈利", "毛利率", "ROE"],
    ...
}

_build_dim_kb_map(dims, asset, report_type) → {dim_id: [entry, ...]}
```

- 为每个维度调 `select_entries(keywords, report_type, max_items=3)`
- `select_entries` 是纯打分排序（无 LLM），延迟可忽略
- `plan()` 输出新增 `dim_kb_map` 字段

### 2.2 section_writer.py（+45 行）

```
self._dim_kb_map = data_context["_dim_kb_map"]  # write() 入口读取

_mkb_for_group(dims) → str
    # 按组维度过滤 dim_kb_map，去重，格式化为 prompt 块
    # dim_kb_map 为空时返回 ""（回退到全局 mkb_str）
```

`_write_group` 内：
```python
_group_mkb = self._mkb_for_group(dims)
# ...
_assemble_data_injection_tail(..., _group_mkb if _group_mkb else mkb_str)
```

### 2.3 e2e_orchestrator.py（+134 行）

**research_plan 节点**：`dim_kb_map` 写入 `collected_data["_dim_kb_map"]`

**rewrite_sections** 新增 Delta-Only Rewrite：
```python
_failed_dims = _locate_failed_dims(gate_feedback, review_comments, context)
_dim_kb_hints = _build_dim_kb_hints(_failed_dims, context)
# rewrite_prompt += f"\n## 失败维度的参考证据\n{_dim_kb_hints}\n"
```

新增两个辅助函数：
- `_locate_failed_dims(gf, rc, ctx)` — 三重匹配：`[DIM:xxx]` 标记 + 中文关键词 + context 显式标注
- `_build_dim_kb_hints(failed_dims, ctx)` — 从 `dim_kb_map` 查对应 MKB 条目，格式化为证据块

### 2.4 tests/test_evidence_grounded.py（11 个测试）

| 测试类 | 覆盖 |
|---|---|
| `TestLocateFailedDims` | DIM 标记 / 中文关键词 / 显式标注 / 组合 / 空输入 |
| `TestBuildDimKBHints` | 有 map / 无 map / 空 failed_dims |
| `TestBuildDimKBMap` | 正常 / 空 dims |
| `TestPlanOutputHasDimKBMap` | plan() 输出含 dim_kb_map |

---

## 三、数据流

```
research_plan 节点
  ├→ question_tree_v2: 每维度 2 个研究问题
  └→ _build_dim_kb_map: 每维度 3 条 MKB 条目
       ↓ 写入 collected_data["_dim_kb_map"]

write_sections 节点
  └→ _write_dimension_parallel
       └→ _write_group (每组)
            ├→ dims = group["dimensions"]
            ├→ _group_mkb = self._mkb_for_group(dims)  ← 只取该组维度的 MKB
            └→ prompt += _assemble_data_injection_tail(..., _group_mkb)

Gate 检查
  └→ kb_citation_coverage: 引用覆盖（不变）

rewrite_sections 节点（attempt > 0）
  ├→ _locate_failed_dims: 提取失败维度 ID
  ├→ _build_dim_kb_hints: 查 dim_kb_map → 精准证据块
  └→ rewrite_prompt += "\n## 失败维度的参考证据\n{hints}\n"
```

---

## 四、向后兼容

| 场景 | 行为 |
|---|---|
| `dim_kb_map` 为空（老 pipeline 不生成） | `_mkb_for_group` 返回 `""` → 用全局 `mkb_str`（原逻辑） |
| `_locate_failed_dims` 提取不到维度 | `_dim_kb_hints` 为 `""` → rewrite prompt 不加证据块（原逻辑） |
| `select_entries` 导入失败 | `_build_dim_kb_map` 返回 `{}` → 不影响 planner 输出 |

---

## 五、验证结果

```
11 passed in 0.57s (test_evidence_grounded.py)
27 passed in 0.56s (test_evidence_grounded.py + test_claim_citation.py)
12 passed in 0.63s (test_agent_graph_contract.py + test_argument_node_contract.py)
```

3 个模块导入正常：
```
research_planner OK
e2e_orchestrator OK
section_writer OK
```

---

## 六、未验证 / 风险

| 项目 | 状态 | 下一步 |
|---|---|---|
| 端到端 smoke test | ⚠️ 未跑 | 需要 `DEEPSEEK_API_KEY` + 网络环境 |
| `_mkb_for_group` 的 `_format_entry` 调用 | ⚠️ 依赖 `methodology_kb._format_entry` 内部函数 | 若该函数签名变化需同步 |
| `_DIM_MKB_KEYWORDS` 覆盖度 | ⚠️ 20 个维度关键词为人工定义 | 新增 SAC 维度时需补充 |
| rewrite 后 KB 引用质量 | ⚠️ 未做 A/B 对比 | 需要 Gate score 对比数据 |

---

## 七、与质量-速度总纲的对应

| 总纲条目 | 本次实现 |
|---|---|
| 门禁④ 方法论应用深度 | ✅ 首阶段：按维度精准注入 MKB 条目（证据整合） |
| A-track 零语义风险 | ✅ 不改 prompt 内容，不改 LLM 参数，不改 Gate 逻辑 |
| B-track 语义风险 | ⚠️ 按维度切 KB 属于 B-track（改变模型看到什么），需 A/B 验证 |
| cascade 反转 | 🔲 未实现（草稿降档 + 审稿强模型） |
| 交错扇出缓存命中 | 🔲 未实现 |
