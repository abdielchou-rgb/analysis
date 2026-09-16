# -*- coding: utf-8 -*-
"""Section Generator - 章节生成器

核心原则：
- Section Patch：只重写失败的 Section，不全文重写
- 依赖图感知：Patch 考虑下游依赖
- 模板化生成：Section 生成基于模板 + Finding 注入
"""

from __future__ import annotations

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field
import re
from collections import defaultdict, deque

from core.analysis_context import (
    AnalysisContext, SectionPlan, SectionPlanMap, 
    FindingStore, Finding, EvidenceBundle, MethodSpec
)
from core.finding_store import Claim
from core.analysis_context import DEFAULT_SECTION_DEPS, build_section_plan_map


@dataclass(frozen=True)
class SectionPatch:
    """Section 补丁"""
    section_id: str
    old_content: str
    new_content: str
    reason: str
    affected_claims: Tuple[str, ...]
    dependencies: Tuple[str, ...]  # 依赖此 section 的下游 section
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class SectionDraft:
    """Section 草稿"""
    section_id: str
    title: str
    content: str
    claims: Tuple[str, ...]  # 产生的 claim_ids
    evidence_refs: Tuple[str, ...]  # 引用的证据
    method_refs: Tuple[str, ...]  # 使用的方法
    word_count: int
    quality_score: float = 0.0
    generated_at: datetime = field(default_factory=datetime.now)


