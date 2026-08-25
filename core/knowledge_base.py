# -*- coding: utf-8 -*-
"""knowledge_base.py — 知识库 RAG 管道（K-07）。

P3-B 最高优先级：652 个 md 文件（9 大类券商研报/方法论/估值方法）→
chunk → SQLite FTS5 全文索引 → 按相关度检索 top-k → 注入写作 prompt。

设计：
- 零外部依赖（SQLite 内置 FTS5，不需要向量库）
- chunk 在段落边界切分，保留上下文完整性
- 元数据含来源路径/类别/chunk 序号，支持溯源引用 [KB:path#chunk]
"""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger("2hao.kb")

_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = _ROOT / "data" / "知识库"
DB_PATH = _ROOT / "data" / "kb_fts.db"
CHUNK_SIZE = 500
_CHUNK_OVERLAP = 50

_AIGC_HEADER = re.compile(r"^---\s*\nAIGC:.*?(?:\n---|\n\n)", re.S | re.M)


def _clean_md(raw: str) -> str:
    """剥离 AIGC 元数据头和 HTML 注释。"""
    raw = _AIGC_HEADER.sub("", raw)
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    return raw.strip()


def _chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """在段落边界切分，保留上下文重叠。"""
    paras = text.split("\n\n")
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) > size and buf:
            chunks.append(buf.strip())
            # 重叠：保留最后 ~50 字符作为上下文衔接
            tail = buf[-_CHUNK_OVERLAP:]
            buf = tail + "\n" + p
        else:
            buf = (buf + "\n\n" + p).strip()
    if buf.strip():
        chunks.append(buf.strip())
    return [c for c in chunks if len(c) > 50]  # 过滤太短的碎片


def _category_from_path(p: Path) -> str:
    """从路径提取一级目录名作为类别标签。"""
    try:
        rel = p.relative_to(KB_DIR)
        return rel.parts[0] if rel.parts else "unknown"
    except Exception:
        return "unknown"


def build_index(force: bool = False) -> int:
    """扫描 KB_DIR → chunk → 写入 FTS5 索引。返回总 chunk 数。

    force=True 时重建索引；否则增量（跳过已索引文件）。
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kb_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT,
            category TEXT,
            chunk_idx INTEGER,
            content TEXT,
            content_hash TEXT UNIQUE,
            file_mtime REAL
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(
            content, source_path, category,
            content='kb_chunks', content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
    """)
    conn.commit()

    if not KB_DIR.exists():
        conn.close()
        return 0

    # 已索引文件集合（按 mtime 判断是否需要更新）
    indexed = {}
    try:
        for row in conn.execute("SELECT source_path, file_mtime FROM kb_chunks"):
            indexed[row[0]] = row[1]
    except Exception:
        pass

    total = 0
    md_files = sorted(KB_DIR.rglob("*.md"))
    for mf in md_files:
        rel_str = str(mf.relative_to(KB_DIR))
        mtime = mf.stat().st_mtime
        if not force and rel_str in indexed and indexed[rel_str] >= mtime:
            continue
        # 删除旧条目
        conn.execute("DELETE FROM kb_chunks WHERE source_path = ?", (rel_str,))
        conn.execute("DELETE FROM kb_fts WHERE source_path = ?", (rel_str,))
        # 读取 & 清洗 & 切分
        raw = mf.read_text(encoding="utf-8", errors="ignore")
        clean = _clean_md(raw)
        if len(clean) < 100:
            continue
        chunks = _chunk_text(clean)
        cat = _category_from_path(mf)
        for idx, chunk in enumerate(chunks):
            h = hashlib.md5(chunk.encode()).hexdigest()
            try:
                conn.execute(
                    "INSERT INTO kb_chunks (source_path, category, chunk_idx, content, content_hash, file_mtime) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (rel_str, cat, idx, chunk, h, mtime),
                )
                conn.execute(
                    "INSERT INTO kb_fts(rowid, content, source_path, category) VALUES (last_insert_rowid(), ?, ?, ?)",
                    (chunk, rel_str, cat),
                )
                total += 1
            except sqlite3.IntegrityError:
                pass  # duplicate hash
    conn.commit()
    conn.close()
    logger.info("[KB] index built: %d chunks from %d files", total, len(md_files))
    return total


def _indexed_categories(conn) -> list[str]:
    """获取已索引的全部类别。"""
    try:
        return [r[0] for r in conn.execute("SELECT DISTINCT category FROM kb_chunks")]
    except Exception:
        return []


def search(query: str, top_k: int = 5, category: str | None = None) -> list[dict]:
    """FTS5 全文搜索 → [{source, category, snippet, rank}]。"""
    if not DB_PATH.exists():
        build_index()

    conn = sqlite3.connect(str(DB_PATH))
    # FTS5 MATCH 语法：用 OR 连接分词结果提高召回
    terms = re.split(r"[\s,，、]+", query.strip())
    match_expr = " OR ".join(f'"{t}"' for t in terms if t)

    where = "WHERE kb_fts MATCH ?"
    params: list = [match_expr]
    if category:
        where += " AND category = ?"
        params.append(category)
    # V1-fix: 只搜研报相关类目，排除 Excel/PPT 教学
    if not category:
        relevant_cats = tuple(
            c for c in _indexed_categories(conn) if any(kw in c for kw in ("观点", "行业", "估值", "回测", "原始"))
        )
        if relevant_cats:
            placeholders = ",".join("?" for _ in relevant_cats)
            where += f" AND category IN ({placeholders})"
            params.extend(relevant_cats)

    try:
        rows = conn.execute(
            f"""
            SELECT source_path, category, content,
                   bm25(kb_fts) AS rank
            FROM kb_fts {where}
            ORDER BY rank LIMIT ?
        """,
            params + [top_k],
        ).fetchall()
    except Exception:
        rows = []

    conn.close()
    return [
        {
            "source": r[0],
            "category": r[1],
            "snippet": r[2][:300],
            "rank": round(r[3], 2),
        }
        for r in rows
    ]


def ensure_index() -> None:
    """确保索引存在（首次调用时自动构建）。"""
    if not DB_PATH.exists() or DB_PATH.stat().st_size < 4096:
        build_index(force=True)
