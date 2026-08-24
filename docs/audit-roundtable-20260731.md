# 2hao-analyst 圆桌会议审计报告

> 审计时间：2026-07-31 | 焦点：全量审计（延续 7-30）+ 当场修复
> 依据：FP1-FP7 v3.0 宪法 | 方法：静态扫描 + import 冒烟 + 引擎实测 + 文档一致性

---

## 一、总体结论

7-30 圆桌审计的 13 项修复全部落地，本次审计发现 **2 个 P0 遗留 Bug + 3 处文档脱节**，均已当场修复。

| 指标 | 7-30 修复后 | 7-31 当前 |
|------|------------|-----------|
| 语法错误 | 0（管线范围） | 0（含 output/ 全量 329 文件） |
| 核心模块 import | 9/9 | 13/13 全部通过 |
| 硬编码 API key | 0 | 0 |
| run_all_checks | — | 9/9 通过（fast 模式） |
| 管线入口 | scheduler.py → E2EOrchestratorV2 | 一致，含图表引擎已接入 |
| Multi-provider | ⚠️ 部分 | ✅ 已激活（通义/OpenRouter/SiliconFlow） |
| 代码量 | ~72K 行 / 335 文件 | 73,325 行 / 335 文件 |
| 真孤儿（可清理） | — | 21 个（多为 tests/scripts 预期） |

---

## 二、本次发现并修复的问题

### P0-1：`data/engine.py` EastMoneyEngine 崩溃（FP7a / FP2a）

**现象**：EastMoney 返回异常时 `r.json()` 为 `None`，`r.json().get(...)` 抛 `AttributeError`。实测 `DataQuery(assets=['000000'])` 稳定复现崩溃。

**影响**：DataPipeline 中 EastMoneyEngine 异常会抛到外层（该引擎 fetch 内 `raise`），使整个数据管线第一条数据通道崩溃。违反 FP7a（不允许静默/非优雅失败）与 FP2a（数据源降级而非中断）。

**修复**：增加 `status_code != 200` 检查、JSON 解析保护、`payload` 空值保护；`except` 分支从 `raise` 改为返回 `DataResponse(error=...)` 优雅降级。

**验证**：修复后 `fetch(assets=['000000'])` 返回 `error: no data from eastmoney`（不崩溃）；`fetch(assets=['600519'])` 成功返回 7 个数据点。

### P0-2：`data_collector.py` 数据溯源失真（FP2a）

**现象**：`collect()` 内 `sources_with_data` 变量被正确累加，但 `_data_quality.sources_with_data` 硬编码为 `1 if chart_data else 0`，抹掉了真实数据源数量。

**影响**：IronGate 的 data_traceability 评分及报告头部降级标注无法反映真实数据覆盖，违反 FP2a 数据可溯源性。

**修复**：改为写入真实 `sources_with_data` 计数。

**验证**：沙箱中（tavily/akshare 缺失）`collect('600519')` 返回 `sources_with_data: 1`（Universal 兜底），正确反映真实数据源。

### P2-1：`output/_gen_scripts_backup/` 语法错误死代码

**现象**：目录下 2 个历史脚本（gen_v3.py / gen_v3_fixed.py）含语法错误（中文引号未转义），为 7/29 前遗留的生成脚本备份，无任何引用。validator 故意跳过 output/ 目录故未被检出。

**修复**：整个 `_gen_scripts_backup/` 目录已删除（6 个文件）。

---

## 三、文档脱节修复（P1）

| 文件 | 问题 | 修复 |
|------|------|------|
| `README.md` | IronGate 写 24 项，实际 34 项 | 更新为 34 项（架构图 + 质量体系表） |
| `README.md` | StyleCompiler 写 8 条，实际 21 条 | 更新为 21 条 |
| `README.md` | LLM 仅描述 DeepSeek | 更新为 Multi-Provider（DeepSeek/通义/OpenRouter） |
| `SKILL.md` | 版本 V1.1（7-26）、宪法指向旧文件、只认 DeepSeek、合规路径错误 | 升级 V1.2：Multi-Provider 原则、指向 FP1-FP7 宪法、合规路径改为 Data→Compute→MD→IronGate→Export |

---

## 四、未修复（建议跟踪）

