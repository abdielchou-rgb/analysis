"""2hao-analyst MCP Tool Server — 供 Claude/Marvis 调用的计算工具包

训练模式下，Claude 通过 tool-calling 直接调 2hao 的确定性计算模块，
不走 section_writer LLM 管线。所有工具输出可审计、可复现。

启动：
    python scripts/mcp_tool_server.py
    # 以 MCP stdio 模式运行，Claude Desktop 可直接接入
"""
import json, sys, os, logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("2hao.mcp_tools")

# ── Tool Registry ──────────────────────────────────────────────
TOOLS = {}
TOOL_DEFS = []

def register(name: str, description: str, parameters: dict):
    """注册一个工具到 MCP Server"""
    def decorator(func):
        TOOLS[name] = func
        TOOL_DEFS.append({
            "name": name, "description": description,
            "input_schema": {"type": "object", "properties": parameters, "required": list(parameters.keys())},
        })
        return func
    return decorator

# ========== 估值工具 ==========

@register(
    "reverse_dcf", "反向 DCF：从当前股价反推市场隐含增长率/预期差",
    {"market_cap": {"type": "number", "description": "总市值（元）"},
     "fcf": {"type": "number", "description": "TTM 自由现金流（元）"},
     "wacc": {"type": "number", "description": "加权平均资本成本（如 0.10）"},
     "net_debt": {"type": "number", "description": "净债务（元，可选）"}},
)
def reverse_dcf(market_cap: float, fcf: float, wacc: float, net_debt: float = 0):
    from core.compute.valuation.reverse_dcf import ReverseDCF
    rd = ReverseDCF(market_cap, net_debt, fcf, wacc=wacc)
    r = rd.solve_implied_growth()
    return r.to_dict() if hasattr(r, "to_dict") else {"implied_growth_pct": r.implied_growth_pct}

@register(
    "peg_valuation", "PEG 估值：PE÷增速判断成长股估值水平",
    {"pe": {"type": "number", "description": "市盈率"},
     "growth_pct": {"type": "number", "description": "预期增速（%）"}},
)
def peg_valuation(pe: float, growth_pct: float):
    from core.compute.valuation.peg import PEGValuation
    r = PEGValuation(pe, growth_pct).analyze()
    return {"peg_ratio": r.peg_ratio, "valuation_label": r.valuation_label}

@register(
    "monte_carlo", "Monte Carlo 概率估值模拟",
    {"wacc": {"type": "number", "description": "WACC 均值（如 0.10）"},
     "wacc_std": {"type": "number", "description": "WACC 标准差"},
     "fcf_mean": {"type": "number", "description": "FCF 均值（元）"},
     "fcf_std": {"type": "number", "description": "FCF 标准差"},
     "n": {"type": "integer", "description": "模拟次数"}},
)
def monte_carlo(wacc: float, wacc_std: float, fcf_mean: float, fcf_std: float, n: int = 10000):
    from core.compute.valuation.monte_carlo import MonteCarloValuation
    mc = MonteCarloValuation(wacc, wacc_std, fcf_mean, fcf_std)
    r = mc.simulate(n)
    return {"mean_ev": round(r.mean_ev, 2), "median_ev": round(r.median_ev, 2),
            "p10_ev": round(r.p10_ev, 2), "p90_ev": round(r.p90_ev, 2)}

@register(
    "eva", "EVA 经济利润：衡量真实价值创造",
    {"nopat": {"type": "number", "description": "税后营业利润（元）"},
     "invested_capital": {"type": "number", "description": "投入资本（元）"},
     "wacc": {"type": "number", "description": "加权平均资本成本"}},
)
def eva(nopat: float, invested_capital: float, wacc: float = 0.10):
    from core.compute.valuation.eva import EVAModel
    r = EVAModel(nopat, invested_capital, wacc).calculate()
    return {"eva": r.eva, "verdict": r.verdict, "eva_margin_pct": r.eva_margin_pct}

@register(
    "altman_z", "Altman Z-Score 破产预警",
    {"working_capital": {"type": "number", "description": "营运资金（元）"},
     "retained_earnings": {"type": "number", "description": "留存收益"},
     "ebit": {"type": "number", "description": "息税前利润"},
     "market_cap": {"type": "number", "description": "总市值"},
     "total_assets": {"type": "number", "description": "总资产"},
     "total_liabilities": {"type": "number", "description": "总负债"},
     "revenue": {"type": "number", "description": "营收"}},
)
def altman_z(working_capital, retained_earnings, ebit, market_cap, total_assets, total_liabilities, revenue):
    from core.compute.valuation.eva import AltmanZScore
    az = AltmanZScore(working_capital, retained_earnings, ebit, market_cap, total_assets, total_liabilities, revenue)
    return az.calculate()

