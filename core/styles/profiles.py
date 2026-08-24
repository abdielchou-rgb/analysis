"""Style profiles — 7 institutional styles with chart configs."""

STYLES = {
    "goldman_sachs": {
        "name": "Goldman Sachs",
        "colors": {"primary":"#051C2C","accent":"#009688","bg":"#FFFFFF","text":"#1A1A1A"},
        "charts": {"preferred":["waterfall","scatter","bar_cluster"],"colors":["#051C2C","#009688","#4CB8E8"]},
    },
    "morgan_stanley": {
        "name": "Morgan Stanley",
        "colors": {"primary":"#003366","accent":"#FFFFFF","bg":"#FAFCFF"},
        "charts": {"preferred":["line","bar_cluster","heatmap"],"colors":["#003366","#4CB8E8","#B0D4E8"]},
    },
    "mckinsey": {
        "name": "McKinsey & Company",
        "colors": {"primary":"#003D2F","accent":"#00A86B"},
        "charts": {"preferred":["bar","waterfall","scatter"],"colors":["#003D2F","#00A86B","#7ED321"]},
    },
    "boston_consulting": {
        "name": "Boston Consulting Group",
        "colors": {"primary":"#003366","accent":"#00A3E0"},
        "charts": {"preferred":["bar","line","scatter"],"colors":["#003366","#00A3E0","#7EC8E3"]},
    },
    "cicc": {
        "name": "CICC",
        "colors": {"primary":"#003366","accent":"#C41E3A"},
        "charts": {"preferred":["bar_cluster","line","pie"],"colors":["#003366","#C41E3A","#E8C84C"]},
    },
    "citic": {
        "name": "CITIC Securities",
        "colors": {"primary":"#8B0000","accent":"#D4A000"},
        "charts": {"preferred":["bar_cluster","line","waterfall"],"colors":["#8B0000","#D4A000","#333333"]},
    },
    "academic": {
        "name": "Academic Paper",
        "colors": {"primary":"#1A1A1A","accent":"#003366"},
        "charts": {"preferred":["line","bar","scatter"],"colors":["#1A1A1A","#003366","#666666"]},
    },
}

def get_style(style_id: str) -> dict:
    return STYLES.get(style_id, STYLES["cicc"])

def list_styles() -> list[str]:
    return list(STYLES.keys())

def style_config_to_compiler_profile(style_id: str) -> dict:
    s = get_style(style_id)
    w = s.get("writing", {})
    return {"conclusion_first": w.get("conclusion_first", True), "writing": w}
