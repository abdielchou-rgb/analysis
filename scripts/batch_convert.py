#!/usr/bin/env python
"""
MinerU Batch Converter — PDF 批量转 Markdown

用法:
    python scripts/batch_convert.py --input-dir benchmark/golden_raw --output-dir benchmark/golden
    python scripts/batch_convert.py --input-dir benchmark/golden_raw/listed_company --output-dir benchmark/golden/listed_company --recursive
    python scripts/batch_convert.py --file benchmark/golden_raw/贵州茅台_cicc.pdf --output-dir benchmark/golden/listed_company
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check_mineru_installed() -> bool:
    """检查 mineru 是否安装"""
    try:
        result = subprocess.run(["mineru", "--version"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_mineru() -> bool:
    """尝试安装 mineru"""
    print("Installing mineru...")
    try:
        # 优先用 pip
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "mineru", "-q"
        ], capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print("✓ mineru installed via pip")
            return True
    except Exception as e:
        print(f"Pip install failed: {e}")
    
    # 尝试 conda
    try:
        result = subprocess.run([
            "conda", "install", "-c", "conda-forge", "mineru", "-y"
        ], capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print("✓ mineru installed via conda")
            return True
    except Exception:
        pass
    
    return False


def convert_single_pdf(pdf_path: Path, output_dir: Path, 
                       backend: str = "pipeline", 
                       lang: str = "ch",
                       formula: bool = True,
                       table: bool = True) -> dict:
    """转换单个 PDF 文件"""
    result = {
        "pdf": str(pdf_path),
        "success": False,
        "output_dir": "",
        "md_file": "",
        "error": "",
        "duration_sec": 0
    }
    
    start_time = datetime.now()
    
    # 创建输出子目录（以 PDF 文件名命名）
    stem = pdf_path.stem
    out_subdir = output_dir / stem
    out_subdir.mkdir(parents=True, exist_ok=True)
    
    # 构建 mineru 命令
    cmd = [
        "mineru",
        "-p", str(pdf_path),
        "-o", str(out_subdir),
        "-b", backend,
        "-l", lang,
    ]
    if formula:
        cmd.append("--formula")
    if table:
        cmd.append("--table")
    
    try:
        # 运行转换
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        duration = (datetime.now() - start_time).total_seconds()
        result["duration_sec"] = round(duration, 1)
        
        if proc.returncode == 0:
            # 查找生成的 markdown 文件
            md_files = list(out_subdir.rglob("*.md"))
            if md_files:
                # 通常有一个主 md 文件
                main_md = max(md_files, key=lambda f: f.stat().st_size)
                result["success"] = True
                result["output_dir"] = str(out_subdir)
                result["md_file"] = str(main_md)
                print(f"  ✓ {pdf_path.name} -> {main_md.name} ({duration:.1f}s)")
            else:
                result["error"] = "No markdown output found"
                print(f"  ✗ {pdf_path.name}: No MD output")
        else:
            result["error"] = proc.stderr[:500]
            print(f"  ✗ {pdf_path.name}: {proc.stderr[:200]}")
            
    except subprocess.TimeoutExpired:
        result["error"] = "Timeout (300s)"
        print(f"  ✗ {pdf_path.name}: Timeout")
    except Exception as e:
        result["error"] = str(e)
        print(f"  ✗ {pdf_path.name}: {e}")
    
    return result


def batch_convert(input_dir: Path, output_dir: Path, 
                  recursive: bool = False,
                  pattern: str = "*.pdf",
                  max_workers: int = 4,
                  backend: str = "pipeline",
                  lang: str = "ch") -> List[dict]:
    """批量转换"""
    # 收集所有 PDF 文件
    if recursive:
        pdf_files = list(input_dir.rglob(pattern))
    else:
        pdf_files = list(input_dir.glob(pattern))
    
    if not pdf_files:
        print(f"No PDF files found in {input_dir}")
        return []
    
    print(f"Found {len(pdf_files)} PDF files")
    print(f"Output directory: {output_dir}")
    print(f"Workers: {max_workers}")
    print("-" * 60)
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(convert_single_pdf, pdf, output_dir, backend, lang): pdf 
            for pdf in pdf_files
        }
        
        for future in as_completed(futures):
            pdf = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({
                    "pdf": str(pdf),
                    "success": False,
                    "error": str(e)
                })
    
    return results


def post_process_markdown(output_dir: Path, rename_to_standard: bool = True):
    """后处理：整理 markdown 文件到标准位置"""
    print("\nPost-processing markdown files...")
    
    for subdir in output_dir.iterdir():
        if not subdir.is_dir():
            continue
        
        # 查找 markdown 文件
        md_files = list(subdir.rglob("*.md"))
        if not md_files:
            continue
        
        # 选择最大的 md 文件作为主文件
        main_md = max(md_files, key=lambda f: f.stat().st_size)
        
        if rename_to_standard:
            # 重命名为标准格式：{stem}.md 放在 output_dir 直接下
            target = output_dir / f"{subdir.name}.md"
            if target.exists():
                target.unlink()
            shutil.move(str(main_md), str(target))
            print(f"  Moved: {main_md.name} -> {target.name}")
        else:
            # 保留在子目录，但创建软链接或复制
            target = output_dir / f"{subdir.name}.md"
            shutil.copy2(main_md, target)
            print(f"  Copied: {main_md.name} -> {target.name}")
    
    print("Post-processing complete.")


def generate_manifest(output_dir: Path, results: List[dict]) -> Path:
    """生成转换清单"""
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "total_files": len(results),
        "successful": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "files": results
    }
    
    manifest_path = output_dir / "conversion_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nManifest saved: {manifest_path}")
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description="Batch convert PDF to Markdown using MinerU")
    parser.add_argument("--input-dir", "-i", help="Input directory containing PDFs")
    parser.add_argument("--input-file", "-f", help="Single PDF file to convert")
    parser.add_argument("--output-dir", "-o", default="benchmark/golden", help="Output directory")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recursive search")
    parser.add_argument("--pattern", default="*.pdf", help="File pattern")
    parser.add_argument("--workers", "-w", type=int, default=4, help="Max parallel workers")
    parser.add_argument("--backend", default="pipeline", choices=["pipeline", "vlm"], help="MinerU backend")
    parser.add_argument("--lang", default="ch", choices=["ch", "en", "korean", "japan"], help="Language")
    parser.add_argument("--no-formula", action="store_true", help="Disable formula extraction")
    parser.add_argument("--no-table", action="store_true", help="Disable table extraction")
    parser.add_argument("--post-process", action="store_true", help="Post-process to standard locations")
    parser.add_argument("--install", action="store_true", help="Install mineru if missing")
    
    args = parser.parse_args()
    
    # 检查/安装 mineru
    if not check_mineru_installed():
        print("MinerU not found.")
        if args.install:
            if not install_mineru():
                print("Failed to install mineru. Please install manually: pip install mineru")
                sys.exit(1)
        else:
            print("Install with: pip install mineru")
            print("Or run with --install flag")
            sys.exit(1)
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    formula = not args.no_formula
    table = not args.no_table
    
    if args.input_file:
        # 单文件转换
        pdf_path = Path(args.input_file)
        if not pdf_path.exists():
            print(f"File not found: {pdf_path}")
            sys.exit(1)
        result = convert_single_pdf(pdf_path, output_dir, args.backend, args.lang, formula, table)
        if result["success"]:
            print(f"Success: {result['md_file']}")
        else:
            print(f"Failed: {result['error']}")
            sys.exit(1)
    elif args.input_dir:
        # 批量转换
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            print(f"Input directory not found: {input_dir}")
            sys.exit(1)
        
        results = batch_convert(
            input_dir, output_dir, 
            recursive=args.recursive,
            pattern=args.pattern,
            max_workers=args.workers,
            backend=args.backend,
            lang=args.lang
        )
        
        # 统计
        success = sum(1 for r in results if r.get("success"))
        failed = len(results) - success
        print(f"\n{'='*60}")
        print(f"Total: {len(results)} | Success: {success} | Failed: {failed}")
        
        if failed > 0:
            print("\nFailed files:")
            for r in results:
                if not r.get("success"):
                    print(f"  - {Path(r['pdf']).name}: {r.get('error', 'Unknown')}")
        
        # 生成清单
        generate_manifest(output_dir, results)
        
        # 后处理
        if args.post_process:
            post_process_markdown(output_dir)
        
        if failed > 0:
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()