@register(
    "real_option", "实物期权估值（Black-Scholes）",
    {"underlying": {"type": "number", "description": "标的资产现值"},
     "strike": {"type": "number", "description": "执行价格"},
     "volatility": {"type": "number", "description": "波动率（如 0.3）"},
     "years": {"type": "number", "description": "期限（年）"}},
)
def real_option(underlying, strike, volatility, years):
    from core.compute.valuation.real_option import RealOption
    ro = RealOption(underlying, strike, volatility, years)
    return ro.black_scholes()

@register(
    "lbo", "LBO 杠杆收购分析",
    {"entry_ebitda": {"type": "number", "description": "进入 EBITDA"},
     "entry_multiple": {"type": "number", "description": "进入倍数"},
     "debt_pct": {"type": "number", "description": "负债比例"}},
)
def lbo(entry_ebitda, entry_multiple, debt_pct):
    from core.compute.valuation.lbo import LBOModel
    r = LBOModel(entry_ebitda, entry_multiple, debt_pct).calculate()
    return {"irr_pct": r.irr_pct, "moic": r.moic, "exit_equity": r.exit_equity}

# ========== 财务工具 ==========

@register(
    "dupont", "Dupont ROE 三分量分解",
    {"net_profit": {"type": "number"}, "revenue": {"type": "number"},
     "total_assets": {"type": "number"}, "equity": {"type": "number"}},
)
def dupont(net_profit, revenue, total_assets, equity):
    from core.compute.financial.dupont import DupontAnalysis
    r = DupontAnalysis(net_profit, revenue, total_assets, equity).decompose()
    return {"roe_pct": r.roe_pct, "net_margin_pct": r.net_margin_pct,
            "asset_turnover": r.asset_turnover, "equity_multiplier": r.equity_multiplier}

@register(
    "factor_attribution", "多因子归因：量/价/结构/汇率对营收的贡献",
    {"q0": {"type": "number"}, "q1": {"type": "number"},
     "p0": {"type": "number"}, "p1": {"type": "number"}},
)
def factor_attribution(q0, q1, p0, p1):
    from core.compute.financial.factor_decomp import RevenueAttribution
    r = RevenueAttribution(q0, q1, p0, p1).decompose()
    return {"volume_pct": r.volume_pct, "price_pct": r.price_pct, "total_growth": r.total_growth}

@register(
    "signal_chain", "先行/同步/滞后信号链",
    {"industry": {"type": "string", "description": "行业名称（如半导体）"}},
)
def signal_chain(industry: str):
    from core.compute.signal_chain import SignalChainEngine
    r = SignalChainEngine(industry).calculate()
    return {"leading": r.leading, "coincident": r.coincident, "lagging": r.lagging}

# ========== 质量门 ==========

@register(
    "iron_gate", "运行 Iron Gate 门禁检查",
    {"report_path": {"type": "string", "description": "报告 .md 文件路径"},
     "report_type": {"type": "string", "description": "报告类型"}},
)
def iron_gate(report_path: str, report_type: str = "industry_deep"):
    from pipeline.iron_gate import IronGate
    g = IronGate(report_path, report_type)
    r = g.run_all()
    return {"passed": r.passed, "score": round(r.overall_score, 3),
            "failures": r.failures[:5]}

@register(
    "check_compliance", "方法论合规检查",
    {"report_text": {"type": "string", "description": "报告正文"},
     "report_type": {"type": "string", "description": "报告类型"}},
)
def check_compliance(report_text: str, report_type: str = "industry_deep"):
    from pipeline.checks.methodology_compliance import check_methodology_compliance
    r = check_methodology_compliance(report_text, report_type)
    return {"passed": r["passed"], "issues": r["issues"], "score": r["score"]}

# ========== MCP Server ==========

def handle_request(request: dict) -> dict:
    """处理 MCP 请求"""
    method = request.get("method")
    params = request.get("params", {})

    if method == "list_tools":
        return {"result": {"tools": TOOL_DEFS}}

    if method == "call_tool":
        name = params.get("name")
        args = params.get("arguments", {})
        if name not in TOOLS:
            return {"error": {"code": -32601, "message": f"Tool not found: {name}"}}
        try:
            result = TOOLS[name](**args)
            return {"result": {"content": [{"type": "json", "json": result}]}}
        except Exception as e:
            logger.exception(f"Tool {name} failed")
            return {"error": {"code": -32603, "message": str(e)}}

    return {"error": {"code": -32601, "message": f"Method not found: {method}"}}

def main():
    """MCP stdio server"""
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"error": {"code": -32700, "message": "Parse error"}}) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    print("2hao MCP Tools Server (stdio mode)", file=sys.stderr)
    print(f"  Registered {len(TOOLS)} tools", file=sys.stderr)
    for name in sorted(TOOLS):
        print(f"    - {name}", file=sys.stderr)
    main()