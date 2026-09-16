# 2hao-analyst 深度审计 — 顶级思考

**审计日期**：2026-09-14
**审计对象**：`D:\Claude\projects\2hao-analyst`（110k+ 行 Python / 398 个业务模块 / 177 commits / 16 天）
**审计方式**：全量结构扫描 + 死代码分析 + 门禁代码路径追踪 + 产物逆向取证 + git 史考古 + 实机复现
**口径**：所有结论均附可复现证据。凡是我验证后推翻的假设，也在文中标注。

---

## 〇、一句话判断

> **这个项目的分析能力已经达到可交付水准，但它的"验证能力"正在变成它最大的负债——不是因为它验得不够多，而是因为它验的方向是错的：105 项检查里 96% 是"过去故障的黑名单快照"，而 Gate 分数已被证明可以通过改检查器在**同一份报告上**从 0.885 拉到 0.950。**

这不是一个"代码质量差"的项目。恰恰相反，代码规范、注释详尽、测试认真、文档海量。问题在于**它是一个只增不减的系统**：模块只加不删、栈只建不退、文档只写不改。于是出现了同一个能力 2~4 份并行实现、同一个类名指向两个不同语义的类、同一条规则在 prompt 和检查器里各存一份且已经漂移。

---

## 〇-bis、修复记录（2026-09-14 已落地）

审计后立即修复了 5 处 P0。**其中 2 处在修复过程中被修正**——初稿判定不够准确，
深挖后重写了 A1 与 A5。保留修正痕迹，因为它本身是审计可信度的一部分。

| # | 文件 | 改动 | 验证 |
|---|---|---|---|
| 1 | `pipeline/e2e_orchestrator.py:2102` | `gate.get("score", 0)` → `gate.get("overall_score", gate.get("score", 0))`。**这是 A1 的真实根因**：`GateReport.to_dict()` 只有 `overall_score`，故指纹 `gate_score` 恒为 0 | 实机：喂 `overall_score=0.9123` → 指纹写出 `0.9123`（修复前恒为 `0`） |
| 2 | `pipeline/e2e_orchestrator.py:1693` | 预写点 `"gate_passed": True` → `bool(gate.get("passed", False))`。**注：此项非伪造产物**（上游 1643 行已有守卫），改的是消除两写入点未来分叉的风险 | 实机：`gate_passed` 正确透传 |
| 3 | `tests/test_r78_data_contract.py` | 重写。原 import 模块级 `validate_chart_data`/`validate_enrich_item`，但真实实现是 **类** `DataContract().validate_chart_data()`（返回 self，违规在 `.violations`），且 `validate_enrich_item` **从未存在** → 收集期 ImportError → CI 红 | 15 passed；`pytest tests/` 收集期不再报错 |
| 4 | `prompts/system/cicc_analyst.md:32` | 示例 `"国金证券研报测算"` → `"〈机构名〉研报测算"`，并加注禁止在示例中写真实机构名 | 全仓唯一出现处，已消除 |
| 5 | `pipeline/section_writer.py:3484` | 清洗正则 `…\s*分?` → 必须有终止符 `分` 或 `/10`，并加 `(?![%‰])`；替换文本去掉自指的"（见正文论证）" | 实测 8 例：`行业评分85%（B）` 与 `（评分1.0）` **不再被破坏**；`评分10/10`、`评分8分` 仍正确清洗；`公司毛利率 85%（A）` 不误伤 |

**回归**：`pytest tests/test_r78_data_contract.py tests/test_fingerprint_bypass.py
tests/test_export_gate_reuse.py tests/test_golden_numeric.py tests/test_placeholder_hard_block.py`
→ **39 passed, 0 failed**。`py_compile` 三个改动文件 → OK。

**未修（需你决策）**：A3（内部标签泄漏）、A4（反斜杠路径）、A7（同名类冲突）以及第二、三节的全部结构性问题。A3/A4 的正确修法不是加模式，而是换成不变量检查（见第七节 P1-8）。

---

## 〇-ter、第二轮修复（测试基础设施 + 静默失效族，2026-09-14 晚）

第一轮 5 处修完后，为验证 A6（"CI 是红的"）我把**全量测试真的跑了一遍**——
结果暴露出一个更大的问题：**这套测试在修复前根本跑不起来**。而"跑不起来"，
正是项目长期采用"手挑文件"验证协议的真正原因（不是懒，是没法跑）。
本轮共修 8 处（A8–A15）。

### 先看数字

| 指标 | 修复前 | 修复后 |
|---|---|---|
| `pytest tests/ --collect-only` | **>570s（9.5 分钟仍未结束）**，且 1 个收集错误 | **14.1s**，0 错误 |
| 收集到的用例 | 919（且被收集错误截断） | 1178 |
| 全量执行 | **无法完成**（收集阶段即失败） | **1138 passed, 8 skipped, 0 failed, 92s** |

### 根因：收集期在重编译整个 `.venv`

`tests/test_regression.py:178` 在**模块作用域**执行：

```python
root.rglob("*.py")                     # 仓内 10375 个 .py
# 过滤条件只排除 __pycache__ 和 V30_，未排除 .venv
# → 其中 9382 个（90%）来自虚拟环境
py_compile.compile(f, doraise=True)    # 每个都读盘 + 解析 + 写 .pyc
```

三处错误叠加：① 未排除 `.venv`；② 用 `py_compile`（会写 `.pyc`，磁盘 I/O）
而本检查只关心语法；③ **结果只 `print`、从不参与断言**——纯装饰性开销。

第 ③ 点尤其严重：正因为从不失败，它**藏着一个真实的 SyntaxError 而无人知晓**
（见 A13）。

### 本轮修了什么

| # | 文件 | 改动 | 验证 |
|---|---|---|---|
| A8 | `tests/conftest.py:15` | `_ROOT = Path(__file__).resolve().parent`（= `tests/`）→ `.parent.parent`（= 项目根）。**后果一**：`.env` 加载器去找 `tests/.env`（从不存在），函数第一行就 `return` → **`.env` 加载从未生效过**。**后果二**：`sys.path` 只挂 `tests/`，无法 `from tests.x import y`，而 `run_all.py:644` 正是这么写的 | 修复后 `.env` 的 8 个键全部进入 `os.environ`（修复前 **0** 个） |
| A9 | `tests/run_all.py:155` | `CacheEngine().fetch(...)` 包 try/except 降级。它在**模块导入期**抛 `ValueError: DataPoint name: access_ts is required`，让后面约 500 行检查全部跑不到 | 越过该点继续执行（详见 A9-bis） |
| A10 | `pipeline/section_writer.py:208` | `__init__` 补 `self._dim_kb_map = {}`。**本轮最有价值的发现**，见下 | `test_engineering_plan.py` **17 passed**（修复前该用例失败） |
| A11 | `pipeline/checks/analysis_mixin.py:867,911` | `so_what_chain` 在"全部段落被豁免规则过滤掉"时返回 `passed=False, score=0.3` → 改为 `passed=True, score=1.0`。**"不适用"不是"不合格"** | `test_fact_quality.py` **23 passed** |
| A12 | `pyproject.toml` / `requirements.txt` | 补 `python-multipart>=0.0.6`。`web/app.py` 用 `Form(...)`，FastAPI 在**导入期**即要求它 → web 应用根本起不来。原清单声明了 `fastapi` 却漏了它 | 已装入 venv；`test_web_app_import` 通过 |
| A13 | `scripts/last30days/lib/render.py:3450` | `f"{'\\#' * len(hashes)}"` 是 **PEP 701 语法，仅 Python 3.12+ 可解析**；而本项目 `requires-python=">=3.10"`、Dockerfile `python:3.11-slim`、实测 venv 3.11.15 → **该模块在本项目自身运行时下无法导入**。等价改法：把反斜杠字面量提到 f-string 之外 | 实测 `### 注入标题` → `\#\#\# 注入标题`；非标题行不动。**这段"防提示注入"逻辑此前从未生效过** |
| A14 | `tests/test_llm_response_cache.py:48` | 夹具响应体由 6 字符改为 ≥50 字符。`_response_cache_set` 有**防污染门槛**（2026-09-04 加：zhipu 限流期曾把截断响应写入缓存 → 同 prompt 恒返回截断文本 → Gate 恒 0.658），而该测试写于 08-24、早于门槛 → 响应被**正当拒绝** → 缓存永不命中。属"测试未跟随实现演进" | 修复后 `posts=1`、两次内容一致（已独立复现验证，非测试自证） |
| A15 | `core/tools/track_record.py`、`core/prediction_validator.py`、`core/cohort.py`、`core/dashboard.py` | 路径 SSOT 收口，见下 | 见下 |

### A10：fail-open 让一条断掉的链路"看起来是好的"

`SectionWriter._write_dimension_parallel` 的分组写入被包在 `try/except` 里，
异常只留一行 `WARNING [DIM-PARALLEL] group failed`。而 `_mkb_for_group()` 读
`self._dim_kb_map`——该属性**只在 `write()` 里赋值**（第 1069 行），
却漏在 `__init__` 那份兜底清单之外（第 201–208 行，注释明说
"防止 write() 之外被独立调用时 AttributeError"，只是漏了这一个）。

