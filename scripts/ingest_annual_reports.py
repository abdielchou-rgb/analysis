#!/usr/bin/env python
"""
Ingest annual report TXT files from Baidu Netdisk into golden sample structure.

Source: D:\\BaiduNetdiskDownload\\小说\\【A025】上市公司报告
Format: {stock_code}_{year}_{company}_{report_type}_{date}.txt (UTF-8, ~593 files, 113 companies, 2018-2024)

Output:
  benchmark/golden_raw/annual_reports/*.txt   - raw archive (verbatim copy)
  benchmark/golden/annual_reports/*.md        - text-as-markdown (no conversion needed)
"""

import shutil
from pathlib import Path

SRC = Path(r"D:\BaiduNetdiskDownload\小说\【A025】上市公司报告")
RAW_DST = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_raw\annual_reports")
MD_DST = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden\annual_reports")


def main():
    files = sorted(SRC.glob("*.txt"))
    print(f"Source files: {len(files)}")
    RAW_DST.mkdir(parents=True, exist_ok=True)
    MD_DST.mkdir(parents=True, exist_ok=True)

    copied_raw = copied_md = skipped_md = 0
    errors = []

    for f in files:
        # 1) Raw archive copy
        raw_target = RAW_DST / f.name
        if not raw_target.exists() or raw_target.stat().st_size != f.stat().st_size:
            shutil.copy2(f, raw_target)
            copied_raw += 1

        # 2) Golden markdown copy (TXT is plain text; valid as .md input)
        md_target = MD_DST / (f.stem + ".md")
        if md_target.exists():
            skipped_md += 1
            continue
        try:
            text = f.read_text(encoding="utf-8")
            if len(text.strip()) < 1000:
                errors.append(f"{f.name}: too short ({len(text)} chars)")
                continue
            header = (
                f"---\n"
                f"source: annual_report_txt\n"
                f"stock_code: {f.stem.split('_')[0]}\n"
                f"year: {f.stem.split('_')[1]}\n"
                f"orig_file: {f.name}\n"
                f"---\n\n"
            )
            md_target.write_text(header + text, encoding="utf-8")
            copied_md += 1
        except UnicodeDecodeError:
            errors.append(f"{f.name}: not UTF-8")
        except Exception as e:
            errors.append(f"{f.name}: {e}")

    print(f"Raw copied: {copied_raw}")
    print(f"MD created: {copied_md}, skipped (existing): {skipped_md}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors[:10]:
            print(f"  {e}")


if __name__ == "__main__":
    main()
