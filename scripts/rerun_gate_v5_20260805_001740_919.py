# -*- coding: utf-8 -*-
import sys, io, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
out = open(r'D:\2hao-analyst\logs\gate_v5_result.txt', 'w', encoding='utf-8')
def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    out.write(s + '\n')
    out.flush()
try:
    sys.path.insert(0, r'D:\2hao-analyst')
    from pipeline.iron_gate import IronGate
    p = r'D:\2hao-analyst\output\柯力传感深度分析报告_v5_20260804.md'
    text = open(p, encoding='utf-8').read()
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) == 3:
            text = parts[2]
    gate = IronGate.from_text(text, report_type='listed_company', style='cicc')
    report = gate.run_all()
    log(f"SCORE: {report.overall_score:.3f}")
    log(f"PASSED: {report.passed}")
    log("FAILURES:")
    for f in report.failures:
        log(" -", f)
    log("CHECKS:")
    for c in getattr(report, 'checks', []):
        log(f"  [{c.name}] passed={c.passed} score={getattr(c,'score',0):.3f} sev={getattr(c,'severity','')} detail={getattr(c,'detail','')}")
except Exception as e:
    log("ERROR:", repr(e))
    log(traceback.format_exc())
finally:
    out.close()
