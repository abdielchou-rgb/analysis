#!/usr/bin/env python
"""R2: Mark golden_numeric entries for verification."""

import json
from pathlib import Path

TRUTH_SET = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set_expanded.json")
OUTPUT = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set_pending.json")

# Load truth set
entries = json.loads(TRUTH_SET.read_text(encoding="utf-8"))

# Mark entries for verification
for entry in entries:
    if entry.get("source") == "akshare_verified" and entry["canonical"] is None:
        entry["source"] = "pending_verification"
        entry["verification_status"] = "needs_akshare_data"

# Count by status
statuses = {}
for entry in entries:
    status = entry.get("verification_status", "verified")
    statuses[status] = statuses.get(status, 0) + 1

print("Verification status:")
for status, count in sorted(statuses.items()):
    print("  %s: %d" % (status, count))

print("\nTotal entries:", len(entries))

# Save
OUTPUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
print("Saved to:", OUTPUT)
