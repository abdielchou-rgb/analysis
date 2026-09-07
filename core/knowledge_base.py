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

# P0-3（2026-09-07）：显式检索 allowlist——只搜"研报/方法论"分析素材。
# 01 宏观 / 02 行业 / 03 估值 / 04 回测 / 07 原始文档 / 08 四大审计 / 09 国际投行
# 是分析主通道；05-Excel知识库、06-PPT排版美学 是工具教学素材，非分析引用源，保持排除。
# 此前用"名称关键词"（观点/行业/估值/回测/原始）过滤，01/08/09 三个方法论目录被误杀。
SEARCH_CATEGORY_ALLOWLIST = (
    "01-宏观分析框架",
    "02-行业与公司研究",
    "03-估值与测算",
    "04-回测基线库",
    "07-原始文档提取",
    "08-四大审计方法论",
    "09-国际投行方法论",
)

# P1（2026-09-07）：类别级查询提示——BM25 全局 top-k 会被高体量的
# 03-估值/04-回测基线库淹没，08（17 chunk）/09（10 chunk）方法论目录
# 在任意资产查询下几乎零命中。类别均衡检索为每个放行目录单独出 top-n，
# 并用与本类别语义一致的提示词保证小目录内容真实命中。
_CATEGORY_QUERY_HINTS = {
    "01-宏观分析框架": "宏观 利率 流动性 周期 GDP",
    "02-行业与公司研究": "行业 产业链 景气 竞争格局",
    "03-估值与测算": "估值 DCF 折现 模型 敏感性",
    "04-回测基线库": "估值 判断 结论 方法",
    "07-原始文档提取": "深度研究 行业 公司 分析",
    "08-四大审计方法论": "审计 勾稽 复核 函证 收入确认",
    "09-国际投行方法论": "投行 高盛 摩根 DCF 研报结构",
}

# P1（2026-09-07）：KB 块在写作侧受 kb_str[:1500] 截断约束，而检索结果若按
# 目录编号排序，08/09/01 方法论目录会排在块尾被截断切掉，永远到不了写作者。
# 故在 search_balanced 输出中把方法论目录显式置前，保证截断前先被看到。
METHODOLOGY_DISPLAY_PRIORITY = (
    "08-四大审计方法论",
    "09-国际投行方法论",
    "01-宏观分析框架",
)


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


def _relevant_categories(conn) -> tuple[str, ...]:
    """返回本次检索放行的类别（allowlist 内且已索引）。

    目录改名但保留编号前缀时按前缀纳入并告警，避免静默漏检；
    Excel/PPT 教学目录即使被索引也永不进入检索范围。
    """
    indexed = _indexed_categories(conn)
    allowed_prefixes = {name.split("-", 1)[0] for name in SEARCH_CATEGORY_ALLOWLIST}
    hits: list[str] = []
    for cat in indexed:
        if cat in SEARCH_CATEGORY_ALLOWLIST:
            hits.append(cat)
            continue
        prefix = cat.split("-", 1)[0]
        if prefix in allowed_prefixes:
            logger.warning(
                "[KB] 类别 %r 保留编号前缀但名称已变，按前缀纳入检索；请更新 SEARCH_CATEGORY_ALLOWLIST 以消除告警",
                cat,
            )
            hits.append(cat)
    return tuple(hits)


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
    # P0-3（2026-09-07）：去重后的单次 allowlist 过滤（原三段复制粘贴代码）。
    else:
        relevant_cats = _relevant_categories(conn)
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


