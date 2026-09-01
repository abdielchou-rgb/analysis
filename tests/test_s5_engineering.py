"""S5-3/S5-4: Engineering reliability tests."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def test_pipeline_context_import():
    from core.pipeline_context import PipelineContext

    assert callable(PipelineContext)


def test_pipeline_context_fields():
    from core.pipeline_context import PipelineContext

    ctx = PipelineContext(asset="test", report_type="listed_company")
    assert ctx.asset == "test"
    assert ctx.report_type == "listed_company"
    assert ctx.chart_data == {}


def test_pipeline_context_get_set():
    from core.pipeline_context import PipelineContext

    ctx = PipelineContext()
    ctx.set("custom_key", "custom_value")
    assert ctx.get("custom_key") == "custom_value"
    assert ctx.get("nonexistent", "default") == "default"


def test_pipeline_context_to_dict():
    from core.pipeline_context import PipelineContext

    ctx = PipelineContext(asset="test")
    d = ctx.to_dict()
    assert isinstance(d, dict)
    assert d["asset"] == "test"


def test_pipeline_context_from_dict():
    from core.pipeline_context import PipelineContext

    d = {"asset": "test", "report_type": "industry_deep", "extra_field": 42}
    ctx = PipelineContext.from_dict(d)
    assert ctx.asset == "test"
    assert ctx.report_type == "industry_deep"
    assert ctx._extra["extra_field"] == 42


def test_checkpoint_save_load_clear():
    from pipeline.agent_graph import clear_checkpoint, load_checkpoint, save_checkpoint

    save_checkpoint("test_pipe", "node_a", {"key": "value"})
    cp = load_checkpoint("test_pipe")
    assert cp is not None
    assert cp["last_node"] == "node_a"
    clear_checkpoint("test_pipe")
    cp2 = load_checkpoint("test_pipe")
    assert cp2 is None


def test_agent_graph_import():
    from pipeline.agent_graph import AgentGraph

    assert callable(AgentGraph)


def test_agent_graph_resume_param():
    """Verify run() accepts resume parameter."""
    import inspect

    from pipeline.agent_graph import AgentGraph

    sig = inspect.signature(AgentGraph.run)
    assert "resume" in sig.parameters
