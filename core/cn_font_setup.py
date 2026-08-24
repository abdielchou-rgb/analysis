"""2号分析师 Matplotlib 字体配置(静默fallback链)"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

_CJK_FONTS = [
    "SimHei",
    "Microsoft YaHei",
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
    "WenQuanYi Micro Hei",
    "Arial Unicode MS",
    "DejaVu Sans",
]


def setup_cn_font():
    fonts = [f.name for f in fm.fontManager.ttflist]
    chosen = next((f for f in _CJK_FONTS if f in fonts), "DejaVu Sans")
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": [chosen], "axes.unicode_minus": False})
    return chosen


def get_cn_font():
    return setup_cn_font()
