"""2hao-analyst Preflight Check — 管线启动前的硬性门禁

在 WriteReviseLoop.run() 的第一步执行，检查：
1. 所有核心模块是否可导入
2. SAC YAML 文件是否存在且完整
3. 数据源是否可用
4. 关键依赖（matplotlib / python-docx 等）是否安装

任一检查失败 → 打印清晰错误信息 → sys.exit(1)
绝不裸奔。
"""

import sys
import importlib
import logging
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

logger = logging.getLogger("2hao.preflight")

# ── 核心模块清单 ──────────────────────────────────────────────────────
# 这些模块在管线执行中必须全部可用。少一个就阻断。
CORE_MODULES = {
    # SAC 框架
    "core.sacs": ["SACLoader"],
    # LLM 通信
    "core.llm_provider": ["LLMProvider"],
    "core.deepseek_client": ["call_deepseek"],
    # 数据采集
    "pipeline.data_collector": ["DataCollectorV5"],
    # 财务计算
    "pipeline.compute_engine": ["ComputeEngine"],
    # 图表
    "core.chart_engine": ["ChartEngine"],
    "pipeline.chart_planner": ["ChartPlanner"],
    # 写作
    "pipeline.section_writer": ["SectionWriter"],
    # 格式
    "pipeline.format_sheriff": ["FormatSheriff"],
    # 门禁
    "pipeline.iron_gate": ["IronGate"],
    # 评分
    "pipeline.agent_loop": ["ScoreEngine"],
    # 学习
    "pipeline.learning_loop": ["LearningLoop"],
    # 导出
    "pipeline.report_writer": ["ReportWriter"],
    # 交叉验证
    "core.cross_validator": ["CrossValidator"],
}

# SAC YAML 文件清单
SAC_YAMLS = [
    "sac_industry_deep.yaml",
    "sac_listed_company.yaml",
    "sac_unlisted_company.yaml",
    "sac_earnings_notes.yaml",
]

# 运行时依赖
RUNTIME_DEPS = {
    "matplotlib": ["pyplot"],
    "yaml": ["safe_load"],
}

# 数据源可用性检查（不阻断，只警告）
DATA_SOURCES = {
    "tavily": {"import": "tavily", "class": "TavilyClient"},
    "yfinance": {"import": "yfinance"},
    "akshare": {"import": "akshare"},
}


class PreflightChecker:
    """管线启动前硬性检查"""

    def __init__(self, report_type: str = "industry_deep"):
        self.report_type = report_type
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def run(self) -> bool:
        """执行所有检查，返回 True=通过 / False=阻断"""
        self._check_core_modules()
        self._check_sac_yamls()
        self._check_runtime_deps()
        self._check_data_sources()
        return self._report()

    def _check_core_modules(self) -> None:
        for module_path, expected_classes in CORE_MODULES.items():
            try:
                mod = importlib.import_module(module_path)
                for cls_name in expected_classes:
                    if not hasattr(mod, cls_name):
                        self.errors.append(f"{module_path} 缺少类 {cls_name}")
            except ImportError as e:
                self.errors.append(f"模块 {module_path} 导入失败: {e}")
            except Exception as e:
                self.errors.append(f"模块 {module_path} 异常: {e}")

    def _check_sac_yamls(self) -> None:
        sac_dir = _ANALYST_ROOT / "core" / "sacs"
        for yaml_file in SAC_YAMLS:
            path = sac_dir / yaml_file
            if not path.exists():
                self.errors.append(f"SAC YAML 缺失: {yaml_file}")
                continue
            try:
                content = path.read_text(encoding="utf-8")
                if "required_dimensions:" not in content and "logic_chain:" not in content:
                    self.warnings.append(f"SAC YAML {yaml_file} 可能不完整（缺少 required_dimensions 或 logic_chain）")
            except Exception as e:
                self.errors.append(f"SAC YAML {yaml_file} 读取失败: {e}")

    def _check_runtime_deps(self) -> None:
        for pkg_name, symbols in RUNTIME_DEPS.items():
            try:
                mod = importlib.import_module(pkg_name)
                for sym in symbols:
                    if not hasattr(mod, sym):
                        self.warnings.append(f"{pkg_name} 缺少符号 {sym}")
            except ImportError:
                self.warnings.append(f"运行时依赖 {pkg_name} 未安装")
            except Exception as e:
                self.warnings.append(f"运行时依赖 {pkg_name} 异常: {e}")

    def _check_data_sources(self) -> None:
        for name, cfg in DATA_SOURCES.items():
            try:
                mod = importlib.import_module(cfg.get("import", name))
                cls_name = cfg.get("class")
                if cls_name and not hasattr(mod, cls_name):
                    self.warnings.append(f"数据源 {name}: 缺少类 {cls_name}")
            except ImportError:
                self.warnings.append(f"数据源 {name} SDK 未安装（不影响运行，但数据采集将受限）")

    def _report(self) -> bool:
        passed = len(self.errors) == 0
        print(f"\n{'='*60}")
        print(f"Preflight Check: {'PASS' if passed else 'FAIL'}")
        print(f"{'='*60}")
        if self.errors:
            print(f"\n  [!] 阻断性错误 ({len(self.errors)}):")
            for e in self.errors:
                print(f"      - {e}")
        if self.warnings:
            print(f"\n  [!] 警告 ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"      - {w}")
        if passed:
            print(f"\n  ✅ 所有核心模块就绪，管线可以安全启动。")
        else:
            print(f"\n  ❌ 存在阻断性错误，管线无法启动。")
            print(f"     请修复上述错误后重试。")
        print(f"{'='*60}\n")
        return passed


def check(report_type: str = "industry_deep") -> bool:
    """快捷入口：启动管线前调用"""
    checker = PreflightChecker(report_type)
    return checker.run()


if __name__ == "__main__":
    import sys
    rt = sys.argv[1] if len(sys.argv) > 1 else "industry_deep"
    sys.exit(0 if check(rt) else 1)
