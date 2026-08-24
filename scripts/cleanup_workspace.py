#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卫生清理脚本 — 清理数据垃圾与敏感残留。

V83 审计（2026-08-03）发现：
  - .env.bak / .env.bak_bom：含 API Key 的敏感备份文件（安全风险）
  - .fuse_hidden*：FUSE 临时垃圾（曾 4180 个 / 130MB）
  - *.corrupt_backup：数据库损坏备份残留
  - *.tmp：临时文件

用法：
  python scripts/cleanup_workspace.py            # 全量清理（打印删除清单）
  python scripts/cleanup_workspace.py --dry-run  # 只列出不删除
"""
import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# 敏感文件（安全风险，删除）
_SENSITIVE = [".env.bak", ".env.bak_bom", "api_key.txt.bak"]
# 垃圾模式（FUSE 残留 / 损坏备份 / 临时文件）
_GARBAGE_PATTERNS = [".fuse_hidden*", "*.corrupt_backup", "*.tmp",
                     "*.swp", "*.swo", ".DS_Store"]
# 扫描目录（排除 .git 和虚拟环境）
_SCAN_DIRS = [_ROOT / "data", _ROOT / "output", _ROOT / "outputs",
              _ROOT / "logs", _ROOT / "docs", _ROOT / "scripts"]


def collect_targets() -> list:
    targets = []
    # 根目录敏感文件
    for f in _SENSITIVE:
        p = _ROOT / f
        if p.exists():
            targets.append(p)
    # 垃圾模式
    for d in _SCAN_DIRS:
        if not d.exists():
            continue
        for pat in _GARBAGE_PATTERNS:
            targets.extend(d.glob(pat))
    # 去重
    return sorted(set(targets))


def main():
    ap = argparse.ArgumentParser(description="卫生清理")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    targets = collect_targets()
    total_size = sum(p.stat().st_size for p in targets if p.is_file())
    print(f"发现 {len(targets)} 个待清理文件，共 {total_size/1024/1024:.1f} MB")

    if args.dry_run:
        print("[DRY-RUN] 未删除，清单如下：")
        for p in targets[:20]:
            print(f"  {p.relative_to(_ROOT)} ({p.stat().st_size/1024:.0f}KB)")
        if len(targets) > 20:
            print(f"  ... 共 {len(targets)} 个")
        return

    removed = 0
    for p in targets:
        try:
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
            removed += 1
            print(f"  已删除 {p.relative_to(_ROOT)}")
        except Exception as e:
            print(f"  跳过 {p.relative_to(_ROOT)}: {e}")

    print(f"\n完成：删除 {removed}/{len(targets)} 个文件")
    if removed < len(targets):
        print("⚠️ 部分文件删除失败（可能被占用或权限限制），请在用户机重试")


if __name__ == "__main__":
    main()
