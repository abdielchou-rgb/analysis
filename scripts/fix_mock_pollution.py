#!/usr/bin/env python
"""Check and fix mock data pollution in track_record.json."""

import json
from pathlib import Path

p = Path(r"D:\Claude\projects\2hao-analyst\core\data\forward_picks\track_record.json")
if not p.exists():
    print("track_record.json not found")
    exit()

data = json.loads(p.read_text(encoding="utf-8"))
entries = data if isinstance(data, list) else data.get("entries", [])

# Find mock entries
mock = []
real = []
for e in entries:
    is_mock = e.get("source") == "mock" or "mock" in str(e.get("id", "")).lower() or "MC" in str(e.get("bold_call", ""))
    if is_mock:
        mock.append(e)
    else:
        real.append(e)

print("Total entries:", len(entries))
print("Mock entries:", len(mock))
print("Real entries:", len(real))

if mock:
    print("\nMock entries found:")
    for e in mock[:5]:
        eid = e.get("id", "N/A")
        bc = str(e.get("bold_call", ""))[:60]
        print("  id=%s, bold_call=%s" % (eid, bc))

    # Move mock to isolated file
    mock_path = p.parent / "mock_track_record.json"
    mock_path.write_text(json.dumps(mock, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nMock entries moved to:", mock_path)

    # Keep only real entries
    if isinstance(data, list):
        clean = real
    else:
        clean = dict(data)
        clean["entries"] = real
    p.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Production track_record cleaned: %d real entries" % len(real))
else:
    print("\nNo mock entries found - production data is clean")
