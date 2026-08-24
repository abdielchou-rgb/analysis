import sys
p = "/sessions/hopeful-awesome-curie/mnt/2hao-analyst/pipeline/iron_gate.py"
t = open(p).read()
marker = "self._check_source_reliability"
if marker in t:
    t = t.replace(marker + ",", marker + ",\n            self._check_methodology_compliance,", 1)
method = '\n    def _check_methodology_compliance(self):\n        from pipeline.checks.base import GateCheckResult\n        from pipeline.checks.methodology_compliance import check_methodology_compliance\n        r = check_methodology_compliance(self.report_text or "", self.report_type or "")\n        det = "; ".join(r["issues"][:3]) if r["issues"] else "无"\n        return GateCheckResult("methodology_compliance", r["passed"], r["score"], det, severity="warning")\n'
t = t.replace("def _detect_value_conflicts", method + "\ndef _detect_value_conflicts", 1)
open(p, "w").write(t)
print("DONE:", t.count("methodology_compliance"), "occurrences")