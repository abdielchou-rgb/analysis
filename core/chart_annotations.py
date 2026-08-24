"""V54 Chart Judgment Annotation System
========================================
Production-grade annotation layer for financial charts.
Adds analyst-level judgment annotations to every chart type.

Design principles:
  1. Every annotation is data-driven (from Conviction Matrix), never LLM-generated
  2. Every annotation is traceable (links to data source)
  3. Every annotation has institution-specific styling (from 505 DNA)
  4. Annotation density adjusts by report type (deep dive > flash note)

Annotation types:
  - ZONE: shaded regions (valuation ranges, forecast bands)
  - LINE: reference lines (median, P25/P75, target price)
  - ARROW: directional callouts (key turning points, anomalies)
  - TEXT: judgment statements ("我们认为当前估值偏高")
  - BRACKET: range indicators (forecast range, confidence interval)
  - HIGHLIGHT: emphasis on specific data points

Integration:
  - ChartEngine._apply_style() already handles styling
  - This module adds the annotation layer on top
  - ConvictionMatrix feeds data into annotations
"""

from __future__ import annotations
import logging
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("v54.chart_annotations")

# ── Annotation types ──────────────────────────────────────────────

class AnnotationType(Enum):
    ZONE = "zone"         # Shaded region (altman z-score zone, valuation range)
    LINE = "line"         # Reference line (mean, median, target)
    ARROW = "arrow"       # Directional callout (turning point, anomaly)
    TEXT = "text"         # Free-form judgment text
    BRACKET = "bracket"   # Range indicator (confidence interval)
    HIGHLIGHT = "highlight"  # Emphasized data point
    TREND = "trend"       # Trend line with slope annotation
    DIVERGENCE = "divergence"  # Market consensus vs our view


class AnnotationSeverity(Enum):
    POSITIVE = "positive"    # Bullish annotation
    NEUTRAL = "neutral"     # Neutral/observation
    NEGATIVE = "negative"   # Bearish annotation
    WARNING = "warning"     # Risk alert
    INFO = "info"           # Informational


@dataclass
class ChartAnnotation:
    """Single annotation on a chart."""
    type: AnnotationType
    severity: AnnotationSeverity = AnnotationSeverity.INFO
    label: str = ""                          # Display text
    value: float = 0.0                       # Numeric value (for LINE type)
    x: float = 0.0                           # X position
    y: float = 0.0                           # Y position
    x_start: float = 0.0                     # Zone/bracket start
    x_end: float = 0.0                       # Zone/bracket end
    y_start: float = 0.0                     # For vertical annotations
    y_end: float = 0.0                       # For vertical annotations
    color: str = ""                          # Override color
    alpha: float = 0.15                      # Zone transparency
    fontsize: int = 8                        # Text size
    data_source: str = ""                    # Traceable source
    confidence: Optional[float] = None       # Conviction level (0-1)
    offset_x: float = 0                      # Text offset for positioning
    offset_y: float = 12                     # Text offset for positioning


@dataclass
class ChartAnnotationSet:
    """Complete set of annotations for one chart."""
    chart_id: str = ""                       # Matches ChartSpec.chart_id
    chart_title: str = ""
    annotations: list[ChartAnnotation] = field(default_factory=list)
    
    def add(self, ann: ChartAnnotation):
        self.annotations.append(ann)
    
    @property
    def count(self) -> int:
        return len(self.annotations)
    
    @property
    def by_severity(self) -> dict:
        result = {}
        for a in self.annotations:
            s = a.severity.value
            if s not in result:
                result[s] = []
            result[s].append(a)
        return result


# ── Severity colors ───────────────────────────────────────────────

SEVERITY_COLORS = {
    AnnotationSeverity.POSITIVE: "#2E8B57",
    AnnotationSeverity.NEUTRAL: "#4A90D9",
    AnnotationSeverity.NEGATIVE: "#C41E3A",
    AnnotationSeverity.WARNING: "#E8A838",
    AnnotationSeverity.INFO: "#666666",
}

