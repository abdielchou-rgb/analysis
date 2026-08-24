# -*- coding: utf-8 -*-
"""R83 P0-2：enrich 回流链路回归测试

油位 v0.89 事故根因（2026-08-07 诊断）：
  enrich v086 文件含全球 TAM=46亿美元(2024)，但 v0.89 正文用 12.8亿美元（油位v8窄口径），
  4倍错差未被 data_caliber 拦截——因为 enrich 数据根本没有进正文。

本测试守护"enrich 注入的关键数值必须能进入报告正文"链路，防止 section_writer
用训练记忆覆盖 enrich 注入值。分三层：
  1. AgentEnricher.merge 正确把 enrich fig_data 合并进 collected_data.chart_data
  2. 合并后 collected_data 可被序列化进写作 prompt（_serialize_data 路径）
  3. R89 市场规模清理器（sanitize_report_market_sizes）把自创口径修正回权威锚点

可独立运行：python tests/test_r83_enrich_roundtrip.py
也可被 tests/run_all.py 调用：run() 返回 (n_pass, n_fail)
"""

from __future__ import annotations
import sys, os, json, tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _make_enrich_file(items: list) -> str:
    """写一个临时 enrich-file，返回路径。"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    payload = {"asset": "油位传感器", "generated_by": "test", "generated_at": "2026-08-07",
               "items": items}
    tmp.write(json.dumps(payload, ensure_ascii=False))
    tmp.close()
    return tmp.name


def run(report=None) -> tuple:
    n_pass, n_fail = 0, 0

    def t(name, ok, detail=""):
        nonlocal n_pass, n_fail
        if ok:
            n_pass += 1
        else:
            n_fail += 1
            msg = f"  FAIL: {name} {detail}"
            print(msg)
            if report:
                report(name, ok, detail)

    from pipeline.data_enrichment import AgentEnricher

    # ── 1. merge 把 enrich fig_data 正确注入 chart_data ─────
    enrich_path = _make_enrich_file([{
        "type": "fig_data", "key": "fig_market_size_global",
        "data": {"2024": 46, "2025": 50, "2030": 65},
        "source": "三角验证(A)", "unit": "亿美元", "confidence": 0.85,
    }])
    data = {"chart_data": {"company_intro": "测试"}}
    merged = AgentEnricher.merge("油位传感器", data, enrich_path)
    cd = merged.get("chart_data", {})
    t("enrich accepted_count==1",
      merged.get("enrichment", {}).get("accepted_count") == 1,
      str(merged.get("enrichment", {}).get("accepted")))
    t("enrich fig injected into chart_data",
      cd.get("fig_market_size_global", {}).get("2024") == 46,
      str(cd.get("fig_market_size_global")))
    t("enrich unit in _caliber",
      cd.get("_caliber", {}).get("fig_market_size_global", {}).get("unit") == "亿美元",
      str(cd.get("_caliber", {}).get("fig_market_size_global")))
    t("enrich source in _agent_sources",
      cd.get("_agent_sources", {}).get("fig_market_size_global", {}).get("source", "").startswith("三角验证"),
      str(cd.get("_agent_sources", {}).get("fig_market_size_global")))
    os.unlink(enrich_path)

    # ── 2. 无 source 的 fig_data 被拒（FP2 合规）─────────────────
    enrich_path2 = _make_enrich_file([{
        "type": "fig_data", "key": "fig_market_size_global",
        "data": {"2024": 99}, "source": "", "confidence": 0.9,
    }])
    data2 = {"chart_data": {}}
    merged2 = AgentEnricher.merge("油位传感器", data2, enrich_path2)
    t("enrich missing source rejected",
      merged2.get("enrichment", {}).get("accepted_count") == 0
      and merged2.get("enrichment", {}).get("rejected_count") == 1,
      str(merged2.get("enrichment", {}).get("rejected")))
    os.unlink(enrich_path2)

    # ── 3. 合并后 collected_data 可被写作侧序列化（prompt 注入）──
    # 模拟 section_writer 的 _serialize_data：图数据 key 必须出现在序列化文本
    try:
        from pipeline.section_writer import SectionWriter
        sw = SectionWriter(report_type="industry_deep")
        ser = sw._serialize_data({"chart_data": {
            "fig_market_size_global": {"2024": 46, "2030": 65},
            "company_intro": "测试",
        }})
        t("enrich fig serialized into prompt",
          "fig_market_size_global" in ser and "46" in ser,
          f"serialized {len(ser)} chars")
    except Exception as e:
        t("enrich fig serialized into prompt", False, f"异常: {str(e)[:80]}")

    # ── 3b. R84：enrich text 键场景继承——场景/竞争/政策/委托方实体必须进序列化 ──
    # 油位 v0.90 事故：46亿/166亿数字进去了，但 competition_truth/policy_chain/
    # 华虹/久通/托肯恒山/加油站/危化品 全没进正文（换了行业叙事）。
    # 本测试守护 text 键（场景数据）可靠进入写作 prompt。
    try:
        from pipeline.section_writer import SectionWriter
        sw2 = SectionWriter(report_type="decision_memo")
        ser2 = sw2._serialize_data({"chart_data": {
            "competition_truth": "托肯恒山是中石化核心供应商(Dover体系)；富仁高科主导国标",
            "policy_chain": "加油站防渗改造执行率62%，2026H2替换高峰，危化品SIS改造",
            "huahong_intro": "华虹科技是柯力控股子公司(拟增持96%)",
            "jiutong_intro": "久通物联覆盖80+国家海关/物流客户",
            "company_intro": "柯力传感603662",
            "keli_strategy": "柯力净利率25.11%，产能闲置15%可承接",
        }})
        _text_ents = ["托肯恒山", "防渗改造", "危化品", "华虹", "久通", "柯力"]
        _missing = [e for e in _text_ents if e not in ser2]
        t("enrich text keys serialize into prompt",
          not _missing, f"缺失: {_missing}")
        t("enrich text 场景(加油站) serialize",
          "加油站" in ser2 or "危化品" in ser2, "场景数据应进 prompt")
    except Exception as e:
        t("enrich text keys serialize into prompt", False, f"异常: {str(e)[:80]}")

    # ── 4. R89 市场规模清理器：自创口径被修正回权威锚点 ────────
    try:
        from pipeline.sw_serialize import sanitize_report_market_sizes
        fake_body = "中国油位传感器市场规模2024年为1亿元，2030年达5亿元。"
        chart_data = {"fig_market_size_china": {"2024": 166, "2025": 172, "2030": 200}}
        cleaned = sanitize_report_market_sizes(fake_body, chart_data=chart_data)
        # 自创口径应被替换为权威锚点 166 亿元（或至少不再是 1 亿元）
        t("R89 sanitize fixes fabricated market size",
          "1亿元" not in cleaned and "166" in cleaned,
          f"cleaned={cleaned[:80]}")
    except Exception as e:
        t("R89 sanitize fixes fabricated market size", False, f"异常: {str(e)[:80]}")

    # ── 5. data_caliber 冲突检测：正文数值 vs enrich 权威锚点 4倍错差应拦截 ──
    try:
        from pipeline.iron_gate import IronGate
        # 构造 enrich 锚点文件（全球46亿美元），设 ENRICH_ANCHOR_FILE 驱动锚点比对
        anchor_path = _make_enrich_file([{
            "type": "fig_data", "key": "fig_market_size_global",
            "data": {"2024": 46, "2025": 50, "2030": 65},
            "source": "三角验证(A)", "unit": "亿美元", "confidence": 0.85,
        }])
        tmp_md = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        tmp_md.write(
            "全球油位传感器市场规模2024年为12.8亿美元，2030年15.2亿美元。"
            "该行业值得关注。")
        tmp_md.close()
        os.environ["ENRICH_ANCHOR_FILE"] = anchor_path
        try:
            ig = IronGate(tmp_md.name, report_type="industry_deep", asset="R83_TEST_ASSET")
            _r1 = ig._check_market_size_consistency()
            # 正文 12.8 vs 权威锚点 46 → 偏差>20% 应 FAIL
            t("gate detects market size 4x mismatch vs enrich anchor",
              not _r1.passed,
              f"name={_r1.name} passed={_r1.passed} score={_r1.score:.2f} det={_r1.details[:120]}")
        finally:
            os.environ.pop("ENRICH_ANCHOR_FILE", None)
            os.unlink(tmp_md.name)
            os.unlink(anchor_path)
    except Exception as e:
        t("gate detects market size 4x mismatch vs enrich anchor", False, f"异常: {str(e)[:80]}")

    return n_pass, n_fail


if __name__ == "__main__":
    p, f = run()
    print(f"\nR83 enrich 回流回归测试: {p} passed, {f} failed")
    sys.exit(1 if f else 0)
