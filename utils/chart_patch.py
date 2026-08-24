"""V53+ Chart Patch - Lightweight compatibility layer.

The ChartEngine now loads palettes directly from chart_config.
This patch ensures backward compatibility and applies quality defaults.
"""

import logging
logger = logging.getLogger("v53.chart_patch")

from utils.chart_config import ensure_init, get_palette, apply_institution_style


def patch_chart_engine():
    """Ensure ChartEngine uses chart_config institutional palettes."""
    from core.chart_engine import ChartEngine
    ensure_init()

    original_set_style = ChartEngine.set_style

    def patched_set_style(self, style_id: str):
        self.style_id = style_id
        palette = get_palette(style_id)
        if palette:
            self.style = palette
            logger.info(f"ChartEngine style set to {style_id} (chart_config)")
        else:
            original_set_style(self, style_id)
        return self

    ChartEngine.set_style = patched_set_style

    original_init = ChartEngine.__init__

    def patched_init(self, output_dir="outputs/charts", style_id="cicc",
                     quality="final", data_source=""):
        from pathlib import Path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.style_id = style_id
        self.generated = []
        self.quality = quality
        self.data_source = data_source
        self._figure_counter = 0
        palette = get_palette(style_id)
        self.style = palette if palette else {"primary": "#003366", "accent": "#C41E3A",
                                               "bg": "#FFFFFF", "text": "#1A1A1A",
                                               "palette": ["#003366","#C41E3A","#E8C84C","#4CB8E8","#666666"]}
        logger.info(f"ChartEngine initialized with {style_id} (patched)")

    ChartEngine.__init__ = patched_init
    logger.info("ChartEngine fully patched with chart_config styling")


def patch_all():
    """Apply all professional chart patches."""
    patch_chart_engine()
