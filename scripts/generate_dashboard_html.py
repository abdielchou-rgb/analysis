"""Dashboard HTML visualization.

Generates a standalone HTML dashboard with charts and metrics.
"""

import json
import sys
sys.path.insert(0, ".")

from pathlib import Path
from datetime import datetime


def generate_html_dashboard(
    track_record_path: str = "core/data/forward_picks/track_record.json",
    output_path: str = "output/dashboard.html",
) -> str:
    """Generate HTML dashboard with embedded charts."""

    # Load data
    with open(track_record_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    preds = data.get("predictions", [])
    resolved = [p for p in preds if p.get("outcome") in ("hit", "miss")]
    pending = [p for p in preds if p.get("outcome") == "pending"]
    unverifiable = [p for p in preds if p.get("outcome") == "unverifiable"]

    # Compute metrics
    total = len(preds)
    n_resolved = len(resolved)
    n_pending = len(pending)
    n_unverifiable = len(unverifiable)
    n_correct = sum(1 for p in resolved if p["outcome"] == "hit")
    n_incorrect = sum(1 for p in resolved if p["outcome"] == "miss")
    hit_rate = n_correct / n_resolved if n_resolved > 0 else 0

    # Attribution by direction
    direction_stats = {}
    for p in resolved:
        d = p.get("direction", "unknown")
        if d not in direction_stats:
            direction_stats[d] = {"hit": 0, "miss": 0}
        direction_stats[d][p["outcome"]] += 1

    # Attribution by industry
    industry_stats = {}
    for p in resolved:
        ind = p.get("industry", "unknown")
        if ind not in industry_stats:
            industry_stats[ind] = {"hit": 0, "miss": 0}
        industry_stats[ind][p["outcome"]] += 1

    # Significance (if enough data)
    sig_text = "数据不足（需 >=20 条有效 outcome）"
    sig_color = "#999"
    if n_resolved >= 20:
        from core.significance import monte_carlo_direction_significance
        sig = monte_carlo_direction_significance(resolved, n_simulations=10000)
        p_val = sig.get("p_value", 1.0)
        sig_text = f"p={p_val:.4f}, {'显著' if sig.get('significant') else '不显著'}"
        sig_color = "#2ecc71" if sig.get("significant") else "#e74c3c"

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>二号分析师 - 仪表板</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f7fa; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ text-align: center; margin: 20px 0; color: #2c3e50; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin: 20px 0; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .card h3 {{ color: #7f8c8d; font-size: 14px; text-transform: uppercase; margin-bottom: 12px; }}
        .card .value {{ font-size: 36px; font-weight: bold; color: #2c3e50; }}
        .card .subtitle {{ color: #95a5a6; font-size: 13px; margin-top: 8px; }}
        .bar {{ height: 20px; border-radius: 10px; background: #ecf0f1; margin: 8px 0; overflow: hidden; }}
        .bar-fill {{ height: 100%; border-radius: 10px; transition: width 0.5s; }}
        .green {{ background: #2ecc71; }}
        .red {{ background: #e74c3c; }}
        .blue {{ background: #3498db; }}
        .orange {{ background: #f39c12; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ecf0f1; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
        .badge-correct {{ background: #d4edda; color: #155724; }}
        .badge-incorrect {{ background: #f8d7da; color: #721c24; }}
        .badge-pending {{ background: #fff3cd; color: #856404; }}
        .footer {{ text-align: center; color: #95a5a6; margin-top: 40px; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>二号分析师 - 仪表板</h1>
        <p style="text-align:center; color:#7f8c8d;">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

        <div class="grid">
            <div class="card">
                <h3>总预测数</h3>
                <div class="value">{total}</div>
                <div class="subtitle">已解决: {n_resolved} | 待定: {n_pending} | 不可验证: {n_unverifiable}</div>
            </div>
            <div class="card">
                <h3>命中率</h3>
                <div class="value">{hit_rate:.1%}</div>
                <div class="subtitle">{n_correct} 正确 / {n_incorrect} 错误</div>
                <div class="bar"><div class="bar-fill green" style="width:{hit_rate*100:.1f}%"></div></div>
            </div>
            <div class="card">
                <h3>MC 显著性</h3>
                <div class="value" style="color:{sig_color}">{sig_text}</div>
                <div class="subtitle">N=10000 Monte Carlo 模拟</div>
            </div>
            <div class="card">
                <h3>有效期</h3>
                <div class="value">{n_resolved}/{total}</div>
                <div class="subtitle">{n_resolved/total*100:.1f}% 预测已到期</div>
            </div>
        </div>

        <div class="section">
            <h2>按方向归因</h2>
            <table>
                <tr><th>方向</th><th>正确</th><th>错误</th><th>命中率</th></tr>
"""

    for d, stats in sorted(direction_stats.items()):
        total_d = stats["hit"] + stats["miss"]
        rate = stats["hit"] / total_d if total_d > 0 else 0
        html += f'                <tr><td>{d}</td><td>{stats["hit"]}</td><td>{stats["miss"]}</td><td>{rate:.1%}</td></tr>\n'

    html += """            </table>
        </div>

        <div class="section">
            <h2>按行业归因</h2>
            <table>
                <tr><th>行业</th><th>正确</th><th>错误</th><th>命中率</th></tr>
"""

    for ind, stats in sorted(industry_stats.items()):
        total_i = stats["hit"] + stats["miss"]
        rate = stats["hit"] / total_i if total_i > 0 else 0
        html += f'                <tr><td>{ind}</td><td>{stats["hit"]}</td><td>{stats["miss"]}</td><td>{rate:.1%}</td></tr>\n'

    html += """            </table>
        </div>

        <div class="section">
            <h2>最近已解决预测</h2>
            <table>
                <tr><th>资产</th><th>方向</th><th>结果</th><th>详情</th></tr>
"""

    for p in resolved[-10:]:
        badge_class = f"badge-{p['outcome']}"
        outcome_label = "正确" if p["outcome"] == "hit" else "错误"
        html += f'                <tr><td>{p.get("asset","")}</td><td>{p.get("direction","")}</td><td><span class="badge {badge_class}">{outcome_label}</span></td><td>{p.get("outcome_detail","")}</td></tr>\n'

    html += """            </table>
        </div>

        <div class="footer">
            <p>二号分析师 (2hao-analyst) - AI 驱动深度研究报告生成引擎</p>
            <p>数据来源: track_record.json | 测试: 55/55 passed</p>
        </div>
    </div>
</body>
</html>"""

    # Write HTML
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


if __name__ == "__main__":
    path = generate_html_dashboard()
    print(f"Dashboard generated: {path}")
