"""WriteReviseLoop — 写→评→改强制循环 (E2EOrchestratorV2 适配器)

此文件是 scheduler.py 的依赖，作为 WriteReviseLoop 类的向后兼容外壳。
实际调用转发至 E2EOrchestratorV2。
"""

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("2hao.write_revise_loop")


class WriteReviseLoop:
    """Write-Revise 循环 — 兼容接口，后端使用 E2EOrchestratorV2"""

    def __init__(
        self,
        asset: str,
        report_type: str = "industry_deep",
        style: str = "cicc",
        output_dir: str = "output",
        time_anchor: dict | None = None,
    ):
        self.asset = asset
        self.report_type = report_type
        self.style = style
        self.output_dir = output_dir
        self.time_anchor = time_anchor or {}
        self._result = None

    def run(self, max_iterations: int = 5) -> dict:
        """运行写循环，返回结果字典

        Returns:
            {"md": "path/to/report.md", "docx": "path/to/report.docx", ...}
            或 {"error": "message"}
        """
        from pipeline.e2e_orchestrator import E2EOrchestratorV2

        logger.info(
            "WriteReviseLoop starting (delegating to E2EOrchestratorV2): asset=%s type=%s style=%s",
            self.asset,
            self.report_type,
            self.style,
        )

        try:
            orchestrator = E2EOrchestratorV2(
                report_type=self.report_type,
                style=self.style,
                output_dir=self.output_dir,
                time_anchor=self.time_anchor,
            )
            result = orchestrator.run(asset=self.asset)
            self._result = result
            return result
        except Exception as e:
            logger.error("WriteReviseLoop failed: %s", e)
            return {"error": str(e)}

    @property
    def result(self) -> dict | None:
        return self._result


def run_loop(
    asset: str,
    report_type: str = "industry_deep",
    style: str = "cicc",
    output_dir: str = "output",
) -> dict:
    """便捷函数 — 单次调用 WriteReviseLoop"""
    loop = WriteReviseLoop(asset, report_type, style, output_dir)
    return loop.run()
