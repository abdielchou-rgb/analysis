"""P1: Multi-institution Style Profiles + Expression DNA"""

from __future__ import annotations
from pathlib import Path

STYLES_DIR = Path(__file__).resolve().parent.parent / "T1_knowledge" / "styles"

STYLES = {
    "goldman_sachs": {
        "name": "Goldman Sachs",
        "colors": {"primary":"#051C2C","accent":"#009688","bg":"#FFFFFF","text":"#1A1A1A"},
        "typography": {"heading":"Times New Roman","body":"Times New Roman","size_heading":16,"size_body":10},
        "writing": {"conclusion_first":True,"judgment_density":1.5,"max_sentence_chars":120,
                    "forbidden_terms":["arguably","it is worth noting"],"citation_style":"footnote_numbered",
                    "signature_terms":["we believe","our analysis suggests","key risk"]},
        "charts": {"preferred":["waterfall","scatter","bar_cluster"],"colors":["#051C2C","#009688","#4CB8E8"]},
    },
    "morgan_stanley": {
        "name": "Morgan Stanley",
        "colors": {"primary":"#003366","accent":"#FFFFFF","bg":"#FAFCFF","text":"#1A1A1A"},
        "writing": {"conclusion_first":False,"judgment_density":1.3,"sentence_length_avg":25,
                    "signature_terms":["we see","our framework suggests","key debate"]},
        "charts": {"preferred":["line","bar_cluster","heatmap"]},
    },
    "mckinsey": {
        "name": "McKinsey & Company",
        "colors": {"primary":"#003D2F","accent":"#00A86B","bg":"#FAFCFA","text":"#1A1A1A"},
        "writing": {"conclusion_first":True,"judgment_density":1.8,"max_sentence_chars":140,
                    "signature_terms":["our analysis suggests","we typically see","it is our view"]},
        "charts": {"preferred":["bar","waterfall","scatter"],"colors":["#003D2F","#00A86B","#7ED321"]},
    },
    "boston_consulting": {
        "name": "Boston Consulting Group",
        "colors": {"primary":"#003366","accent":"#00A3E0","bg":"#FFFFFF","text":"#1A1A1A"},
        "writing": {"conclusion_first":True,"judgment_density":1.6,"signature_terms":["we expect","our perspective","key insight"]},
    },
    "cicc": {
        "name": "CICC",
        "colors": {"primary":"#003366","accent":"#C41E3A","bg":"#FFFFFF","text":"#2C2C2C"},
        "writing": {"conclusion_first":True,"judgment_density":1.2,"max_sentence_chars":130,
                    "forbidden_terms":["值得注意的是","从某种程度上说"],
                    "signature_terms":["预计","判断","我们认为"]},
    },
    "citic": {
        "name": "CITIC Securities",
        "colors": {"primary":"#1B2A4A","accent":"#D4A017","bg":"#FAFAFA","text":"#2C2C2C"},
        "writing": {"conclusion_first":True,"judgment_density":1.1,"signature_terms":["我们认为","预计","展望"]},
    },
    "academic": {
        "name": "Academic Paper",
        "colors": {"primary":"#1A1A1A","accent":"#003366","bg":"#FFFFFF","text":"#000000"},
        "writing": {"conclusion_first":False,"judgment_density":0.6,"citation_style":"apa",
                    "signature_terms":["we argue","we find","our analysis demonstrates"]},
        "charts": {"preferred":["line","bar","box"]},
    },
}


def get_style(style_id: str) -> dict:
    return STYLES.get(style_id, STYLES["cicc"])


def list_styles() -> list[str]:
    return list(STYLES.keys())


def style_config_to_compiler_profile(style_id: str) -> dict:
    """Convert a style profile to StyleCompiler-compatible config."""
    s = get_style(style_id)
    w = s.get("writing", {})
    return {"conclusion_first": w.get("conclusion_first", True), "writing": w}