于是：**抛异常 → 被吞 → 该组以"没有方法论知识注入"的降级形态继续写下去**。
报告不报错、不失败，只是内容悄悄变差——`三表勾稽`、`预期差`、`对标矩阵`、
`估值锚` 这些注入全部消失。

这正是本审计第三节所讲"门禁/指标与真实质量脱钩"的**同一个模式**，
只不过这次发生在代码路径上，而不是评分上。

### A15：一个每天空转、且输出与"正常"无法区分的定时任务

同一份 `track_record.json`，仓内存在**两个不同路径**：

- `core/tools/track_record.py`（`TrackRecordManager` 默认解析）、
  `core/cohort.py`、`core/dashboard.py` → `<root>/core/data/forward_picks/track_record.json` ✅ **真实存在**
- `core/prediction_validator.py` → `<root>/data/forward_picks/track_record.json` ❌ **不存在**

`prediction_validator` 是文档中声明的每日定时任务（`python -m core.prediction_validator`），
职责是"用真实行情校验到期预测"。实测：

| | 修复前 | 修复后 |
|---|---|---|
| `storage_path` | `data/forward_picks/track_record.json`（不存在） | `core/data/forward_picks/track_record.json` |
| 读入预测数 | **0** | **2087** |
| `validate_all()` 返回 | `total=0, validated=0, failed=0` | `total=0, validated=0, failed=0` |

**注意最后一行修复前后完全相同**——这正是它长期未被发现的原因：**输入为空**
与**"确实没有到期预测"**的输出一模一样，无法区分。
当前 2087 条预测全部 `pending`、最早（2026-07-31，12m 期限）尚未到期，
所以 `total=0` 这一次是**正当的**；但修复前那个 0 是**因为读不到文件**。
两者不可区分，这就是静默失效的定义。

`core/cohort.py` / `core/dashboard.py` 的默认值同样有问题：它们是**相对路径**
`"core/data/forward_picks/track_record.json"`，解析结果取决于进程 CWD——
只有恰好在项目根启动才指向真实文件，否则 `load_predictions()` **静默返回 `[]`**。
现统一收口到 `core/tools/track_record.default_storage_path()`（单一事实源）。

### A9-bis：`run_all.py` 是历史沉积，不是测试

修掉 A9 的模块级崩溃后，`run_all.py` 继续执行 15s，然后倒在**下一个**真实问题上：

```
ImportError: cannot import name 'EvidenceItem' from 'core.protocol'
```

另有 `compile data/engine.py FILE NOT FOUND`（`data/engine.py` 已不存在）。
该文件 713 行、**零个 `test_` 函数**、不被 pytest 收集
（`python_files=["test_*.py"]`），内部却混着"编译检查 / bare-except 审计 /
数据引擎连通性"三类异质职责。

**建议退役或拆解，而不是继续逐个修 import**——它的每一条检查在 pytest 侧
都有更可靠的对应物。本轮只修掉"导入期即崩"，让崩溃点从**被掩盖的契约违规**
（A9）变成**真实的 import 腐化**——后者至少是诚实的。

### 仍未解决：3 个全图 e2e 用例会永久挂死

全量执行必须排除这 3 个用例，否则整轮 run 会挂死、且**不产出任何 summary**：

| 用例 | 挂死点 |
|---|---|
| `test_e2e_no_network.py::test_core_chain_no_network` | `pipeline/agent_graph.py:210` `_fut.result(timeout=_timeout_s)` |
| `test_e2e_no_network.py::test_enrich_file_injection` | 同上 |
| `test_golden_regression.py::test_golden_regression` | `pipeline/agent_graph.py:409` `as_completed(futures)`（**完全没有 timeout**） |

根因在 `agent_graph.py:203`：

```python
_timeout_s = int(node.get("timeout_s") or 0)
if _timeout_s > 0: ... _fut.result(timeout=_timeout_s)
else: output = node["fn"](node_id, context)   # 只有声明 timeout_s 的节点才有超时
```

即**节点不声明 `timeout_s` 就等于没有任何超时**；声明了的，值又给得很宽
（数百秒），于是在"无网络"测试里会一直阻塞到 `pytest-timeout` 介入——
而它介入后进程被撕掉、**连 summary 都不打印**。

**本轮未修**：这需要先定位到"究竟哪个节点在无网络环境下阻塞"，
属要专门设计的一次改动，不宜在审计里顺手改。

### 附带发现：测试会写生产数据（非 hermetic）

`core/cohort.py` / `core/dashboard.py` / `TrackRecordManager` 的默认路径都指向
**生产** `track_record.json`，而部分用例构造它们时未传 `track_record_path`。
实测：一次全量 run 让 `core/data/forward_picks/track_record.json` 增加了
**652 条** forward-pick 记录（`"source": "pipeline"`）。用例本身幂等，
所以多数时候内容不变（md5 相同、仅 mtime 变化），不易察觉。

**即测试不是 hermetic 的：跑一次测试会污染生产追踪库。**
建议为这些用例统一注入 `tmp_path`（`tests/conftest.py` 已有 `tmp_output_dir`
夹具，可循此扩展）。

### 回归

```
pytest tests/ --timeout=90 \
  --deselect tests/test_e2e_no_network.py::test_core_chain_no_network \
  --deselect tests/test_e2e_no_network.py::test_enrich_file_injection \
  --deselect tests/test_golden_regression.py::test_golden_regression
→ 1138 passed, 8 skipped, 32 deselected, 0 failed, 92s (exit 0)
```

**仍未修（需你决策）**：A3、A4、A7（同第一轮）、第二/三节全部结构性问题，
以及本轮新暴露的 3 个挂死 e2e 用例与"测试写生产数据"。

另有一处上游诱因需你定夺：`analysis_mixin.py` 的 `_is_heading_meta` 用
`_heading_ratio >= 0.5` 判定"标题/元信息段"，导致"标题 + 1 段正文"恰好取到
`0.5` 而被误判丢弃（A11 的诱因）。改它会改变**真实报告**的评分口径，故未擅动。

---

## 〇-quater、第三轮：把"门禁真的在拦东西吗"变成可测量的量（2026-09-15）

上一轮只能说"105 项检查全通过"。这句话没有信息量——它只证明检查项没报错，
不证明它们能抓到东西。本轮用**变异测试**把这件事量化。

### 结论先行

| 指标 | 数值 | 含义 |
|---|---|---|
| PATTERN 层 TPR | **92.9%**（13/14） | 照检查项**自己实现的模式**喂缺陷 → 基本都能抓到 |
| NATURAL 层 TPR | **19.0%**（4/21） | 喂**真人评审会挑出的毛病** → 81% 漏检 |
| 变异覆盖率 | **32/105** | 105 项检查里，只有 32 项有变异体证明它有用 |

**一句话**：门禁不是坏了，是**窄**。它是一份"历史翻车模式清单"，
不是质量探测器。清单内的缺陷它抓得很好（92.9%），清单外的一概看不见（19%）。
这正是第二节 B 类"枚举式检查"结论的量化印证——枚举的代价不是写起来累，
而是**覆盖的集合永远不会收敛**：每新增一类翻车，就多一条规则；没翻过的车，
永远没人拦。

复现：

```bash
python scripts/gate_tpr.py --json docs/gate_tpr_20260915.json
pytest tests/test_gate_mutation.py -q      # 20 passed, 5 skipped, 18 xfailed
```

### 为什么要分两层（这是本轮最重要的方法论决定）

一开始只有一个 TPR：38.7%。这个数字**既冤枉检查项、又放过盲区**——
因为它把两类完全不同的漏检混在一起：

- 我按自己想象写的"算术错误：100→300 说成增长 50%"，`arithmetic_audit`
  确实抓不到。但它的实现只认四种形态（占比/区间中值/目标价空间/CAGR 桥），
  **这不属于它的职责范围**，怪它不公平。
- 我照它 docstring 抄的"318.29万股，占总股本约0.24%（基于总市值131.23亿元、
  股价46.73元）"，它**也**抓不到——这就是它坏了。

所以拆成 PATTERN（照它的模式喂）/ NATURAL（照真人的标准喂）。
**只有 PATTERN 层漏检才能判定"检查项失灵"**；NATURAL 层漏检说明的是
"门禁有盲区"，两者要分开修：前者改代码，后者改范式。

### A16：`arithmetic_audit` 抓不到它自己的文档示例（幽灵能力，已修）

A/B 对照实验（`_probe3.py`，已删）：

```
A 推导句在前（总股本约2.81亿股。…持有318.29万股，占总股本约0.24%）  score=0.70  ← 抓到
B 推导句在后（…占总股本约0.24%（基于总市值131.23亿元、股价46.73元）） score=1.00  ← 完全放行
C 总市值/股价在前                                                    score=0.70  ← 抓到
```

B 正是本检查**自己 docstring 里的原型案例**（柯力案）。也就是说：
这个检查被创建出来就是为了拦这个错误，而它对这个错误 100% 放行。

根因（`pipeline/checks/data_quality_mixin.py`）：

