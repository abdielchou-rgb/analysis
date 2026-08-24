---
name: trader3_integration
description: 3号交易员量化引擎 + 策略进化工厂集成——回测/优化/信号验证/估值/市场状态/进化挖因子/ETF策略，供 marvis 写报告时调用
---

# 3号交易员集成 Skill（Marvis 操作指令）

> 这是 marvis 使用 **3号交易员 (trader3)** 量化引擎 + **策略进化工厂 (evolve)** 的操作手册。
> 所有输出为**候选信号，非投资建议**；必须过 IronGate 门禁才能进报告。

## 触发条件
- 报告中需要：回测验证 / 组合优化 / 信号因子验证 / 估值锚 / 市场状态 / 交易成本 / 策略进化
- 用户说"用3号交易员算一下""帮我回测""验证这个因子""算估值""看市场状态""进化策略""跑ETF策略"

## 环境
- **3号交易员**: `D:\Claude\projects\3号交易员\`（包名 `trader3`，已 editable 安装）
- **进化工厂**: `D:\Claude\projects\3号交易员\evolve\`
- **真实数据**: `D:\2hao-analyst\data\qlib_bin\`（行情）+ `D:\2hao-analyst\data\financials.db`（财务）
- **Python**: 直接用 `python`（沙箱/本机已装 numpy/scipy）

---

## 一、10 个量化工具（写报告时嵌入调用）

```python
from trader3 import Trader3
t3 = Trader3()          # gates 默认启用

# 1. 回测验证
r = t3.run_backtest(start_date="2020-01-01", end_date="2024-12-31")
# → "[动量策略·真实数据] 年化 15.2%, 夏普 0.64, 超额 15.7%, 最大回撤 -27.2%"

# 2. Walk-Forward 过拟合检测
r = t3.walk_forward_analysis(train_window=252, test_window=63)
# → 样本外年化/夏普/过拟合概率/参数稳定性

# 3. 组合优化（三种方法）
r = t3.optimize_portfolio(signals={"600519.SH":80,"000858.SZ":70}, method="risk_budget")
# 或 method="mean_variance" / "black_litterman"

# 4. 情境路由
r = t3.regime_aware_allocation(signals={...}, regime_probs={...}, regime_weights={...})

# 5. 交易成本估算（A股印花税/冲击）
buy = t3.estimate_transaction_cost(orders=[{"symbol":"600519.SH","side":"buy","value_cny":5000000}])
sell = t3.estimate_transaction_cost(orders=[{"symbol":"600519.SH","side":"sell","value_cny":5000000}])

# 6. 执行计划（TWAP/VWAP/IS/自适应）
r = t3.generate_execution_plan(target_weights={"600519.SH":0.3}, algorithm="adaptive_vwap")

# 7. 信号/因子验证（真实行情）
r = t3.validate_signal(signal_name="20日动量")
# → IC/ICIR/分组单调性/半衰期/拥挤度

# 8. 市场状态诊断（真实CSI300指数 + HMM）
r = t3.diagnose_market_regime()
# → 当前状态/概率/建议仓位

# 9. 估值锚（真实财务 DCF/PE分位/PB-ROE/EV-EBITDA）
r = t3.valuation_anchor(codes=["600519"])
# → 加权目标价/Base/Bull/Bear/隐含收益率

# 10. 基本面评分卡
r = t3.fundamental_scorecard(codes=["600519"], template="quality_growth")
# → 六维评分/红旗预警
```

### 结果引用格式（写进报告）

```markdown
> **【3号交易员验证】** {r.summary}
>
> *来源: trader3.{tool_name} | 数据: {数据源} | 门禁: {passed/failed}*
```

每次调用结果都带 `r.key_metrics`（可直接做表格）和 `r.metadata["gate_results"]`（门禁明细）。

---

## 二、策略进化工厂（挖因子/进化策略）

### 2.1 股票策略进化（真实 qlib 行情，沙箱可跑）

```bash
cd D:\Claude\projects\3号交易员

# 基础跑法（推荐，~2-3分钟）
python evolve/run_evolution.py --source qlib --universe csi300 --n-stocks 60 --gen 15 --pop 50 --top-k 5

