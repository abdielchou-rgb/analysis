# Evidence-Grounded Writing — 执行手册

**日期**：2026-09-07
**前置文档**：`QUALITY_SPEED_MASTER_20260907.md`、`EVIDENCE_GROUNDED_CLOSURE_20260907.md`
**性质**：从代码交付到生产验证的完整执行清单。

---

## 〇、执行前提

| 条件 | 状态 |
|---|---|
| 代码修改完成（3 modified + 1 new test） | ✅ |
| 单元测试通过（11 新 + 27 已有） | ✅ |
| 模块导入正常 | ✅ |
| `DEEPSEEK_API_KEY` 可用 | ⚠️ 需确认 |
| 网络环境（eastmoney / tencent / deepseek） | ⚠️ 需确认 |

---

## 一、提交代码

```bash
cd D:\Claude\projects\2hao-analyst

# 1. 查看变更
git status --short
git diff --stat HEAD

# 2. 暂存（不含 kb_fts.db / .bak 文件）
git add pipeline/research_planner.py
git add pipeline/section_writer.py
git add pipeline/e2e_orchestrator.py
git add tests/test_evidence_grounded.py
git add docs/EVIDENCE_GROUNDED_CLOSURE_20260907.md
git add docs/EVIDENCE_GROUNDED_EXECUTE_20260907.md
git add docs/SESSION_REPORT_20260907.md
git add docs/WORK_SUMMARY_20260907.md

# 3. 提交
git commit -m "feat(evidence): Evidence-Grounded Writing + Delta-Only Rewrite

- planner: _build_dim_kb_map() 每维度预检索 MKB 条目
- writer: _mkb_for_group() 按组维度过滤 MKB（替代全量盲注）
- rewriter: _locate_failed_dims + _build_dim_kb_hints 精准证据注入
- tests: 11 个新测试用例
- docs: 闭环文档 + 执行手册"

# 4. 推送
git push origin main
```

**验证**：`git log --oneline -1` 确认 commit hash。

---

## 二、Smoke Test（端到端验证）

### 2.1 最小冒烟（单报告）

```bash
cd D:\Claude\projects\2hao-analyst

# earnings_notes 最快（8-12 分钟）
& ".venv\Scripts\python.exe" -u main.py "宁德时代" --type earnings_notes --style cicc --output test_output
```

**检查项**：

| 检查 | 预期 | 如何验证 |
|---|---|---|
| 管线跑完不报错 | exit code 0 | 终端输出 |
| Gate 通过 | gate_score ≥ 0.55 | 日志 `[GATE] score=0.xx` |
| 报告正文含 KB 引用 | 正文出现 `[MKB` 标记 | `Select-String -Path output\*宁德时代*.md -Pattern "\[MKB"` |
| dim_kb_map 注入 | 日志出现 `[DIM-PARALLEL] 写组` | 日志 |
| rewrite 证据块注入 | attempt > 0 时日志出现 `failed_dims=` | 日志 |

### 2.2 多类型验证

```bash
# industry_deep（15-20 分钟）
& ".venv\Scripts\python.exe" -u main.py "半导体" --type industry_deep --style cicc --output test_output

# listed_company（15-20 分钟）
& ".venv\Scripts\python.exe" -u main.py "贵州茅台" --type listed_company --style cicc --output test_output
```

### 2.3 失败场景验证（Delta-Only Rewrite）

故意制造一次 Gate 失败（attempt > 0），验证 rewrite 路径：

```bash
# 设置 MAX_ATTEMPTS=2 强制触发 rewrite
$env:MAX_ATTEMPTS='2'
& ".venv\Scripts\python.exe" -u main.py "宁德时代" --type earnings_notes --style cicc --output test_output
```

**检查项**：

| 检查 | 预期 | 如何验证 |
|---|---|---|
| attempt 1 rewrite 触发 | 日志 `[REWRITE] failed_dims=` | 日志 |
| rewrite 后报告长度 | ≥ 原报告 50% | 对比字符数 |
| rewrite 后 Gate 分数 | ≥ attempt 0 分数 | 对比 gate_score |

---

## 三、质量-速度五元组基线

按 `QUALITY_SPEED_MASTER_20260907.md` §四，跑 5 份代表报告，记录五元组：