```python
before = text[max(0, m.start() - 120): m.start()]
...
mcap  = _re.search(r"总市值(?:约|为)?(\d+(?:\.\d+)?)\s*亿元", before)   # 只回看
price = _re.search(r"(?:股价|现价|当前价)[^\d]{0,6}(\d+(?:\.\d+)?)", before)  # 只回看
if mcap and price: ...        # 否则 shares=None → 静默跳过，不算 issue
```

从"总市值/股价"反推股本的兜底路径**只回看前 120 字符**，而示例的推导句在
声明**之后**。后向窗口 `text[m.end():m.end()+80]` 只被用于找"总股本X亿股"，
没被用于找"总市值/股价"。→ 兜底永远不触发 → `shares is None` → 静默放行。

已修：前向未命中时补查后向 120 字符。修复后 B 也是 0.70。

### A17：`data/predictions.json` 有两个模块各自声明同一个路径

`core/prediction_loop.py`（schema `V51.3`）与 `core/prediction_loop_v2.py`
（schema `V2`，多一个 `backtest_results` 键）都声明了
`PREDICTION_DB = <root>/data/predictions.json`。两者各自 `_load()` 整体读入、
整体写回。`core/prediction_extract.record_predictions` 走的是 v2：

```python
def record_predictions(report_text, code, loop=None):
    try:
        from core.prediction_loop_v2 import PredictionLoop   # ← 不是 v1
```

后果：同一文件两套 schema，谁后写谁定 schema；v1 先写时 v2 读到的字典
缺 `backtest_results`。目前 `backtest_results` 只在默认字典里出现、
从未被读取，所以还没炸——是**引信已装、尚未点燃**。

这一条也是第三轮沙箱化第一次没做干净的直接原因：只 patch 了 v1 的
`PREDICTION_DB`，`predictions.json` 照样被改写。

### A18：A15 的路径收口不彻底

A15 把 `track_record.json` 收口到 `default_storage_path()`，只改了
`prediction_validator / cohort / dashboard` 三处。漏了
`eval/score_predictions.py::_find_records`——它内联写死了
`_ANALYST_ROOT/"core"/"data"/"forward_picks"/"track_record.json"`。
已修：把权威路径置于候选表首位，历史位置保留作兜底（兼容旧部署，不删）。

### 测试 hermetic：已修，但必须先说清楚一个环境事实

做受控实验时发现：**纯空闲 100 秒、一个测试都不跑，本仓库的 `data/` 仍在
自己变化**——新增 81 个文件（`data/module_versions/600519/**`）并重写 2 个
checkpoint。本机上有一个并发的 600519（贵州茅台）报告生成任务在跑。

这意味着**任何"跑测试前后比对 data/"的测量都被它污染**。因此：

1. 每个结论都配了对照窗口（跑套件 vs 纯空闲），只把对照窗口里不出现的变化
   归因给套件；
2. 逐用例守卫 `tests/conftest.py::_no_production_writes` 默认只观测不 fail
   （`HERMETIC_GUARD_FAIL=1` 开启）——若默认 fail，本机每次跑都会因外部
   任务随机红。CI 无并发任务，应显式开启。

修复前（受控实验，基线 6675 文件 md5 快照，套件跑完比对）：

```
MODIFIED data/learning_data.db          MODIFIED data/predictions.json
MODIFIED data/llm_cache/cache.db        MODIFIED data/write_checkpoints.db
MODIFIED data/method_reflection_log.json
CREATED  data/checkpoints/ba7579980e50.json
→ 5 modified, 1 created
```

其中 `method_reflection_log.json` 是**永久泄漏**：`test_r77_method_reflection`
把 `__r77test__/__r77a__/__r77b__` 写进日志后只还原了 registry，日志条目从未
清理（该文件已累积到 53KB）。其余几个靠用例内手写 backup/restore 侥幸还原
——这是 fail-open 的：它依赖"每个用例都记得收尾"，没有任何机制强制。

修复后：7 个受监视的生产存储**全部零改动**。

做法（`tests/conftest.py`）：session 级 tmp 沙箱 + 逐用例 monkeypatch
把 11 个模块级常量重定向过去。刻意选 session 级而非 function 级——
`track_record.json` 单文件 1.9MB，1136 个用例 × 拷贝 ≈ 2GB I/O。

**边界（不夸大）**：本机制保证的是**生产零写入**，不是**用例间零串扰**；
沙箱在 session 内共享。用例间串扰是另一个问题（如 `smart_router` 熔断器
进程级全局态），由各自 fixture 处理。

顺带修掉两处测试内的路径重复硬编码（`_ROOT/"data"/"framework_registry.json"`
与生产模块常量各写一遍）——这正是"测试钉死了它无权假设的路径"：
一旦写路径被重定向，读路径仍指生产，用例就假失败。
已改为从 `core.method_reflection.REGISTRY_PATH / REFLECTION_LOG_PATH` 取。

### 本轮落地清单

| 编号 | 内容 | 位置 |
|---|---|---|
| R1 | 40 个变异体的黄金缺陷语料库 + TPR 报告 | `tests/gate_mutation/`、`scripts/gate_tpr.py` |
| R1 | 逐变异体 CI 断言（已知盲区标 xfail，修好会 XPASS） | `tests/test_gate_mutation.py` |
| R4 | 生产数据沙箱 + 逐用例写入守卫 | `tests/conftest.py` |
| R5 | 门禁指标冻结（阈值/判定版本/评分公式） | `tests/test_gate_registry_integrity.py`、`benchmark/gate_metric_lock.json` |
| R6 | "定义了必须注册"结构断言（防幽灵检查） | `tests/test_gate_registry_integrity.py` |
| — | A16 / A17 / A18 修复 | `data_quality_mixin.py`、`eval/score_predictions.py` |
| — | 两个 e2e 用例的 `network` 标记（`pyproject.toml` 已排除，CI 不再烧 token） | `tests/test_golden_regression.py` |

### 回归

```
pytest tests/
→ 1162 passed, 12 skipped, 35 deselected, 18 xfailed, 0 failed, 90s (exit 0)
```

（上轮 1136 → 本轮 1162，增加 20 个变异断言 + 6 个注册表/指标冻结断言；
18 个 xfailed 是**已登记的盲区**，不是失败——它们会在有人把对应检查项
升级为不变量式时自动变成 XPASS 浮出来。）

### 仍未做

R3（用不变量替换枚举）是唯一能真正抬高 NATURAL 层 TPR 的路径，
但它会改变真实报告的评分口径，**需要你决策后动手**，我没有擅动。
`invariant_audit` 是最合适的第一个改造对象：它已经有"物理不可能事件"的
概念框架，只是实现成了 5 条枚举；把"份额之和 = 100%""流通市值 ≤ 总市值"
做成真断言即可覆盖两个已确认盲区。

---

## 〇-quinquies、第四轮：门禁的**性格**——它报的红灯可信，它放的绿灯不可信（2026-09-15）

上一轮我测出了 TPR，然后在自评里写了一句"我测了 TPR，没测 TNR"。
这句话不是自谦，是真缺口：**TPR 单独拿出来是没有意义的**。
一个对所有输入都报警的检测器，TPR = 100%。

本轮补上负对照，并顺手关掉上一轮留下的三个尾巴。

### 1. 先修一个"空集通过"的假能力（幽灵能力 A19）

`_check_data_point_provenance` 在 `collected_data.data_points` 为空时，
对空列表做 `all(...)` → 恒真 → 返回 `passed=True, score=1.0`，
details 写"全部 DataPoint 出处字段齐全"。

**一句话：没有数据被校验，结论却是"校验全过"。**

这正是"过滤条件只排除 `__pycache__`"的同构错误——
`all([]) == True` 是 Python 的语义，却是质量的谎言。空集必须显式声明。

改成三态：

| 输入 | 结果 | 语义 |
|---|---|---|
| `data_points` 为空 | `passed=True, score=0.0, severity="info"` + "本次未做任何出处校验" | 通过但**不计分**，且不假装校验过 |
| 类型不符（`dict`/`None`） | `passed=False, score=0.5, severity="warning"` | 降级而非放行 |
| 字段齐全 | `score=1.0` + "N 个 DataPoint 出处字段齐全" | 数字进 details，可被差分判据观测 |

**顺带发现**：`core/models.py:193` 的 `DataPoint.__post_init__` 已经对
`excerpt_sha256` 等出处字段强制校验，缺字段时**构造即抛异常**。
也就是说"字段缺失"这个分支在生产中根本走不到——它是一段**死代码**，
只是看起来像一道防线。这比功能缺失更危险：它给人"这里有人看着"的错觉。

### 2. TNR / FPR：给门禁做一次"性格测试"

新增 BENIGN 层：注入**正确无害**的内容，看检查项会不会乱叫。
判据是 `HOLD`——分数不动、details 不变、仍然通过 = 保持安静。

实测结果：

```
PATTERN 层: 可判定 14 | 检出 13 | 漏检  1 → TPR = 92.9%
NATURAL 层: 可判定 21 | 检出  4 | 漏检 17 → TPR = 19.0%
BENIGN  层: 可判定  6 | 保持安静 6 | 误报 0 → FPR = 0.0%
```

**结论：这个门禁是"高特异度、低敏感度"的性格。**

