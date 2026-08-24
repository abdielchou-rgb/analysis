"""
V50+ T2x — 修改引擎与修改学习回路（第一性原理新增）

核心能力：
1. 六类修改分类——不是整段重写，是精确手术
2. 修改学习持久化——每次修改记录为 EditCase
3. 1,000+ case 后，系统从历史修改中学习分析师的偏好
4. 同类场景自动建议——"上次你在这个场景下选择了调低措辞强度"
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.models import (
    EditCase,
    EditingType,
)


class EditClassifier:
    """
    修改分类器——确定"不对"的类型。

    输入："第三段的判断太激进了，直销占比不一定能到50%"
    输出：{type: biased_judgment, target_section: "sec_03", action: "调低判断措辞强度"}

    实现方式：关键词匹配 + 简单规则（可扩展为轻量分类器）
    """

    @staticmethod
    def classify(instruction: str, correction_type: str | None = None) -> tuple[EditingType, str]:
        """
        分类一条修改指令。

        如果调用方显式指定了类型（下拉菜单），直接使用。
        如果未指定，从自然语言的修改指令中推断。
        """
        if correction_type:
            try:
                return EditingType(correction_type), ""
            except ValueError:
                pass

        # 从自然语言推断
        text = instruction

        # 证据弱
        if any(w in text for w in ["证据不够", "依据不足", "根据不够", "数据不够", "source"]):
            return EditingType.WEAK_EVIDENCE, "检测到'证据不够'相关关键词"

        # 判断偏
        if any(w in text for w in ["太激进", "太保守", "太确定", "太模糊", "语气不对", "判断过强", "判断过弱"]):
            return EditingType.BIASED_JUDGMENT, "检测到'判断偏'相关关键词"

        # 逻辑跳
        if any(w in text for w in ["逻辑跳", "缺少一步", "说不通", "看不懂", "这里不对", "因果关系不清"]):
            return EditingType.LOGIC_GAP, "检测到'逻辑跳跃'相关关键词"

        # 风格不对
        if any(w in text for w in ["风格不对", "太口语化", "太正式", "不像我们", "语气不对", "措辞不当"]):
            return EditingType.STYLE_MISMATCH, "检测到'风格不对'相关关键词"

        # 结构乱
        if any(w in text for w in ["放错地方", "位置不对", "章节不对", "应该放到", "顺序不对"]):
            return EditingType.STRUCTURE, "检测到'结构乱'相关关键词"

        # 冗余
        if any(w in text for w in ["太啰嗦", "太长", "精炼", "压缩", "简写"]):
            return EditingType.VERBOSE, "检测到'冗余'相关关键词"

        # 默认：整段重写
        return EditingType.WEAK_EVIDENCE, "未识别到具体分类，默认整段重写"


class EditEngine:
    """
    修改引擎——执行分类修改。

    每种修改类型有对应的执行策略：
    - weak_evidence: 回查 T1 找更强证据 → 替换证据句
    - biased_judgment: 调整判断词强度（可以->有望->确定）
    - logic_gap: 定位断裂点 + 生成中间推理
    - style_mismatch: 调用 Style Compiler 改写
    - structure: 移动段落 + 调整过渡句（规则驱动，不需要 LLM）
    - verbose: 段落压缩（保留 thesis + evidence）
    """

    def __init__(self, style_compiler=None):
        self.style_compiler = style_compiler
        self.classifier = EditClassifier()

    def apply(
        self, report_text: str, instruction: str, edit_type: str | None = None, location: str | None = None
    ) -> EditCase:
        """执行分类修改"""
        # 1. 分类
        etype, classifier_note = self.classifier.classify(instruction, edit_type)

        # 2. 修改类型对应的处理策略
        strategies = {
            EditingType.WEAK_EVIDENCE: self._fix_weak_evidence,
            EditingType.BIASED_JUDGMENT: self._fix_biased_judgment,
            EditingType.LOGIC_GAP: self._fix_logic_gap,
            EditingType.STYLE_MISMATCH: self._fix_style_mismatch,
            EditingType.STRUCTURE: self._fix_structure,
            EditingType.VERBOSE: self._fix_verbose,
        }

        strategy = strategies.get(etype, self._fallback_rewrite)
        corrected_text, action = strategy(report_text, instruction, location)

        case = EditCase(
            case_id="",
            report_id="",
            original_text=report_text,
            correction_type=etype,
            correction_action=f"{action} | {classifier_note}" if action else classifier_note,
            corrected_text=corrected_text,
        )

        return case

    def _fix_weak_evidence(self, text: str, instruction: str, location: str | None = None) -> tuple[str, str]:
        """证据弱：回查 T1 找更强证据 → 替换证据句"""
        # 在实际系统中：查询 T1 数据引擎获取更强证据
        # 当前原型：标记需要替换
        return text, f"需要回查 T1 数据引擎获取更强证据: {instruction[:50]}"

    def _fix_biased_judgment(self, text: str, instruction: str, location: str | None = None) -> tuple[str, str]:
        """判断偏：调整判断措辞强度"""
        # 判断强度映射表
        intensity_map = {
            # 强 → 中
            "必然": "大概率",
            "一定": "有望",
            "确定": "预计",
            "无疑": "大概率",
            # 中 → 弱
            "有望": "有机会",
            "预计": "预期",
            "将": "可能将",
            # 弱 → 强
            "可能有机会": "有望",
            "有一定可能": "预计",
        }

        replacements = 0
        for old, new in intensity_map.items():
            if old in text:
                text = text.replace(old, new)
                replacements += 1

        return text, f"判断措辞强度调整: {replacements} 处替换"

    def _fix_logic_gap(self, text: str, instruction: str, location: str | None = None) -> tuple[str, str]:
        """逻辑跳跃：定位断裂点 → 需要 LLM 补全中间推理"""
        return text, f"逻辑断裂标记: {instruction[:50]}（需要 LLM 补全中间推理）"

    def _fix_style_mismatch(self, text: str, instruction: str, location: str | None = None) -> tuple[str, str]:
        """风格不对：调用 Style Compiler 改写"""
        if self.style_compiler:
            result = self.style_compiler.compile(text)
            return result.compiled, f"Style Compiler 改写: {len(result.rules_applied)} 条规则应用"
        return text, "Style Compiler 未配置，检查点已标记"

    def _fix_structure(self, text: str, instruction: str, location: str | None = None) -> tuple[str, str]:
        """结构乱：移动段落（规则驱动，不需要 LLM）"""
        return text, f"段落移动标记: {instruction[:50]}（规则驱动）"

    def _fix_verbose(self, text: str, instruction: str, location: str | None = None) -> tuple[str, str]:
        """冗余：段落压缩"""
        # 基本压缩：提取前 3 句话作为段落
        paragraphs = text.split("\n\n")
        compressed = []
        for para in paragraphs:
            sentences = para.split("。")
            if len(sentences) > 4:
                para = "。".join(sentences[:3]) + "。"
            compressed.append(para)
        return "\n\n".join(compressed), "段落压缩: 保留前3句"

    def _fallback_rewrite(self, text: str, instruction: str, location: str | None = None) -> tuple[str, str]:
        """默认：整段重写"""
        return text, "整段重写（fallback）"


class EditLearningDB:
    """
    修改学习数据库——持久化 EditCase。

    使用 SQLite 存储。每一条修改记录都是一个学习案例。
    积累足够多的案例后，可以：
    1. 在生成时自动应用分析师的偏好
    2. 在验证时预测分析师可能的修改点
    3. 评估"这个分析师对哪类修改最敏感"
    """

    def __init__(self, db_path: str = ""):
        if not db_path:
            db_path = str(Path(__file__).resolve().parent.parent / "_observability" / "edit_learning.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS edit_cases (
                case_id TEXT PRIMARY KEY,
                report_id TEXT,
                analyst_id TEXT,
                original_text TEXT,
                correction_type TEXT,
                correction_action TEXT,
                corrected_text TEXT,
                report_type TEXT,
                section_type TEXT,
                style_profile TEXT,
                persisted INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save(self, case: EditCase):
        """保存一条修改案例"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO edit_cases
            (case_id, report_id, analyst_id, original_text,
             correction_type, correction_action, corrected_text,
             report_type, section_type, style_profile,
             persisted, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                case.case_id,
                case.report_id,
                case.analyst_id,
                case.original_text,
                case.correction_type.value,
                case.correction_action,
                case.corrected_text,
                case.report_type,
                case.section_type,
                case.style_profile,
                int(case.persisted),
                case.created_at,
            ),
        )
        conn.commit()
        conn.close()

    def get_similar_cases(
        self, report_type: str = "", correction_type: str = "", style_profile: str = "", limit: int = 5
    ) -> list[EditCase]:
        """检索相似修改案例——broad matching, any non-empty field filters."""
        conn = sqlite3.connect(self.db_path)
        conditions = []
        params = []
        if report_type:
            conditions.append("(report_type = ? OR report_type LIKE ?)")
            params.extend([report_type, f"%{report_type}%"])
        if correction_type:
            conditions.append("correction_type = ?")
            params.append(correction_type)
        if style_profile:
            conditions.append("(style_profile = ? OR style_profile LIKE ?)")
            params.extend([style_profile, f"%{style_profile}%"])
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        rows = conn.execute(
            f"""
            SELECT * FROM edit_cases
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (*params, limit),
        ).fetchall()
        conn.close()
        return [self._row_to_case(r) for r in rows]

    def count_cases(self) -> int:
        """返回案例总数"""
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM edit_cases").fetchone()[0]
        conn.close()
        return count

    def get_stats_by_type(self) -> dict:
        """按修改类型统计"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT correction_type, COUNT(*) as cnt
            FROM edit_cases GROUP BY correction_type
            ORDER BY cnt DESC
        """).fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}

    @staticmethod
    def _row_to_case(row: tuple) -> EditCase:
        return EditCase(
            case_id=row[0],
            report_id=row[1],
            analyst_id=row[2],
            original_text=row[3],
            correction_type=EditingType(row[4]),
            correction_action=row[5],
            corrected_text=row[6],
            report_type=row[7] or "",
            section_type=row[8] or "",
            style_profile=row[9] or "",
            persisted=bool(row[10]),
            created_at=row[11] or "",
        )


class ModificationSuggester:
    """
    修改建议器——根据历史学习，在分析师修改前预判可能的问题。

    在 T2b 生成时：
    1. 检索该分析师 + 同类报告的历史修改案例
    2. 预判"这类报告最容易在哪些方面被修改"
    3. 在 T2b 生成时自动调整策略
    """

    def __init__(self, db: EditLearningDB):
        self.db = db

    def suggest(self, report_type: str, style_profile: str, analyst_id: str = "") -> list[dict]:
        """给出修改建议"""
        suggestions = []

        # 该报告类型的常见修改
        stats = self.db.get_stats_by_type()

        if stats:
            total = sum(stats.values())
            suggestions.append({"type": "distribution", "data": stats, "note": f"基于 {total} 条历史修改记录"})

            # 最常见的修改类型
            most_common = max(stats, key=stats.get)
            suggestions.append(
                {
                    "type": "attention",
                    "correction_type": most_common,
                    "frequency": f"{stats[most_common] / total * 100:.0f}%",
                }
            )

        return suggestions