```bash
# 跑 5 份报告（每个类型一份）
& ".venv\Scripts\python.exe" -u main.py "宁德时代" --type earnings_notes --style cicc --output benchmark
& ".venv\Scripts\python.exe" -u main.py "半导体" --type industry_deep --style cicc --output benchmark
& ".venv\Scripts\python.exe" -u main.py "贵州茅台" --type listed_company --style cicc --output benchmark
& ".venv\Scripts\python.exe" -u main.py "字节跳动" --type unlisted_company --style mck --output benchmark
& ".venv\Scripts\python.exe" -u main.py "中芯国际" --type decision_memo --style cicc --output benchmark
```

**五元组记录表**（每份报告填一行）：

```
| 报告 | gate_score | kb_citation_cov | methodology_application | report_cost | report_wallclock |
|------|-----------|----------------|------------------------|-------------|-----------------|
|      |           |                |                        |             |                 |
```

**基线对比**：与 Evidence-Grounded Writing 之前的基线对比（如有），确认：
- `gate_score` 不劣化（持平或提升）
- `kb_citation_cov` 提升（精准注入 → 引用率上升）
- `methodology_application` 提升（框架结论出现率上升）
- `report_cost` 持平或下降（MKB 条目减少 → token 减少）
- `report_wallclock` 持平或下降（MKB 条目减少 → 生成速度不变或加快）

---

## 四、回滚方案

如 Evidence-Grounded Writing 引入问题，回滚步骤：

```bash
# 回滚代码（保留文档）
git revert HEAD

# 或手动回滚单个文件
git checkout HEAD~1 -- pipeline/research_planner.py
git checkout HEAD~1 -- pipeline/section_writer.py
git checkout HEAD~1 -- pipeline/e2e_orchestrator.py
```

**回滚触发条件**：

| 条件 | 动作 |
|---|---|
| 管线报错（exit code ≠ 0） | 立即回滚 |
| Gate 分数下降 > 0.1 | 回滚 + 排查 |
| rewrite 后报告长度 < 原 50% | 回滚 + 排查 |
| `_format_entry` 签名变化导致异常 | 同步修复或回滚 |

---

## 五、监控指标

部署后持续监控：

### 5.1 日志关键词

```bash
# 正常路径
Select-String -Path logs\*.log -Pattern "\[DIM-PARALLEL\] 写组"
Select-String -Path logs\*.log -Pattern "dim_kb_map"
Select-String -Path logs\*.log -Pattern "failed_dims="

# 异常路径
Select-String -Path logs\*.log -Pattern "KB-MKB.*FAILED"
Select-String -Path logs\*.log -Pattern "REWRITE.*failed"
Select-String -Path logs\*.log -Pattern "DIM-COVERAGE"
```

### 5.2 关键指标

| 指标 | 正常范围 | 告警阈值 |
|---|---|---|
| `dim_kb_map` 维度数 | ≥ 10 | < 5（关键词覆盖不足） |
| `_mkb_for_group` 输出长度 | 200-2000 字符 | 0（回退全局） |
| rewrite `failed_dims` 数 | 1-5 个 | 0（未提取到）或 > 10（关键词过宽） |
| Gate 通过率 | ≥ 80% | < 60% |

---

## 六、后续迭代

| 优先级 | 项目 | 依赖 |
|---|---|---|
| P0 | 提交代码 + smoke test | DEEPSEEK_API_KEY |
| P1 | 五元组基线记录 | 5 份报告跑完 |
| P1 | `_DIM_MKB_KEYWORDS` 补全（新 SAC 维度） | SAC YAML 变更 |
| P2 | 方法论应用深度门禁（框架间交叉验证） | 五元组基线 |
| P2 | cascade 反转 A/B（草稿降档） | 五元组基线 |
| P3 | 交错扇出缓存命中 | DeepSeek 缓存可用 |

---

## 七、执行 checklist

```
[ ] 1. 提交代码（git add + commit + push）
[ ] 2. Smoke test: earnings_notes（宁德时代）
[ ] 3. Smoke test: industry_deep（半导体）
[ ] 4. Smoke test: listed_company（贵州茅台）
[ ] 5. Delta-Only Rewrite 验证（MAX_ATTEMPTS=2）
[ ] 6. 五元组基线记录（5 份报告）
[ ] 7. 日志监控确认
[ ] 8. 回滚方案验证（git revert dry-run）
[ ] 9. 更新 AGENTS.md / CLAUDE.md（如需）
[ ] 10. 标记完成
```