```
TPR = 19.0%   FPR = 0.0%   TNR = 100.0%
⟹ 它报的红灯基本都是真的 —— 红灯可信
⟹ 它放行的绿灯不作数（多数缺陷没被看见）—— 绿灯不可信
```

这个结论比"TPR 低"有用得多，因为它直接给出**使用说明书**：

- 门禁报红 → 认真看，那是真问题（误报率 0）
- 门禁放行 → **不能**当作质量证明，只当作"没触发已枚举的模式"

### 3. Rogan–Gladen：0.95 分到底意味着什么

`error_mean = 0.95` 一直在被读成"5% 有问题"。这个读法隐含了
`TPR = TNR = 1` 的假设，而假设不成立。

门禁是一个不完美的诊断工具，它的 error_mean 是**观测患病率**，不是真实缺陷率。
用流行病学的 Rogan–Gladen 估计量反校准：

```
p = (观测失败率 − (1−TNR)) / (TPR + TNR − 1)
```

TNR = 1 时化简为 `p = 观测失败率 / TPR`。实测换算：

| 观测失败率 | 真实缺陷率 |
|---|---|
| 5% | **≈ 26.2%** |
| 10% | ≈ 52.5% |
| 15% | ≈ 78.8% |

**一份 error_mean = 0.95 的报告，真实缺陷率大约是 26%，不是 5%。**
差 5 倍。这就是"绿灯不可信"的量化版本。

两条方法边界（都写进了脚本输出，不让人拿去乱用）：

1. **本基线解越界**（观测 42.9% > TPR 19.0%）——这份 golden 样本只有 6917 字，
   远低于 10420 字门槛，42.9% 的报红是**截断造成的**，不代表生产报告。
2. **观测率与 TPR 必须来自同一总体**。不能拿本样本的 TPR 去反推生产报告分数。
   要得到生产可用的换算，必须在**生产报告样本**上重测 TPR。

### 4. 盲区台账：给 xfail 加账期

19 条已登记盲区，此前只有注释。**xfail 是双刃剑**：它让 CI 保持绿，
也让盲区可以无限期挂着。一条 xfail 挂三年没人管，和删掉这条用例没有区别。

所以每条盲区现在必须带 `owner` + `retire` + `action` 三个字段：

| 责任域 | 条数 | 退役日期 | 代表盲区 |
|---|---|---|---|
| `numerics` 数值一致性 | 6 | 10-15 / 11-15 / 12-31 | 份额之和 ≠ 100%、流通市值 > 总市值、错误 CAGR |
| `argument` 论证质量 | 8 | 11-15 / 12-31 | 出处实体化口径窄、证伪条件不计分 |
| `structure` 结构与格式 | 3 | 10-15 / 11-15 | 未闭合加粗、`table_density` 幽灵检查 |
| `style` 文风与叙事 | 2 | 10-15 / 11-15 | 相似度阈值定得比"能识别重复"还高 |

到期后 `test_blind_spots_are_not_stale` **变红**，只有两条路：

1. 修好了 → 用例 XPASS → 从登记册删除（最好的结局）
2. 没修好 → 续期，但**必须改写 `action`**，说明这次比上次多知道了什么

第 2 条是刻意的摩擦力。续期要写东西，才不会变成无脑 +3 个月。
**这是从"登记"变成"债务台账"的关键一步：台账有账期，登记没有。**

### 5. 三个新断言，都是为了防止"指标被悄悄绕过"

| 断言 | 防的是什么 |
|---|---|
| `test_negative_controls_exist` | 删掉负对照 → FPR 变成"无样本→None→看起来没问题" |
| `test_tpr_and_fpr_measured_on_overlapping_targets` | 敏感度取自 A 人群、特异度取自 B 人群，再拿去反推总体——流行病学里经典的错配 |
| `test_prevalence_correction_is_finite` | `TPR + TNR ≤ 1` 意味着门禁不如抛硬币，此时任何换算出来的数字都是假的 |

### 6. 修掉的工程缺陷

`scripts/gate_tpr.py` 有个 `NameError`：`_print_prevalence_correction` 引用了
`print_table` 的局部变量 `stats`。后果不只是崩溃——**漏检清单被塞在这个函数里，
若 `fpr is None` 会提前 return，清单永远不打印**。已拆成独立的
`_print_survivors`，患病率换算与漏检清单解耦。

### 本轮落地清单

| 编号 | 内容 | 位置 |
|---|---|---|
| A19 | 出处校验空集不再假通过（三态：info/warning/计分） | `pipeline/iron_gate.py` |
| — | `from_text` 支持透传 `collected_data`（否则该检查永远拿不到数据） | `pipeline/iron_gate.py` |
| R1 | BENIGN 层 9 个良性变异体 + `HOLD` 判据 + `rogan_gladen()` | `tests/gate_mutation/` |
| R1 | FPR 预算断言 + 负对照存在性 + 同总体校验 + 能力下界 | `tests/test_gate_mutation.py` |
| R1 | 患病率反校准 + 两条方法边界警告 | `scripts/gate_tpr.py` |
| R1 | 盲区台账 owner/retire/action + 过期即红的断言 | `tests/gate_mutation/corpus.py` |

---

## 一、七个可复现的硬缺陷（先看证据，再谈原理）

### A1. 管线指纹的 `gate_score` 恒为 0（真实根因：键名写错）

> **本节在修复过程中被修正。** 初稿我判定"`gate_passed` 被硬编码为 `True`，所以指纹说谎"。
> 深挖后发现该判定**不准确**，已在下文更正。修正过程本身是审计可信度的一部分，故保留。

**位置**：`pipeline/e2e_orchestrator.py:2102`（权威写入点 `_write_pipeline_fingerprint`）

```python
"gate_score": gate.get("score", 0) if isinstance(gate, dict) else 0,
```

**真实根因**：`GateReport.to_dict()`（`pipeline/checks/base.py:59-68`）输出的键是 **`overall_score`**，**根本不存在 `score`**：

```python
def to_dict(self):
    return {"passed": ..., "overall_score": ..., "checks": [...],
            "failures": [...], "suggestions": [...],
            "judge_ver": ..., "gate_config_hash": ...}
```

→ `gate.get("score", 0)` **恒为 0**。**每一份管线指纹的 `gate_score` 都是 0**，与真实分数完全脱钩。

**物证**：`output/贵州茅台_pipeline_fingerprint.json`

```json
"gate_score": 0,
"gate_passed": true,
"judge_ver": "v2-error-mean-0.78",
"gate_config_hash": "9f7f28f7e73d3ca4"
```

该报告是**通过**门禁的（`PASS_THRESHOLD = 0.78`，通过则分数必然 ≥ 0.78）。所以 `gate_score: 0` 与 `gate_passed: true` 在数学上不可能同时成立——指纹里的分数是假的。

**同文件已有先例，本处漏网**：`e2e_orchestrator.py:1746-1750` 的注释明确记录了这个 bug 并已修好：

```python
# 非 score——此前用 gate.get("score",0) 恒得 0，导致 report_scores 62% 假 0 分。
```

1892-1898 行也修了同一模式。**2102 行被遗漏。** 这不是"没人知道这个坑"，是"修了两处，漏了第三处"——正是"约束只写在注释里、没有机制保证全覆盖"的典型。

**关于 `gate_passed: True`（初稿的误判）**：预写点 `export_docx` 里的 `"gate_passed": True` 确实存在，但它上游 1643 行紧跟着 `if not gate.get("passed", False): return` 守卫——**该节点只在门禁通过时才执行**。所以它是一处冗余字面量（有分叉风险），但**并未伪造产物**。我已在修复中一并改为读真值以消除分叉风险，但必须说明：它原本不是"谎报通过"。

**修正后的性质**：溯源层的**分数**字段结构性失效。危害是——任何按 `gate_score` 做跨版本对比、质量趋势分析、或人工复核筛选的下游消费者，看到的全是 0。项目自己的 `report_scores` 曾因此产生 62% 假 0 分，同一根因在指纹层复发。

---

### A2. 清洗器把数字吃掉，留下孤儿单位——最终报告里出现 3 次残骸

**位置**：`pipeline/section_writer.py:3484`

```python
# 3e-3. 主观评分形态清除：FP4 禁"N/10 评分"类主观打分。
(r"(?:综合)?评分[:：]?\s*(\d+(?:\.\d+)?)(?:\s*/\s*\d+)?\s*分?", r"定性判断（见正文论证）"),
```

**物证**：`output/_gate_check.md` 中，`定性判断（见正文论证）%` 出现 **3 次**，另有 `.0` 残骸：

```
行业定性判断（见正文论证）%（B），属"待观望"区间
公司当前处于成长期（生命周期定性判断（见正文论证）.0，来源：XiaoJing知识模块分析）
（成长期，定性判断（见正文论证）%，数据待观望）
```

**根因**：该正则把"评分"当触发词，但 `[:：]?` 和 `\s*` 全是可选的，于是它会匹配到**不属于评分的数字**（如 `评分85%` 中的 `85`），把数字吃掉、把单位 `%` 留下。替换文本 `定性判断（见正文论证）` 更是一句**指向报告自身的元指令**（"见正文论证"），被写进了正文——语义上自相矛盾。

