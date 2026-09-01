"""numeric_chain.py — 数值链自洽校验（Strangler Fig 拆解第一步，P4-3 2026-09-01）。

从 pipeline/checks/data_quality_mixin.py 的 _check_numeric_chain_consistency 拆出
（264 行巨石方法）。只依赖 report_text，无其他 self 依赖 → 完美拆解点。

Strangler Fig 纪律：拆出后 data_quality_mixin 委托调用本函数，
行为不变（golden 报告 diff 为空），后续可逐步迁移其他大方法。
"""

from __future__ import annotations

from pipeline.checks.base import GateCheckResult

import re as _re


def check_numeric_chain_consistency(report_text: str) -> "GateCheckResult":
    """R88（2026-08-10）：数值链自洽校验——行业报告分散式数值的独立验算。

    背景：商业航天行业报告 Gate 全绿却含 3 处算术硬伤——
      ①"中国占全球 8.3%"（实为 83%，数量级错误）；
      ②目标价"0.70×55=38.40"（实为 38.5）；
      ③上行空间"15-20%"（按自身数据实为 25.2%）。
    根因：R35/R53 的正则都是为个股报告特定表述设计的（"X股占总股本Y%"、
          "目标价X元较现价Y元Z%"三段同现），行业报告分散式表述全部漏检。

    本检查不依赖特定表述，做**数值链自洽**验算（偏差 >5% 或数量级错即 FAIL）：
      1. 占比反向验算："X占[前文N]的Z%" → 抓同句内 X/Y=Z% 的数量级错误
         （覆盖"中国占全球 8.3%"——X=2.83万亿、Y=4800亿美元 需归一化后验算）
      2. EPS×PE 目标价链："EPS X元、PE Y倍、目标价=Z元" → 验算 X×Y=Z
         （覆盖"0.70×55=38.40"——实为 38.5）
      3. 目标价/现价空间："目标价X元、现价/当前价Y元、空间Z%" → 验算 (X/Y-1)=Z
         （覆盖"目标价38.40元、当前股价对应2025PE52倍(隐含30.68元)、空间15-20%"）
      4. 细分合计 vs 总量："A+B+C+D=约E" → 验算累加一致
         （覆盖"4450+8520+7530+9350=约2.99万亿"）
    """
    import re as _re

    text = report_text or ""
    if len(text) < 300:
        return GateCheckResult(
            "numeric_chain_consistency", True, 1.0, "text too short, skipped", severity="warning"
        )
    issues = []
    _TOL = 0.05

    def _fmt(x):
        return f"{x:.2f}" if abs(x - round(x, 2)) > 1e-6 else f"{x:g}"

    # ── 1. 占比反向验算（含币种归一化） ────────────────────
    # 商业航天案："中国TAM 2.83万亿元人民币（2025年，A）...按当前汇率（约7.1）折算，
    #              中国占全球商业航天市场约8.3%（...人民币÷7.1÷4800亿美元）"
    # 分子（2.83万亿元）在"占"前 60-200 字，分母（4800亿美元）在"占"后括号内。
    # 策略：找"占...市场约Z%"结构，然后在"占"前 260 字内找最近的"X万亿元/亿元"作分子，
    # 在"占"后 120 字内找"Y亿美元/亿元"作分母。
    _fx = 7.0
    _fx_m = _re.search(r"汇率[^\d]{0,4}(\d+(?:\.\d+)?)", text)
    if _fx_m:
        try:
            _fx = float(_fx_m.group(1))
        except (ValueError, TypeError):
            pass

    for m in _re.finditer(
        r"(?:占|占全|占市场|占全球)[^\n。；]{0,4}?"
        r"(?:全球|全球市场|市场|总规模|总市场)"
        r"[^。；\n]{0,25}?(?:约|为|占|达)?\s*(\d+(?:\.\d+)?)\s*%",
        text,
    ):
        try:
            pct_claimed = float(m.group(1))
            if not (0.01 < pct_claimed < 1000):
                continue
            # 分子：占前同一句内（不跨句号）找"X万亿/亿元"，窗口 200 字
            before = text[max(0, m.start() - 200) : m.start()]
            # 若"占"前有句号，截到句号后（防止跨句串数）
            _last_period = before.rfind("。")
            if _last_period >= 0:
                before = before[_last_period + 1 :]
            # 分子必须是"占"前紧邻的金额（前 30 字内优先），否则可能把
            # "国内收入11.81亿元，占总收入75.76%"这种合法表述误配——
            # 该表述的占比(75.76%)就是直接声明，无需分母验算，且分母不在句中。
            num_m = None
            for nm in reversed(list(_re.finditer(r"(\d+(?:\.\d+)?)\s*(万亿元|亿元|万亿美元|亿美元)", before))):
                num_m = nm
                break
            if not num_m:
                continue
            # 关键约束：分子距"占"不能太远（>120字）→ 视为非占比语境，跳过
            if m.start() - num_m.end() > 120:
                continue
            num = float(num_m.group(1))
            num_unit = num_m.group(2)
            # 分母：占后 100 字内"Y亿美元/亿元"（优先紧邻）
            after = text[m.end() : m.end() + 100]
            # 若"占后"跨句号则截断（分母须同句）
            _nxt_period = after.find("。")
            if _nxt_period >= 0:
                after = after[:_nxt_period]
            den_m = _re.search(r"(\d+(?:\.\d+)?)\s*(万亿美元|亿美元|亿元)", after)
            if not den_m:
                continue
            den = float(den_m.group(1))
            den_unit = den_m.group(2)

            # 归一化到亿元
            def _to_yi(v, u):
                if u == "万亿元":
                    return v * 1e4
                if u == "万亿美元":
                    return v * 1e4
                if u == "亿美元":
                    return v
                if u == "亿元":
                    return v
                return v

            num_yi = _to_yi(num, num_unit)
            den_yi = _to_yi(den, den_unit)
            # 币种归一：美元×汇率→人民币
            if num_unit in ("万亿美元", "亿美元") and den_unit in ("万亿元", "亿元"):
                num_yi = num_yi * _fx
            elif den_unit in ("万亿美元", "亿美元") and num_unit in ("万亿元", "亿元"):
                den_yi = den_yi * _fx
            if den_yi <= 0:
                continue
            actual_pct = num_yi / den_yi * 100
            # 数量级/比例偏差：实际与声称差 >2倍，或相对偏差>20%
            if abs(actual_pct - pct_claimed) / max(actual_pct, 1e-9) > 0.20 or abs(pct_claimed - actual_pct) > 5:
                issues.append(
                    f"占比数量级错误: {_fmt(num)}{num_unit}占{_fmt(den)}{den_unit}="
                    f"{actual_pct:.1f}%，报告写{pct_claimed:.1f}%"
                    f"（差{abs(actual_pct - pct_claimed) / max(actual_pct, 1e-9) * 100:.0f}%）"
                )
        except (ValueError, TypeError, ZeroDivisionError):
            continue

    # ── 2. EPS×PE 目标价链 ────────────────────────────────
    # 模式："EPS X元" + "PE Y倍" + "目标价Z元" 或 "X×Y=Z"
    # 场景A：显式乘积 "0.70×55=38.40" 或 "0.70 × 55 = 38.40"
    # 注意：这是"声称的算术"，必须精确匹配（容差 <0.01%）。
    # 商业航天案：0.70×55=38.5，报告写 38.40（尾数错误），0.26% 偏差，
    # 若用 0.5% 容差会被吞掉。声称的等号表示"恒等"，差一位都不行。
    for m in _re.finditer(r"(\d+(?:\.\d+)?)\s*[×xX*]\s*(\d+(?:\.\d+)?)\s*[=＝]\s*(\d+(?:\.\d+)?)", text):
        try:
            a, b, c = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if a > 0 and b > 0 and c > 0 and 0.1 < a < 100 and 1 < b < 200:
                prod = a * b
                # 精确容差：声称的乘积必须与实算几乎一致（<0.01%）
                if abs(prod - c) / max(prod, 1e-9) > 0.0001:
                    issues.append(f"乘积验算错误: {_fmt(a)}×{_fmt(b)}={_fmt(prod)}，报告写{_fmt(c)}")
        except (ValueError, TypeError, ZeroDivisionError):
            continue
    # 场景B：目标价与 PE/EPS 显式绑定（括号内自洽结构）
    # 柯力案："目标价35元（基于2027年30倍PE，对应EPS 1.17元）" → 30×1.17=35.1≈35 ✓
    # 汇川案："目标价85元（对应2026年35倍PE，EPS 1.7元）" → 35×1.7=59.5 ≠ 85 ✗
    # 仅当"目标价"与"PE"与"EPS"同句且通过"基于/对应"绑定才验算，
    # 避免把多估值锚（PE30 vs PE35 各自目标价）串配。
    for m in _re.finditer(
        r"目标价[^。；\n]{0,30}?(\d+(?:\.\d+)?)\s*元[^。；\n]{0,25}?"
        r"(?:基于|对应|取)[^。；\n]{0,15}?"
        r"(\d+(?:\.\d+)?)\s*倍\s*PE[^。；\n]{0,20}?"
        r"(?:对应|EPS|每股收益)[^\d]{0,6}(\d+(?:\.\d+)?)\s*元",
        text,
    ):
        try:
            tp, pe, eps = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if tp > 0 and pe > 0 and eps > 0 and 1 < pe < 200 and 0 < eps < 100:
                implied = pe * eps
                # 该绑定应自洽：EPS×PE ≈ 目标价（<5% 容差，估值取整可接受）
                if abs(implied - tp) / max(implied, 1e-9) > 0.05:
                    issues.append(
                        f"目标价链错误: EPS{_fmt(eps)}×PE{_fmt(pe)}={_fmt(implied)}元，报告目标价写{_fmt(tp)}元"
                    )
        except (ValueError, TypeError, ZeroDivisionError):
            continue

    # ── 3. 目标价/现价空间 ────────────────────────────────
    # 覆盖商业航天案："目标价=0.70×55=38.40元...当前股价对应2025年PE约52倍" + "上行空间约15-20%"
    # 注意目标价正则要跳过"目标价=0.70×55="这种推导式（[^\d] 不能吞掉乘法数字），
    # 用"目标价[^=\d]{0,10}"禁止 = 后直接取数，优先匹配纯目标价"目标价38.40元"。
    # 关键：跳过**情景/敏感性目标价**（"双杀情景...目标价30元"）——这些是分情景值，
    # 合法地与现价产生负空间/大空间，只有结论/综合目标价才应对照上行空间验算。
    _SCENARIO_MARKERS = ("情景", "概率", "悲观", "双杀", "牛市", "中性", "乐观", "下行", "上行")
    for m in _re.finditer(r"目标价[^=\d]{0,10}(\d+(?:\.\d+)?)\s*元", text):
        try:
            tp = float(m.group(1))
            if not (1 < tp < 1000):
                continue
            # 情景过滤：目标价前 40 字或后 40 字内出现情景词 → 跳过
            _ctx_before = text[max(0, m.start() - 40) : m.start()]
            _ctx_after = text[m.end() : m.end() + 40]
            if any(mk in _ctx_before or mk in _ctx_after for mk in _SCENARIO_MARKERS):
                continue
            seg = text[max(0, m.start() - 300) : m.end() + 400]
            # 找现价（明写或隐含）
            cp = None
            cp_m = _re.search(r"(?:现价|当前股价|当前价|收盘价)[^\d]{0,6}(\d+(?:\.\d+)?)\s*元", seg)
            if cp_m:
                cp = float(cp_m.group(1))
            else:
                # 隐含现价：当前股价对应PE Y倍 × EPS Z元
                # 商业航天案：'当前股价对应2025年PE约52倍' + EPS约0.59元（前文）
                pe_m = _re.search(r"(?:对应|对应PE|PE\(TTM\)|当前PE|PE)[^\d]{0,4}(\d{1,3}(?:\.\d+)?)\s*倍", seg)
                eps_m = _re.search(r"EPS(?:约|为)?\s*(\d+(?:\.\d+)?)\s*元", seg)
                if pe_m and eps_m:
                    try:
                        pe_v = float(pe_m.group(1))
                        eps_v = float(eps_m.group(1))
                        if 5 < pe_v < 200 and 0 < eps_v < 100:
                            cp = pe_v * eps_v
                    except (ValueError, TypeError):
                        pass
            # 找上行空间（目标价后 500 字内——目标价声明后常隔"综合来看…"等
            # 长句才进入推导段，300 字窗口会漏，商业航天案实测）
            # 区间处理："约15-20%" → 15 后是 "-20%"；"约15%" → 15 后直接 "%"。
            up_m = _re.search(
                r"(?:上行空间|上涨空间)[^\d]{0,8}(?:约|为)?\s*"
                r"(\d+(?:\.\d+)?)(?:\s*%|\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*%)",
                text[m.end() : m.end() + 500],
            )
            if cp and cp > 0 and up_m:
                up_lo = float(up_m.group(1))
                up_hi = float(up_m.group(2)) if up_m.group(2) else up_lo
                actual = (tp / cp - 1) * 100
                # 容差：实际空间与声称区间端点偏差 >3pp 即报
                if actual < up_lo - 3 or actual > up_hi + 3:
                    # 多估值锚豁免：若段内存在**另一个**目标价，其相对现价的空间
                    # 与声称区间吻合（如汇川案 PE法27.4 vs DCF 70-80，上行空间
                    # 20-38% 对应 70-80），说明声称空间属于另一锚，非本锚矛盾。
                    _alt_ok = False
                    for _am in _re.finditer(r"(\d+(?:\.\d+)?)\s*元", seg):
                        try:
                            _alt_tp = float(_am.group(1))
                            if abs(_alt_tp - tp) < 1e-6 or _alt_tp <= 0:
                                continue
                            _alt_actual = (_alt_tp / cp - 1) * 100
                            if up_lo - 3 <= _alt_actual <= up_hi + 3:
                                _alt_ok = True
                                break
                        except (ValueError, TypeError, ZeroDivisionError):
                            continue
                    if not _alt_ok:
                        issues.append(
                            f"目标价空间错误: 目标价{tp}元 vs 隐含现价{cp:.2f}元=+{actual:.1f}%，"
                            f"报告写{up_lo:g}-{up_hi:g}%"
                        )
        except (ValueError, TypeError, ZeroDivisionError):
            continue

    # ── 4. 细分合计 vs 总量 ───────────────────────────────
    # 模式："A、B、C、D合计约E" 或 "A+B+C+D=E"（多个数字+单位累加）
    # 覆盖"火箭发射制造约4450亿元、卫星制造约8520亿元...合计约2.99万亿元"
    # 注意：数字可能带千分位逗号（"4,450亿元"），正则须兼容，否则 4450 被拆成 4 和 450。
    for m in _re.finditer(
        r"(\d[\d,]*\.?\d*)\s*亿元[^。；\n]{0,15}?(\d[\d,]*\.?\d*)\s*亿元[^。；\n]{0,15}?"
        r"(\d[\d,]*\.?\d*)\s*亿元[^。；\n]{0,15}?(\d[\d,]*\.?\d*)\s*亿元[^。；\n]{0,30}?"
        r"(?:合计|总计|总和)[^。；\n]{0,10}?(?:约|为)?\s*(\d[\d,]*\.?\d*)\s*万亿元",
        text,
    ):
        try:

            def _num(s):
                return float(s.replace(",", ""))

            parts = [_num(m.group(i)) for i in range(1, 5)]
            total_claimed = _num(m.group(5))
            total_actual = sum(parts) / 1e4  # 亿元→万亿元
            if abs(total_actual - total_claimed) / max(total_claimed, 1e-9) > _TOL:
                issues.append(
                    f"细分合计错误: {parts[0]:.0f}+{parts[1]:.0f}+{parts[2]:.0f}+{parts[3]:.0f}"
                    f"={total_actual:.2f}万亿元，报告写{total_claimed:.2f}万亿元"
                )
        except (ValueError, TypeError, ZeroDivisionError):
            continue

    passed = len(issues) == 0
    score = 1.0 if passed else max(0.2, 1.0 - 0.3 * len(issues))
    det = f"数值链校验: {len(issues)} 项错误" + (": " + "; ".join(issues[:3]) if issues else "无")
    return GateCheckResult("numeric_chain_consistency", passed, score, det, severity="error")