# 换股票池
python evolve/run_evolution.py --source qlib --universe csi500 --n-stocks 80 --gen 20 --pop 60
python evolve/run_evolution.py --source qlib --universe csi1000 --n-stocks 100 --gen 20 --pop 60
```

**产出**：
- `evolve/strategies/selected.json` — 筛选通过的策略（含 IC/ICIR/单调性/多空年化）
- `evolve/strategies/evolution_summary.json` — 进化摘要
- `evolve/evolution_log/` — 每代最优

### 2.2 ETF 策略进化（需本机拉数据）

**第一步（本机有网）**：
```bash
pip install akshare
cd D:\Claude\projects\3号交易员
python evolve/scripts/fetch_etf_data.py --out evolve/data/etf --n 50
```

**第二步（进化）**：
```bash
python evolve/run_evolution.py --source etf --etf-dir evolve/data/etf --n-stocks 30 --gen 15 --pop 50 --top-k 5
```

### 2.3 进化策略 → 回测验证闭环

```python
import sys; sys.path.insert(0, r"D:\Claude\projects\3号交易员")
sys.path.insert(0, r"D:\Claude\projects\3号交易员\evolve")
from core.gp import evaluate, parse_expr
from core.data_loader import load_qlib_panel

panel, fwd = load_qlib_panel(universe='csi300', n_stocks=60)
node = parse_expr("ts_corr(low, zscore(volume), 10)")   # 从 selected.json 取
signal = evaluate(node, panel)
# → 把 signal 交给 trader3.run_backtest 做最终验证
```

---

## 三、筛选门禁（进化策略必须全过）

| 门槛 | 阈值 | 说明 |
|------|------|------|
| IC | \|IC\| > 0.02 | 相关性 |
| ICIR | > 0.15 | 稳定性 |
| 单调性 | > 0.4 | 分组收益单调 |
| 多空年化 | > 0.10 | 可交易性 |
| 复杂度 | < 25 节点 | 可解释性 |
| 去重 | 相似度 < 0.7 | 与已选策略去重 |

---

## 四、每日/每周例行任务

### 每日（盘后）
```bash
cd D:\Claude\projects\3号交易员
# 1. 数据新鲜度检查
python -c "from trader3.data_provider import QlibDataProvider; d=QlibDataProvider().describe(); print(d)"

# 2. 股票策略进化（一轮）
python evolve/run_evolution.py --source qlib --universe csi300 --gen 15 --pop 50 --top-k 3

# 3. 市场状态推送（给 2号分析师共享）
python -c "from trader3 import Trader3; t=Trader3(); t.push_regime_to_state(); print('状态已推送')"
```

### 每周
```bash
# 1. 本机拉 ETF 数据
python evolve/scripts/fetch_etf_data.py --out evolve/data/etf --n 50

# 2. ETF 策略进化
python evolve/run_evolution.py --source etf --etf-dir evolve/data/etf --gen 15 --pop 50 --top-k 5

# 3. Top 策略回测验证（闭环）
# 4. 换数据窗口复验（防过拟合）
python evolve/run_evolution.py --source qlib --universe csi300 --start 2018-01-01 --end 2022-12-31
```

---

## 五、与 2hao 管线的关系

```
2hao 写报告
  │
  ├─► 需要量化验证？ → 加载本 Skill → 调 trader3 10个工具
  ├─► 需要挖新因子？ → 跑 evolve 进化工厂 → 过筛选门禁
  ├─► 需要引用策略？ → 读 evolve/strategies/selected.json
  │
  └─► 结果进报告：必须标注【3号交易员验证】+ 门禁状态 + 数据源
```

**铁律**：
1. 任何量化数据必须来自 trader3 / evolve，**严禁 WebSearch 数据直接写正文**
2. 进化策略是候选信号，必须过筛选门禁 + 回测验证才能引用
3. 报告中数字挂来源标注（真实数据 / 门禁通过）

---

## 六、常见问题

| 问题 | 解决 |
|------|------|
| qlib 数据没更新 | 检查 `D:\2hao-analyst\data\qlib_bin\calendars\day.txt` 最后日期 |
| ETF 数据为空 | 本机跑 `fetch_etf_data.py`（沙箱无 akshare） |
| 进化 0 策略通过 | 增大 `--gen`/`--pop`，或放宽门槛 |
| 估值目标价异常 | 检查该股票 financials.db 是否有数据（`_quarter` 标注） |
| 回测门禁 failed | 看 `r.metadata["gate_results"]` 哪道门没过 |

---

## 七、命令速查

```bash
# 回测
python -m trader3.cli backtest --start 2020-01-01 --end 2024-12-31
# 市场状态
python -m trader3.cli regime
# 信号验证
python -m trader3.cli validate --signal-name "动量因子"
# 进化
python evolve/run_evolution.py --source qlib --universe csi300 --gen 15 --pop 50
# ETF 进化
python evolve/run_evolution.py --source etf --etf-dir evolve/data/etf
# 拉 ETF 数据（本机）
python evolve/scripts/fetch_etf_data.py --out evolve/data/etf --n 50
```
