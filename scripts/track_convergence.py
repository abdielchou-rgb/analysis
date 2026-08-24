#!/usr/bin/env python3
"""FP3: 六维收敛追踪

测量 2hao-analyst 在 6 个超级维度上的当前表现。
每版本发布前运行一次。

用法:
    python scripts/track_convergence.py          # 测量并报告
    python scripts/track_convergence.py --save   # 存储到 convergence_log
    python scripts/track_convergence.py --json   # JSON 输出
"""

import sys, os, json, time, subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("convergence")


def measure_all() -> dict:
    """Measure all 6 dimensions"""
    measurements = {}
    
    # D1: 速度 — SAC load time
    logger.info("[D1] Measuring SAC load speed...")
    t0 = time.time()
    try:
        from core.sacs import SACLoader
        s = SACLoader("listed_company")
        _ = s.get_logic_chain()
        load_time = time.time() - t0
        measurements["speed_sac_load_ms"] = round(load_time * 1000)
    except Exception as e:
        measurements["speed_sac_load_ms"] = -1
        logger.warning(f"  SAC load failed: {e}")
    
    # D2: 广度 — SAC dimension count
    logger.info("[D2] Measuring SAC breadth...")
    try:
        from core.sacs import SACLoader as S
        for rt in ["listed_company", "industry_deep", "unlisted_company", "earnings_notes"]:
            s = S(rt)
            measurements[f"breadth_{rt}_dims"] = len(s.get_dimension_ids())
            measurements[f"breadth_{rt}_chain"] = len(s.get_logic_chain())
    except Exception as e:
        logger.warning(f"  Breadth failed: {e}")
    
    # D3: 深度 — IronGate check count
    logger.info("[D3] Measuring gate depth...")
    try:
        with open(_ROOT / "pipeline" / "iron_gate.py") as f:
            content = f.read()
        import re
        checks = re.findall(r'self\._check_\w+\(\)', content)
        measurements["depth_iron_gate_checks"] = len(checks)
        measurements["depth_iron_gate_lines"] = content.count('\\n')
    except Exception as e:
        logger.warning(f"  Depth failed: {e}")
    
    # D4: 记忆 — DB record counts
    logger.info("[D4] Measuring memory persistence...")
    try:
        import sqlite3
        for db_name in ["learning_data.db", "findings.db"]:
            db_path = _ROOT / "output" / db_name
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                rec_count = 0
                for t in tables:
                    cnt = c.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
                    rec_count += cnt
                conn.close()
                measurements[f"memory_{db_name}_records"] = rec_count
                measurements[f"memory_{db_name}_tables"] = len(tables)
            else:
                measurements[f"memory_{db_name}_records"] = -1
    except Exception as e:
        logger.warning(f"  Memory failed: {e}")
    
    # D5: 协作 — agent count
    logger.info("[D5] Measuring collaboration...")
    try:
        with open(_ROOT / "pipeline" / "e2e_orchestrator.py") as f:
            content = f.read()
        from core.sacs import SACLoader as S
        measurements["collab_agent_nodes"] = content.count("g.add_node(")
        measurements["collab_debate_refs"] = content.count("debate") + content.count("Debate")
    except Exception as e:
        logger.warning(f"  Collab failed: {e}")
    
    # D6: 持续 — log age
    logger.info("[D6] Measuring stability...")
    try:
        log_dir = _ROOT / "logs"
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log"))
            measurements["stability_log_count"] = len(log_files)
            measurements["stability_log_bytes"] = sum(f.stat().st_size for f in log_files)
        else:
            measurements["stability_log_count"] = 0
            measurements["stability_log_bytes"] = 0
    except Exception as e:
        logger.warning(f"  Stability failed: {e}")
    
    measurements["timestamp"] = time.time()
    return measurements


def print_report(m: dict):
    """Print human-readable report"""
    print(f"\\n{'='*60}")
    print(f"  FP3 六维收敛报告")
    print(f"{'='*60}")
    
    dims = [
        ("D1 速度", [("SAC load (ms)", "speed_sac_load_ms")]),
        ("D2 广度", [(k, k) for k in m if k.startswith("breadth_")]),
        ("D3 深度", [(k, k) for k in m if k.startswith("depth_")]),
        ("D4 记忆", [(k, k) for k in m if k.startswith("memory_")]),
        ("D5 协作", [(k, k) for k in m if k.startswith("collab_")]),
        ("D6 持续", [(k, k) for k in m if k.startswith("stability_")]),
    ]
    
    for dim_name, metrics in dims:
        print(f"\\n  [{dim_name}]")
        for label, key in metrics:
            if key in m:
                v = m[key]
                print(f"    {label}: {v}")
    
    print(f"\\n{'='*60}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--save", action="store_true", help="Save to convergence log")
    p.add_argument("--json", action="store_true", help="JSON output")
    args = p.parse_args()
    
    m = measure_all()
    
    if args.json:
        print(json.dumps(m, indent=2))
    else:
        print_report(m)
    
    if args.save:
        log_dir = _ROOT / "output"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / "convergence_log.json"
        entries = []
        if log_path.exists():
            entries = json.loads(log_path.read_text(encoding="utf-8"))
        entries.append(m)
        log_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\\nSaved to {log_path} ({len(entries)} entries)")
