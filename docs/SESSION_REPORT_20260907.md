# 二号分析师（2hao-analyst）— 会话总结报告

**日期**：2026-09-07
**会话周期**：知识保留率审计 → KB 间隙闭环 → Pipeline 加速分析 → Evidence-Grounded Writing 交付
**代码仓库**：`D:\Claude\projects\2hao-analyst`（remote: `github.com/abdielchou-rgb/analysis.git`）

---

## 〇、一句话

本次会话从"24 个引擎方法论注入器 100% 空转"的审计发现出发，完成了数据层修复、KB 全链路可观测、Pipeline 加速分析（7 份文档）、管线超时/Profiling/墙钟预算三项止血，最终交付 **Evidence-Grounded Writing + Delta-Only Rewrite**——把 KB 注入从"全量盲注"升级到"按维度精准匹配"，把 rewrite 从"全文重写"升级到"失败维度精准修复"。

---

## 一、完成清单

### 阶段 A：数据层修复（已提交）

| # | 问题 | 根因 | 修复 | Commit |
|---|---|---|---|---|
| A1 | 引擎计算结果到不了报告正文 | `compute_results` 在 context 顶层，`write_sections` 只传 `collected_data` | 并入 `_write_dc` | `3160714` |
| A2 | DCF current_price=0.0 触发 pydantic 校验失败 | `gt=0` 不允许 0.0 | 改为 `None` | `3160714` |
| A3 | scenario base_price=None 触发 Optional 校验 | `base_price` 非 Optional | 改为 `None or 0.0` | `3160714` |

**验证**：engine_ib ok，fair_value=1571.39，IronGate 0.85，172 tests passing。

### 阶段 B：KB 全链路可观测（已提交）

| # | 问题 | 修复 | Commit |
|---|---|---|---|
| B1 | 行业标签不统一（5 个注入器各自只读 biz_model） | `_industry_tags_for()` 统一回退链 | `78379e4` |
| B2 | P1-3 注入观测在 except 内（静默死代码） | 移到成功路径 | `78379e4` |
| B3 | KB/MKB 检索到但注入量为零时 Gate 弱检查 | 注入前记录 `retrieved_count`，双通道诊断 | `5a6b97e` |

**验证**：224 tests passing。

### 阶段 C：Pipeline 加速分析（7 份文档）

| 文档 | 核心结论 |
|---|---|
| `PIPELINE_ACCELERATION_ANALYSIS_20260907.md` | 原始 10-cut：131s→59s，54.9% 提速（理论上限） |
| `PIPELINE_ACCELERATION_HONEST_ASSESSMENT_20260907.md` | 诚实评估：真正"加速"的只有 P0-1a 超时（+ semaphore + 稳定前缀） |
| `PIPELINE_ACCELERATION_UPGRADED_20260907.md` | 升级 5-cut：分层超时 + 全局并发闸 + 稳定前缀 + 级联熔断 + Gate 反馈 |
| `PIPELINE_ACCELERATION_BEYOND_UPGRADED_20260907.md` | Prompt caching 是 ROI 最高的优化 |
| `PIPELINE_ACCELERATION_CACHE_REVISED_20260907.md` | DeepSeek 缓存经济学修正（strict prefix match，30-120x） |
| `PIPELINE_ACCELERATION_BEYOND_CACHE_REVISED_20260907.md` | 三种缓存持久化路径 + 交错扇出 |
| `QUALITY_SPEED_MASTER_20260907.md` | 质量-速度双层框架（质量四门禁 + 速度零语义风险分类） |

### 阶段 D：管线止血（已提交）

| # | 修复 | Commit |
|---|---|---|
| D1 | P0-1a：`call_llm`/`call_deepseek` 新增 `timeout` 参数；`_llm_generate_questions` 30s 超时 + `fallback_count` | `e63375f` |
| D2 | P0-2a：`[SELF-HEAL][PROFILE]` / `[VALIDATE][PROFILE]` / `[DATA][PROFILE]` / `[RECORD][PROFILE]` 子步骤计时 | `e63375f` |
| D3 | P0-3：`settings.py` 新增 `data/validate/record_node_budget_s()`；`AgentGraph` 新增 `node_timeout_s` + `future.result(timeout)` | `e63375f` |

### 阶段 E：Evidence-Grounded Writing + Delta-Only Rewrite（本次核心交付，未提交）

| 文件 | 改动 | 行数 |
|---|---|---|
| `pipeline/research_planner.py` | `_DIM_MKB_KEYWORDS`（20 个维度→关键词）、`_build_dim_kb_map()`、`plan()` 输出 `dim_kb_map` | +57 |
| `pipeline/section_writer.py` | `write()` 读取 `_dim_kb_map`、`_mkb_for_group()` 按组过滤、`_write_group` 用 `_group_mkb` | +45 |
| `pipeline/e2e_orchestrator.py` | `dim_kb_map` 入 `collected_data`；`rewrite_sections` Delta-Only Rewrite；`_locate_failed_dims()` + `_build_dim_kb_hints()` | +134 |
| `tests/test_evidence_grounded.py` | 11 个测试用例（locate_failed_dims / build_dim_kb_hints / build_dim_kb_map / plan output） | +167 |

---

## 二、Evidence-Grounded Writing 架构

### 2.1 问题

```
之前：
  planner → question_tree（每维度 2 个问题，无 KB 映射）
  writer  → _inj_mkb_str() 检索 8 条 MKB → 全量塞进每组 prompt
  rewrite → 20K 全文 + 审稿意见 → LLM 重写全文

后果：
  估值组拿到 ESG 条目，ESG 组拿到 DCF 条目（证据错配）
  LLM 改了不该改的段、丢了数据标注（rewrite 失控）
  Gate 无法归因"哪条 KB 被哪段正文引用"
```

