# -*- coding: utf-8 -*-
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
src = open(r"D:\2hao-analyst\pipeline\iron_gate.py", encoding="utf-8").read()
for name in ["_check_so_what_chain", "_check_completeness_scan"]:
    m = re.search(r"def " + name + r"\(self.*?(?=\n    def |\nclass )", src, re.S)
    if m:
        print("=" * 80)
        print(m.group(0)[:5000])