SEVERITY_ZONE_COLORS = {
    AnnotationSeverity.POSITIVE: "#2E8B57",
    AnnotationSeverity.NEUTRAL: "#4A90D9",
    AnnotationSeverity.NEGATIVE: "#C41E3A",
    AnnotationSeverity.WARNING: "#E8A838",
    AnnotationSeverity.INFO: "#AAAAAA",
}

# ── Annotation presets for common financial scenarios ─────────────

def make_valuation_zone(pe_band: list, current_pe: float,
                       label: str = "当前估值区间") -> list[ChartAnnotation]:
    """Create valuation zone annotations from PE band data."""
    anns = []
    if len(pe_band) >= 4:
        # Create mean ± 1σ zone
        mean_pe = np.mean(pe_band)
        std_pe = np.std(pe_band)
        
        anns.append(ChartAnnotation(
            type=AnnotationType.ZONE,
            severity=AnnotationSeverity.NEUTRAL,
            label=f"均值±1σ ({mean_pe-std_pe:.1f}x-{mean_pe+std_pe:.1f}x)",
            y_start=mean_pe - std_pe, y_end=mean_pe + std_pe,
            alpha=0.12, color="#4A90D9",
            data_source="历史PE Band"
        ))
        
        # Mean line
        anns.append(ChartAnnotation(
            type=AnnotationType.LINE,
            severity=AnnotationSeverity.INFO,
            label=f"历史均值 {mean_pe:.1f}x",
            value=mean_pe,
            color="#4A90D9", alpha=0.6,
            data_source="历史PE Band"
        ))
        
        # Current PE annotation
        if current_pe > mean_pe + std_pe:
            sev = AnnotationSeverity.NEGATIVE
            txt = f"当前PE({current_pe:.1f}x)高于均值+1σ，估值偏高"
        elif current_pe < mean_pe - std_pe:
            sev = AnnotationSeverity.POSITIVE
            txt = f"当前PE({current_pe:.1f}x)低于均值-1σ，估值偏低"
        else:
            sev = AnnotationSeverity.NEUTRAL
            txt = f"当前PE({current_pe:.1f}x)处于合理区间"
        
        anns.append(ChartAnnotation(
            type=AnnotationType.TEXT,
            severity=sev,
            label=txt,
            x=0.02, y=0.98, offset_x=0, offset_y=0,
            fontsize=9,
            data_source="Conviction Matrix估值分析"
        ))
    
    return anns


def make_target_price_line(target: float, current: float,
                          label: str = "目标价") -> ChartAnnotation:
    """Create target price reference line annotation."""
    upside = (target / current - 1) * 100
    return ChartAnnotation(
        type=AnnotationType.LINE,
        severity=AnnotationSeverity.POSITIVE if upside > 0 else AnnotationSeverity.NEGATIVE,
        label=f"{label}: {target:.2f} ({upside:+.1f}%)",
        value=target,
        color="#2E8B57" if upside > 0 else "#C41E3A",
        alpha=0.8,
        data_source="Conviction Matrix目标价校准"
    )


def make_consensus_divergence(current: float, consensus: float,
                             label: str = "我们 vs 市场") -> ChartAnnotation:
    """Create annotation showing our view vs market consensus."""
    diff_pct = (current / consensus - 1) * 100
    normalized_diff = abs(diff_pct)
    
    if normalized_diff < 5:
        txt = f"我们的判断({current:.1f})与市场共识({consensus:.1f})接近"
        sev = AnnotationSeverity.NEUTRAL
    elif diff_pct > 0:
        txt = f"我们比市场更乐观(+{diff_pct:.0f}%)"
        sev = AnnotationSeverity.POSITIVE
    else:
        txt = f"我们比市场更谨慎({diff_pct:.0f}%)"
        sev = AnnotationSeverity.WARNING
    
    return ChartAnnotation(
        type=AnnotationType.TEXT,
        severity=sev,
        label=txt,
        x=0.98, y=0.05, offset_x=0, offset_y=0,
        fontsize=8,
        data_source="一致预期数据"
    )


