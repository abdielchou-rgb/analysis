#!/usr/bin/env python
"""R0: Isolate mock data from production track_record."""

import json
from pathlib import Path

SOURCE = Path(r"D:\Claude\projects\2hao-analyst\core\data\forward_picks")
TRACK_FILE = SOURCE / "track_record.json"
MOCK_FILE = SOURCE / "mock_track_record.json"
CLEAN_FILE = SOURCE / "track_record_clean.json"

# Mock indicators
MOCK_INDICATORS = ["mock", "test", "demo", "sample", "MC", "彩排", "演练"]

data = json.loads(TRACK_FILE.read_text(encoding="utf-8"))
preds = data.get("predictions", [])

mock = []
clean = []

for pred in preds:
    is_mock = False
    text = " ".join(
        [
            str(pred.get("bold_call", "")),
            str(pred.get("id", "")),
            str(pred.get("asset", "")),
            str(pred.get("outcome_detail", "")),
        ]
    ).lower()

    for indicator in MOCK_INDICATORS:
        if indicator.lower() in text:
            is_mock = True
            break

    # Check for mock outcome format (correct/incorrect vs hit/miss/partial)
    outcome = pred.get("outcome", "")
    if outcome in ("correct", "incorrect") and not pred.get("outcome_date"):
        is_mock = True

    if is_mock:
        mock.append(pred)
    else:
        clean.append(pred)

print("Original:", len(preds))
print("Mock:", len(mock))
print("Clean:", len(clean))

# Save mock to isolated file
mock_data = {
    "analyst_name": "2号分析师 (MOCK - 隔离库)",
    "predictions": mock,
    "last_updated": "2026-09-03",
    "note": "Mock predictions isolated from production track_record",
}
MOCK_FILE.write_text(json.dumps(mock_data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Mock saved to:", MOCK_FILE)

# Save clean production file
clean_data = {
    "analyst_name": data.get("analyst_name", "2号分析师"),
    "predictions": clean,
    "last_updated": data.get("last_updated", ""),
}
CLEAN_FILE.write_text(json.dumps(clean_data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Clean saved to:", CLEAN_FILE)

# Replace original
TRACK_FILE.write_text(json.dumps(clean_data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Production track_record cleaned")
