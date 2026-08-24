"""
ComputeInjector V3 — 基于实际计算结果的确定性注入

核心变更:
1. 删除所有硬编码 fallback 值（8.50元、9.8%等）
2. compute_results 为空时注入"数据待补充"占位符
3. 集成 Damodaran ERP 结果
4. 集成 Pattern/DecisionHub 结果
5. 只做 ML 层替换，不做 LLM 做不好的字符串拼接
"""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("2hao.compute_injector.v3")


class ComputeInjector:
    PLACEHOLDER_RE = r"{{([A-Z_]+):([a-z_]+)}}"

    def __init__(self, compute_results: dict = None, data: dict = None):
        self.cr = compute_results or {}
        self.data = data or {}

    def inject(self, report_text: str, asset: str = "") -> str:
        text = report_text
        fixes = []
        text, n = self._inject_date(text)
        fixes.append(f"date:{n}")
        text, n = self._replace_placeholders(text)
        fixes.append(f"ph:{n}")

        # WACC/Beta 注入
        text, n = self._inject_wacc_beta(text)
        fixes.append(f"params:{n}")

        # ERP 注入（估值段附近）
        text, n = self._inject_erp(text)
        fixes.append(f"erp:{n}")

        # DecisionHub 信号注入（核心判断段附近）
        text, n = self._inject_decision(text)
        fixes.append(f"decision:{n}")

        # Pattern信号注入（趋势分析段附近）
        text, n = self._inject_patterns(text)
        fixes.append(f"patterns:{n}")

        active = [f for f in fixes if not f.endswith(":0")]
        if active:
            print(f"[ComputeInjector] {len(active)} injections: {active}")
        return text

    def _inject_date(self, text: str) -> tuple:
        today = datetime.now().strftime("%Y年%m月%d日")
        count = 0
        for pat in [
            (r"报告日期[：:]\s*\d{4}年\d{1,2}月\d{1,2}日", f"报告日期：{today}"),
            (r"报告日期[：:]\s*\d{4}-\d{2}-\d{2}", f"报告日期：{today}"),
        ]:
            if re.search(pat[0], text):
                text = re.sub(pat[0], pat[1], text)
                count += 1
        return text, count

    def _replace_placeholders(self, text: str) -> tuple:
        count = 0

        def replacer(m):
            nonlocal count
            prefix, key = m.group(1), m.group(2)
            if prefix == "DCF":
                v = self.cr.get("dcf_valuation", {})
                if v.get("status") == "ok":
                    r = v.get("result", {})
                    if key in r and r[key] is not None:
                        val = r[key]
                        count += 1
                        if isinstance(val, float):
                            return f"{val:.2f}"
                        return str(val)
                    # 尝试 key 的不同命名
                    key_map = {
                        "target_price": "fair_value",
                        "fair_value": "fair_value",
                        "wacc": "wacc",
                        "upside": "upside_pct",
                        "pe": "implied_pe",
                        "eps": "eps",
                    }
                    mapped = key_map.get(key)
                    if mapped and mapped in r:
                        count += 1
                        return str(r[mapped])
            # 不再硬编码，留下占位符让 IronGate 检测到后触发重写
            return f"【数据待补充：{prefix}:{key}】"

        text = re.sub(self.PLACEHOLDER_RE, replacer, text)
        return text, count

    def _inject_wacc_beta(self, text: str) -> tuple:
        """注入 WACC/Beta（仅当估值段存在且参数缺失时）"""
        v = self.cr.get("dcf_valuation", {})
        if v.get("status") != "ok":
            return text, 0
        vr = v.get("result", {})
        wacc_str = vr.get("wacc", "")

        # 检查估值段附近是否已包含这些信息
        valuation_idx = text.find("估值")
        if valuation_idx < 0:
            return text, 0
        nearby = text[valuation_idx : valuation_idx + 300]
        if wacc_str and f"WACC {wacc_str}" in nearby:
            return text, 0
        if "WACC" in nearby and wacc_str:
            return text, 0

        # 注入参数（仅 WACC，不注入硬编码 beta）
        if wacc_str and "WACC" not in nearby:
            insert = f"\n\n**估值参数**：WACC {wacc_str}（Damodaran ERP + CAPM）\n"
            # 找估值段后第一个 section 标记
            next_sec = len(text)
            for m in ["催化剂", "证伪", "资金面", "风险提示", "投资评级"]:
                idx = text.find(m, valuation_idx)
                if idx > 0 and idx < next_sec:
                    next_sec = idx
            text = text[:next_sec] + insert + text[next_sec:]
            return text, 1
        return text, 0

    def _inject_erp(self, text: str) -> tuple:
        """在估值段附近注入达摩达兰ERP信息"""
        erp = self.cr.get("damodaran_erp", {})
        if erp.get("status") != "ok":
            return text, 0
        er = erp.get("result", {})

        valuation_idx = text.find("估值")
        if valuation_idx < 0:
            return text, 0

        # 检查是否已有 ERP 信息
        sec = text[valuation_idx : valuation_idx + 400]
        if "ERP" in sec or "风险溢价" in sec or "达摩达兰" in sec:
            return text, 0

        insert = (
            f"\n\n**国家风险溢价**：中国主权评级 {er.get('rating', 'A1')}，"
            f"总ERP {er.get('total_erp', 0) * 100:.2f}%（Damodaran模型）\n"
        )
        next_sec = len(text)
        for m in ["催化剂", "证伪", "风险提示"]:
            idx = text.find(m, valuation_idx)
            if idx > 0 and idx < next_sec:
                next_sec = idx
        text = text[:next_sec] + insert + text[next_sec:]
        return text, 1

    def _inject_decision(self, text: str) -> tuple:
        """注入DecisionHub融合信号"""
        fusion = self.cr.get("fusion_decision", {})
        if fusion.get("status") != "ok":
            return text, 0
        fr = fusion.get("result", {})

        # 在核心判断段附近注入
        for marker in ["核心判断", "投资亮点", "核心逻辑", "投资要点"]:
            idx = text.find(marker)
            if idx >= 0:
                sec = text[idx : idx + 200]
                if "bull_prob" in sec or "信号融合" in sec:
                    return text, 0
                insert = (
                    f"\n\n**信号融合（定量）**：Bull {fr.get('bull_prob', 0) * 100:.0f}% / "
                    f"Bear {fr.get('bear_prob', 0) * 100:.0f}% / "
                    f"置信度 {fr.get('conviction', 0) * 100:.0f}%"
                    f"（{fr.get('n_signals', 0)}个信号）\n"
                )
                text = text[: idx + len(marker)] + insert + text[idx + len(marker) :]
                return text, 1
        return text, 0

    def _inject_heritage(self, text: str) -> tuple:
        """注入Heritage方法论内容"""
        h = self.cr.get("heritage", {})
        injection = h.get("_injection", "") if isinstance(h, dict) else ""
        if not injection:
            return text, 0
        # 在方法论段附近注入
        for marker in ["研究框架", "分析方法", "核心逻辑", "投资要点"]:
            idx = text.find(marker)
            if idx >= 0:
                sec = text[idx : idx + 100]
                if "方法论" in sec or "范式" in sec:
                    return text, 0
                text = text[: idx + len(marker)] + injection + text[idx + len(marker) :]
                return text, 1
        return text, 0

    def _inject_patterns(self, text: str) -> tuple:
        """注入Pattern检测信号"""
        pat = self.cr.get("pattern_signals", {})
        if pat.get("status") != "ok":
            return text, 0
        pr = pat.get("result", {})

        for marker in ["趋势分析", "财务分析", "成长性", "盈利能力"]:
            idx = text.find(marker)
            if idx >= 0:
                sec = text[idx : idx + 200]
                if "Pattern" in sec or "模式检测" in sec:
                    return text, 0
                lines = ["\n\n**模式检测信号**："]
                for pid, info in pr.items():
                    lines.append(
                        f"- {info.get('pattern_name', '')}: {info.get('signal', '')} "
                        f"(置信度 {info.get('confidence', 0) * 100:.0f}%)"
                    )
                lines.append("")
                insert = "\n".join(lines)
                text = text[: idx + len(marker)] + insert + text[idx + len(marker) :]
                return text, 1
        return text, 0
