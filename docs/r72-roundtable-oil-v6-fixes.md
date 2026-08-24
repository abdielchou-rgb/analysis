# R72 油位传感器 v6 圆桌审计 + P0/P1 全量修复

> 审计主席：2hao-analyst (R70 全模块接线完成态视角)
> 审计对象：`D:\Marvis\output\oil_level_v6_final`（SAC 26/26，25272字，v1→v6 多轮手动打磨）
> 实施日期：2026-08-05

## 一句话

**油位 v6 表面 95 分（26/26 SAC 覆盖、13 图、8 表、0 禁止词），圆桌审计揭示 3 类沉默缺陷 + 14/26 维度为软覆盖。综合得分 80/100。根因触发 3 项管线修复全部落地。**

---

## 一、审计核心发现（3 类沉默缺陷）

### 缺陷 1：模板句重复（dim-parallel 合并引擎的把合变成了拼合）

4 类同义模板句各出现 2-4 次，同一意思用不同措辞重复：

| 模板 | 次数 | 根因 |
|------|------|------|
| 「后续…将成为验证这一判断的关键观测点」 | 4 | 各组并行写，合并编辑只拼接未去重 |
| 「上述变化对盈利预测的传导…」 | 3 | R54 语义重复检测查逐字重复，不查同义变体 |
| 「在此背景下…」 | 多处 | 合并 LLM prompt 无"避免同义重复"约束 |

### 缺陷 2：催化剂日历截断至 1 行

SAC capital_market 要求"3/6/12 个月事件驱动"4 季度时间轴，v6 只写了 1 行 2026Q3。

### 缺陷 3：R42 修复的 AI 免责声明在手动路径复活

v6 末尾 `*（内容由AI生成，仅供参考）*` —— 管线 export 链路拦截了，但 Marvis 手动补修绕过了管线。R42 修复判定不完整——修复目标不是"管线的出口链路删掉"，而是"报告正文无论通过什么路径产出都不能含免责声明"。

---

## 二、SAC 覆盖真相：14/26 维度为软覆盖

| 覆盖级别 | 数量 | 代表维度 |
|---------|------|---------|
| 硬覆盖（有数据+判断+So What） | 12 | market_size, life_cycle, competitive, policy, profit_pool |
| 软覆盖（关键词命中无实质） | 14 | capital_market(缺双击/赔率/均值回归), elasticity(只IED缺PED/PES/XED), esg_materiality(0处命中), peer_benchmarking, global_market_sizing, signal_chain(缺滞后指标), investable_standouts, industry_consolidation, geopolitics, core_hypothesis, falsification(只1条), decision_gate(3门缺2门), unlisted_players(9家仅图表), catalyst(截断) |

---

## 三、已落地 3 项修复

### R72-1：P0 禁AI免责声明硬拦截

| 文件 | 行 | 变更 |
|------|-----|------|
| `pipeline/checks/content_format_mixin.py` | 484 | 白名单豁免 → 硬拦截 |

此前 `_check_forbidden_patterns` 把 "内容由AI生成，仅供参考" 从文本中删除后再扫描——等于白名单豁免。现在改为：**如果检测到该免责声明，直接 FAIL（score=0.0）**，无论通过什么路径产出。

### R72-2：P0 ESG实质性议题注入模块

此前 SAC 行业深度/unlisted 均有 `esg_materiality` 维度但 section_writer **完全无任何注入函数**。新建 `esg_str` 注入：环境/社会/治理三层提示 + GRI/SASB/TCFD 对标 + 估值影响判断。

| 变更 | 文件 |
|------|------|
| `esg_str` 注入块（+15 行） | `pipeline/section_writer.py` |
| prompt 接线 | `pipeline/section_writer.py` 组级 prompt 模板 |

### R72-3：P1 催化剂日历结构最低要求

在 `cat_str` 产出后追加结构化提示：

```
[催化剂日历结构要求] 必须覆盖未来4个季度（2026Q3/Q4/2027Q1/Q2），
每季度至少1条可验证事件。若某季度无可查事件，标注'暂无确定催化剂'而非跳过该季度。
```

| 变更 | 文件 |
|------|------|
| `cat_str` 追加结构要求（+5 行） | `pipeline/section_writer.py` |

---

## 四、变更全览

| 文件 | 行数变化 | 新增内容 |
|------|---------|---------|
| `pipeline/section_writer.py` | 2055→2083 | esg_str 注入块 + 催化剂日历结构要求 |
| `pipeline/checks/content_format_mixin.py` | 583→588 | R72 硬拦截逻辑 |

---

## 五、综合评分 vs 自评

| 维度 | 自评 | 圆桌审计 |
|------|------|---------|
| 数据完整度 | 10/10 | 9/10（13图表OK，催化剂截断-1） |
| SAC 覆盖 | 26/26 = 100% | 12/26 硬覆盖（关键词≠实质） |
| 逻辑自洽 | 10/10 | 8/10（内部数据一致OK，但估值章节缺双击/赔率/反DCF） |
| 方法论深度 | — | 7/10（TAM/SAM/SOM/波特好，缺弹性矩阵全维度） |
| 阅读体验 | — | 6/10（模板句重复破坏流畅度） |
| AI 指纹 | 10/10 | 9/10（禁止词OK，免责声明复活-1） |
| **综合** | **85/100** | **80/100** |

偏差来源：自评是表层质检（关键词搜索命中→覆盖），圆桌是深层实质分析（产出内容深度 vs SAC 要求）。

## 六、R68→R72 注入变量演进

| 版本 | 变量数 | 新增变量 |
|------|--------|---------|
| R68 | 18 | 基线 |
| R69 | 18 | logger.debug→warning（零变量新增） |
| R70 | 24 | ma_str, ut_str, us_str, _tm_str, (ma/ut/us 全部 logger.warning) |
| R71 | 26 | di_str, ex_str (均 logger.warning) |
| R72 | 27 | esg_str (logger.warning) |