def make_trend_arrow(x: float, y: float, direction: str,
                    label: str = "", severity: AnnotationSeverity = AnnotationSeverity.INFO,
                    data_source: str = "") -> ChartAnnotation:
    """Create trend direction arrow annotation."""
    return ChartAnnotation(
        type=AnnotationType.ARROW,
        severity=severity,
        label=label,
        x=x, y=y,
        color=SEVERITY_COLORS.get(severity, "#666666"),
        data_source=data_source
    )


def make_anomaly_callout(x: float, y: float, label: str,
                        severity: AnnotationSeverity = AnnotationSeverity.WARNING,
                        data_source: str = "") -> ChartAnnotation:
    """Create anomaly callout pointing to a specific data point."""
    return ChartAnnotation(
        type=AnnotationType.HIGHLIGHT,
        severity=severity,
        label=label,
        x=x, y=y,
        color=SEVERITY_COLORS.get(severity, "#E8A838"),
        offset_y=-15,
        data_source=data_source
    )


# ── Main annotator ────────────────────────────────────────────────

class ChartAnnotator:
    """Applies analyst judgment annotations to matplotlib charts.
    
    Usage:
        annotator = ChartAnnotator(style)
        annotator.add_annotation(ax, chart_annotation)
        annotator.apply_all(ax, annotation_set)
    """
    
    def __init__(self, style: dict):
        self.style = style
        self._text_color = style.get("annotation_style", {}).get("color", "#666666")
        self._arrow_color = style.get("accent", "#C41E3A")
    
    def add_zone(self, ax, ann: ChartAnnotation):
        """Add shaded zone annotation."""
        if ann.y_start and ann.y_end:
            color = ann.color or SEVERITY_ZONE_COLORS.get(ann.severity, "#AAAAAA")
            ax.axhspan(ann.y_start, ann.y_end, alpha=ann.alpha,
                       facecolor=color, zorder=1)
            if ann.label:
                ax.text(0.02, ann.y_end + (ann.y_end - ann.y_start) * 0.05,
                       ann.label, fontsize=ann.fontsize - 1,
                       color=color, alpha=0.7, transform=ax.get_yaxis_transform(),
                       va="bottom", ha="left")
    
    def add_line(self, ax, ann: ChartAnnotation):
        """Add reference line annotation."""
        color = ann.color or SEVERITY_COLORS.get(ann.severity, "#666666")
        ax.axhline(y=ann.value, color=color, linewidth=1.0,
                   linestyle="--", alpha=ann.alpha, zorder=3)
        if ann.label:
            ax.text(0.98, ann.value, f" {ann.label}",
                   transform=ax.get_yaxis_transform(),
                   fontsize=ann.fontsize, color=color, alpha=0.8,
                   va="bottom", ha="right",
                   bbox=dict(boxstyle="round,pad=0.3",
                            facecolor="white", edgecolor=color, alpha=0.7))
    
    def add_arrow(self, ax, ann: ChartAnnotation):
        """Add directional arrow annotation."""
        color = ann.color or self._arrow_color
        ax.annotate(
            ann.label if ann.label else "",
            xy=(ann.x, ann.y),
            xytext=(ann.x + (ann.offset_x or 0),
                    ann.y + (ann.offset_y or 20)),
            textcoords="offset points",
            fontsize=ann.fontsize,
            color=color,
            arrowprops=dict(arrowstyle="->", color=color, lw=1.2),
            bbox=dict(boxstyle="round,pad=0.3",
                     facecolor="white", edgecolor=color, alpha=0.8),
            zorder=5
        )
    
    def add_text(self, ax, ann: ChartAnnotation):
        """Add judgment text annotation."""
        color = ann.color or SEVERITY_COLORS.get(ann.severity, self._text_color)
        x = ann.x if ann.x else 0.02
        y = ann.y if ann.y else 0.98
        
        # Determine severity icon (use ASCII to avoid font rendering issues)
        icons = {
            AnnotationSeverity.POSITIVE: "+",
            AnnotationSeverity.NEUTRAL: "o",
            AnnotationSeverity.NEGATIVE: "-",
            AnnotationSeverity.WARNING: "!",
            AnnotationSeverity.INFO: "",
        }
        icon = icons.get(ann.severity, "")
        display_text = f"{icon} {ann.label}" if icon else ann.label
        
        ax.text(x, y, display_text,
               transform=ax.transAxes,
               fontsize=ann.fontsize,
               color=color,
               verticalalignment="top",
               horizontalalignment="left" if x < 0.5 else "right",
               bbox=dict(boxstyle="round,pad=0.4",
                        facecolor="white", edgecolor=color, alpha=0.85),
               zorder=6)
    
    def add_highlight(self, ax, ann: ChartAnnotation):
        """Add highlighted data point annotation."""
        color = ann.color or SEVERITY_COLORS.get(ann.severity, "#E8A838")
        # Highlight marker
        ax.scatter([ann.x], [ann.y], color=color, s=120,
                  marker="o", zorder=4, edgecolors="white", linewidth=1.5)
        # Callout text
        if ann.label:
            offset_y = ann.offset_y if ann.offset_y else -18
            ax.annotate(ann.label, (ann.x, ann.y),
                       textcoords="offset points",
                       xytext=(8, offset_y),
                       fontsize=ann.fontsize,
                       color=color,
                       arrowprops=dict(arrowstyle="->", color=color, lw=0.8),
                       bbox=dict(boxstyle="round,pad=0.3",
                                facecolor="white", edgecolor=color, alpha=0.85),
                       zorder=5)
    
    def add_trend(self, ax, ann: ChartAnnotation):
        """Add trend line annotation."""
        color = ann.color or SEVERITY_COLORS.get(ann.severity, "#666666")
        if ann.x_start and ann.x_end:
            ax.plot([ann.x_start, ann.x_end], [ann.y_start, ann.y_end],
                   color=color, linewidth=1.5, linestyle="-", zorder=2)
            if ann.label:
                mid_x = (ann.x_start + ann.x_end) / 2
                mid_y = (ann.y_start + ann.y_end) / 2
                ax.text(mid_x, mid_y, f" {ann.label}",
                       fontsize=ann.fontsize, color=color, alpha=0.8,
                       rotation=np.degrees(np.arctan2(
                           ann.y_end - ann.y_start, ann.x_end - ann.x_start)),
                       va="bottom", ha="center")
    
    def add_divergence(self, ax, ann: ChartAnnotation):
        """Add consensus divergence annotation."""
        color = ann.color or SEVERITY_COLORS.get(ann.severity, "#4A90D9")
        # Draw two horizontal lines showing the gap
        consensus_y = ann.value
        our_y = ann.y
        if consensus_y and our_y:
            ax.plot([ann.x_start, ann.x_end],
                   [consensus_y, consensus_y],
                   color="#888888", linewidth=2, linestyle=":", alpha=0.6,
                   label="市场共识")
            ax.plot([ann.x_start, ann.x_end],
                   [our_y, our_y],
                   color=ann.color or self._arrow_color,
                   linewidth=2, linestyle="-", alpha=0.8,
                   label=ann.label)
    
    def apply(self, ax, ann: ChartAnnotation):
        """Apply a single annotation to axes."""
        dispatch = {
            AnnotationType.ZONE: self.add_zone,
            AnnotationType.LINE: self.add_line,
            AnnotationType.ARROW: self.add_arrow,
            AnnotationType.TEXT: self.add_text,
            AnnotationType.HIGHLIGHT: self.add_highlight,
            AnnotationType.TREND: self.add_trend,
            AnnotationType.DIVERGENCE: self.add_divergence,
            AnnotationType.BRACKET: self.add_line,  # Same visual as line
        }
        handler = dispatch.get(ann.type)
        if handler:
            try:
                handler(ax, ann)
            except Exception as e:
                logger.debug(f"Annotation failed ({ann.type.value}): {e}")
    
    def apply_all(self, ax, ann_set: ChartAnnotationSet):
        """Apply all annotations in a set to axes."""
        for ann in ann_set.annotations:
            self.apply(ax, ann)