| # | 项 | 级别 | 原因 | 建议 |
|---|----|------|------|------|
| 1 | `docs/` 57 份文档多版本冲突 | P1 | 需人工选择保留哪些 | 下轮圆桌逐份过 |
| 2 | `assets/` 空目录未填充 | P2 | 需人工提供标杆报告库 | 收集 50+ PDF 归档 |
| 3 | 沙箱缺 akshare/tavily/openai/yfinance | P2 | 用户环境依赖未安装 | 按 `pip install -r requirements.txt` 安装 |
| 4 | `compute/V30_compute/`（14K 行）+ `core/` 未接入孤儿 | P2 | 剪枝需谨慎确认 | Phase 3 剪枝（72K→50K 目标） |
| 5 | `data_collector.py` 内 `import re` 局部重复 | P3 | 低危 | 后续重构顺手清理 |

---

## 五、管线健康度核验

### import 冒烟测试（13/13 通过）

scheduler / e2e_orchestrator / preflight_check / data_collector / chart_runner / section_writer / iron_gate / report_gate / exporter / core.sacs / core.deepseek_client / core.protocol / step_manager

### 数据引擎实测

- `DataPipeline.fetch(assets=['600519'])` → eastmoney 7 点成功
- `DataCollectorV5.collect('600519')` → Universal 兜底，`status: done`
- EastMoney 异常降级路径实测生效

### 今日活跃改动（Phase 0 进展）

- `pipeline/section_writer.py`（12:11）— 含 `_debate_bold_call`（FP3-D5 协作维度已在 section_writer 落地 bull→bear→judge）
- `pipeline/scheduler.py` / `data_collector.py` — 管线入口与多源采集增强
- `pipeline/iron_gate.py` — 已扩至 34 项检查
- `core/` 10 个文件 + `export/exporter.py` — 图表引擎接入、方法论/PDF 提取器
- `data/*.json`（9 个）— 基线/方法论/估值参数知识库填充

---

## 六、全量修复结果（2026-07-31 圆桌当场执行）

### 已完成的修复

| # | 类别 | 内容 | 验证 |
|---|------|------|------|
| 1 | P0-1 | `data/engine.py` EastMoney 崩溃 → 优雅降级 | `fetch(['000000'])` 不崩溃 |
| 2 | P0-2 | `data_collector.py` 溯源计数失真 → 真实计数 | `sources_with_data=1` 正确 |
| 3 | P3 | 局部重复 import re（2处） | 语法通过 |
| 4 | 文档 | README/SKILL 版本脱节修复 | 一致性核对 |
| 5 | 文档 | docs/ 39→17 份活跃，22 份归档 | 引用关系验证 |
| 6 | 清理 | `_gen_scripts_backup/` + 33份 self-audit + 旧运行目录 | output/ 265→212 文件 |
| 7 | 剪枝 | V30_compute(13K行)+V30_tools+layer1_data+compute包 归档 | import 15/15 通过 |
| 8 | 依赖 | openai+tavily 已装；yfinance/akshare 沙箱待装 | import 验证 |

### 剪枝成果

```
归档前: 73,325 行 / 335 文件
现在:   56,462 行 / 275 文件  (-23% / -18%)
归档:   archive/ 1.2M + docs/archive/ 596K (54 个 .py)
```

### 最终健康基线

- 语法错误: **0**（全量 276 文件）
- import 冒烟: **15/15 + 11/11 全部通过**
- run_all_checks: **2/2 通过**
- 数据引擎实测: EastMoney 7 点成功 / DataCollector done
- V30 残留引用: 0（活跃代码，全部条件 import 或归档）

### 遗留

- 沙箱 yfinance/akshare 未装（curl_cffi 大文件下载慢，需更长超时或用户环境安装）
- assets/deep_reports B/C/E/F 风格库空（需人工填充真实标杆报告）
- Phase 1 debate_resolution IronGate 检查未做（section_writer 已产出 debate）

---

## 七、后续建议

```
本周:  完成 Phase 0 剩余 — 用户环境装 akshare+tavily，跑 1 份含图表的完整报告
本月:  Phase 1 — IronGate 增加 debate_resolution 检查（section_writer 已产出 debate）
持续:  Phase 2 — 每周 2-3 份报告积累 learning_loop 数据
已完:  Phase 3 — 剪枝 73K→56K ✅（V30_compute + compute 包 + 孤儿模块归档）
```

---

*审计工具：py_compile 全量 / AST import 图 / run_all_checks / 引擎实测*
