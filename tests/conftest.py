"""2hao-analyst 全局 pytest 配置。

P1-audit 2026-08-24：此前全项目 0 个 conftest——sys.path 样板在 70 个
测试文件里逐字复制、无共享 fixture、无统一 env 处理。本文件收口：

1. sys.path 引导（等价于各测试文件头部的三行样板，可逐步删除重复）
2. .env 加载（仅当未注入时；CI 通过 secrets 注入，不读盘）
3. 网络隔离 fixture（offline guard，防止意外真实 LLM 调用烧钱）
"""

import importlib
import os
import shutil
import sys
from pathlib import Path

# 2026-09-14 审计修复（A8）：原 `_ROOT = Path(__file__).resolve().parent`
# 指向的是 tests/ 而非项目根，由此产生两个静默缺陷：
#   1) .env 加载器去找 tests/.env —— 该文件从不存在（真实 .env 在项目根），
#      于是 _load_env_dotenv_lite() 在第一行就 return，整个加载逻辑从未生效过。
#      实测：tests/.env → False；2hao-analyst/.env → True。
#   2) sys.path 只挂 tests/，无法 `from tests.x import y`——而 tests/run_all.py:644
#      正是这么写的（依赖各测试文件自行 insert 项目根才碰巧能跑）。
# 真实项目根是 parent.parent。tests/ 仍保留在 path 上以兼容既有写法。
_TESTS_DIR = Path(__file__).resolve().parent
_ROOT = _TESTS_DIR.parent
for _p in (str(_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load_env_dotenv_lite() -> None:
    """轻量 .env 解析（与 main.py 同规则）；已存在的环境变量不覆盖。

    2026-09-14：改为按 项目根 → tests/ 顺序探测，兼容两种放置方式。
    """
    for env_path in (_ROOT / ".env", _TESTS_DIR / ".env"):
        if not env_path.exists():
            continue
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
    """项目根目录（含 core/ pipeline/ tests/ 的那一层）。

    2026-09-14 审计修复前此 fixture 返回的是 tests/ 目录本身（见上方 _ROOT 注释），
    与名字不符；现返回真实项目根。当前无用例引用它，改动无破坏面。
    """
    return _ROOT


@pytest.fixture(scope="session")
def tests_dir() -> Path:
    """tests/ 目录本身（需要相对 tests/ 定位 golden 等夹具时用）。"""
    return _TESTS_DIR


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


# ══════════════════════════════════════════════════════════════════════
# 生产数据隔离（2026-09-14 审计 R4）——测试不得写生产 data/
# ══════════════════════════════════════════════════════════════════════
#
# 证据（受控实验）：对 data/ 与 core/data/ 下 6675 个 .json/.csv/.db/.jsonl
# 文件做 md5 快照，跑完整套件后比对，恰好 5 改 1 增：
#
#   MODIFIED data/learning_data.db
#   MODIFIED data/llm_cache/cache.db
#   MODIFIED data/method_reflection_log.json
#   MODIFIED data/predictions.json
#   MODIFIED data/write_checkpoints.db
#   CREATED  data/checkpoints/ba7579980e50.json
#
# 其中 method_reflection_log.json 是**永久泄漏**：test_r77_method_reflection
# 的两个用例把 __r77test__/__r77a__/__r77b__ 写进日志后只还原了 registry，
# 日志条目从未清理（该文件已累积到 53KB 垃圾）。其余几个靠用例内手写
# backup/restore 侥幸还原——一旦进程被杀或 restore 前抛异常，生产数据即被
# 污染。这类"手工回滚"是 fail-open 的：它依赖"每个用例都记得收尾"，
# 而没有任何机制强制这一点。
#
# 修复策略：把全部会写盘的存储重定向到 session 级 tmp 沙箱。
#
# 边界说明（不夸大）：本 fixture 保证的是**生产零写入**，不是**用例间零串扰**
# ——沙箱在 session 内共享，用例 A 写的数据用例 B 仍可见。这是刻意的取舍：
# track_record.json 单文件 1.9MB，若逐用例（function 级）建沙箱，
# 1136 个用例 × 拷贝 ≈ 2GB I/O，换来的只是更严格的用例间隔离。
# 用例间隔离属于另一个问题（如 smart_router 熔断器进程级全局态），
# 由各自的 fixture 处理，不应混入本机制。
# ══════════════════════════════════════════════════════════════════════

# (沙箱内相对路径, 生产源相对路径) —— 源不存在则跳过（不制造假夹具）
_HERMETIC_SEEDS: tuple[tuple[str, str], ...] = (
    ("framework_registry.json", "data/framework_registry.json"),
    ("method_reflection_log.json", "data/method_reflection_log.json"),
    ("predictions.json", "data/predictions.json"),
    ("forward_picks/track_record.json", "core/data/forward_picks/track_record.json"),
)

# diskcache 实例的持有者（Path 对象不支持 setattr，不能挂在沙箱路径上）
_HERMETIC_CACHE: dict = {}


@pytest.fixture(scope="session")
def hermetic_data_root(tmp_path_factory) -> Path:
    """session 级数据沙箱：预置只读副本 + 可写目标目录。

    需要断言"生产文件被写成什么样"的用例，应改为读取本沙箱——
    即读路径必须与生产代码的写路径同源（见 _HERMETIC_PATCHES）。
    """
    sandbox = tmp_path_factory.mktemp("hermetic_data")
    for rel, src_rel in _HERMETIC_SEEDS:
        src = _ROOT / src_rel
        if not src.exists():
            continue
        dst = sandbox / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for sub in ("checkpoints", "batches", "llm_cache", "forward_picks"):
        (sandbox / sub).mkdir(parents=True, exist_ok=True)
    return sandbox


def _hermetic_patches(sandbox: Path) -> list[tuple[str, str, object]]:
    """(模块, 属性, 沙箱值) —— 覆盖全部实测会写盘的存储。

    每条都对应一个**模块级常量**，消费者一律在函数体内通过模块全局读取
    （已逐一核对：learning_loop 在 __init__ 读、method_reflection 在函数内读、
    write_checkpoint 在 _connect 内读、agent_graph 在 _save/_load 内读），
    因此在模块属性上打桩即可生效，无需改产品代码。
    """
    return [
        ("pipeline.learning_loop", "LEARNING_DB", sandbox / "learning_data.db"),
        ("core.method_reflection", "REFLECTION_LOG_PATH", sandbox / "method_reflection_log.json"),
        ("core.method_reflection", "REGISTRY_PATH", sandbox / "framework_registry.json"),
        ("core.analyst_planner", "REGISTRY_PATH", sandbox / "framework_registry.json"),
        ("core.prediction_loop", "PREDICTION_DB", sandbox / "predictions.json"),
        # 2026-09-14 审计发现：data/predictions.json 有**两个**独立常量声明
        # ——prediction_loop（schema V51.3）与 prediction_loop_v2（schema V2，
        # 多一个 backtest_results 键）。core.prediction_extract.record_predictions
        # 走的是 v2，故只 patch v1 会漏——这正是首轮沙箱化后 predictions.json
        # 仍被改写的原因。两模块抢同一文件且 schema 不同，本身是产品缺陷
        # （见 AUDIT_20260914_top_thinking.md §预测账本双写），此处先补齐隔离。
        ("core.prediction_loop_v2", "PREDICTION_DB", sandbox / "predictions.json"),
        ("core.methodology_confidence", "_DB", sandbox / "predictions.json"),
        ("pipeline.write_checkpoint", "_CHECKPOINT_DB", sandbox / "write_checkpoints.db"),
        ("pipeline.agent_graph", "_CHECKPOINT_DIR", sandbox / "checkpoints"),
        ("scripts.run_reports", "_BATCH_DIR", sandbox / "batches"),
        # 函数而非常量：消费者（cohort/dashboard/prediction_validator）都在函数内
        # `from ... import default_storage_path`，调用时重新解析，故打桩有效。
        (
            "core.tools.track_record",
            "default_storage_path",
            lambda: str(sandbox / "forward_picks" / "track_record.json"),
        ),
    ]


# ── 生产写入守卫 ────────────────────────────────────────────────────
#
# 沙箱重定向只能覆盖**已知**的存储。新代码随时可能引入新的写路径
# （本轮实测：data/predictions.json 就因为存在第二个常量声明
#  prediction_loop_v2.PREDICTION_DB 而漏出沙箱）。把"零写入"做成
#  一次性人工验证等于没有验证——必须持续强制。
#
# 本守卫逐用例复检生产存储指纹，变了就让用例失败并点名写路径。
# 注意：这里用的是 (size, mtime_ns) 而非 md5——1136 个用例 × 2 次 ×
# 8MB 全量哈希 ≈ 18GB 读，代价不可接受。size+mtime 对 JSON 存储
# （写入必然改大小）足够灵敏；内容级验证由 _snap.py 全套件实验承担。

_GUARD_FILES = (
    "data/learning_data.db",
    "data/llm_cache/cache.db",
    "data/method_reflection_log.json",
    "data/framework_registry.json",
    "data/predictions.json",
    "data/write_checkpoints.db",
    "core/data/forward_picks/track_record.json",
)
_GUARD_DIRS = ("data/checkpoints", "data/batches")


def _guard_fingerprint() -> dict[str, str]:
    fp: dict[str, str] = {}
    for rel in _GUARD_FILES:
        p = _ROOT / rel
        try:
            st = p.stat()
            fp[rel] = f"{st.st_size}:{st.st_mtime_ns}"
        except OSError:
            fp[rel] = "ABSENT"
    for rel in _GUARD_DIRS:
        d = _ROOT / rel
        try:
            # 用 (name,size,mtime) 而非仅 name——只比名字会漏掉"覆盖已有文件"
            # （实测：test_e2e_no_network 每次都重写 data/checkpoints/pipeline.json，
            #  名字不变，纯 name 比对完全看不见）。
            fp[rel] = "|".join(sorted(f"{c.name}:{c.stat().st_size}:{c.stat().st_mtime_ns}" for c in d.iterdir()))
        except OSError:
            fp[rel] = "ABSENT"
    return fp


@pytest.fixture(autouse=True)
def _no_production_writes(request):
    """逐用例断言：产品代码不得改写生产 data/（HERMETIC_GUARD_FAIL=1 启用）。

    默认只观测、不 fail，原因是一个**环境事实**而非设计妥协：本机上有一个
    并发的 600519（贵州茅台）报告生成任务在持续写同一个 data/ 树。实测
    ——纯空闲 100 秒、一个测试都不跑，data/ 仍新增 81 个文件
    （data/module_versions/600519/**）并重写 2 个 checkpoint。若默认 fail，
    本机每次跑套件都会因这个外部任务而随机红。CI（无并发任务）应显式开启。
    """
    if os.environ.get("HERMETIC_GUARD_FAIL") != "1":
        yield
        return
    before = _guard_fingerprint()
    yield
    after = _guard_fingerprint()
    dirty = [f"{k} ({before[k]} → {after[k]})" for k in before if before[k] != after[k]]
    if dirty:
        pytest.fail(f"用例改写生产数据：{'; '.join(dirty)}", pytrace=False)


@pytest.fixture(autouse=True)
def _hermetic_stores(hermetic_data_root, monkeypatch):
    """autouse：把生产数据存储整体重定向到沙箱（生产零写入）。"""
    sandbox = hermetic_data_root

    for mod_name, attr, value in _hermetic_patches(sandbox):
        try:
            mod = importlib.import_module(mod_name)
        except Exception:  # noqa: BLE001 — 模块不可导入则跳过（如可选依赖缺失）
            continue
        monkeypatch.setattr(mod, attr, value, raising=False)

    # llm_cache：diskcache 实例在 get_cache() 内惰性构造，打桩 get_cache 即够。
    # 该缓存受 LLM_RESPONSE_CACHE 门控（默认关），仅 test_llm_response_cache 开启。
    def _sandbox_cache():
        try:
            import diskcache
        except ImportError:
            return None
        c = _HERMETIC_CACHE.get("cache")
        if c is None:
            c = diskcache.Cache(str(sandbox / "llm_cache"))
            _HERMETIC_CACHE["cache"] = c
        return c

    try:
        _llm_cache = importlib.import_module("core.compute.llm_cache")
        monkeypatch.setattr(_llm_cache, "get_cache", _sandbox_cache, raising=False)
    except Exception:  # noqa: BLE001
        pass

    yield sandbox
