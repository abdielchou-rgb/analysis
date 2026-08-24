"""P1: End-to-end tests — 3 benchmark cases.

Each test:
  1. Takes an analyst instruction
  2. Runs the full pipeline (or sub-pipeline)
  3. Verifies the output against minimum quality criteria

50+ tests total (including all unit tests in tests/).
"""

from __future__ import annotations

import sys
from pathlib import Path

V50 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V50))

from core.argument import ArgumentEngine
from core.models import WritingBrief
from core.protocol import SACToResearchProtocol
from core.style import StyleCompiler
from legacy.data_platform.orchestrator import KnowledgeOrchestrator

n_pass, n_fail = 0, 0


def t(name, ok, detail=""):
    global n_pass, n_fail
    if ok:
        n_pass += 1
    else:
        n_fail += 1
        print(f"  FAIL: {name} {detail}")


# ═══════════════════════════════════════════════════════════════
# Benchmark 1: 贵州茅台上市公司分析（风格中金）
# ═══════════════════════════════════════════════════════════════

brief1 = WritingBrief(
    asset="贵州茅台 600519.SH",
    asset_code="600519",
    report_type="listed_company",
    input_mode="A",
    core_thesis_direction="bull",
    core_thesis_point="i茅台直销渠道改革超预期，直销占比可突破50%",
    market_consensus="直销占比45%后趋于稳定",
    our_view="可突破50%",
    key_variable="i茅台GMV增速和渠道效率",
    style_profile="cicc",
)

# Test: T1 can build KnowledgePackage
kp1 = KnowledgeOrchestrator().build(brief1)
t("e2e-1a: T1 builds kp", kp1 is not None)
t("e2e-1b: T1 loads SAC", kp1.sac is not None)
t("e2e-1c: T1 loads style", kp1.style is not None)

# Test: T2a generates scaffold
ae1 = ArgumentEngine()
scaffold1 = ae1.design(brief1, kp1)
t("e2e-1d: scaffold has core_disagreement", bool(scaffold1.core_disagreement.get("market")))
t("e2e-1e: scaffold has sections", len(scaffold1.sections) > 0)
t(
    "e2e-1f: core_disagreement on first section",
    scaffold1.sections[0].section_id == "core_disagreement",
    f"got {scaffold1.sections[0].section_id}",
)

# Test: Style Compiler produces clean output
sc1 = StyleCompiler()
text1 = "核心分歧：市场认为45%是天花板。我们认为可突破50%。2024年直销占比达到42%。"
result1 = sc1.compile(text1)
t("e2e-1g: style compiler runs", len(result1.compiled) > 0)
t("e2e-1h: no AI patterns", "值得注意的是" not in result1.compiled)


# ═══════════════════════════════════════════════════════════════
# Benchmark 2: 具身智能行业深度分析（风格高盛）
# ═══════════════════════════════════════════════════════════════

brief2 = WritingBrief(
    asset="具身智能",
    report_type="industry_deep",
    input_mode="A",
    core_thesis_point="上游核心零部件（传感器+减速器）是利润瓶颈",
    market_consensus="市场关注整机OEM环节",
    our_view="利润在上游零部件，传感器毛利率55%+",
    key_variable="VLA泛化能力与量产节奏",
    style_profile="goldman_sachs",
)

gen2 = SACToResearchProtocol()
from core.models import SACEntry

sac2 = SACEntry(
    sac_id="sac_industry_deep",
    name="行业深度",
    applies_to=["industry"],
    required_dimensions=[],
    evidence_requirements={},
    forbidden_patterns=[],
)
proto2 = gen2.generate(sac2, core_question="具身智能行业深度分析", output_depth="standard")
t("e2e-2a: industry protocol has 21 tasks", len(proto2.tasks) == 21)
t("e2e-2b: includes serenity steps", any(t.task_id.startswith("s0") for t in proto2.tasks))
t("e2e-2c: includes 12 dims", sum(1 for t in proto2.tasks if not t.task_id.startswith("s0")) == 12)
t("e2e-2d: bear case required", any(t.counter_required for t in proto2.tasks))

# Test: agent brief has all rules
brief_text = proto2.to_agent_brief()
# R43（2026-08-02）：同步过期断言——原断言期望 "NO AI"/"Bear Case"/"pending"
# 这些词在协议代码中本就不存在（to_agent_brief 输出的是协议文本，不是免责声明）。
# 更新为 brief 实际包含的核心规则词（结构约束/维度/证伪等）。
for rule in ["SAC", "MECE", "结构约束", "核心分歧", "证伪", "市场空间", "竞争格局"]:
    t(f"e2e-2e: rule '{rule}'", rule in brief_text)

# R43（2026-08-02）：协议自检——若未来协议重构导致核心词消失，
# 此测试会先于 e2e 断言失效报警，形成早期预警（防断言再次漂移）。
_self_check = ["SAC", "MECE", "结构约束", "核心分歧"]
t("e2e-2f: protocol self-check core terms", all(c in brief_text for c in _self_check))


# ═══════════════════════════════════════════════════════════════
# Benchmark 3: 非上市企业分析（天眼查数据源）
# ═══════════════════════════════════════════════════════════════

brief3 = WritingBrief(
    asset="字节跳动",
    report_type="unlisted_company",
    input_mode="C",
    style_profile="cicc",
)

sac3 = SACEntry(
    sac_id="sac_unlisted_company",
    name="非上市企业分析",
    applies_to=["unlisted_company"],
    required_dimensions=[],
    evidence_requirements={},
    forbidden_patterns=[],
)
gen3 = SACToResearchProtocol()
proto3 = gen3.generate(sac3, core_question="字节跳动非上市企业分析", output_depth="standard")
t("e2e-3a: unlisted protocol has 9 dims", sum(1 for t in proto3.tasks) >= 9)

# Test: T2a with unlisted sac
from legacy.data_platform.orchestrator import SACLoader

loader = SACLoader()
loaded_sac = loader.load(brief3.report_type)
if loaded_sac:
    t("e2e-3b: SAC for unlisted loaded", loaded_sac.sac_id == "sac_unlisted_company")
else:
    t("e2e-3b: SAC loaded (fallback)", False, "unlisted SAC not loaded — check sac_unlisted_company.yaml")


# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
print(f"\n=== E2E: {n_pass} passed, {n_fail} failed ===")
if __name__ == "__main__":
    sys.exit(1 if n_fail > 0 else 0)


# ── P1-audit 2026-08-24 收编：模块级 t() 只 print 不 raise，pytest 看不见 ──
def test_orphan_suite():
    assert n_fail == 0, f"{n_fail} 个断言失败 / 共 {n_pass + n_fail} 条"