**为什么门禁没拦**：没有任何一项检查在找"替换后残留的孤儿单位"。`_check_placeholder_xxx` 找的是 `XXX`/`TODO` 类占位符，不覆盖这一类。

**性质**：这是最典型的"修复引入新缺陷类"——清洗器为了堵住"内部评分外泄"，自己制造了"语法破碎"。而检查器是跟着已知故障走的，所以新缺陷类必然漏网（详见第三节）。

---

### A3. 内部节点标签泄漏进正文标题

**物证**：`output/_gate_check.md` 正文出现：

```
## 组1输出（合并润色版）。
```

这是**管线内部的分组-合并节点名**，直接变成了报告的二级标题。来源可追：`pipeline/section_writer.py:3608` 的合并节点 prompt「你是资深投行主编，擅长合并润色深度研究报告」——LLM 把任务框架当成标题回显了。

**为什么门禁没拦**：`_check_template_leak`（`pipeline/checks/analysis_mixin.py:1172`）的四个模式是：

```python
patterns = [r"第[一二三四五六七八九十]章\s+行业概览",
            r"这是正文样例", r"1\.1\s+市场规模", r"Key\s+Takeaways"]
```

这四项是**早期模板时代**的泄漏模式。一个叫 `template_leak` 的检查，恰好漏掉了当下真实发生的模板泄漏。检查器的名字比它的能力大得多。

---

### A4. 图片路径用 Windows 反斜杠

**物证**：`output/_gate_check.md` 中出现 `![fig_business_model](charts\fig_business_model.png)`——**2 处**。

Markdown 里 `\f` 是转义序列，这条链接在 DOCX/HTML/PDF 导出和非 Windows 渲染器里**必然断图**。而 `_check_markdown_artifacts` 只查 `---` 分隔符、` ``` ` 代码块、游离反引号——**不查反斜杠路径**。

一份以"机构级 DOCX 交付"为卖点的系统，图挂了而门禁无感。

---

### A5. 报告被署上了真实券商的名字（prompt 示例污染）

> **本节在修复过程中被精确化。** 初稿把"所有含国金证券的产物"都算作缺陷。
> 复核发现：**柯力传感案的国金证券是合法来源**（`tests/golden/keli_latest.md` 与
> 柯力报告里引用了真实的国金证券研报：EPS 1.399/1.639/1.944 元、2026-04）。
> 缺陷范围比初稿更窄，但性质更准。以下是精确版。

**位置**：`prompts/system/cicc_analyst.md:32`

```
❌ 禁止逐段机械追加"（数据来源：公司公告及行业公开资料）"——来源标注必须自然融入句子
   （如"据公司2025年年报"、"国金证券研报测算"），同一来源标注措辞全文不得重复出现
```

**物证**：`output/_gate_check.md`——这份报告是 **浙江觉纤**（非上市光纤企业），
其数据层**不含任何国金证券来源**。但报告里 3 次出现：

```
资料来源：公开信息交叉验证，国金证券研究所整理。
资料来源：行业可比公司公开信息，国金证券研究所整理。
资料来源：公司收入数据(A)、三表勾稽模型、行业可比公司基准(B)，国金证券研究所整理。
```

"国金证券研究所整理" = **本报告由国金证券研究所编制**。这是一句**署名**，
不是数据引用——模型把 prompt 示例里的券商名，当成了**自己的机构身份**。

**因果链闭合**：全仓唯一出现"国金证券"作为**示例**的地方就是这一行 prompt。
浙江觉纤数据里没有它。所以"示例 → 模型采纳为自身署名"是唯一解释。

**性质**：这是本审计中**风险等级最高**的一项——一份 AI 生成的投研报告，
正文署名一家真实券商的研究所。而整套 105 项检查里，有 `_check_personal_narrative`
（个人叙事）、`_check_source_entity`（来源实体）、`_check_entity_verification`
（实体核验），**没有一项在问"报告署名的机构是否真实、是否有权署名"**。

**为什么是设计失误而非模型故障**：few-shot 示例污染是 LLM 的**已知**行为。
把示例写成具体机构名，等于在提示词里放了一个会被复制的身份标签。正确写法是占位符。
修复成本 1 行——但它逃过了 105 项检查，因为它属于"检查器的想象力之外"：
检查器在验证**数据来源**，而缺陷在**报告身份**。

---

### A6. CI 现在是红的（测试收集期即失败）

**位置**：`tests/test_r78_data_contract.py:10`

```python
from core.data_contract import validate_chart_data, validate_enrich_item
```

**实机复现**：

```
$ ./.venv/Scripts/python.exe -c "from core.data_contract import validate_chart_data"
ImportError: cannot import name 'validate_chart_data' from 'core.data_contract'
```

**根因**：这两个函数是 `DataContract` 类的**方法**（`core/data_contract.py:124`），不是模块级函数。测试写在旧 API 上，实现被重构成类以后，测试没跟着改。

**后果**：`pytest tests/` 在**收集阶段**就报错（919 items / 1 error），pytest 退出码非零 → CI 的 "Run tests" 步骤失败。`.github/workflows/ci.yml` 里跑的是 `pytest tests/ -v`，没有 `continue-on-error`。

**为什么没被发现**：因为验证协议是**手工挑文件**跑的。作者的 SSOT 报告里写的验证命令是：

```
pytest test_ssot_single_writer + test_deep_audit_fixes + test_calibration
     + test_outcome_vocab_unified + test_prediction_contract + test_golden_numeric
     + test_claim_citation + test_price_feeder + test_significance_guard
     → 102 passed, 0 failed
```

"102 passed, 0 failed" 是**真的**，但它不是测试套件的结论——它是 9 个手挑文件的结论。**手挑文件永远测不到没被挑中的文件的收集错误。** 这是验证协议的结构性盲区，不是一次疏忽。

**已修复（2026-09-14）**：`tests/test_r78_data_contract.py` 已按真实 API 重写，15 passed，全量收集不再报错。

**顺带发现的第二个问题：收集期本身就极慢。** `pytest tests/ --collect-only`（不执行任何用例）在本机耗时 **>4 分钟**。说明大量测试模块在 **import 期**就加载了重依赖（akshare / matplotlib / sentence-transformers 等）。叠加 CI 无超时设置，这既拖慢反馈环，也让"跑全量"在实践中不可行——**而"跑全量不可行"正是手挑文件协议形成的真正原因**。修掉收集期慢，才能让全量验证变成习惯。

---

### A7. 两个不同的类，同名 `IronGateV2`

**实机复现**：

```
$ python -c "from engine.irongate_v2 import IronGateV2 as A; from irongate_v2 import IronGateV2 as B; print(A is B)"
engine.irongate_v2.IronGateV2 -> engine.irongate_v2.registry  IronGateV2
scripts.irongate_v2.IronGateV2 -> irongate_v2                IronGateV2
SAME CLASS? False
A.verify exists: False | B.verify exists: True
```

| | `engine/irongate_v2/` | `scripts/irongate_v2.py` |
|---|---|---|
| 层级 | L1 / L2 / L3（**3 层**） | Layer 1-5（**5 层**） |
| 语义 | 会计恒等式 / 经济物理 / 文本数值契约 | 数值核验 / NLI 落地性 / 多空对抗 / 风格 / 归因 |
| API | `validate(assumptions, report_text)` | `verify(report_text, context, threshold)` |
| 行数 | 480 | 318 |

**两者都从管线可达**：

- `pipeline/engine_bridge.py:358` → `from engine.irongate_v2 import IronGateV2` → 3 层版
- `pipeline/iron_gate.py:774` → `sys.path.insert(0, .../scripts)` + `from irongate_v2 import IronGateV2` → 5 层版

`pipeline/iron_gate.py` 里还硬编码了 `threshold=0.55`——**正是 AGENTS.md 里那个过期的阈值**（真实 `PASS_THRESHOLD = 0.78`）。

**性质**：同名类、不同语义、不同 API、通过 `sys.path` 注入 `scripts/` 才能到达。这是一个定时炸弹：未来任何人把 `iron_gate.py` 的 v2 路径接线到 `run_all`（作者的 SSOT 报告已经讨论过这个可能性），拿到的将是**和 engine 路径完全不同的门禁**。

---

## 二、结构诊断：同一个能力，2~4 份实现

### B1. 两套完整的估值栈，都在线上

| | `core/compute/` | `engine/` |
|---|---|---|
| 行数 | 9,110 | 6,784（不含门禁） |
| DCF | `valuation/dcf.py` → `compute_dcf` | `dcf_model.py` → `DCFEngine`（Decimal 精度） |
| 三表 | `three_statement.py` | `three_statement.py`（846 行，完整三表联动） |
| 可比 | `valuation/comparable.py` | `comparable_model.py` |
| 蒙特卡洛 | `valuation/monte_carlo.py` | `monte_carlo.py` |
| 反向 DCF | `valuation/reverse_dcf.py` | `reverse_dcf.py` |
| 谁在用 | `pipeline/compute_engine.py` 直接 import | **只有 `pipeline/engine_bridge.py`** |

`engine/` 的接线方式是（`pipeline/compute_engine.py:266-277`）：

```python
try:
    from pipeline.engine_bridge import run_engine_ib
    _ib = run_engine_ib(financial_data)
    if _ib.get("status") == "ok":
        _fv = _ib["result"]["fair_value"]
        _prices.insert(0, ("Engine-IB", float(_fv)))   # 只是往价格列表里插一个数