# ── Intelligence layer: auto-generate annotations from data ──────

class AnnotationIntelligence:
    """Auto-generates judgment annotations from financial data.
    
    Analyzes data patterns and generates appropriate annotations
    without requiring explicit annotation inputs.
    """
    
    @staticmethod
    def detect_anomalies(x_data: list, y_data: list) -> list[ChartAnnotation]:
        """Detect anomalous data points (spikes, drops, reversals)."""
        anns = []
        if len(y_data) < 4:
            return anns
        
        arr = np.array(y_data)
        mean = np.mean(arr)
        std = np.std(arr)
        
        for i in range(1, len(arr) - 1):
            # Detect spikes (z-score > 2)
            z = abs(arr[i] - mean) / max(std, 0.001)
            if z > 2.0:
                if arr[i] > arr[i-1] and arr[i] > arr[i+1]:
                    anns.append(ChartAnnotation(
                        type=AnnotationType.HIGHLIGHT,
                        severity=AnnotationSeverity.WARNING,
                        label=f"异常峰值: {arr[i]:.1f}",
                        x=i, y=arr[i],
                        color="#E8A838", offset_y=-20,
                        data_source="统计异常检测(z>{:.1f})".format(z)
                    ))
                elif arr[i] < arr[i-1] and arr[i] < arr[i+1]:
                    anns.append(ChartAnnotation(
                        type=AnnotationType.HIGHLIGHT,
                        severity=AnnotationSeverity.NEUTRAL,
                        label=f"异常低谷: {arr[i]:.1f}",
                        x=i, y=arr[i],
                        color="#4A90D9", offset_y=12,
                        data_source="统计异常检测(z>{:.1f})".format(z)
                    ))
        
        # Detect trend reversal
        try:
            slope_before = arr[1] - arr[0]
            slope_after = arr[-1] - arr[-2]
            if slope_before * slope_after < 0 and abs(slope_before) > std * 0.5:
                direction = "反弹" if slope_after > 0 else "回落"
                anns.append(ChartAnnotation(
                    type=AnnotationType.TREND,
                    severity=AnnotationSeverity.WARNING,
                    label=f"趋势{direction}信号",
                    x_start=len(arr)//3, y_start=arr[len(arr)//3],
                    x_end=len(arr)*2//3, y_end=arr[len(arr)*2//3],
                    color="#E8A838",
                    data_source="趋势拐点检测"
                ))
        except Exception:
            pass
        
        return anns
    
    @staticmethod
    def detect_valuation_signals(values: list, labels: list = None,
                                current_value: float = None) -> list[ChartAnnotation]:
        """Detect valuation signals from time series data."""
        anns = []
        if len(values) < 3:
            return anns
        
        arr = np.array(values)
        p25, p50, p75 = np.percentile(arr, [25, 50, 75])
        
        if current_value is None:
            current_value = arr[-1]
        
        # Valuation zone annotations
        anns.append(ChartAnnotation(
            type=AnnotationType.ZONE,
            severity=AnnotationSeverity.NEUTRAL,
            label=f"P25-P75区间 ({p25:.1f}-{p75:.1f})",
            y_start=p25, y_end=p75,
            alpha=0.1, color="#4A90D9",
            data_source="历史百分位分析"
        ))
        
        anns.append(ChartAnnotation(
            type=AnnotationType.LINE,
            severity=AnnotationSeverity.INFO,
            label=f"中位数 {p50:.1f}",
            value=p50,
            color="#4A90D9", alpha=0.5,
            data_source="历史百分位分析"
        ))
        
        # Current position judgment
        if current_value > p75:
            excess = (current_value / p75 - 1) * 100
            anns.append(ChartAnnotation(
                type=AnnotationType.TEXT,
                severity=AnnotationSeverity.NEGATIVE,
                label=f"当前({current_value:.1f})高于P75，超出{excess:.0f}%",
                x=0.02, y=0.90, fontsize=9,
                data_source="Conviction Matrix估值校准"
            ))
        elif current_value < p25:
            discount = (1 - current_value / p25) * 100
            anns.append(ChartAnnotation(
                type=AnnotationType.TEXT,
                severity=AnnotationSeverity.POSITIVE,
                label=f"当前({current_value:.1f})低于P25，折价{discount:.0f}%",
                x=0.02, y=0.90, fontsize=9,
                data_source="Conviction Matrix估值校准"
            ))
        
        return anns
    
    @staticmethod
    def detect_growth_signals(revenue_history: list, 
                             profit_history: list = None) -> list[ChartAnnotation]:
        """Detect growth-related patterns."""
        anns = []
        if len(revenue_history) < 3:
            return anns
        
        rev = np.array(revenue_history)
        growth_rates = [(rev[i] / rev[i-1] - 1) * 100 for i in range(1, len(rev))]
        
        if growth_rates:
            avg_growth = np.mean(growth_rates)
            recent_growth = growth_rates[-1]
            
            # Growth acceleration/deceleration
            if recent_growth > avg_growth * 1.3:
                anns.append(ChartAnnotation(
                    type=AnnotationType.TEXT,
                    severity=AnnotationSeverity.POSITIVE,
                    label=f"增长加速: {recent_growth:.1f}%(近3年平均{avg_growth:.1f}%)",
                    x=0.02, y=0.82, fontsize=8,
                    data_source="营收增长率趋势分析"
                ))
            elif recent_growth < avg_growth * 0.7:
                anns.append(ChartAnnotation(
                    type=AnnotationType.TEXT,
                    severity=AnnotationSeverity.WARNING,
                    label=f"增长放缓: {recent_growth:.1f}%(近3年平均{avg_growth:.1f}%)",
                    x=0.02, y=0.82, fontsize=8,
                    data_source="营收增长率趋势分析"
                ))
            
            # Consecutive decline
            if len(growth_rates) >= 3 and all(g < g_prev for g, g_prev in 
                                              zip(growth_rates[-3:], growth_rates[-4:-1])):
                anns.append(ChartAnnotation(
                    type=AnnotationType.ARROW,
                    severity=AnnotationSeverity.NEGATIVE,
                    label="连续下滑",
                    x=len(rev)-1, y=rev[-1],
                    color="#C41E3A",
                    data_source="增长率趋势检测"
                ))
        
        if profit_history and len(profit_history) >= 3:
            profit = np.array(profit_history)
            # Margin expansion/contraction
            margins = [(p / r) * 100 if r > 0 else 0 
                      for p, r in zip(profit, rev)]
            if margins:
                margin_trend = margins[-1] - margins[0]
                if margin_trend > 5:
                    anns.append(ChartAnnotation(
                        type=AnnotationType.TEXT,
                        severity=AnnotationSeverity.POSITIVE,
                        label=f"利润率扩张: +{margin_trend:.1f}ppt",
                        x=0.98, y=0.90, fontsize=8,
                        data_source="利润率趋势分析"
                    ))
                elif margin_trend < -5:
                    anns.append(ChartAnnotation(
                        type=AnnotationType.TEXT,
                        severity=AnnotationSeverity.NEGATIVE,
                        label=f"利润率收缩: {margin_trend:.1f}ppt",
                        x=0.98, y=0.90, fontsize=8,
                        data_source="利润率趋势分析"
                    ))
        
        return anns


