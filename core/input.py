"""V51 输入解析"""
from __future__ import annotations
import re
from .models import WritingBrief, ReportType, Direction, InputMode

class V51Input:
    def parse(self, inp: str) -> WritingBrief:
        mode = "A" if any(k in inp for k in["核心判断","风格"]) else "C"
        COMMON = {"贵州茅台":"贵州茅台 600519.SH","宁德时代":"宁德时代 300750.SZ","比亚迪":"比亚迪 002594.SZ"}
        dr = Direction.BULL if any(k in inp for k in["看多","看好","超预期"]) else Direction.BEAR if any(k in inp for k in["看空"]) else Direction.NEUTRAL
        tp = next((v for k,v in {"业绩点评":ReportType.EARNINGS_NOTES,"财报":ReportType.EARNINGS_NOTES,"行业":ReportType.INDUSTRY_DEEP,"非上市":ReportType.UNLISTED_COMPANY}.items() if k in inp), ReportType.LISTED_COMPANY)
        st = next((s for k,s in {"中金":"cicc","高盛":"goldman_sachs","中信":"citic"}.items() if k in inp), "cicc")
        asset = ""
        for k,v in COMMON.items():
            if k in inp: asset = v; break
        if not asset:
            m = re.search(r'(\d{6})', inp)
            asset = f"{m.group(1)}.SH" if m else inp.strip()
        b = WritingBrief(asset=asset, report_type=tp, input_mode=InputMode.STRUCTURED if mode == "A" else InputMode.FALLBACK, core_thesis_direction=dr, style_profile=st)
        tm = re.search(r'核心判断[：:是]\s*([^；。\n]+)', inp)
        if tm: b.core_thesis_point = tm.group(1).strip()
        return b
