"""
2hao-analyst Chart Data Adapter
Flattens nested compute data into {label: value} for chart_engine.
"""

import logging
from typing import Any

logger = logging.getLogger("2hao.chart_adapter")


def flatten_data(data: Any, prefix: str = "", max_items: int = 15) -> dict[str, float]:
    result = {}
    if data is None:
        return result
    if isinstance(data, dict):
        for key, val in data.items():
            np = f"{prefix}_{key}" if prefix else str(key)
            result.update(flatten_data(val, np, max_items))
            if len(result) >= max_items:
                break
    elif isinstance(data, (int, float)):
        if prefix:
            result[prefix] = float(data)
    elif isinstance(data, str):
        c = data.replace(",", "").replace("\uff0c", "").replace("%", "").replace("\u4ebf", "").strip()
        try:
            result[prefix] = float(c)
        except (ValueError, TypeError):
            pass
    elif isinstance(data, list):
        for i, item in enumerate(data):
            result.update(flatten_data(item, f"{prefix}_{i}", max_items))
            if len(result) >= max_items:
                break
    return result


def generate_chart_data(compute_results: dict[str, Any]) -> dict[str, float]:
    flat = flatten_data(compute_results)
    if not flat:
        return None
    return dict(sorted(flat.items(), key=lambda x: abs(x[1]), reverse=True))
