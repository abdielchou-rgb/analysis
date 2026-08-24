"""
StepManager — 执行过程纪律

确保每个步骤按顺序执行，不可跳过。
使用文件标记（marker）机制实现跨进程步骤追踪。

STEPS:
  1. data_collect — 数据采集
  2. charts — 图表生成
  3. section1_write — 第一节写作
  4. section2_write — 第二节写作
  5. section3_write — 第三节写作
  6. gate — 质量门禁校验
  7. export — 报告导出
"""

import logging
from pathlib import Path

logger = logging.getLogger("2hao.step_manager")


class StepManager:
    """步骤管理器 — 确保按序执行，不可跳过"""

    STEPS = [
        "data_collect",
        "enrich",
        "charts",
        "section1_write",
        "section2_write",
        "section3_write",
        "gate",
        "export",
    ]

    def __init__(self, output_dir: str = "output"):
        self.marker_dir = Path(output_dir) / "step_markers"

    # ── 标记方法 ──

    def mark_start(self, step: str) -> None:
        """记录步骤开始：{step}.started"""
        self._validate_step(step)
        self._ensure_marker_dir()
        filepath = self.marker_dir / f"{step}.started"
        filepath.write_text("", encoding="utf-8")

    def mark_done(self, step: str) -> None:
        """记录步骤完成：{step}.done"""
        self._validate_step(step)
        self._ensure_marker_dir()
        filepath = self.marker_dir / f"{step}.done"
        filepath.write_text("", encoding="utf-8")

    # ── 检查方法 ──

    def require_done(self, step: str) -> None:
        """要求某步骤已完成，否则抛出RuntimeError"""
        self._validate_step(step)
        filepath = self.marker_dir / f"{step}.done"
        if not filepath.exists():
            raise RuntimeError(f"[StepManager] 步骤 '{step}' 尚未完成（标记文件缺失: {filepath}）请先完成前置步骤")

    def require_sequential(self, step: str) -> None:
        """要求所有前置步骤均已完成，否则抛出RuntimeError"""
        self._validate_step(step)
        idx = self.STEPS.index(step)
        for i in range(idx):
            prev = self.STEPS[i]
            self.require_done(prev)

    # ── 状态管理 ──

    def reset(self) -> None:
        """重置所有步骤标记"""
        if self.marker_dir.exists():
            for f in self.marker_dir.iterdir():
                if f.is_file() and (f.suffix in (".started", ".done")):
                    try:
                        f.unlink()
                    except PermissionError:
                        logger.warning("StepManager: cannot remove %s, ignoring", f)

    def get_status(self) -> dict:
        """获取所有步骤的完成状态"""
        status = {}
        for step in self.STEPS:
            started = (self.marker_dir / f"{step}.started").exists()
            done = (self.marker_dir / f"{step}.done").exists()
            status[step] = {"started": started, "done": done}
        return status

    # ── 辅助方法 ──

    def _validate_step(self, step: str) -> None:
        if step not in self.STEPS:
            raise ValueError(f"[StepManager] 非法步骤 '{step}'（允许: {', '.join(self.STEPS)}）")

    def _ensure_marker_dir(self) -> None:
        self.marker_dir.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        sm = StepManager(output_dir=tmpdir)
        sm.reset()
        print("开始状态:", sm.get_status())

        for step in StepManager.STEPS:
            sm.mark_start(step)
            sm.mark_done(step)

        sm.require_sequential("export")
        print("顺序验证通过")

        sm.reset()
        sm.mark_start("section1_write")
        try:
            sm.require_sequential("section1_write")
            print("ERROR: 应抛出异常但未抛")
        except RuntimeError as e:
            print(f"正确拦截: {e}")

        print(f"状态: {sm.get_status()}")