### 2.2 解法

```
之后：
  planner → _build_dim_kb_map: 每维度 3 条 MKB（select_entries 纯打分，无 LLM）
  writer  → _mkb_for_group(dims): 只取该组维度的 MKB 条目
  rewrite → _locate_failed_dims → _build_dim_kb_hints → 只给失败维度的 KB 证据
```

### 2.3 数据流

```
research_plan 节点
  ├→ question_tree_v2: 每维度 2 个研究问题
  └→ _build_dim_kb_map: 每维度 3 条 MKB 条目
       ↓ 写入 collected_data["_dim_kb_map"]

write_sections 节点
  └→ _write_dimension_parallel
       └→ _write_group (每组)
            ├→ dims = group["dimensions"]
            ├→ _group_mkb = self._mkb_for_group(dims)
            └→ prompt += _assemble_data_injection_tail(..., _group_mkb)

Gate 检查
  └→ kb_citation_coverage: 引用覆盖（不变）

rewrite_sections 节点（attempt > 0）
  ├→ _locate_failed_dims: 提取失败维度 ID
  ├→ _build_dim_kb_hints: 查 dim_kb_map → 精准证据块
  └→ rewrite_prompt += "\n## 失败维度的参考证据\n{hints}\n"
```

### 2.4 向后兼容

| 场景 | 行为 |
|---|---|
| `dim_kb_map` 为空 | `_mkb_for_group` 返回 `""` → 用全局 `mkb_str`（原逻辑） |
| `_locate_failed_dims` 提取不到维度 | `_dim_kb_hints` 为 `""` → rewrite 不加证据块（原逻辑） |
| `select_entries` 导入失败 | `_build_dim_kb_map` 返回 `{}` → 不影响 planner |

### 2.5 验证

```
test_evidence_grounded.py        11 passed  0.57s
test_claim_citation.py           16 passed  0.56s
test_agent_graph_contract.py      5 passed  0.63s
test_argument_node_contract.py    7 passed  0.63s
```

---

## 三、与质量-速度总纲的对应

| 总纲条目 | 状态 | 对应交付 |
|---|---|---|
| 门禁① SAC 维度覆盖 | ✅ 已有 | IronGate `_check_sac_coverage` |
| 门禁② 来源标注 | ✅ 已有 | `_check_evidence_layer` / `_check_inline_citations` |
| 门禁③ KB/方法论引用覆盖 | ✅ 已有 | `kb_citation_coverage`（阶段 B 补齐 retrieved 漏斗） |
| 门禁④ 方法论应用深度 | ✅ 首阶段 | **Evidence-Grounded Writing**（按维度精准注入 MKB） |
| A-track 零语义风险 | ✅ | 不改 prompt 内容 / 不改 LLM 参数 / 不改 Gate 逻辑 |
| B-track 语义风险 | ⚠️ 待 A/B | 按维度切 KB 改变了模型看到什么 |
| cascade 反转 | 🔲 未实现 | 草稿降档 + 审稿强模型 |
| 交错扇出缓存命中 | 🔲 未实现 | 三种持久化路径 |

---

## 四、风险与未验证项

| 项目 | 状态 | 下一步 |
|---|---|---|
| 端到端 smoke test | ⚠️ 未跑 | 需 `DEEPSEEK_API_KEY` + 网络环境 |
| `_format_entry` 内部函数依赖 | ⚠️ 签名变化需同步 | 关注 `methodology_kb.py` 变更 |
| `_DIM_MKB_KEYWORDS` 覆盖度 | ⚠️ 20 个维度人工定义 | 新增 SAC 维度时补充 |
| rewrite 后 KB 引用质量 A/B | ⚠️ 未做 | 需 Gate score 对比数据 |
| `test_r78_data_contract.py` | ❌ pre-existing | `validate_chart_data` 导入缺失，非本次引入 |

---

## 五、文件变更总览

### 已提交（4 commits）

```
e63375f perf(pipeline): P0-1a/P0-2a/P0-3 管线加速审计修正
5a6b97e fix(kb): KB retrieved 漏斗补全
78379e4 feat(kb): P0-P2 全量推进——行业标签回退链 + cited 去重 + retrieved 漏斗
3160714 feat(data): eastmoney-direct collector + price-less DCF tolerance
```

### 未提交（Evidence-Grounded Writing）

```
M  pipeline/e2e_orchestrator.py    +134
M  pipeline/research_planner.py     +57
M  pipeline/section_writer.py       +45
A  tests/test_evidence_grounded.py +167
```

### 本次产出的文档

```
docs/WORK_SUMMARY_20260907.md
docs/EVIDENCE_GROUNDED_CLOSURE_20260907.md
docs/QUALITY_SPEED_MASTER_20260907.md
docs/PIPELINE_ACCELERATION_ANALYSIS_20260907.md
docs/PIPELINE_ACCELERATION_HONEST_ASSESSMENT_20260907.md
docs/PIPELINE_ACCELERATION_UPGRADED_20260907.md
docs/PIPELINE_ACCELERATION_BEYOND_UPGRADED_20260907.md
docs/PIPELINE_ACCELERATION_CACHE_REVISED_20260907.md
docs/PIPELINE_ACCELERATION_BEYOND_CACHE_REVISED_20260907.md
```

---

## 六、下一步

1. **提交** Evidence-Grounded Writing + Delta-Only Rewrite
2. **Smoke test**：跑一次完整 e2e pipeline 验证端到端效果
3. **质量门升级**：门禁④ 从"框架名出现"升级到"框架间交叉验证"（矛盾覆盖率）
4. **B-track 加速**：cascade 反转（草稿降档）+ 交错扇出缓存命中
5. **证据密度指标**：正文数据点/段落 ≥3，量化结论占比 ≥60%
