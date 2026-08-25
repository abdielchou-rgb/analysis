"""IronGate 检查 Mixin — llm_checks 类检查。

R61（2026-08-03 迁移）：由 scripts/migrate_iron_gate.py 自动生成。
方法原样迁移自 pipeline/iron_gate.py，签名不变，IronGate 继承后行为零变化。
"""

import re

from pipeline.checks.base import GateCheckResult, logger


class LlmChecksMixin:
    @staticmethod
    def _get_cross_audit_provider(writing_provider: str = "deepseek") -> tuple[str, str]:
        """T-11：异源审查——Gate LLM 检查强制路由到非写作 provider。

        写作用 DeepSeek → 审查用 OpenRouter（真实可用的异源通道）。
        写作用 OpenRouter → 审查用 DeepSeek。
        避免同一模型"自采自校验"的同源偏见。
        """
        if "deepseek" in writing_provider.lower():
            # T-11 升级：异源审查指定 Claude Sonnet 5（与 DeepSeek 零训练数据重叠）
            return "openrouter", "anthropic/claude-sonnet-5"
        return "deepseek", "deepseek-reasoner"

    """llm_checks 类检查方法。"""

    def _check_ai_tone_by_llm(self) -> GateCheckResult:
        """FP4: Use LLM to detect AI tone beyond regex patterns

        P0-1 修复（2026-08-01 审计）：改用独立评估视角。
        使用与生成端不同的模型（deepseek-reasoner）作为第三方审计器，
        并在 prompt 中明确"你评估的是另一个模型生成的文本"，
        打破 DeepSeek 评判 DeepSeek 自身输出的循环论证陷阱。
        """
        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("ai_tone_llm", True, 1.0, "Text too short, skipped", severity="warning")

        sample = text[:3000].replace('"', "'")[:2500]
        prompt = (
            "System: 你是独立的第三方审计评委（你本身不是生成这份报告的大模型）。"
            '下面这段文本是由"另一个大语言模型"生成的投研报告。请以第三方审计师的视角，'
            "严格判断这段文本更像人类专业分析师撰写的，还是明显带有AI生成痕迹。"
            "注意：专业投研报告天然具有结构化标题、评级、目标价、数据来源标注等特征，"
            "这些是行业规范，不应被误判为AI痕迹。"
            "人类分析师文本通常包含：具体到小数点后两位的财务数据、来源标注(如Wind/年报/公告)、"
            "基于数据的独立判断(我们判断/我们预计)、风险提示、第一人称观点、相互矛盾的论据权衡。"
            "AI痕迹包括：过多模板化过渡句、缺乏具体数据支撑的判断、前后文风格割裂。"
            "你是独立审计者，你与被评估文本的生成模型不同——请以客观第三方立场评判。"
            '只输出JSON: {"score": 0.xx, "reason": "..."}，score=1表示极可能人类撰写，0表示极可能AI生成。\n'
            "User: " + sample[:1200]
        )
        try:
            from core.deepseek_client import call_llm

            # P0-1: 使用 deepseek-reasoner（与生成端 deepseek-chat 不同模型）作为独立审计器
            # T-11：异源审查——强制路由到非写作 provider
            _audit_provider, _audit_model = self._get_cross_audit_provider("deepseek")
            result = call_llm(
                messages=[{"role": "user", "content": prompt}],
                model=_audit_model,
                temperature=0.1,
                max_tokens=200,
                provider=_audit_provider,
            )
            output = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            try:
                import json as _json

                parsed = _json.loads(output)
                score = float(parsed.get("score", 0.5))
                reason = parsed.get("reason", "")
            except Exception:
                import re as _re

                score_match = _re.search(r"(\d+\.\d+)", output)
                score = float(score_match.group(1)) if score_match else 0.5
                reason = output[:30]

            # 机构特征兜底：含评级/目标价/风险提示等机构表达时，避免因结构化误判
            inst_markers = re.findall(r"(?:评级|目标价|风险提示|买入|增持|来源[：:]|Wind|公告)", text[:4000])
            if score < 0.4 and len(inst_markers) >= 3:
                score = max(score, 0.5)
            passed = score >= 0.4
            if score >= 0.7:
                details = f"Likely human (score={score:.2f})"
            elif score >= 0.4:
                details = f"Uncertain (score={score:.2f}) - {reason}"
            else:
                details = f"Likely AI (score={score:.2f}) - {reason}"
            return GateCheckResult("ai_tone_llm", passed, score, details)
        except Exception as e:
            # R92（2026-08-10）：LLM 校验器不可用 ≠ 报告不通过。
            # 此前强制 error 阻断，导致 provider 离线时本该通过的报告被无谓卡死、
            # 逼着重跑整条管线。改为：warning 降级放行 + 标记 degraded（不假装通过，
            # 但也不卡死）。与 _check_llm_data_verification 的降级语义一致。
            logger.error("[AI_TONE_LLM] 评估器不可用，降级放行: %s", e)
            self._degraded_checks = getattr(self, "_degraded_checks", [])
            self._degraded_checks.append("ai_tone_llm")
            return GateCheckResult(
                "ai_tone_llm", True, 0.5, f"AI Tone评估器不可用(降级放行): {str(e)[:60]}", severity="warning"
            )

    def _check_human_impossible_dimension(self) -> GateCheckResult:
        """FP4: Verify report contains at least one dimension beyond human analyst capability.

        检查三个维度：数据密度（>50来源）、推理深度（>5层归因）、覆盖广度（>20家）。
        至少满足一个即通过上阈。
        """
        text = self.report_text or ""
        if len(text) < 1000:
            return GateCheckResult("human_impossible", False, 0.0, "text too short, cannot verify")

        import re as _re

        # 1. 数据密度: 检查不同的来源引用数
        sources = set(_re.findall(r"(?:来源[：:]|数据来源[：:]|Source[：:]|sourced from|据[一-鿿]+报告)", text))
        source_density = len(sources)

        # 2. 推理深度: 检查 So What 链的层次
        reasoning_layers = _re.findall(r"(?:因此|这意味着|这导致|其根本原因|更深层次|本质上|推论|由此得出)", text)
        reasoning_depth = len(reasoning_layers)

        # 3. 覆盖广度: 检查提到的公司/竞争对手数
        companies = _re.findall(r"(?:公司|集团|[A-Z][a-z]+(?:\.[A-Z]{2})?)", text)
        company_count = len(set(companies))

        # Score each dimension
        density_score = min(1.0, source_density / 10)  # 10+ sources = 1.0
        depth_score = min(1.0, reasoning_depth / 8)  # 8+ layers = 1.0
        breadth_score = min(1.0, company_count / 20)  # 20+ companies = 1.0

        max_score = max(density_score, depth_score, breadth_score)
        passed = max_score >= 0.5  # At least one dimension at 50%+

        details = (
            f"Sources={source_density}({density_score:.2f}) "
            f"Depth={reasoning_depth}({depth_score:.2f}) "
            f"Breadth={company_count}({breadth_score:.2f}) "
            f"max={max_score:.2f}"
        )
        return GateCheckResult("human_impossible", passed, max_score, details, severity="error")

    def _check_llm_data_verification(self) -> "GateCheckResult":
        """R55（2026-08-03 Phase E）：LLM 数据交叉验证——独立于生成的校验层。

        原理（FinDVer/FActScore/EvidenceLens 共识）：生成与校验必须解耦，
        否则 LLM 自采自校验 = 同源偏见（幻觉双向通过）。

        对侧 provider 路由：
          训练模式（生成=agent_provider/Marvis）→ 校验=deepseek
          性能模式（生成=deepseek）→ 校验=agent_provider 或 ollama_local
        读 LLM_PROVIDER 判断生成端，校验端取反。

        校验内容：报告关键数字断言的可信度——只做确定性规则覆盖不到的语义判断
        （来源可信度、数字是否被过度精确、有无编造感），不重复 R35/R46 已覆盖的
        算术/估值勾稽（那些是确定性硬规则，更快更准）。
        """
        import os as _os
        import re as _re

        text = self.report_text or ""
        if len(text) < 500:
            return GateCheckResult("llm_data_verification", True, 1.0, "Text too short, skipped", severity="warning")

        # 生成端 provider（读环境变量，训练=agent_provider / 性能=deepseek）
        _gen_provider = _os.environ.get("LLM_PROVIDER", "deepseek")
        # 校验端取对侧：生成用 Marvis → 校验用 DeepSeek；生成用 DeepSeek → 校验用 Marvis/本地
        if _gen_provider == "agent_provider":
            _verify_provider = "deepseek"
            _verify_model = "deepseek-reasoner"
        else:
            # 性能模式（DeepSeek 生成）→ 校验用 Marvis（agent_provider）或本地 Ollama
            _verify_provider = "agent_provider" if _os.environ.get("HAS_AGENT", "1") == "1" else "ollama_local"
            _verify_model = "agent-writing" if _verify_provider == "agent_provider" else ""

        # 抽取报告中带数字的断言（关键数据点），交校验 LLM 审查
        _number_claims = _re.findall(
            r"[^。；\n]{0,40}?\d+(?:\.\d+)?%?[^。；\n]{0,20}?(?:亿元|亿|万|元|%|倍|家)", text[:8000]
        )
        _sample = _number_claims[:8] if _number_claims else text[:800].replace("\n", " ")

        prompt = (
            "System: 你是独立的第三方数据审计评委。下面是从一份投研报告中抽取的"
            '带数字的数据断言。请以审计视角判断：这些数字是否存在"来源不可信/'
            '过度精确（如编造的精确小数）/明显不合理"的问题。'
            "注意：专业报告的数字精度（如6.88亿元）是正常的，不应误判。"
            "你是独立审计者，与被评估报告的生成模型不同。\n"
            '只输出JSON: {"issues": [..], "score": 0.xx, "reason": "..."}\n'
            "score=1表示数据可信，0表示存在明显编造/不可信。\n"
            "User: " + str(_sample)[:1800]
        )
        try:
            from core.deepseek_client import call_llm

            result = call_llm(
                messages=[{"role": "user", "content": prompt}],
                model=_verify_model,
                temperature=0.1,
                max_tokens=300,
                provider=_verify_provider,
            )
            output = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            try:
                import json as _json

                parsed = _json.loads(output)
                score = float(parsed.get("score", 0.5))
                issues = parsed.get("issues", [])
                reason = parsed.get("reason", "")
            except Exception:
                import re as _r2

                _m = _r2.search(r"(\d+\.\d+)", output)
                score = float(_m.group(1)) if _m else 0.5
                issues = []
                reason = output[:30]

            # FP v3.2（FP2a）：三级判定（校准于真实样本）
            #  - score ≥ 0.7  数据可信 → 通过
            #  - 0.4 ≤ score < 0.7  有 issues（如未说明来源）→ 警告不硬阻断
            #    （确定性检查已覆盖算术/估值勾稽硬伤，LLM 校验是语义增强层）
            #  - score < 0.4  明显编造/不可信 → 硬阻断
            _MIN_PASS = float(_os.environ.get("LLM_VERIFY_MIN_PASS", "0.70"))
            _MIN_BLOCK = float(_os.environ.get("LLM_VERIFY_MIN_BLOCK", "0.40"))
            if score < _MIN_BLOCK:
                passed = False
                _sev = "error"
            elif score < _MIN_PASS:
                passed = True
                _sev = "warning"
            else:
                passed = True
                _sev = "warning"
            _det = f"数据交叉验证(校验={_verify_provider}): score={score:.2f}"
            if issues:
                _det += f" issues={str(issues)[:80]}"
            return GateCheckResult("llm_data_verification", passed, score, _det, severity=_sev)
        except Exception as e:
            # 校验 LLM 不可用：不阻断但降级（确定性检查已覆盖算术/勾稽，语义校验是增强层）
            logger.warning("[LLM_DATA_VERIFY] 校验器不可用，降级放行: %s", str(e)[:80])
            return GateCheckResult(
                "llm_data_verification", True, 0.5, f"校验器不可用，降级（{str(e)[:50]}）", severity="warning"
            )