# ── Integration with ChartEngine ──────────────────────────────────

def annotate_from_conviction(ax, style: dict, 
                            data: dict = None,
                            conviction_data: dict = None,
                            asset_name: str = "",
                            report_type: str = "company") -> list[ChartAnnotation]:
    """Generate and apply annotations from Conviction Matrix data.
    
    This is the main integration point between Conviction Matrix
    and the chart annotation system.
    
    Args:
        ax: matplotlib axes to annotate
        style: institution style dict
        data: chart data dict (keys=labels, values=numbers)
        conviction_data: ConvictionMatrix results
        asset_name: company/industry name
        report_type: "company", "industry", "unlisted"
    
    Returns:
        list of applied annotations
    """
    annotator = ChartAnnotator(style)
    ann_set = ChartAnnotationSet()
    
    if not data or len(data) < 2:
        return []
    
    keys = list(data.keys())
    vals = list(data.values())
    
    # 1. Statistical annotations (always)
    if len(vals) >= 4:
        ann_set.annotations.extend(
            AnnotationIntelligence.detect_valuation_signals(vals, keys)
        )
    
    # 2. Anomaly detection
    if len(vals) >= 4:
        ann_set.annotations.extend(
            AnnotationIntelligence.detect_anomalies(list(range(len(vals))), vals)
        )
    
    # 3. Growth signals (for revenue/profit data)
    if conviction_data:
        rev = conviction_data.get("revenue_history")
        profit = conviction_data.get("profit_history")
        if rev:
            ann_set.annotations.extend(
                AnnotationIntelligence.detect_growth_signals(rev, profit)
            )
    
    # 4. Conviction-level annotation
    if conviction_data:
        conviction = conviction_data.get("overall_conviction", 0)
        if conviction > 0:
            sev = (AnnotationSeverity.POSITIVE if conviction >= 0.7
                   else AnnotationSeverity.NEUTRAL if conviction >= 0.4
                   else AnnotationSeverity.WARNING)
            ann_set.annotations.append(ChartAnnotation(
                type=AnnotationType.TEXT,
                severity=sev,
                label=f"综合置信度: {conviction:.0%}",
                x=0.98, y=0.02, fontsize=7,
                data_source="Conviction Matrix"
            ))
    
    # 5. Apply all
    for ann in ann_set.annotations:
        annotator.apply(ax, ann)
    
    return ann_set.annotations


# ── Quick annotation function ─────────────────────────────────────

def quick_annotate(ax, style: dict, 
                  annotations: list[ChartAnnotation] = None,
                  auto_detect: bool = True,
                  data: dict = None) -> int:
    """Quick one-call annotation function.
    
    Args:
        ax: matplotlib axes
        style: institution style dict
        annotations: optional pre-defined annotations
        auto_detect: whether to auto-detect patterns
        data: data dict for auto-detection
    
    Returns:
        number of annotations applied
    """
    annotator = ChartAnnotator(style)
    count = 0
    
    # Apply pre-defined annotations
    if annotations:
        for ann in annotations:
            annotator.apply(ax, ann)
            count += 1
    
    # Auto-detect patterns
    if auto_detect and data and len(data) >= 3:
        vals = list(data.values())
        
        # Anomaly detection
        anomalies = AnnotationIntelligence.detect_anomalies(
            list(range(len(vals))), vals
        )
        for ann in anomalies:
            annotator.apply(ax, ann)
            count += 1
        
        # Valuation signals
        signals = AnnotationIntelligence.detect_valuation_signals(vals)
        for ann in signals:
            annotator.apply(ax, ann)
            count += 1
    
    return count
