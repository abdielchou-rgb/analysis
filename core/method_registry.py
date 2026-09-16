# -*- coding: utf-8 -*-
"""Method Registry - 方法注册表

核心原则：
- 方法即契约：定义前置条件、后置条件、判断信号
- 方法即执行单元：可确定性执行、可验证、可组合
- 知识引用显性化：每个方法引用具体的 MKB 条目
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Protocol, Set, Tuple, Type
from abc import ABC, abstractmethod
import re


class ExecutionMode(Enum):
    DETERMINISTIC = "deterministic"   # 纯 Python 计算，无 LLM
    LLM = "llm"                        # 需要 LLM 推理
    HYBRID = "hybrid"                  # 混合：确定性计算 + LLM 判断


class ProblemClass(str, Enum):
    PROFITABILITY_ANALYSIS = "profitability_analysis"
    GROWTH_ANALYSIS = "growth_analysis"
    VALUATION = "valuation"
    COMPETITIVE_POSITION = "competitive_position"
    RISK_ASSESSMENT = "risk_assessment"
    CASH_FLOW_ANALYSIS = "cash_flow_analysis"
    BALANCE_SHEET_QUALITY = "balance_sheet_quality"
    MARKET_SIZING = "market_sizing"
    COMPETITIVE_DYNAMICS = "competitive_dynamics"
    REGULATORY_RISK = "regulatory_risk"
    TECHNOLOGY_DISRUPTION = "technology_disruption"
    MANAGEMENT_QUALITY = "management_quality"
    CAPITAL_ALLOCATION = "capital_allocation"
    UNSPECIFIED = "unspecified"


class ExecutionStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class MethodContract:
    """方法契约 - 定义方法的完整契约"""
    id: str
    name: str
    problem_class: str  # ProblemClass 值
    description: str
    
    # 执行模式
    execution_mode: str = "deterministic"  # deterministic / llm / hybrid
    
    # 前置条件：输入证据要求
    required_evidence: Tuple[str, ...] = ()
    optional_evidence: Tuple[str, ...] = ()
    preconditions: Tuple[str, ...] = ()  # 可评估为 bool 的表达式字符串
    
    # 后置条件：输出保证
    outputs_schema: Dict[str, Any] = field(default_factory=dict)
    postconditions: Tuple[str, ...] = ()  # 输出必须满足的条件
    
    # 判断信号：给 Gate 验证用
    judgment_signals: Tuple[str, ...] = ()
    
    # 知识引用
    knowledge_refs: Tuple[str, ...] = ()  # MKB 条目 ID
    
    # 执行参数
    confidence_threshold: float = 0.8
    timeout_seconds: float = 30.0
    max_retries: int = 1
    
    # 版本
    version: str = "1.0"
    
    def validate_preconditions(self, evidence: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证前置条件"""
        errors = []
        for cond in self.preconditions:
            try:
                if not eval(cond, {"__builtins__": {}}, {"evidence": self._flatten_evidence(self)}):
                    errors.append(f"Precondition failed: {cond}")
            except Exception as e:
                errors.append(f"Precondition error: {cond} - {e}")
        return len(errors) == 0, errors
    
    def validate_postconditions(self, output: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证后置条件"""
        errors = []
        for cond in self.postconditions:
            try:
                if not eval(cond, {"__builtins__": {}}, {"output": output}):
                    errors.append(f"Postcondition failed: {cond}")
            except Exception as e:
                errors.append(f"Postcondition error: {cond} - {e}")
        return len(errors) == 0, errors
    
    def check_judgment_signals(self, output: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """检查判断信号是否存在于输出中"""
        missing = []
        for signal in self.judgment_signals:
            if signal not in str(output):
                pass  # TODO: 更精确的信号检查
        return True, []
    
    def _flatten_evidence(self, evidence) -> Dict:
        """展平证据用于条件评估"""
        # 简化实现
        return {}


class MethodExecutor(Protocol):
    """方法执行器协议"""
    
    contract: 'MethodContract'
    
    async def execute(self, evidence: Dict[str, Any], context: Dict) -> 'MethodResult':
        ...
    
    def validate_input(self, evidence: Dict) -> Tuple[bool, List[str]]:
        """验证输入证据"""
        return True, []


@dataclass(frozen=True)
class MethodResult:
    """方法执行结果"""
    method_id: str
    status: str  # success / failed / partial / skipped
    output: Dict[str, Any]
    findings: List[Dict]  # 生成的 Findings
    confidence: float
    execution_time: float
    evidence_used: List[str]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class MethodExecutorBase:
    """方法执行器基类"""
    
    def __init__(self, contract: 'MethodContract'):
        self.contract = contract
    
    def validate_input(self, evidence: Dict) -> Tuple[bool, List[str]]:
        """验证输入证据是否满足前置条件"""
        missing = []
        for req in self.contract.required_evidence:
            if req not in evidence or evidence[req] is None:
                missing.append(req)
        if missing:
            return False, [f"Missing required evidence: {m}" for m in missing]
        return True, []
    
    async def execute(self, evidence: Dict[str, Any], context: Dict) -> 'MethodResult':
        """执行方法 - 子类实现"""
        raise NotImplementedError


class DeterministicExecutor(MethodExecutorBase):
    """确定性执行器 - 纯 Python 计算，无 LLM"""
    
    def __init__(self, contract: 'MethodContract', compute_fn: Callable):
        super().__init__(contract)
        self.compute_fn = compute_fn
    
    async def execute(self, evidence: Dict[str, Any], context: Dict) -> 'MethodResult':
        import time
        start = time.time()
        
        try:
            # 验证输入
            valid, errors = self.validate_input(evidence)
            if not valid:
                return MethodResult(
                    method_id=self.contract.id,
                    status="failed",
                    output={},
                    findings=[],
                    confidence=0.0,
                    execution_time=0.0,
                    evidence_used=[],
                    errors=[f"Input validation failed: {e}" for e in self.validate_input(evidence)[1]]
                )
            
            # 执行计算
            output = await self.compute_fn(evidence)
            
            # 验证后置条件
            valid, errors = self.contract.validate_postconditions(output)
            if not valid:
                return MethodResult(
                    method_id=self.contract.id,
                    status="partial",
                    output=output,
                    findings=[],
                    confidence=0.5,
                    execution_time=time.time() - start,
                    evidence_used=list(output.keys()),
                    errors=[f"Postcondition failed: {e}" for e in errors]
                )
            
            # 生成 findings
            findings = self._generate_findings(output, evidence)
            
            return MethodResult(
                method_id=self.contract.id,
                status="success",
                output=output,
                findings=findings,
                confidence=0.95,
                execution_time=time.time() - start,
                evidence_used=list(output.keys()),
            )
        except Exception as e:
            return MethodResult(
                method_id=self.contract.id,
                status="failed",
                output={},
                findings=[],
                confidence=0.0,
                execution_time=time.time() - start,
                evidence_used=[],
                errors=[str(e)]
            )
    
    def _generate_findings(self, output: Dict, evidence: Dict) -> List[Dict]:
        """将输出转换为标准 Finding 格式"""
        findings = []
        for key, value in evidence.items():
            findings.append({
                "claim": f"{key} = {evidence[key]}",
                "evidence": key,
                "method": self.contract.id,
                "confidence": 0.95
            })
        return findings


class LLMExecutor:
    """LLM 执行器 - 用于需要推理的复杂任务"""
    
    def __init__(self, contract: 'MethodContract', prompt_template: str, parser: Callable):
        self.contract = contract
        self.prompt_template = prompt_template
        self.parser = parser
    
    async def execute(self, evidence: Dict[str, Any], context: Dict) -> 'MethodResult':
        # TODO: 实现 LLM 调用
        # 1. 构建 prompt
        # 2. 调用 LLM
        # 3. 解析输出
        # 4. 验证 postconditions
        pass


class HybridExecutor:
    """混合执行器 - 确定性计算 + LLM 判断"""
    pass


# ==================== 预定义方法契约 ====================

# 常用方法契约预定义
PREDEFINED_METHODS = {
    "margin_bridge": {
        "id": "margin_bridge",
        "name": "毛利率拆解桥接",
        "problem_class": "profitability_analysis",
        "description": "将毛利率变化拆解为价格效应、成本效应、产品组合效应",
        "required_evidence": ("revenue", "cogs", "revenue_breakdown", "cogs_breakdown"),
        "preconditions": ("evidence['revenue'] is not None", "evidence['cogs'] is not None"),
        "outputs_schema": {
            "price_effect": "float",
            "cost_effect": "float", 
            "mix_effect": "float",
            "total_change": "float"
        },
        "postconditions": ("output['total_change'] == output['price_effect'] + output['cost_effect'] + output['mix_effect']",),
        "judgment_signals": ("price_effect", "cost_effect", "mix_effect"),
        "knowledge_refs": ("MKB_1842", "MKB_921"),
    },
    
    "dupont_decomposition": {
        "id": "dupont_decomposition",
        "name": "杜邦分析分解",
        "problem_class": "profitability_analysis",
        "description": "ROE 分解为净利率、资产周转率、权益乘数",
        "required_evidence": ("net_income", "revenue", "total_assets", "equity"),
        "preconditions": ("evidence['revenue'] > 0", "evidence['equity'] > 0"),
        "outputs_schema": {
            "net_margin": "float",
            "asset_turnover": "float",
            "equity_multiplier": "float",
            "roe": "float"
        },
        "postconditions": (
            "abs(output['net_margin'] * output['asset_turnover'] * output['equity_multiplier'] - output['roe']) < 0.001",
        ),
        "judgment_signals": ("margin_decline驱动", "turnover_driven", "leverage_change"),
        "knowledge_refs": ("MKB_1842", "MKB_921"),
    },
    
    "margin_bridge": {
        "id": "margin_bridge",
        "name": "毛利率拆解桥接",
        "problem_class": "profitability_analysis",
        "description": "毛利率变化拆解：价格效应、成本效应、组合效应",
        "required_evidence": ("revenue", "cogs", "revenue_breakdown", "cogs_breakdown"),
        "preconditions": ("evidence['revenue'] > 0", "evidence['cogs'] is not None"),
        "outputs_schema": {
            "price_effect": "float",
            "cost_effect": "float",
            "mix_effect": "float",
            "total_change": "float"
        },
        "postconditions": (
            "output['total_change'] == output['price_effect'] + output['cost_effect'] + output['mix_effect']",
        ),
        "judgment_signals": ("price_effect", "cost_effect", "mix_effect"),
        "knowledge_refs": ("MKB_1842", "MKB_921"),
    },
    
    "dupont": {
        "id": "dupont",
        "name": "杜邦分析",
        "problem_class": "profitability_analysis",
        "description": "ROE 杜邦分解：净利率 × 资产周转率 × 权益乘数",
        "required_evidence": ("net_income", "revenue", "total_assets", "equity"),
        "preconditions": ("evidence['revenue'] > 0", "evidence['equity'] > 0"),
        "outputs_schema": {
            "net_margin": "float",
            "asset_turnover": "float",
            "equity_multiplier": "float",
            "roe": "float"
        },
        "postconditions": (
            "abs(output['net_margin'] * output['asset_turnover'] * output['equity_multiplier'] - output['roe']) < 0.001",
        ),
        "judgment_signals": ("margin_driven", "turnover_driven", "leverage_driven"),
        "knowledge_refs": ("MKB_1842", "MKB_921"),
    },
}

class MethodRegistry:
    """方法注册表 - 统一管理方法契约、选择器、执行器和发现存储
    
    核心职责：
    1. 管理所有方法契约的注册与查询
    2. 提供方法选择器 (MethodSelector)
    3. 管理方法执行器 (DeterministicExecutor / LLMExecutor / HybridExecutor)
    4. 集成 FindingStore 实现 Claim 级谱系追踪
    """
    
    def __init__(self):
        self._selector = None
        self._executors: Dict[str, 'MethodExecutorBase'] = {}
        self._finding_store = None
        self._initialized = False
    
    def initialize(self):
        """初始化注册表"""
        if self._initialized:
            return
        
        from core.method_selector import MethodSelector
        from core.finding_store import LineageTracker
        
        self._selector = MethodSelector()
        self._finding_store = LineageTracker()
        self._initialized = True
        
        # 注册预定义方法
        for method_def in PREDEFINED_METHODS.values():
            contract = self._create_contract_from_def(method_def)
            self.register(contract)
    
    def _create_contract_from_def(self, def_dict: dict) -> 'MethodContract':
        """从定义字典创建合同"""
        from core.method_registry import MethodContract, ExecutionMode
        return MethodContract(
            id=def_dict["id"],
            name=def_dict["name"],
            problem_class=def_dict["problem_class"],
            description=def_dict.get("description", ""),
            execution_mode=ExecutionMode.DETERMINISTIC,
            required_evidence=tuple(def_dict.get("required_evidence", [])),
            optional_evidence=tuple(def_dict.get("optional_evidence", [])),
            preconditions=tuple(def_dict.get("preconditions", [])),
            outputs_schema=def_dict.get("outputs_schema", {}),
            postconditions=tuple(def_dict.get("postconditions", [])),
            judgment_signals=tuple(def_dict.get("judgment_signals", [])),
            knowledge_refs=tuple(def_dict.get("knowledge_refs", [])),
            confidence_threshold=def_dict.get("confidence_threshold", 0.8),
            timeout_seconds=def_dict.get("timeout_seconds", 30.0),
            max_retries=def_dict.get("max_retries", 1),
        )
    
    def register(self, contract: 'MethodContract') -> None:
        """注册方法契约"""
        self._selector.register(contract)
    
    def get_selector(self) -> 'MethodSelector':
        """获取方法选择器"""
        if not self._initialized:
            self.initialize()
        return self._selector
    
    def get_finding_store(self) -> 'LineageTracker':
        """获取发现存储"""
        if not self._initialized:
            self.initialize()
        return self._finding_store
    
    def get_executor(self, contract: 'MethodContract') -> 'MethodExecutorBase':
        """获取或创建执行器"""
        if contract.id not in self._executors:
            if contract.execution_mode == "deterministic":
                # 这里需要根据 contract.id 找到对应的 compute_fn
                # 简化处理：使用默认的 DeterministicExecutor
                from core.method_registry import DeterministicExecutor
                self._executors[contract.id] = DeterministicExecutor(contract, lambda ev: {})
            elif contract.execution_mode == "llm":
                from core.method_registry import LLMExecutor
                self._executors[contract.id] = LLMExecutor(contract, "", lambda x: x)
            else:
                from core.method_registry import HybridExecutor
                self._executors[contract.id] = HybridExecutor(contract)
        return self._executors[contract.id]
    
    def select_methods(
        self,
        problem_class: str,
        available_evidence: Set[str],
        max_methods: int = 5,
        prefer_deterministic: bool = True,
        confidence_threshold: float = 0.7
    ) -> List[Dict]:
        """选择方法"""
        return self._selector.select_methods(
            problem_class=problem_class,
            available_evidence=available_evidence,
            max_methods=max_methods,
            prefer_deterministic=prefer_deterministic,
            confidence_threshold=0.7
        )
    
    async def execute_method(
        self,
        method_id: str,
        evidence: Dict[str, Any],
        context: Dict
    ) -> 'MethodResult':
        """执行方法"""
        contract = self._selector._registry.get(method_id)
        if not contract:
            raise ValueError(f"Method {method_id} not found")
        
        executor = self.get_executor(contract)
        return await executor.execute(evidence, context)
    
    def record_claim(
        self,
        text: str,
        section: str,
        evidence: Tuple[Dict[str, Any], ...],
        method: str,
        method_ref: str,
        mkb_refs: Tuple[str, ...] = (),
        gate_passed: bool = False,
        gate_checks: Mapping[str, str] = None
    ) -> 'Claim':
        """记录 Claim 到 FindingStore"""
        from core.finding_store import LineageTracker
        tracker = self.get_finding_store()
        return tracker.record_claim(
            text="",
            section="",
            evidence=(),
            method="",
            method_ref="",
            mkb_refs=(),
        )
    
    def get_finding_store(self) -> 'LineageTracker':
        return self.get_finding_store()


# 全局注册表实例
_global_registry = None


def get_method_registry() -> 'MethodRegistry':
    global _global_registry
    if _global_registry is None:
        _global_registry = MethodRegistry()
        _global_registry.initialize()
    return _global_registry