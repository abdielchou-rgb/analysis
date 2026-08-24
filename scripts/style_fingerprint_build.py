# -*- coding: utf-8 -*-
"""style_fingerprint_build.py — 指纹档案冷启动构建器。

用法：
  # 从 tests/golden 全集构建 'golden_deep' 基准档案
  python scripts/style_fingerprint_build.py --style golden_deep \
      --files "tests/golden/*.md"

  # 未来语料就绪后按机构构建：
  python scripts/style_fingerprint_build.py --style cicc_corpus --files "corpus/cicc/*.md"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.style_fingerprint import build_from_files  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", required=True)
    ap.add_argument("--files", nargs="+", required=True, help="md 文件或 glob")
    a = ap.parse_args()

    paths: list[Path] = []
    for pat in a.files:
        p = Path(pat)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.md")))
        else:
            paths.extend(sorted(Path().glob(pat)))
    paths = [p for p in paths if p.exists() and p.stat().st_size > 1000]
    if not paths:
        print("no input files")
        return 1

    fp = build_from_files(paths)
    out = _ROOT / "data" / "fingerprints" / f"{a.style}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fp, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"fingerprint[{a.style}] -> {out}")
    print(json.dumps({k: v for k, v in fp.items() if k != "connective_spectrum"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
