"""V51 Style Profiles — 7 institution profiles with expression DNA.

Loads YAML profiles and provides lookup/merge for Style Compiler.
Profiles are loaded lazily — only the requested one is parsed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("v51.styles")

STYLES_DIR = Path(__file__).resolve().parent

# ── Built-in profiles (from design-rationale roundtable, P2-2) ──

BUILTIN_PROFILES = {
    "cicc": {
        "name": "中金公司", "primary": "#003366", "accent": "#C41E3A",
        "heading_font": "SimHei", "body_font": "SimSun",
        "conclusion_first": True, "min_judgment_density": 1.2,
        "forbidden_terms": ["值得注意的是", "从某种程度上说"],
        "signature_terms": ["我们认为", "我们判断"],
    },
    "goldman_sachs": {
        "name": "Goldman Sachs", "primary": "#051C2C", "accent": "#009688",
        "heading_font": "Calibri", "body_font": "Calibri",
        "conclusion_first": True, "min_judgment_density": 1.5,
        "forbidden_terms": ["arguably", "it is worth noting", "notably"],
        "signature_terms": ["we believe", "our analysis suggests"],
    },
    "morgan_stanley": {
        "name": "Morgan Stanley", "primary": "#000066", "accent": "#D4AF37",
        "heading_font": "Arial", "body_font": "Arial",
        "conclusion_first": True, "min_judgment_density": 1.4,
        "forbidden_terms": ["值得注意的是", "不可否认的是"],
        "signature_terms": ["we believe", "our analysis suggests"],
    },
    "mckinsey": {
        "name": "McKinsey & Company", "primary": "#003A70", "accent": "#00A3E0",
        "heading_font": "Arial", "body_font": "Times New Roman",
        "conclusion_first": True, "min_judgment_density": 1.8,
        "forbidden_terms": ["值得注意的是", "让我们来看看"],
        "signature_terms": ["our analysis indicates", "we find"],
    },
    "bcg": {
        "name": "Boston Consulting Group", "primary": "#000000", "accent": "#00684E",
        "heading_font": "Georgia", "body_font": "Georgia",
        "conclusion_first": True, "min_judgment_density": 1.3,
        "forbidden_terms": ["综上所述", "总而言之"],
        "signature_terms": ["the evidence suggests", "we see"],
    },
    "citic": {
        "name": "中信证券", "primary": "#8B0000", "accent": "#D4A000",
        "heading_font": "SimHei", "body_font": "SimSun",
        "conclusion_first": True, "min_judgment_density": 1.2,
        "forbidden_terms": ["值得注意的是", "从某种程度上说"],
        "signature_terms": ["我们认为", "核心风险在于"],
    },
    "academic": {
        "name": "学术论文", "primary": "#1A1A1A", "accent": "#2C5282",
        "heading_font": "Times New Roman", "body_font": "Times New Roman",
        "conclusion_first": False, "min_judgment_density": 0.8,
        "forbidden_terms": ["AI生成", "本报告由系统生成"],
        "signature_terms": ["本文认为", "研究表明"],
    },
}


# ── YAML loader ──

def _load_yaml_profile(style_id: str) -> Optional[dict]:
    """Load a style profile from YAML file if it exists."""
    yaml_path = STYLES_DIR / f"{style_id}.yaml"
    if not yaml_path.exists():
        return None
    try:
        import yaml
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return None
        w = data.get("writing", {})
        return {
            "name": data.get("name", style_id),
            "primary": data.get("colors", {}).get("primary", "#333333"),
            "accent": data.get("colors", {}).get("accent", "#666666"),
            "heading_font": data.get("typography", {}).get("heading_font", "Arial"),
            "body_font": data.get("typography", {}).get("main_font", "Arial"),
            "conclusion_first": w.get("conclusion_first", True),
            "min_judgment_density": w.get("min_judgment_density", 1.0),
            "forbidden_terms": w.get("forbidden_terms", []),
            "signature_terms": w.get("signature_terms", []),
        }
    except Exception as e:
        logger.warning(f"Failed to load YAML profile {style_id}: {e}")
        return None


def get_profile(style_id: str = "cicc") -> dict:
    """Get a style profile by ID. Falls back to cicc.

    Priority: 1) YAML file 2) built-in 3) cicc default.
    """
    profile = _load_yaml_profile(style_id)
    if profile:
        return profile
    return BUILTIN_PROFILES.get(style_id, BUILTIN_PROFILES["cicc"])


def list_profiles() -> list[str]:
    """List all available style profile IDs."""
    yaml_ids = []
    for f in STYLES_DIR.glob("*.yaml"):
        yaml_ids.append(f.stem.replace("style_", ""))
    return sorted(set(list(BUILTIN_PROFILES.keys()) + yaml_ids))


def profile_to_compiler_config(profile: dict) -> dict:
    """Convert a full profile dict to Style Compiler config."""
    return {
        "conclusion_first": profile.get("conclusion_first", True),
        "writing": {
            "min_judgment_density": profile.get("min_judgment_density", 1.0),
            "forbidden_terms": profile.get("forbidden_terms", []),
        },
    }