except Exception as _ibe:
    logger.debug("[ENGINE-IB] bridge skip: %s", _ibe)   # 静默吞掉
```

**READ ME 把它宣传成核心资产**：

> `engine/compute/valuation/` | DCF/可比/情景/SOTP
> "Engine IB-Grade (V3.0 16-step, Decimal 精度)" —— 注释称其为"最高优先级目标价来源"

**实际地位**：一个被 `except Exception` 静默包裹的可选路径，产出被降维成一个 `float` 插进 `_prices` 列表。整套 Decimal 精度层、16 步编排、Excel 审计底稿生成——最终只贡献**一个数字**。

**这不是"死代码"——死代码是可以删的。这是"活代码但没有明确所有权"，更危险**：两条路径都能跑，都会随时间独立演化，没有机制保证它们对同一组输入给出一致的估值。当两套 DCF 给出不同的目标价时，系统没有任何仲裁逻辑。

**补充说明（我验证后推翻的假设）**：我曾怀疑 `engine_bridge` 调用的 `gate.validate(params)` 会因缺 key 而永远 blocked。实测**不成立**——`extract_engine_params` 确实产出了 `base_revenue`（line 274）和 `shares_outstanding`（line 279），L1 的 fail-closed 行为是正确的。这一项不是缺陷。

### B2. 四套门禁实现

| 文件 | 类名 | 行数 | 状态 |
|---|---|---|---|
| `pipeline/iron_gate.py` | `IronGate` | 1,106 | **真门禁**，105 项检查，进 `run_all` |
| `engine/irongate.py` | `IronGateEngine` | 446 | 仅在 `engine/` 内部被 DCF/可比/情景调用 |
| `engine/irongate_v2/` | `IronGateV2`（3 层） | 480 | 被 `engine_bridge` 用作前置校验 |
| `scripts/irongate_v2.py` | `IronGateV2`（5 层） | 318 | 被 `iron_gate.py:774` 引用，**该函数无调用点** |

作者自己在 `docs/SSOT_SINGLE_WRITER_REPORT_20260907.md` 已经发现：「`_run_irongate_v2_checks` 定义于 `pipeline/iron_gate.py:758` 但**无任何 run_all 调用点**」。这个发现是对的。但它被处理成"把 v2 的 severity 降为 warning，保持语义一致"——**没有处理"为什么会有四套门禁"**。

### B3. 三个 `chart_planner.py`

| 文件 | 行数 | logger 标识 |
|---|---|---|
| `core/chart_planner.py` | 319 | `v57.chart_planner` |
| `pipeline/chart_planner.py` | 350 | `2hao.chart_planner` |
| `utils/chart_planner.py` | 432 | `v53.chart_planner` |

三代图表规划器并存，各自被不同调用点引用（`pipeline/report_writer.py`、`scripts/resume_driver*.py`、`utils/v53_integration.py`）。三个都不相同（md5 各异）。

### B4. 51 个孤儿模块

全量扫描 398 个业务模块，**51 个从未被任何地方 import**。其中 5 个连字符串引用都没有：

```
core/earnings_call_nlp.py
core/semantic_match.py
pipeline/template_detector.py
utils/build_505_dna.py
utils/scan_reports_layer2.py
```

其余 46 个（如 `core/persuasion.py`、`core/methodology_extractor.py`、`export/html_exporter.py`、`harness/property_test.py`、`pipeline/self_consistency.py`）只在文档或一次性脚本里被提到过名字，代码路径从未进入。

**注意**：`export/html_exporter.py`、`export/model_exporter.py`、`export/output_validator.py` 都在孤儿名单里——而 README 把 `export/` 描述成交付链路的一环。

---

## 三、核心命题：Gate 分数是"共适应"的产物，不是质量的度量

这是本次审计最重要的一节。请先看一行 commit message。

### C1. 铁证：同一份文本，分数从 0.885 涨到 0.950

**commit `3d3e50f`（2026-09-09）**，标题 `fix(gate): 检查器口径修复——0.885→0.950`：

```
七处修复（全部确定性，无 prompt 语义改动）：
- so_what_chain: 切分保留标题（合规段误入分母根因）+ 补披露段 mark + 图表展示段豁免
- detect_value_conflicts: 指标精确匹配（净利率不再误比 margin 库值）+ 预测语境豁免
- consistency_engine: 现价/目标价分簇（现价260 vs 目标价300 误判消除）
- anti_patterns: 框架应用句/计数前缀/结论句式豁免（3 误报→0）
- cross_industry: agency_exemptions 行业机构白名单
- inline_citations: [注N] 脚注标记合并计数（68 标注不再误判 0）
- template_repeat: 综合判断引导词改内容判定

验证：17 新回归测试 + 56 全量通过；同文本 error_mean 0.885→0.950
```

**"同文本"** 三个字是关键。报告的文本**一个字符都没变**。分数涨了 6.5 个点，全部来自**放宽检查器**。

逐条看这七项修复的性质：

| 修复 | 性质 |
|---|---|
| 净利率不再误比 margin 库值 | 消除**误报** |
| 现价260 vs 目标价300 误判消除 | 消除**误报** |
| anti_patterns 3 误报→0 | 消除**误报** |
| 68 标注不再误判 0 | 消除**误判** |
| 合规段不再进 so_what 分母 | **缩小分母** |
| 图表展示段豁免 | **缩小分母** |
| 披露段 mark 扩充 | **缩小分母** |

**没有一项是修复报告。全部是修复尺子。**

**推论**：0.885 从来不是"报告质量 88.5 分"，它至少在很大程度上是"**写手与检查器的不一致程度**"。而这个数字可以通过调尺子随意移动。

**这带来一个致命的可比性问题**：跨版本的 Gate 分数不可比。`judge_ver` 从 `v2-error-mean-0.78` 变了吗？没有——**判据版本号没变，但判据变了**。`gate_config_hash` 只哈希了 `threshold + formula`，**没有哈希检查器实现**。所以：

> 一份 2026-09-08 的 0.885 报告和一份 2026-09-09 的 0.885 报告，含金量可能完全不同，而指纹里看不出任何区别。

这是审计链的第二个漏洞（第一个是 A1 的 `gate_passed: True`）。

### C2. 检查器被反复"提分"修改，代码注释自证

`pipeline/checks/` 里 `2026-09-09（Gate 0.95 提分）` 这个标注出现 **9 次**：

```
analysis_mixin.py:800   # 切分保留标题（捕获组）
analysis_mixin.py:839   # 补"评级说明/重要提示/风险提示/评级体系/分析师声明/联系方式/本报告由"
analysis_mixin.py:898   # 跳过图表展示段——段首即图表引用
analysis_mixin.py:940   # 补充通用推理/结论连接词
analysis_mixin.py:1896  # [注N] 脚注标记合并计数
checks/base.py:112      # 指标精确匹配修复
content_format_mixin.py:741  # "综合判断："是 4 字通用结论引导词，按字面计数≥2 误伤
data_quality_mixin.py:1514   # 行业→合法机构白名单
data_quality_mixin.py:1539   # 应用行业机构豁免
```

`_check_so_what_chain` 的注释把这条演化路径写得非常清楚：

```python
# 2026-09-04：补"利益冲突披露/合规声明/分析师声明"——合规声明段无推理链属正常
# 2026-09-09（Gate 0.95 提分）：补"评级说明/重要提示/风险提示/评级体系/
#   分析师声明/联系方式/本报告由"——合规披露段与评级说明表无推理链属预期，
#   计入分母会稀释密度（实测 42 段 avg 0.60 被拉到 score 0.36）
```

**这是一段诚实的代码史。它的每一步都有道理**——合规段确实不该计入 So What 分母。但把 9 次"分母豁免"叠加起来，`so_what_chain` 这个指标测的东西，已经和它 2026-08 月刚写出来时测的东西**不是一回事**了。而它的名字没变、分数刻度没变。

这正是 Goodhart 定律的教科书形态：**当一个度量成为目标，它就不再是好的度量**。而作者在自己的 `docs/GATE_SCORE_095_TOP_THINKING_20260909.md` 里明确写过这个风险：

> 对着不透明的分数优化会产生两种病：1. **指标游戏**：猜测 Gate 喜欢什么，堆模板句式骗 So What 密度（分数涨了，质量降了）

**诊断极其准确，而它没有阻止事情发生。** 这一点非常重要，我在第五节展开。

### C3. 96% 的检查是"冻结的模式清单"

我对 `pipeline/checks/` 下 102 个 `_check_*` 方法做了分类（判据：方法体内含 ≥3 个硬编码中文字符串字面量 → 枚举式）：

```
枚举式（硬编码模式清单）：98 项
不变量式（比较计算出的量）：  4 项
  _check_content_volume          （字数 vs 阈值）
  _check_content_density         （信息密度 vs 阈值）
  _check_numeric_chain_consistency（数字链勾稽）
  _check_numerical_tier          （数值分级）