def search_balanced(
    query: str,
    categories: tuple[str, ...] | list[str] | None = None,
    per_category: int = 2,
    max_total: int = 14,
) -> list[dict]:
    """类别均衡检索：每个放行类别单独取 top-n，保证小体量方法论目录不被淹没。

    背景（2026-09-07 实证）：真实 FTS 中 04-回测基线库 7.6 万 chunk、
    03-估值 1.7 万 chunk，而 08-四大审计方法论仅 17 chunk、09-国际投行方法论
    仅 10 chunk。纯 BM25 全局 top-k 在任意资产查询下 top-5 几乎全部命中
    03/04，审计/投行方法论"注入成功但实际不可见"。

    本函数按 allowlist 逐类别检索：每个类别先用 FTS5 匹配 [全局查询词 + 类别
    语义提示词]，FTS 命不足时再用 instr() 子串兜底——FTS5 unicode61 不做中文
    分词，连续中文被当作整段 token，"投行/高盛" 等短词只要未被标点恰好切成
    独立 token 就永远匹配不到，方法论文档尤其如此；子串匹配与 token 无关，
    能稳定召回。结果按 METHODOLOGY_DISPLAY_PRIORITY 置前合并去重，方法论
    小目录因此获得与体量无关、且不会被写作侧截断切掉的稳定席位。
    """
    if not DB_PATH.exists():
        build_index()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        raw_wanted = tuple(categories) if categories else _relevant_categories(conn)
        wanted = _order_for_display(raw_wanted)
        if not wanted:
            return []
        # 类别语义提示词只对 allowlist 内目录生效，未知类别退化为全局查询词。
        hint = _CATEGORY_QUERY_HINTS.get
        results: list[dict] = []
        seen_sources: set[str] = set()
        for cat in wanted:
            cat_query = (query + " " + hint(cat, query)).strip()
            terms = [t for t in re.split(r"[\s,，、]+", cat_query) if t]
            rows = _fts_balanced_rows(conn, cat, terms, per_category)
            if len(rows) < per_category:
                rows += _substring_balanced_rows(conn, cat, terms, per_category - len(rows))
            for src, c, content, rank in rows:
                if src in seen_sources:
                    continue
                seen_sources.add(src)
                results.append(
                    {
                        "source": src,
                        "category": c,
                        "snippet": content[:300],
                        "rank": round(float(rank), 2),
                    }
                )
        return results[:max_total]
    finally:
        conn.close()


def _order_for_display(categories) -> tuple[str, ...]:
    """方法论目录置前，避免写作侧 kb_str[:1500] 截断把 08/09/01 切掉。"""
    cats = list(categories)
    head = [c for c in METHODOLOGY_DISPLAY_PRIORITY if c in cats]
    return tuple(head + [c for c in cats if c not in head])


def _fts_balanced_rows(conn, category: str, terms: list[str], want: int) -> list[tuple]:
    """单类别 FTS5 top 行（按 source 去重，至多 want 个不同来源）。"""
    if want <= 0 or not terms:
        return []
    clean = [t.replace('"', "") for t in terms]
    clean = [t for t in clean if t]
    if not clean:
        return []
    match_expr = " OR ".join(f'"{t}"' for t in clean)
    try:
        rows = conn.execute(
            """
            SELECT source_path, category, content, bm25(kb_fts) AS rank
            FROM kb_fts
            WHERE kb_fts MATCH ? AND category = ?
            ORDER BY rank LIMIT ?
            """,
            (match_expr, category, max(want * 3, 10)),
        ).fetchall()
    except Exception:
        return []
    out, seen = [], set()
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        out.append((r[0], r[1], r[2], r[3]))
        if len(out) >= want:
            break
    return out


def _substring_balanced_rows(conn, category: str, terms: list[str], want: int) -> list[tuple]:
    """单类别子串兜底：FTS5 中文分词不可达时用 instr() 保证方法论目录可见。

    只回查 kb_chunks 基础表（不依赖 FTS 索引格式/tokenizer），命中数越多的
    chunk 排越前；rank 记作负命中数以保持"越小越相关"的语义。
    """
    if want <= 0:
        return []
    needles = list(dict.fromkeys(t for t in terms if len(t) >= 2))
    if not needles:
        return []
    counters = " + ".join("(instr(content, ?) > 0)" for _ in needles)
    clauses = " OR ".join("instr(content, ?) > 0" for _ in needles)
    # 参数顺序须与 SQL 文本中 ? 的出现顺序一致：SELECT 计数、WHERE、LIMIT。
    params = needles + [category] + needles + [max(want * 2, 5)]
    sql = (
        "SELECT source_path, category, content, (" + counters + ") AS hits "
        "FROM kb_chunks WHERE category = ? AND (" + clauses + ") "
        "ORDER BY hits DESC, id ASC LIMIT ?"
    )
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        return []
    out, seen = [], set()
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        out.append((r[0], r[1], r[2], -r[3]))
        if len(out) >= want:
            break
    return out


def ensure_index() -> None:
    """确保索引存在（首次调用时自动构建）。"""
    if not DB_PATH.exists() or DB_PATH.stat().st_size < 4096:
        build_index(force=True)