class SectionDependencyGraph:
    """Section 依赖图 - 管理章节间的依赖关系"""
    
    def __init__(self, deps: Dict[str, Set[str]] = None):
        if deps is not None:
            self._deps = deps
        else:
            # Convert DEFAULT_SECTION_DEPS (frozenset of (section, dep) tuples) to dict
            self._deps = defaultdict(set)
            for section, dep in DEFAULT_SECTION_DEPS:
                self._deps[section].add(dep)
            self._deps = dict(self._deps)
        self._reverse_deps = self._build_reverse_deps()
    
    def _build_reverse_deps(self) -> Dict[str, Set[str]]:
        """构建反向依赖图：section -> 依赖它的 sections"""
        reverse = defaultdict(set)
        for section, deps in self._deps.items():
            for dep in deps:
                reverse[dep].add(section)
        return dict(reverse)
    
    def get_dependencies(self, section_id: str) -> Set[str]:
        """获取 section 的直接依赖"""
        return self._deps.get(section_id, set())
    
    def get_dependents(self, section_id: str) -> Set[str]:
        """获取依赖该 section 的下游 sections"""
        return self._reverse_deps.get(section_id, set())
    
    def get_all_dependencies(self, section_id: str) -> Set[str]:
        """获取所有传递依赖（递归）"""
        visited = set()
        result = set()
        
        def dfs(section):
            if section in visited:
                return
            visited.add(section)
            for dep in self.get_dependencies(section):
                result.add(dep)
                dfs(dep)
        
        dfs(section_id)
        return result
    
    def get_all_dependents(self, section_id: str) -> Set[str]:
        """获取所有传递依赖者（递归）"""
        visited = set()
        result = set()
        
        def dfs(section):
            if section in visited:
                return
            visited.add(section)
            for dep in self.get_dependents(section):
                result.add(dep)
                dfs(dep)
        
        dfs(section_id)
        return result
    
    def get_all_downstream(self, section_ids: Set[str]) -> Set[str]:
        """获取给定 section 集合的所有下游依赖"""
        result = set()
        for sid in section_ids:
            result.update(self.get_all_dependents(sid))
        return result
    
    def topological_sort(self, section_ids: Set[str]) -> List[str]:
        """拓扑排序 - 返回按依赖顺序排序的 section 列表"""
        # Kahn's algorithm
        in_degree = defaultdict(int)
        adj = defaultdict(list)
        
        for sid in section_ids:
            for dep in self.get_dependencies(sid):
                if dep in section_ids:
                    adj[dep].append(sid)
                    in_degree[sid] += 1
        
        queue = deque([sid for sid in section_ids if in_degree[sid] == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result
    
    def add_dependency(self, section_id: str, depends_on: str):
        """添加依赖关系"""
        if section_id not in self._deps:
            self._deps[section_id] = set()
        self._deps[section_id].add(depends_on)
        self._reverse_deps = self._build_reverse_deps()


class SectionPatchManager:
    """Section Patch 管理器 - 处理局部重写"""
    
    def __init__(self, section_deps: SectionDependencyGraph = None):
        self.section_deps = section_deps or SectionDependencyGraph()
    
    def create_patches(
        self,
        context: 'AnalysisContext',
        failed_section_ids: Set[str],
        failed_claims: Dict[str, List[str]]  # section_id -> failed_claim_ids
    ) -> List['SectionPatch']:
        """创建 Section 补丁列表
        
        Args:
            context: 分析上下文
            failed_section_ids: 失败的 section ID 集合
            failed_claims: 每个 section 失败的 claim IDs
            
        Returns:
            补丁列表，按拓扑序排序
        """
        # 1. 计算需要重写的 Section（失败段 + 下游依赖）
        dirty_sections = self._compute_dirty_sections(failed_section_ids)
        
        # 2. 拓扑排序确保按依赖顺序重写
        sorted_dirty = self.section_deps.topological_sort(dirty_sections)
        
        patches = []
        for section_id in sorted_dirty:
            patch = SectionPatch(
                section_id=section_id,
                old_content=self._get_section_content(context, section_id),
                new_content="",  # 将由 Writer 生成
                reason=f"Gate 失败: {failed_section_ids.get(section_id, [])}",
                affected_claims=tuple(failed_claims.get(section_id, [])),
                dependencies=tuple(self.section_deps.get_dependencies(section_id))
            )
            patches.append(patch)
        
        return patches
    
    def _compute_dirty_sections(self, failed_section_ids: Set[str]) -> Set[str]:
        """计算需要重写的 Section（失败段 + 下游依赖）"""
        dirty = set(failed_section_ids)
        
        # 广度优先搜索下游依赖
        queue = deque(failed_section_ids)
        visited = set(failed_section_ids)
        
        while queue:
            current = queue.popleft()
            # 找到依赖 current 的所有 section
            for sid in self.section_deps.get_dependents(current):
                if sid not in visited:
                    dirty.add(sid)
                    visited.add(sid)
                    queue.append(sid)
        
        return dirty
    
    def _get_section_content(self, context: 'AnalysisContext', section_id: str) -> str:
        """获取 Section 内容"""
        for section in context.sections:
            if section.section_id == section_id:
                return getattr(section, 'content', '')
        return ""
    
    def apply_patches(self, context: 'AnalysisContext', patches: List['SectionPatch']) -> 'AnalysisContext':
        """应用补丁生成新 Context"""
        new_sections = list(context.sections)
        for patch in patches:
            for i, section in enumerate(new_sections):
                if section.section_id == patch.section_id:
                    from core.analysis_context import SectionPlan
                    new_sections[i] = SectionPlan(
                        section_id=patch.section_id,
                        title=patch.section_id,
                        required_findings=frozenset(),
                        dependencies=frozenset(patch.dependencies)
                    )
                    break
        
        from core.analysis_context import AnalysisContext
        new_context = context.new_version(
            sections=tuple(new_sections),
        )
        return new_context
    
    def apply_patch_content(
        self,
        context: 'AnalysisContext',
        patch: 'SectionPatch',
        new_content: str
    ) -> 'AnalysisContext':
        """应用单个补丁的具体内容"""
        return self.apply_patches(context, [patch])


class SectionGenerator:
    """章节生成器 - 基于 Finding 生成 Section"""
    
    def __init__(self):
        self._templates: Dict[str, str] = {}
        self._section_hooks: Dict[str, Callable] = {}
        self._load_default_templates()
    
    def register_template(self, section_id: str, template: str):
        """注册 Section 模板"""
        self._templates[section_id] = template
    
    def register_hook(self, section_id: str, hook: Callable):
        """注册 Section 生成钩子"""
        self._section_hooks[section_id] = hook
    
    def _load_default_templates(self):
        """加载默认模板"""
        # 基础结构模板
        self._templates["default"] = """## {title}

{content}

---
*本节引用证据: {evidence_refs}*
*分析方法: {method_refs}*
"""
        
        # 常用 Section 模板
        self._templates["financial_analysis"] = """## {title}

### 核心财务指标
{key_metrics}

### 趋势分析
{trend_analysis}

### 同业对比
{peer_comparison}

### 结论
{conclusion}
"""
        
        self._templates["valuation"] = """## {title}

### 估值概览
{valuation_summary}

### 多模型估值
{dcf_analysis}
{comparable_analysis}
{scenario_analysis}

### 估值锚点交叉验证
{cross_validation}

### 目标价与评级
{target_price_rating}
"""
    
    def generate_section(
        self,
        context: 'AnalysisContext',
        section_plan: 'SectionPlan',
        findings: List[Any],
        evidence: 'EvidenceBundle',
        methods: Tuple = ()
    ) -> str:
        """生成 Section 内容"""
        section_id = section_plan.section_id
        
        # 1. 收集该 Section 相关的 Findings
        section_findings = [f for f in context.findings.findings if f.section == section_id]
        
        # 2. 选择模板
        template = self._templates.get(section_id, self._templates.get("default", ""))
        
        # 3. 准备填充变量
        variables = self._prepare_variables(context, section_id)
        
        # 4. 渲染模板
        content = self._render_template(template, variables)
        
        # 5. 运行钩子
        if section_id in self._section_hooks:
            content = self._section_hooks[section_id](content, context)
        
        return content
    
    def _prepare_variables(self, context: 'AnalysisContext', section_id: str) -> Dict:
        """准备模板变量"""
        section_findings = [f for f in context.findings.findings if f.section == section_id]
        
        # 按方法分组
        by_method = {}
        for f in context.findings.findings:
            if f.section == section_id:
                method = getattr(f, 'method', 'unknown')
                if method not in by_method:
                    by_method[method] = []
                by_method[method].append(f)
        
        return {
            "section_id": section_id,
            "findings": section_findings,
            "evidence_refs": "",
            "method_refs": "",
        }
    
    def _render_template(self, template: str, variables: Dict) -> str:
        """渲染模板"""
        result = template
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return result
    
    def register_template(self, section_id: str, template: str):
        """注册 Section 模板"""
        self._templates[section_id] = template
    
    def register_hook(self, section_id: str, hook: Callable):
        """注册 Section 生成钩子"""
        self._section_hooks[section_id] = hook


# 全局实例
_global_section_deps = SectionDependencyGraph()
_global_patch_manager = SectionPatchManager(_global_section_deps)


def get_section_dependency_graph() -> SectionDependencyGraph:
    return _global_section_deps


def get_patch_manager() -> SectionPatchManager:
    return _global_patch_manager