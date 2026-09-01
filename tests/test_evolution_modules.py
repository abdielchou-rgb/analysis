"""
tests/test_evolution_modules.py — 进化模块测试

测试新创建的模块：
1. pipeline/debate_engine.py
2. pipeline/prompt_manager.py
3. pipeline/data_bundler.py
4. pipeline/adversarial_committee.py
5. pipeline/dynamic_rag.py
6. pipeline/traceability.py
7. pipeline/human_in_the_loop.py
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 添加项目根目录到路径
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class TestDebateEngine:
    """测试辩论引擎"""

    def test_import(self):
        """测试导入"""
        from pipeline.debate_engine import DebateEngine, DebateResult, DebateRole

        assert DebateEngine is not None
        assert DebateResult is not None
        assert DebateRole is not None

    def test_debate_roles(self):
        """测试辩论角色"""
        from pipeline.debate_engine import DebateRole

        assert DebateRole.BULL.value == "bull"
        assert DebateRole.BEAR.value == "bear"
        assert DebateRole.JUDGE.value == "judge"
        assert DebateRole.QUANT_REFEREE.value == "quant_referee"

    def test_debate_result_defaults(self):
        """测试辩论结果默认值"""
        from pipeline.debate_engine import DebateResult

        result = DebateResult()
        assert result.bull_thesis == ""
        assert result.bear_thesis == ""
        assert result.judge_conclusion == ""
        assert result.confidence == 0.0
        assert result.probability == 0.0
        assert result.rounds == 0

    def test_debate_engine_init(self):
        """测试辩论引擎初始化"""
        from pipeline.debate_engine import DebateEngine

        engine = DebateEngine(max_rounds=5, convergence_threshold=0.2)
        assert engine.max_rounds == 5
        assert engine.convergence_threshold == 0.2

    @patch("pipeline.debate_engine.call_deepseek")
    def test_debate_flow(self, mock_call):
        """测试辩论流程"""
        from pipeline.debate_engine import DebateEngine

        # Mock LLM 响应
        mock_call.return_value = {"choices": [{"message": {"content": "测试论点，置信度: 70%"}}]}

        engine = DebateEngine(max_rounds=2)
        result = engine.debate(
            asset="测试标的",
            data_str="测试数据",
            report_type="listed_company",
        )

        assert result.rounds > 0
        assert result.bull_thesis != ""
        assert result.bear_thesis != ""
        assert result.judge_conclusion != ""


class TestPromptManager:
    """测试 Prompt 管理器"""

    def test_import(self):
        """测试导入"""
        from pipeline.prompt_manager import PromptContext, PromptManager

        assert PromptManager is not None
        assert PromptContext is not None

    def test_prompt_context(self):
        """测试 Prompt 上下文"""
        from pipeline.prompt_manager import PromptContext

        ctx = PromptContext(
            report_type="listed_company",
            style="cicc",
            asset="测试标的",
        )
        assert ctx.report_type == "listed_company"
        assert ctx.style == "cicc"
        assert ctx.asset == "测试标的"

    def test_prompt_manager_init(self):
        """测试 Prompt 管理器初始化"""
        from pipeline.prompt_manager import PromptManager

        pm = PromptManager(report_type="industry_deep", style="gs")
        assert pm.report_type == "industry_deep"
        assert pm.style == "gs"

    def test_build_system_prompt(self):
        """测试构建系统提示词"""
        from pipeline.prompt_manager import PromptContext, PromptManager

        pm = PromptManager()
        ctx = PromptContext(report_type="listed_company")
        prompt = pm.build_system_prompt(ctx)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_user_prompt(self):
        """测试构建用户提示词"""
        from pipeline.prompt_manager import PromptContext, PromptManager

        pm = PromptManager()
        ctx = PromptContext(report_type="listed_company")
        prompt = pm.build_user_prompt(ctx, data_str="测试数据")
        assert isinstance(prompt, str)


class TestDataBundler:
    """测试数据捆绑器"""

    def test_import(self):
        """测试导入"""
        from pipeline.data_bundler import DataBundle, DataBundler

        assert DataBundler is not None
        assert DataBundle is not None

    def test_data_bundle_defaults(self):
        """测试数据捆绑默认值"""
        from pipeline.data_bundler import DataBundle

        bundle = DataBundle()
        assert bundle.live == {}
        assert bundle.reference == {}

    def test_data_bundler_init(self):
        """测试数据捆绑器初始化"""
        from pipeline.data_bundler import DataBundler

        bundler = DataBundler(max_data_length=5000)
        assert bundler.max_data_length == 5000

    def test_build_bundle(self):
        """测试构建数据捆绑"""
        from pipeline.data_bundler import DataBundler

        bundler = DataBundler()
        bundle = bundler.build_bundle({"financials": {"revenue": 100}})
        assert "financials" in bundle.live

    def test_bundle_to_string(self):
        """测试数据捆绑转字符串"""
        from pipeline.data_bundler import DataBundle, DataBundler

        bundler = DataBundler()
        bundle = DataBundle(live={"test": "value"})
        result = bundler.bundle_to_string(bundle)
        assert isinstance(result, str)
        assert "test" in result


class TestAdversarialCommittee:
    """测试对抗委员会"""

    def test_import(self):
        """测试导入"""
        from pipeline.adversarial_committee import AdversarialCommittee, CommitteeMember

        assert AdversarialCommittee is not None
        assert CommitteeMember is not None

    def test_committee_member(self):
        """测试委员会成员"""
        from pipeline.adversarial_committee import CommitteeMember

        member = CommitteeMember(name="Test", role="bull", provider="deepseek")
        assert member.name == "Test"
        assert member.role == "bull"

    def test_committee_init(self):
        """测试委员会初始化"""
        from pipeline.adversarial_committee import AdversarialCommittee

        committee = AdversarialCommittee(max_rounds=2)
        assert committee.max_rounds == 2
        assert len(committee.members) > 0


class TestDynamicRAG:
    """测试动态 RAG"""

    def test_import(self):
        """测试导入"""
        from pipeline.dynamic_rag import DynamicRAG, Evidence, RAGResult

        assert DynamicRAG is not None
        assert Evidence is not None
        assert RAGResult is not None

    def test_evidence(self):
        """测试证据"""
        from pipeline.dynamic_rag import Evidence

        evidence = Evidence(content="test", source="test_source", relevance=0.8)
        assert evidence.content == "test"
        assert evidence.relevance == 0.8

    def test_rag_init(self):
        """测试 RAG 初始化"""
        from pipeline.dynamic_rag import DynamicRAG

        rag = DynamicRAG(max_evidences=5)
        assert rag.max_evidences == 5

    def test_retrieve(self):
        """测试检索"""
        from pipeline.dynamic_rag import DynamicRAG

        rag = DynamicRAG()
        result = rag.retrieve("测试查询")
        assert isinstance(result.evidences, list)


class TestTraceability:
    """测试溯源链"""

    def test_import(self):
        """测试导入"""
        from pipeline.traceability import Claim, DataSource, TraceabilityEngine

        assert TraceabilityEngine is not None
        assert Claim is not None
        assert DataSource is not None

    def test_claim(self):
        """测试观点"""
        from pipeline.traceability import Claim

        claim = Claim(claim_id="test", content="测试观点", confidence=0.8)
        assert claim.claim_id == "test"
        assert claim.confidence == 0.8

    def test_traceability_init(self):
        """测试溯源引擎初始化"""
        from pipeline.traceability import TraceabilityEngine

        engine = TraceabilityEngine()
        assert len(engine._claims) == 0

    def test_add_claim(self):
        """测试添加观点"""
        from pipeline.traceability import TraceabilityEngine

        engine = TraceabilityEngine()
        claim = engine.add_claim("test", "测试观点", confidence=0.8)
        assert claim.claim_id == "test"
        assert len(engine._claims) == 1

    def test_trace_claim(self):
        """测试溯源观点"""
        from pipeline.traceability import TraceabilityEngine

        engine = TraceabilityEngine()
        engine.add_claim("test", "测试观点", confidence=0.8)
        result = engine.trace_claim("test")
        assert result is not None
        assert result["claim"]["id"] == "test"


class TestHumanInTheLoop:
    """测试 Human-in-the-loop"""

    def test_import(self):
        """测试导入"""
        from pipeline.human_in_the_loop import DecisionPoint, HumanInTheLoop

        assert HumanInTheLoop is not None
        assert DecisionPoint is not None

    def test_decision_point(self):
        """测试决策点"""
        from pipeline.human_in_the_loop import DecisionPoint

        point = DecisionPoint(
            point_id="test",
            description="测试决策点",
            options=["选项1", "选项2"],
        )
        assert point.point_id == "test"
        assert len(point.options) == 2

    def test_human_in_the_loop_init(self):
        """测试 Human-in-the-loop 初始化"""
        from pipeline.human_in_the_loop import HumanInTheLoop

        hitl = HumanInTheLoop()
        assert len(hitl._decision_points) == 0

    def test_add_decision_point(self):
        """测试添加决策点"""
        from pipeline.human_in_the_loop import HumanInTheLoop

        hitl = HumanInTheLoop()
        point = hitl.add_decision_point("test", "测试决策点", ["选项1", "选项2"])
        assert point.point_id == "test"
        assert len(hitl._decision_points) == 1

    def test_record_human_decision(self):
        """测试记录人工决策"""
        from pipeline.human_in_the_loop import HumanInTheLoop

        hitl = HumanInTheLoop()
        hitl.add_decision_point("test", "测试决策点", ["选项1", "选项2"])
        record = hitl.record_human_decision("test", "选项1", "原因")
        assert record is not None
        assert record.final_decision == "选项1"

    def test_get_pending_decisions(self):
        """测试获取待决策点"""
        from pipeline.human_in_the_loop import HumanInTheLoop

        hitl = HumanInTheLoop()
        hitl.add_decision_point("test", "测试决策点", ["选项1", "选项2"])
        pending = hitl.get_pending_decisions()
        assert len(pending) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
