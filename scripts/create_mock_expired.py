"""Create mock expired predictions for P0-6 MC validation rehearsal.

Inserts 5 predictions with made_date=2026-01-01, expiry_date=2026-09-01
that can be resolved with real or mock prices.
"""

import json
from pathlib import Path
from datetime import datetime

TRACK_RECORD = Path("core/data/forward_picks/track_record.json")

MOCK_EXPIRED = [
    {
        "id": "mock_001_宁德时代",
        "asset": "300750",
        "report_type": "listed_company",
        "industry": "新能源",
        "direction": "bullish",
        "bold_call": "目标价260元",
        "target_price": "260",
        "falsification": "低于200元",
        "time_horizon": "6m",
        "made_date": "2026-01-15",
        "outcome_date": "2026-07-15",
        "outcome": "pending",
        "outcome_detail": "",
        "confidence_at_make": 0.7,
    },
    {
        "id": "mock_002_贵州茅台",
        "asset": "600519",
        "report_type": "listed_company",
        "industry": "白酒",
        "direction": "bullish",
        "bold_call": "目标价1900元",
        "target_price": "1900",
        "falsification": "低于1500元",
        "time_horizon": "6m",
        "made_date": "2026-02-01",
        "outcome_date": "2026-08-01",
        "outcome": "pending",
        "outcome_detail": "",
        "confidence_at_make": 0.6,
    },
    {
        "id": "mock_003_比亚迪",
        "asset": "002594",
        "report_type": "listed_company",
        "industry": "汽车",
        "direction": "bullish",
        "bold_call": "目标价350元",
        "target_price": "350",
        "falsification": "低于250元",
        "time_horizon": "6m",
        "made_date": "2026-01-20",
        "outcome_date": "2026-07-20",
        "outcome": "pending",
        "outcome_detail": "",
        "confidence_at_make": 0.65,
    },
    {
        "id": "mock_004_中芯国际",
        "asset": "688981",
        "report_type": "listed_company",
        "industry": "半导体",
        "direction": "bearish",
        "bold_call": "目标价70元",
        "target_price": "70",
        "falsification": "高于100元",
        "time_horizon": "6m",
        "made_date": "2026-02-10",
        "outcome_date": "2026-08-10",
        "outcome": "pending",
        "outcome_detail": "",
        "confidence_at_make": 0.55,
    },
    {
        "id": "mock_005_药明康德",
        "asset": "603259",
        "report_type": "listed_company",
        "industry": "医药",
        "direction": "bullish",
        "bold_call": "目标价130元",
        "target_price": "130",
        "falsification": "低于90元",
        "time_horizon": "6m",
        "made_date": "2026-01-25",
        "outcome_date": "2026-07-25",
        "outcome": "pending",
        "outcome_detail": "",
        "confidence_at_make": 0.6,
    },
]


def main():
    with open(TRACK_RECORD, "r", encoding="utf-8") as f:
        data = json.load(f)

    preds = data.get("predictions", [])

    # Check if mock already exists
    existing_ids = {p["id"] for p in preds}
    added = 0
    for mock in MOCK_EXPIRED:
        if mock["id"] not in existing_ids:
            preds.append(mock)
            added += 1

    data["predictions"] = preds
    data["last_updated"] = datetime.now().isoformat()

    with open(TRACK_RECORD, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Added {added} mock expired predictions (total: {len(preds)})")


if __name__ == "__main__":
    main()