比例：96% 是冻结的模式枚举
```

看最大的几个：

| 检查 | 硬编码字面量数 |
|---|---|
| `_check_so_what_chain` | 96 |
| `_check_market_size_consistency` | 90 |
| `_check_completeness_scan` | 89 |
| `_check_client_questions_coverage` | 59 |
| `_check_valuation_integrity` | 57 |

**这是本审计的核心结构洞察**：

> 枚举式检查的覆盖率是 **O(已发现的故障数)**；LLM 的输出空间是**开放的**。两者之间的差距**永远不可能收敛**。

每一项检查都编码了"过去踩过的坑"。一个新坑出现 → 报告漏过 → 人工发现 → 加一条模式 → 再漏 → 再加。这就是作者已经命名的"打地鼠"，但它的**数学本质**是：**你在用有限集合去覆盖无限集合，且只能事后覆盖。**

**决定性证据**：我在第一节列出的 A2/A3/A4/A5 四个缺陷，**每一个都落在某一项检查声称覆盖的类别里**：

| 缺陷 | 应该负责的检查 | 为什么漏 |
|---|---|---|
| `组1输出（合并润色版）` | `_check_template_leak` | 模式清单是早期模板时代的（"这是正文样例"） |
| `定性判断（见正文论证）%` | `_check_placeholder_xxx` | 只找 `XXX`/`TODO`，不找"替换后孤儿单位" |
| `charts\xxx.png` | `_check_markdown_artifacts` | 只查 `---`/```` ``` ````/反引号 |
| `国金证券研究所整理` | `_check_source_entity` / `_check_entity_verification` | 检查"实体是否在数据里"，不检查"署名机构是否有权署名" |

**四项检查都在，四项全部无效。** 这不是巧合——这是枚举式设计的必然结果。检查器的**名字**描述的是意图，**实现**描述的是历史。当两者背离时，读名字的人会高估覆盖。

---

## 四、文档与事实的漂移（治理问题）

同一个事实在三个文档里有三个值，而且**权威文档（README）是错的**：

| 事实 | README | AGENTS.md | PIPELINE_FACTS（代码生成） | 真值 |
|---|---|---|---|---|
| 检查项数 | **101** | **101** | 105 | 105 |
| 门禁阈值 | — | **0.55** | 0.78 | **0.78** |
| listed_company 维度 | — | **14** | 20 | 20 |
| industry_deep 维度 | — | **12** | 26 | 26 |
| unlisted_company 维度 | — | **11** | 26 | 26 |
| earnings_notes 维度 | — | **7** | 5 | 5 |

README 已经学会了写"以 `pipeline/iron_gate.py` 注册表为唯一事实源，实时数量见 `docs/PIPELINE_FACTS.md`"——**它知道该指向哪，但仍然把过期的 101 写在了正文里**。

**关键点**：`docs/PIPELINE_FACTS.md` 是 `harness/generate_docs.py` 自动生成的，pre-commit 强制同步。**机制是有的，而且工作正常。** 问题出在**那些不参与自动化的文档**——README、AGENTS.md、PRODUCT.md 靠人手维护，于是必然漂移。

这跟第三节是同一个病的两个症状：**能自动同步的不会漂移，靠人记得的必然漂移**。

`AGENTS.md` 的抬头写着「最后更新: 2026-07-30 | 更新方式: 手动（与 SAC YAML 对齐）」——45 天前，SAC 维度已经翻倍了。

**文档规模**：`docs/` 下 **166 个 md**，仓库根目录另有 **31 个 md**（MASTER_PLAN、OPTIMIZATION_PLAN、ULTRA_OPTIMIZATION_ROADMAP、EXECUTION_PLAN、WORK_EXECUTION_PLAN、ENGINEERING_PUSH_PLAN、UPGRADE_ENGINEERING_PLAN、ROADMAP_V1-V3…）。**197 份文档**。其中大量是同一天的"计划/报告/总结"三件套（`WORKPLAN_20260901` / `WORKPLAN_SUMMARY_20260901` / `WORK_SUMMARY_20260902`）。

---

## 五、对作者自身思考的批判（这是最有价值的一节）

我读了 `docs/GATE_SCORE_095_TOP_THINKING_20260909.md`。**它的质量非常高**，不在多数工程团队的复盘水平之下。它提出的五条原理——下限定律、缺陷不可平均、三工件漂移、约束卡、仪表先行——每一条都准确、可迁移、有证据支撑。

**但我必须指出它的结构性盲区，因为不指出，这个项目就不会改变。**

### 盲区一：所有处方都在"当前框架内"优化，没有一条质疑框架本身

五条处方归纳起来是：修管线、改门禁分层、加元测试、提约束卡、加 explain 模式。

**没有一条问：一个 105 项、取均值的门禁，是不是正确的仪器？**

作者在思考二里已经推导出了答案的一半：

> **合规层**（一票否决）：数据矛盾、编造来源、目标价冲突、体系性泄漏。任一触发即 block，与总分无关。
> **编辑层**（平均打分）：密度类检查，均值 + 阈值。

这个分层是对的，而且**它直接蕴含了一个推论：105 项检查里，绝大多数不该在"门禁"里**。密度类检查不该否决交付，它们该是编辑意见。合规类检查不该参与平均，它们该是一票否决。

**按这个原则重新划分，真正属于"门禁"的检查大概是个位数，而不是 105 项。** 作者推导出了原则，但没有把原则施加到既有的 105 项上——因为把 105 项砍到 8 项，意味着承认过去几周在这 105 项上的工作大部分是**错误的抽象层级**。

### 盲区二：处方三（金/毒样本元测试）的方向正确，但机制缺失，所以 7 天内就被反向执行了

作者在思考三里写：

> **处方**：`tests/gate_meta/` 建金/毒样本对，Gate 每次改检查逻辑必须过元测试。校验器从"不可测的黑盒法官"变成"被测系统"。

**这是完全正确的处方。** 但请看时间线：

- `GATE_SCORE_095_TOP_THINKING` 的日期：**2026-09-09**
- commit `3d3e50f`（检查器口径修复 0.885→0.950）的日期：**2026-09-09**

**同一天。** 同一天里，一边写出了"要防止指标游戏"的顶级思考，一边提交了 7 处放宽检查器的改动，commit message 里写着"同文本 0.885→0.950"。

**这不是讽刺，这是本审计最有价值的实证发现**：

> 作者在思考四里提出的原理——「**节点间隐式契约必丢；不变式要提为单一共享工件 + 强制复验**」——**恰好适用于他自己的思考文档**。
>
> "Gate 分数不应通过改检查器来提升"这条约束，写在了一份 md 文档里。md 文档**不是**约束卡。它没有测试、没有 CI 钩子、没有 commit 拦截。所以它在写下的当天就被违反了。

**这是递归自证**：作者关于"约束必须有强制机制"的理论，被"作者自己的约束因为没有强制机制而失效"这件事所证实。

任何给这个项目的建议，如果只是"再写一份文档说应该怎样"，都注定重复这个失败。**第五节的全部价值就在这里。**

### 盲区三：把 6.5 分的涨幅归因为"管线 bug"，但证据显示是"检查器误报"

作者思考一的表格里列了 9 个质量问题，归类为"8 个确定性工程缺陷 + 1 个模型问题"，结论是"85% 的失分是管线在漏"。

**这个归因需要修正。** commit `3d3e50f` 的七项修复里，至少四项明确是**检查器误报**（"净利率不再误比 margin 库值"、"3 误报→0"、"68 标注不再误判 0"、"现价260 vs 目标价300 误判消除"）。

**"管线 bug"和"检查器误报"是两个完全不同的诊断**：

- 若是**管线 bug**（rewrite 丢锚、数字被改）→ 报告**确实**是坏的 → 修管线**提升了产品**
- 若是**检查器误报** → 报告**本来是好的** → 修检查器**只提升了数字**

后者意味着：那 6.5 分不是"把坏报告改好"，而是"停止冤枉好报告"。**这个区别决定了这周的工作是产品改进还是数字美化。** 证据支持后者。

---

## 六、七条第一性原理（可迁移）

| # | 原理 | 一句话 | 本项目证据 |
|---|---|---|---|
| 1 | **尺子共适应定律** | 当写手和校验器都被反复调优，分数收敛于"两者一致度"，而非质量。冻结报告改尺子能提分，就是共适应的证据。 | commit `3d3e50f`：同文本 0.885→0.950 |
| 2 | **枚举不可能收敛** | 用"过去故障清单"做校验，覆盖率是 O(已发现数)，输出空间是开放的，差距永不闭合。唯一出路是不变量。 | 96% 检查是硬编码模式；4 项缺陷全部落在"有检查但无效"的类别 |
| 3 | **名字比能力大** | 检查器的名字描述意图，实现描述历史。`template_leak` 抓不到真实的模板泄漏，是因为它的模式清单停在早期。读名字的人必然高估覆盖。 | `_check_template_leak` 四模式 vs `组1输出（合并润色版）` |
| 4 | **溯源层不能 fail-open** | 审计凭证一旦会说谎，整套合规叙事归零。溯源层的默认值必须是"未验证"，不是"通过"。 | `gate_passed: True` 硬编码 + `gate_score: 0` |
| 5 | **只增不减是熵增的另一种写法** | 模块只加不删、栈只建不退、文档只写不改，必然产出 2~4 份并行实现和 197 份文档。SSOT 在**文件**层做到了，在**能力**层没有。 | 2 套估值栈 / 4 套门禁 / 3 个 chart_planner / 51 个孤儿模块 |
| 6 | **示例即指令** | Prompt 里的示例会被逐字复制。任何示例中的具体实体（机构名、代码、数字）都会变成产物的一部分。 | `国金证券研报测算` → 报告署名"国金证券研究所整理" |
| 7 | **靠人记得的必然漂移，能自动生成的不会** | 机制的有无，而不是人的认真程度，决定同步。作者很认真，文档照样漂了 45 天。 | `PIPELINE_FACTS.md`（自动生成）准确；README/AGENTS.md（手写）三处过期 |

