"""2hao-analyst 全局 pytest 配置。

P1-audit 2026-08-24：此前全项目 0 个 conftest——sys.path 样板在 70 个
测试文件里逐字复制、无共享 fixture、无统一 env 处理。本文件收口：

1. sys.path 引导（等价于各测试文件头部的三行样板，可逐步删除重复）
2. .env 加载（仅当未注入时；CI 通过 secrets 注入，不读盘）
3. 网络隔离 fixture（offline guard，防止意外真实 LLM 调用烧钱）
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_env_dotenv_lite() -> None:
    """轻量 .env 解析（与 main.py 同规则）；已存在的环境变量不覆盖。"""
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


_load_env_dotenv_lite()


# ── 共享 fixtures ──

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return _ROOT


@pytest.fixture()
def no_llm_calls(monkeypatch):
    """阻断真实 LLM 调用的保险丝。

    对 deepseek_client 与 section_writer 两处绑定同时打桩——
    from-import 持引用副本，只 patch 一处会漏（见 test_engineering_plan.py 注释）。
    """
    def _deny(*args, **kwargs):
        raise RuntimeError("测试尝试发起真实 LLM 调用（被 no_llm_calls fixture 拦截）")

    try:
        import core.deepseek_client as dsc
        monkeypatch.setattr(dsc, "call_deepseek", _deny, raising=False)
    except Exception:
        pass
    try:
        import pipeline.section_writer as sw
        if hasattr(sw, "call_deepseek"):
            monkeypatch.setattr(sw, "call_deepseek", _deny, raising=False)
    except Exception:
        pass


@pytest.fixture()
def tmp_output_dir(tmp_path):
    """替代直接写 output/ 的临时输出目录（切断对运行时产物的耦合）。"""
    out = tmp_path / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out
