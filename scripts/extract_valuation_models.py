#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量提取投行估值模型（Excel → 知识库），支持分批/续跑。

用法:
    python scripts/extract_valuation_models.py --limit 30    # 提前30个
    python scripts/extract_valuation_models.py --resume      # 续跑未完成的
    python scripts/extract_valuation_models.py --status      # 查看进度
"""

import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("extract_val")

from core.valuation_model_extractor import (
    MODELS_DIR,
    extract_model,
    load_knowledge,
    save_knowledge,
)

STATE_FILE = _ROOT / "data" / "valuation_extract_state.json"


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": []}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def _all_excels():
    files = list(MODELS_DIR.rglob("*.xlsx")) + list(MODELS_DIR.rglob("*.xls"))
    files = [f for f in files if not any(k in f.name for k in ["使用帮助", "速算", "资源包", "工具包"])]
    return files


def run_batch(limit: int = 30, resume: bool = False):
    files = _all_excels()
    state = _load_state()
    done_set = set(state["done"])

    if resume:
        pending = [f for f in files if f.name not in done_set]
    else:
        pending = files[:limit]

    if not pending:
        print(f"无待处理文件（已完成 {len(done_set)}/{len(files)}）")
        return

    # 加载已提取的知识（增量合并）
    knowledge = load_knowledge()
    models = knowledge.get("models", {})

    processed = 0
    for f in pending[:limit]:
        try:
            m = extract_model(f)
            if m and m.get("company"):
                comp = m["company"]
                if comp not in models:
                    models[comp] = m
                else:
                    # 合并补充
                    for k, v in m.items():
                        if v and not models[comp].get(k):
                            models[comp][k] = v
            done_set.add(f.name)
            processed += 1
            if processed % 10 == 0:
                print(f"  进度: {processed}/{min(limit, len(pending))}")
        except Exception as e:
            logger.warning("提取失败 %s: %s", f.name, str(e)[:80])
            done_set.add(f.name)  # 记录失败避免死循环

    state["done"] = sorted(done_set)
    _save_state(state)
    save_knowledge(models)
    print(f"\n完成 {processed} 个，累计 {len(models)} 个模型，已处理 {len(done_set)}/{len(files)} 文件")


def status():
    files = _all_excels()
    state = _load_state()
    knowledge = load_knowledge()
    models = knowledge.get("models", {})
    with_wacc = sum(1 for m in models.values() if m.get("wacc"))
    print(f"Excel 文件: {len(files)}")
    print(f"已处理: {len(state['done'])}")
    print(f"已提取模型: {len(models)}")
    print(f"有WACC: {with_wacc}")
    print(f"知识文件: {knowledge.get('_meta', {})}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--status", action="store_true")
    args = p.parse_args()
    if args.status:
        status()
    else:
        run_batch(args.limit, args.resume)
