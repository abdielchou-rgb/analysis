# -*- coding: utf-8 -*-
"""Import 图扫描器 v2 — 精确 full-module-path 匹配"""
import ast
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
EXCLUDE_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", "node_modules", "temp", "output", "logs"}


def iter_py_files():
    for p in ROOT.rglob("*.py"):
        if set(p.parts) & EXCLUDE_DIRS:
            continue
        # 排除自己以免误报
        if p.name == "import_graph_scanner.py":
            continue
        yield p


def module_name_of(path):
    try:
        rel = path.relative_to(ROOT)
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts) if parts else None
    except (ValueError, IndexError):
        return None


def scan_file(path):
    imports = set()
    strings = set()
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except Exception:
        return imports, strings

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.add(node.module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.add(node.value)

    return imports, strings


def main():
    graph = defaultdict(set)
    strings_graph = defaultdict(set)
    all_py = list(iter_py_files())
    print(f"[SCAN] Scanning {len(all_py)} files")

    for f in all_py:
        imports, strings = scan_file(f)
        for imp in imports:
            graph[imp].add(str(f.relative_to(ROOT)))
        for s in strings:
            strings_graph[s].add(str(f.relative_to(ROOT)))

    return graph, strings_graph


def is_candidate_referenced(module_path, graph, strings_graph):
    mod_name = module_name_of(module_path)
    if not mod_name:
        return True, "cannot parse module name"

    stem = module_path.stem
    skip_modules = {"__init__", "conftest", "__main__"}
    if stem in skip_modules:
        return True, "special module name"

    # 1. 完整模块路径精确静态导入
    if mod_name in graph:
        return True, f"static import: {list(graph[mod_name])[:3]}"

    # 2. 动态字符串精确匹配完整模块路径
    for s, files in strings_graph.items():
        if mod_name in s:
            return True, f"string ref '{s[:60]}' in: {list(files)[:3]}"

    # 3. 文件名 stem 匹配（防止 scripts/ 里的脚本名被 import 为 from x import y）
    if stem and len(stem) > 3:
        if stem in graph:
            return True, f"stem import: {list(graph[stem])[:3]}"
        for s, files in strings_graph.items():
            if stem in s and not s.startswith(("import", "from")):
                return True, f"stem string '{s[:60]}' in: {list(files)[:3]}"

    # 4. 入口/测试保留
    p = module_path.relative_to(ROOT)
    if p.name in ("main.py", "scheduler.py") or "tests" in p.parts:
        return True, "entry/test preserved"

    return False, ""


if __name__ == "__main__":
    candidates_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("candidates.txt")
    lines = candidates_file.read_text(encoding="utf-8").splitlines()
    candidates = []
    for line in lines:
        line = line.strip()
        if line:
            candidates.append(ROOT / line)

    graph, strings_graph = main()
    unreferenced = []
    referenced = []

    for c in candidates:
        is_ref, reason = is_candidate_referenced(c, graph, strings_graph)
        if is_ref:
            referenced.append((c, reason))
        else:
            unreferenced.append(c)

    print(f"\n[UNREFERENCED] safe-to-delete: {len(unreferenced)}")
    for f in unreferenced:
        print(f"  OK {str(f.relative_to(ROOT))[:80]}")

    print(f"\n[REFERENCED] still-referenced: {len(referenced)}")
    # 先写入清单，再打印，保证 Unicode 异常不影响后续步骤
    out = ROOT / "deletion_candidates_verified.txt"
    out.write_text("\n".join(str(f.relative_to(ROOT)) for f in unreferenced), encoding="utf-8")
    print(f"[WRITE] verified list saved: {out.name} ({len(unreferenced)} files)")

    for f, reason in referenced:
        safe_reason = reason.encode("ascii", "replace").decode()[:100]
        print(f"  FAIL {str(f.relative_to(ROOT))[:60]} -- {safe_reason}")