---

## 七、行动清单（按"确定性 × 影响"排序）

作者的思考一已经确立了排序原则：「质量工作排期按"确定性 × 失分"排，不按"听起来重要"排」。我沿用。

### P0 — 确定性 100%，且直接破坏可信度（建议当天）

1. **删掉 `gate_passed: True`**，改为 `gate.get("passed", False)`。同时给指纹加 `"verified": false` 默认值语义——**溯源层必须 fail-closed**。（1 行）
2. **修 `tests/test_r78_data_contract.py`**：改 import 为 `DataContract` 类方法调用。让 `pytest tests/` 在收集期通过，CI 转绿。**然后立刻把 CI 的测试步骤改为全量**（现在就是全量，但从未真正跑通过）。
3. **`prompts/system/cicc_analyst.md:32` 的示例改为占位符**：`"国金证券研报测算"` → `"<机构名>研报测算"`。**并全仓扫描其它 prompt 里的具体机构名/人名示例**（这是系统性风险，不是孤例）。
4. **给 `section_writer.py:3484` 的正则加边界**：`评分` 后必须紧跟数字和"分"，且不能吞掉 `%`。或者更稳的做法——**不要用正则做这个替换**，改成结构化的后处理。

### P1 — 高确定性，防止再次漂移（建议本周）

5. **验证协议从"手挑文件"改为全量**：`pytest tests/ -q` 作为唯一验收口径。手挑文件只用于调试，不作为"通过"的证据。这条直接来自 A6。
6. **引入"删除纪律"**（针对原理 5）：规定**每个新增模块/栈，必须在同一 commit 里指名它取代了什么，并删除被取代者**。首刀：`engine/` 估值栈 vs `core/compute/` 二选一（建议保留 `engine/` 的 Decimal 精度层并入 `core/compute/`，或明确降级 `engine/` 为离线工具并移出交付链路）。
7. **消灭同名类**：`scripts/irongate_v2.py` 的 `IronGateV2` 重命名为 `IronGateV5Layer` 或移到 `legacy/`。同时删掉 `iron_gate.py:774` 的 `sys.path` 注入——用 `sys.path` 找到另一个同名类是不可接受的接线方式。
8. **把 `_check_template_leak` 的 4 个模式换成不变量**：改为「报告的所有 H2 标题必须属于 SAC 维度白名单 ∪ 合规段白名单」。这一条同时消灭 A3 和所有未来的"内部标签泄漏"，**且不需要预见具体标签**。

### P2 — 结构性，需要一次专门的设计（建议本月）

9. **门禁按作者自己的思考二分**：合规层（一票否决，不参与平均）+ 编辑层（均值 + 阈值）。按此重新划分 105 项，预计真门禁 ≤ 10 项。
10. **检查器版本化纳入指纹**：`gate_config_hash` 必须哈希**检查器实现的源码哈希**，不只是 threshold+formula。否则跨版本分数不可比（C1）。
11. **建 `tests/gate_meta/` 金/毒样本**（作者处方三，正确但未落地）。毒样本至少包含：内部标签泄漏、孤儿单位、反斜杠路径、假机构署名。**这四类目前全部漏网。**
12. **文档收敛**：197 份 md 中，把"计划/执行/总结"三件套合并为每阶段一份。`AGENTS.md` 要么接入 `generate_docs.py` 自动生成，要么在抬头标注"历史文档，事实以 PIPELINE_FACTS 为准"。

### P3 — 部署与工程卫生

13. **Dockerfile**：`RUN pip install -r <(...)` 用了 bash 进程替换，但 Dockerfile `RUN` 默认是 `sh`——这一行**靠 `||` 兜底才没炸**，且 `pip compile` 未安装。改为直接 `pip install -r requirements.txt`。
14. **加 `.dockerignore`**：现在 `COPY . .` 会复制 `.venv/`（19 万文件）、`data/`、`.git/`。
15. **清理**：仓库内 `D:/Cache/ruff_cache_2hao/`（Windows 路径被 Git Bash 当成相对路径创建的字面目录，27 个文件）、8 个 `test_output*` 目录、0 字节的 `kb_fts.db`。

---

## 八、结论：这个项目真正缺的是什么

把 110k 行代码、177 个 commit、197 份文档、105 项检查放在一起看，我看到的是一个**能力过剩、收敛不足**的系统。

它不缺方法论——SAC 维度、框架库、Damodaran ERP、专业怀疑，这些都在代码里，而且**真的被用上了**。我审的那份报告里，"数据有限，待尽调核实"的诚实标注、三段式反方论证、经济护城河框架的逐维拆解，都是**真实的机构级分析动作**，不是模板填充。这一点必须先说清楚。

它也不缺勤奋——每一处修复都有日期、有原因、有验证记录。这种注释密度在商业代码库里是罕见的。

**它缺的是一个"减法"的动作。**

- 门禁缺减法 → 105 项里 96% 是历史故障清单，越加越像一堵用旧砖砌的墙
- 架构缺减法 → 两套估值栈、四套门禁、三个图表规划器，全部"都还在"
- 文档缺减法 → 197 份 md，权威文档（README/AGENTS）反而过期最久
- 验证缺减法 → 手挑 9 个文件跑出"102 passed"，掩盖了整套测试收集失败

而这一切的总根因，可以浓缩成一句：

> **这套系统的每一个部件都在防止"这次出错"，没有任何部件在防止"下次出错"。**

105 项检查防的是"这份报告有缺陷"；没有机制防的是"检查器本身会失效"。SSOT 修复防的是"track_record 被两个地方写"；没有机制防的是"估值能力被两套栈实现"。金/毒样本处方防的是"检查器逻辑漂移"；没有机制强制它落地，所以它没落地。

**最能说明问题的，是作者写下的那段思考，和当天提交的那次改尺子。** 想法是对的，理论是自洽的，文档是优质的——而行为没有变。这不是能力问题，这是**机制缺位**的教科书案例。

所以，如果只能给一条建议：

> **不要再写"应该怎样"的文档。把每一条约束变成一个会失败的测试、一个会红的 CI、一个会拒绝的 pre-commit 钩子。**
>
> 作者已经证明了自己有写出顶级思考的能力。现在缺的，是让那些思考**在没有人记得它们的时候依然生效**的机制。

---

## 附录：复现命令

```bash
cd D:/Claude/projects/2hao-analyst

# A1 指纹 gate_score 恒 0（根因：键名写错）
grep -n 'gate.get("score"' pipeline/e2e_orchestrator.py            # → line 2102（权威写入点）
sed -n '59,68p' pipeline/checks/base.py                            # → to_dict 只有 overall_score，无 score
cat output/贵州茅台_pipeline_fingerprint.json | grep -E "gate_score|gate_passed"
#   → gate_score: 0 与 gate_passed: true 不可能并存（阈值 0.78，通过则分数 ≥0.78）

# A2 孤儿单位残骸
grep -c "定性判断（见正文论证）" output/_gate_check.md             # → 3
sed -n '3479,3492p' pipeline/section_writer.py

# A3 内部标签泄漏
grep -o "组[0-9]*输出（合并润色版）" output/_gate_check.md

# A4 反斜杠路径
grep -o 'charts\\\\[a-z_]*\.png' output/_gate_check.md

# A5 假机构署名
sed -n '32p' prompts/system/cicc_analyst.md
grep -rl "国金证券" output/

# A6 CI 红
./.venv/Scripts/python.exe -c "from core.data_contract import validate_chart_data"
./.venv/Scripts/python.exe -m pytest tests/ --collect-only -q | tail -3

# A7 同名类冲突
./.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'.'); sys.path.insert(0,'scripts')
from engine.irongate_v2 import IronGateV2 as A
from irongate_v2 import IronGateV2 as B
print('same class?', A is B, '| A.verify:', hasattr(A,'verify'), '| B.verify:', hasattr(B,'verify'))"

# C1 同文本提分
git log --format="%H %s" --all --grep="0.885"
git show --stat 3d3e50f | head -20

# C2 提分标注
grep -rn "Gate 0.95 提分" pipeline/checks/ | wc -l                # → 9

# B4 孤儿模块（51 个）：见审计脚本口径说明
```

**审计脚本已清理，未在仓库留下残留文件。**
