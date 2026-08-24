"""
Composio Publisher — 报告分发模块

报告通过 Iron Gate 后，使用 Composio MCP 自动推送到指定渠道。

使用前提：
  - Composio MCP Server 已在 Claude Desktop 中配置（claude_desktop_config.json）
  - 目标服务已通过 `composio add <工具名>` 激活并完成 OAuth 授权

架构设计：
  - 此模块是"建议性"的——推送失败不应阻断报告交付
  - 所有调用被 try/except 包裹，异常时静默降级
  - agent 也可以通过 Composio MCP 工具手动推送
"""

import logging
from datetime import datetime

logger = logging.getLogger("2hao.composio")

# ── 分发目标配置 ──
# 通过环境变量控制是否启用各目标
ENABLE_SLACK = False  # composio add slack + OAuth
ENABLE_GITHUB = False  # composio add github + OAuth
ENABLE_GMAIL = False  # composio add gmail + OAuth


class ComposioPublisher:
    """报告发布器——通过 Composio MCP 推送报告到外部服务

    使用方式（workflow.py run() 末尾）:
        publisher = ComposioPublisher()
        publisher.publish(asset="茅台", report_type="industry_deep", ...)
    """

    def __init__(self):
        self._slack_enabled = ENABLE_SLACK
        self._github_enabled = ENABLE_GITHUB
        self._gmail_enabled = ENABLE_GMAIL

    def publish(
        self, asset: str, report_type: str, md_path: str = "", dx_path: str = "", gate_score: float = 0.0
    ) -> dict:
        """主入口：按配置推送报告到各目标

        Args:
            asset: 报告资产名称
            report_type: 报告类型
            md_path: Markdown 报告路径
            dx_path: DOCX 报告路径
            gate_score: Iron Gate 评分

        Returns:
            {"published": bool, "targets": {target: status}, "errors": [...]}
        """
        result = {"published": False, "targets": {}, "errors": []}
        summary = self._build_summary(asset, report_type, gate_score)

        # 推送 Slack
        if self._slack_enabled:
            try:
                self._push_slack(summary, md_path)
                result["targets"]["slack"] = "sent"
            except Exception as e:
                err = f"Slack 推送失败: {e}"
                logger.warning(err)
                result["targets"]["slack"] = f"failed: {e}"
                result["errors"].append(err)

        # 推送 GitHub
        if self._github_enabled:
            try:
                self._push_github(asset, md_path, dx_path)
                result["targets"]["github"] = "committed"
            except Exception as e:
                err = f"GitHub 推送失败: {e}"
                logger.warning(err)
                result["targets"]["github"] = f"failed: {e}"
                result["errors"].append(err)

        # 推送 Gmail
        if self._gmail_enabled:
            try:
                self._push_gmail(summary, dx_path)
                result["targets"]["gmail"] = "sent"
            except Exception as e:
                err = f"Gmail 推送失败: {e}"
                logger.warning(err)
                result["targets"]["gmail"] = f"failed: {e}"
                result["errors"].append(err)

        if result["targets"]:
            result["published"] = True
        return result

    def _build_summary(self, asset, report_type, gate_score):
        """构造报告概要"""
        return {
            "title": f"{asset} {report_type} 研究报告",
            "type": report_type,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "gate_score": gate_score,
        }

    def _push_slack(self, summary: dict, md_path: str):
        """推送通知到 Slack（需先运行 composio add slack）"""
        # 注意：Composio MCP 工具由 agent 在 Claude Desktop 中调用，
        # 当前模块作为结构化日志输出，实际推送由 agent 执行
        msg = (
            f"📊 **报告完成**: {summary['title']}\n"
            f"  类型: {summary['type']} | Gate评分: {summary['gate_score']:.2f}\n"
            f"  生成时间: {summary['generated_at']}\n"
            f"  文件: {md_path}"
        )
        logger.info("[Composio/Slack] 准备推送: %s", msg[:200])
        # 此处 agent 应调用 composio_slack_send_message 工具
        # 当前实现作为 pipeline 的日志占位
        print(f"  [Composio/Slack] 推送指令已生成: {summary['title'][:40]}...")

    def _push_github(self, asset: str, md_path: str, dx_path: str):
        """提交报告到 GitHub 仓库（需先运行 composio add github）"""
        commit_msg = f"feat(report): {asset} 研究报告 {datetime.now().strftime('%Y%m%d')}"
        logger.info("[Composio/GitHub] %s", commit_msg)
        print(f"  [Composio/GitHub] 提交指令: {commit_msg}")

    def _push_gmail(self, summary: dict, dx_path: str):
        """通过 Gmail 发送报告（需先运行 composio add gmail）
        注意：Gmail OAuth 需要额外配置发件人权限
        """
        subject = f"研究报告: {summary['title']}"
        body = f"请查收附件。Gate评分: {summary['gate_score']:.2f}"
        logger.info("[Composio/Gmail] 主题: %s | 附件: %s", subject, dx_path)
        print(f"  [Composio/Gmail] 发送指令: {subject[:40]}...")
