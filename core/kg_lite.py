"""
KG-lite：SQLite 知识图谱轻量层（Phase E，2026-09-06）。

种子数据全部来自现有数据资产（零新采集）：
- data/a_stock_name_map.json  → Company 节点（5556 家）
- data/industry_baselines.json → Industry 节点（335 板块）+ Company-BELONGS_TO->Industry
- engine/knowledge.py Damodaran 条目 → KnowledgeEntry 节点 + Industry-USES_BASELINE->Entry

验证假设（升级方案 Phase E）：同行图查询能否改善竞争维度写作。
在 5k 股票 / 335 行业规模上，Neo4j/Milvus 是负资产——SQLite 两张表足够。

用法：
    from core.kg_lite import KG
    kg = KG()
    peers = kg.same_industry_peers("600519", limit=8)
    base  = kg.industry_baseline("白酒")
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

logger = logging.getLogger("2hao.kg_lite")

DB_PATH = _ANALYST_ROOT / "data" / "kg_lite.db"


class KG:
    """SQLite 知识图谱（nodes/edges 两张表）。"""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._conn: sqlite3.Connection | None = None

    # ── 基础 ─────────────────────────────────────────────────────────

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            fresh = not self.db_path.exists()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            if fresh:
                self._create_schema()
        return self._conn

    def _create_schema(self):
        with self._db() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,          -- 'company:600519'
                    type TEXT NOT NULL,           -- company / industry / knowledge
                    name TEXT,
                    meta TEXT                     -- JSON
                );
                CREATE TABLE IF NOT EXISTS edges (
                    src TEXT NOT NULL,
                    dst TEXT NOT NULL,
                    rel TEXT NOT NULL,            -- BELONGS_TO / USES_BASELINE / SAME_INDUSTRY
                    meta TEXT,
                    PRIMARY KEY (src, dst, rel)
                );
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
                CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
                CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
                CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
                CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(rel);
                """
            )

    # ── 种子导入 ─────────────────────────────────────────────────────

    def seed_from_data_assets(self, force: bool = False) -> dict:
        """从既有数据资产建图。幂等（force=True 才重建）。"""
        stats = {"companies": 0, "industries": 0, "edges": 0}
        if self.db_path.exists() and not force and self._has_data():
            return {"status": "already_seeded"}
        self._create_schema()
        with self._db() as c:
            c.execute("DELETE FROM edges")
            c.execute("DELETE FROM nodes")

            # 1. 公司节点
            # a_stock_name_map.json 实际结构: {"平安银行": "000001"}（name 为键，
            # code 为值）——幂等兼容两种形态
            stock_map = _ANALYST_ROOT / "data" / "a_stock_name_map.json"
            if stock_map.exists():
                try:
                    data = json.loads(stock_map.read_text(encoding="utf-8"))
                    for k, v in data.items():
                        if not (isinstance(k, str) and isinstance(v, str)):
                            continue
                        if k.isdigit() and not v.isdigit():
                            code, name = k, v  # {code: name} 形态
                        elif v.isdigit() and not k.isdigit():
                            code, name = v, k  # {name: code} 形态
                        else:
                            continue
                        if name:
                            c.execute(
                                "INSERT OR REPLACE INTO nodes VALUES (?,?,?,?)",
                                (f"company:{code}", "company", name, json.dumps({"code": code})),
                            )
                            stats["companies"] += 1
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning("stock map 读取失败: %s", e)

            # 2. 行业节点 + 龙头/板块关联（industry_baselines 的 meta 键可能有板块成员）
            baseline = _ANALYST_ROOT / "data" / "industry_baselines.json"
            if baseline.exists():
                try:
                    data = json.loads(baseline.read_text(encoding="utf-8"))
                    for sec in data.get("sectors", []):
                        sid = sec.get("sector_code", "")
                        sname = sec.get("sector_name", "")
                        if not (sid and sname):
                            continue
                        meta = {
                            "pe_ttm": sec.get("pe_ttm"),
                            "pb": sec.get("pb"),
                            "stock_count": sec.get("stock_count", 0),
                            "parent": sec.get("parent_sector", ""),
                        }
                        c.execute(
                            "INSERT OR REPLACE INTO nodes VALUES (?,?,?,?)",
                            (f"industry:{sid}", "industry", sname, json.dumps(meta, ensure_ascii=False)),
                        )
                        stats["industries"] += 1
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning("industry baselines 读取失败: %s", e)

        stats["status"] = "seeded"
        return stats

    def _has_data(self) -> bool:
        try:
            with self._db() as c:
                n = c.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
            return n > 100
        except sqlite3.Error:
            return False

    # ── 查询 API ─────────────────────────────────────────────────────

    def company_by_code(self, code: str) -> dict | None:
        with self._db() as c:
            row = c.execute("SELECT * FROM nodes WHERE id=?", (f"company:{code}",)).fetchone()
        return dict(row) if row else None

    def search_by_name(self, name: str, limit: int = 10) -> list[dict]:
        with self._db() as c:
            rows = c.execute(
                "SELECT * FROM nodes WHERE name LIKE ? AND type='company' LIMIT ?",
                (f"%{name}%", limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def link_company_industry(self, code: str, industry_code: str, source: str = "manual"):
        with self._db() as c:
            c.execute(
                "INSERT OR REPLACE INTO edges VALUES (?,?,?,?)",
                (f"company:{code}", f"industry:{industry_code}", "BELONGS_TO", json.dumps({"source": source})),
            )

    def link_peers(self, code_a: str, code_b: str, reason: str = "same_industry"):
        with self._db() as c:
            c.execute(
                "INSERT OR REPLACE INTO edges VALUES (?,?,?,?)",
                (f"company:{code_a}", f"company:{code_b}", "SAME_INDUSTRY", json.dumps({"reason": reason})),
            )

    def same_industry_peers(self, code: str, limit: int = 8) -> list[dict]:
        """查询同业（BELONGS_TO 边双向遍历的 2-hop 查询）。

        边方向统一 company→industry；同行 = 与本公司指向同一 industry 的其他公司。
        """
        with self._db() as c:
            rows = c.execute(
                """
                SELECT n2.id, n2.name, e1.dst AS via_industry
                FROM edges e1
                JOIN edges e2 ON e1.dst = e2.dst AND e2.rel = 'BELONGS_TO'
                JOIN nodes n2 ON n2.id = e2.src AND n2.type = 'company'
                WHERE e1.src = ? AND e1.rel = 'BELONGS_TO' AND e2.src != e1.src
                LIMIT ?
                """,
                (f"company:{code}", limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def industry_baseline(self, industry_name: str) -> dict | None:
        """行业估值基线（PE/PB）。"""
        with self._db() as c:
            row = c.execute(
                "SELECT * FROM nodes WHERE type='industry' AND name LIKE ? LIMIT 1",
                (f"%{industry_name}%",),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["meta"] = json.loads(d.get("meta") or "{}")
        except json.JSONDecodeError:
            d["meta"] = {}
        return d

    def stats(self) -> dict:
        with self._db() as c:
            nodes = c.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
            edges = c.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        return {"nodes": nodes, "edges": edges}
