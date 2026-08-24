# 3号交易员 + 策略进化工厂 — Marvis 操作指令

> 交接给 marvis 执行。目标：让 2hao 分析师在写报告时，能直接调用 **3号交易员量化引擎** 做回测/估值/信号验证/市场状态，并用 **策略进化工厂** 挖出可用策略（含 ETF）。
> 生成日期：2026-08-11

## 0. 背景与目标

2hao 分析师的判断目前主要靠研究框架 + 财务数据，缺少**量化验证闭环**。现在 3号交易员（trader3）已落地 10 个量化工具 + GP 策略进化工厂，但 marvis 尚未掌握如何调用。

**目标**：
1. marvis 写报告时能嵌入调用 3号交易员的 10 个工具（回测/优化/估值/信号/市场状态/成本/执行）
2. marvis 能跑策略进化工厂，挖出真实有效的量价因子策略（含 ETF）
3. 进化出的策略过筛选门禁后，能回测验证并沉淀给 2hao 引用

**执行原则**：所有量化数据必须来自 trader3 / evolve，**严禁 WebSearch 数据直接写正文**；策略为候选信号，须过门禁 + 回测验证。

---

## 1. 环境准备

```
3号交易员:  D:\Claude\projects\3号交易员\   （包名 trader3，已安装）
进化工厂:  D:\Claude\projects\3号交易员\evolve\
真实行情:  D:\2hao-analyst\data\qlib_bin\    （6440交易日 / 6122股票）
真实财务:  D:\2hao-analyst\data\financials.db （560万行 / 5259股票）
```

**首次验证**（必须跑通）：
```bash
cd D:\Claude\projects\3号交易员
python -c "from trader3 import Trader3; t=Trader3(); r=t.diagnose_market_regime(); print(r.summary); print('环境OK')"
```

---

## 2. 任务清单（按优先级）

### P0-① 掌握 10 个量化工具（写报告嵌入调用）

**产出**：marvis 能独立调用以下 10 个工具，把结果引用进报告。

| # | 工具 | 2hao 报告用途 | 调用示例 |
|---|------|--------------|----------|
| 1 | `run_backtest` | 策略回测验证 | `t3.run_backtest(start_date="2020-01-01", end_date="2024-12-31")` |
| 2 | `walk_forward_analysis` | 过拟合检测 | `t3.walk_forward_analysis(train_window=252, test_window=63)` |
| 3 | `optimize_portfolio` | 组合优化 | `t3.optimize_portfolio(signals={...}, method="risk_budget")` |
| 4 | `regime_aware_allocation` | 情境路由 | `t3.regime_aware_allocation(signals={...}, regime_probs={...}, regime_weights={...})` |
| 5 | `estimate_transaction_cost` | 交易成本 | `t3.estimate_transaction_cost(orders=[{...}])` |
| 6 | `generate_execution_plan` | 执行计划 | `t3.generate_execution_plan(target_weights={...})` |
| 7 | `validate_signal` | 因子验证 | `t3.validate_signal(signal_name="20日动量")` |
| 8 | `diagnose_market_regime` | 市场状态 | `t3.diagnose_market_regime()` |
| 9 | `valuation_anchor` | 估值锚 | `t3.valuation_anchor(codes=["600519"])` |
| 10 | `fundamental_scorecard` | 基本面评分 | `t3.fundamental_scorecard(codes=["600519"], template="quality_growth")` |

**报告引用格式**：
```markdown
> **【3号交易员验证】** {r.summary}
>
> *来源: trader3.{tool_name} | 数据: {数据源} | 门禁: {passed/failed}*
```

**练习任务**：写一篇《贵州茅台估值锚定》，调用 `valuation_anchor(["600519"])` + `estimate_transaction_cost`，产出报告引用块。

---

### P0-② 股票策略进化（真实 qlib 行情，沙箱可跑）

**命令**：
```bash
cd D:\Claude\projects\3号交易员
python evolve/run_evolution.py --source qlib --universe csi300 --n-stocks 60 --gen 15 --pop 50 --top-k 5
```

**产出**：
- `evolve/strategies/selected.json` — 筛选通过的策略（含 IC/ICIR/单调性/多空年化）
- `evolve/strategies/evolution_summary.json` — 进化摘要
- `evolve/evolution_log/` — 每代最优

**验证标准**：至少筛出 1 个策略通过 6 道门禁（IC>0.02, ICIR>0.15, 单调性>0.4, 多空年化>0.10, 复杂度<25, 去重）。

**多股票池尝试**：
```bash
python evolve/run_evolution.py --source qlib --universe csi500 --n-stocks 80 --gen 20 --pop 60 --top-k 5
python evolve/run_evolution.py --source qlib --universe csi1000 --n-stocks 100 --gen 20 --pop 60 --top-k 5
```

---

### P0-③ 拉取 ETF 数据（本机有网，沙箱不行）

**说明**：沙箱无 akshare，需在本机（有网）执行。

**命令**（本机）：
```bash
pip install akshare
cd D:\Claude\projects\3号交易员
python evolve/scripts/fetch_etf_data.py --out evolve/data/etf --n 50
```

**产出**：`evolve/data/etf/{code}.csv`（每只 ETF 一个文件，date/open/high/low/close/volume）

---

### P0-④ ETF 策略进化（需 P0-③ 完成后）

**命令**：
```bash
cd D:\Claude\projects\3号交易员
python evolve/run_evolution.py --source etf --etf-dir evolve/data/etf --n-stocks 30 --gen 15 --pop 50 --top-k 5
```

---

### P1-① 进化策略 → 回测验证闭环

把 `selected.json` 里的策略表达式转成信号，喂给 3号交易员回测验证。

```python
import sys; sys.path.insert(0, r"D:\Claude\projects\3号交易员")
sys.path.insert(0, r"D:\Claude\projects\3号交易员\evolve")
from core.gp import evaluate, parse_expr
from core.data_loader import load_qlib_panel
from trader3 import Trader3

panel, fwd = load_qlib_panel(universe='csi300', n_stocks=60)
node = parse_expr("ts_corr(low, zscore(volume), 10)")   # 从 selected.json 取
signal = evaluate(node, panel)
# → 把 signal 交给 trader3.run_backtest 做最终验证
t3 = Trader3()
r = t3.run_backtest()   # 用进化信号替换默认动量策略
```

**验证标准**：进化策略回测表现（年化/夏普/回撤）写入报告，标注【3号交易员验证】。

---

### P1-② 每日例行任务（沉淀给 marvis 定期跑）

```
每日盘后：
  1. 检查 qlib 数据新鲜度
  2. 跑一轮股票进化（~2-3分钟）
  3. 新策略过门禁 → 追加 selected.json
  4. 推送市场状态给 2hao: python -c "from trader3 import Trader3; t=Trader3(); t.push_regime_to_state()"

每周：
  1. 本机拉 ETF 数据
  2. ETF 进化一轮
  3. Top 策略回测验证
  4. 换数据窗口复验（防过拟合）
```

---

## 3. 筛选门禁（策略必须全过）

| 门槛 | 阈值 | 说明 |
|------|------|------|
| IC | \|IC\| > 0.02 | 相关性 |
| ICIR | > 0.15 | 稳定性（A股量价实际水平） |
| 单调性 | > 0.4 | 分组收益单调 |
| 多空年化 | > 0.10 | 可交易性 |
| 复杂度 | < 25 节点 | 可解释性 |
| 去重 | 相似度 < 0.7 | 与已选策略去重 |

---

## 4. 常见问题

| 问题 | 解决 |
|------|------|
| qlib 数据没更新 | 检查 `D:\2hao-analyst\data\qlib_bin\calendars\day.txt` 最后日期 |
| ETF 数据为空 | 本机跑 `fetch_etf_data.py`（沙箱无 akshare） |
| 进化 0 策略通过 | 增大 `--gen`/`--pop`，或放宽门槛 |
| 估值目标价异常 | 检查该股票 financials.db 是否有数据（看 `_quarter`） |
| 回测门禁 failed | 看 `r.metadata["gate_results"]` 哪道门没过 |

---

## 5. 完成定义（DoD）

- [ ] 能独立调用 10 个量化工具，报告引用格式正确
- [ ] 股票策略进化跑通，至少 1 个策略通过门禁
- [ ] ETF 数据管线建立（本机），ETF 进化可跑
- [ ] 进化策略 → 回测验证闭环打通
- [ ] 每日/每周例行任务脚本化

---

## 6. 相关文件

- `D:\2hao-analyst\skills\trader3_integration\SKILL.md` — 集成 Skill（marvis 加载用）
- `D:\Claude\projects\3号交易员\README.md` — 3号交易员完整文档
- `D:\Claude\projects\3号交易员\evolve\TASKS_marvis.md` — 进化工厂任务
- `D:\Claude\projects\3号交易员\evolve\run_evolution.py` — 进化主入口
