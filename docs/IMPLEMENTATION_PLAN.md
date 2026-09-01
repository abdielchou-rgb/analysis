# 2hao-analyst 并行化 + 定制化 实施方案

> 版本: v1.0 | 日期: 2026-08-27 | 目标: 并行提速 55% + 定制化写作

---

## 一、现状分析

### 1.1 当前架构瓶颈

```
当前串行执行路径（~45min/3轮）:

preflight (2s)
    → biz_macro (30s)
    → data (120s) ← 网络I/O瓶颈
    → universe_build (10s)
    → enrich (60s)
    → [串行] scarcity (5s) + cross_validate (5s) + argument (5s) + compute (30s) + charts (20s)
    → write_sections (480s) ← ★最大瓶颈★（8个依赖聚合 + 串行写作）
    → style (3s)
    → assemble (5s)
    → validate (10s)
    → critic (10s)
    → compliance (5s)
    → export (5s)
```

**关键瓶颈：**
1. **write_sections** (480s) — 串行写作 7-14 个 SAC 维度，每维度 ~35s
2. **L4 分析层** (65s) — 5 个模块串行执行，实际可并行
3. **data** (120s) — 网络 I/O 密集，已是异步但等待时间长

### 1.2 当前已有的并行支持

```python
# e2e_orchestrator.py 第 604 行
dimension_parallel = os.environ.get("DIM_PARALLEL", "1") == "1"
```

**发现：维度级并行已部分实现！** 但受限于：
- AgentGraph 本身是串行拓扑排序执行
- write_sections 节点内部虽支持并行，但外部依赖仍需串行等待

### 1.3 SAC 维度结构

| 报告类型 | 维度数 | 维度列表 |
|----------|--------|----------|
| earnings_notes | 5 | headline, key_surprise, segment_analysis, balance_cashflow, outlook_implication |
| listed_company | 14 | 决策门→核心分歧→商业模式→财务验证→竞争→增长→治理ESG→估值→催化剂→证伪→母子公司→资金面→Bold Call→风险 |
| industry_deep | 12 | 产业定义→市场规模→增长驱动→技术路线→竞争格局→供应链→政策→盈利→风险→趋势→Bold Call→投资建议 |
| unlisted_company | 11 | 商业模式→市场验证→增长→团队→财务→估值→竞争→风险→退出→Bold Call→建议 |

---

## 二、并行化改造方案

### 2.1 架构设计：三层并行

```
改造后并行执行路径（~20min/3轮）:

┌─────────────────────────────────────────────────────────────┐
│  L1 并行层（4模块，~30s）                                    │
│  ┌──────────┐ ┌───────────┐ ┌────────┐ ┌──────────┐        │
│  │preflight │ │hypothesis │ │  data  │ │ learning │        │
│  └──────────┘ └───────────┘ └────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  L2 串行层（依赖 data 完成）                                  │
│  universe_build (10s) → enrich (60s)                        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  L3 并行层（6模块，~30s，取最长）                             │
│  ┌──────────┐ ┌───────────┐ ┌──────────────┐               │
│  │scarcity  │ │cross_v.   │ │  argument    │               │
│  └──────────┘ └───────────┘ └──────────────┘               │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐                   │
│  │ compute  │ │  charts   │ │ research_p│                   │
│  └──────────┘ └───────────┘ └──────────┘                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  L4 维度级并行（核心提速，~120s，取最长维度）                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐             │
│  │ dim1 │ │ dim2 │ │ dim3 │ │ dim4 │ │ dimN │  × 5-14 并行 │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  L5 串行层（后处理）                                          │
│  style (3s) → assemble (5s) → validate (10s) → export (5s) │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 改造步骤

#### Step 1: AgentGraph 并行执行器（1天）

**目标：** 支持无依赖节点并行执行

**改动文件：** `pipeline/agent_graph.py`

**改动内容：**

```python
# 新增：并行执行模式
class AgentGraph:
    def __init__(self, name: str = "default", parallel_mode: bool = True):
        self.name = name
        self._nodes: dict[str, dict] = {}
        self._results: dict[str, NodeResult] = {}
        self._start_time: float = 0.0
        self._parallel_mode = parallel_mode  # 新增

    def run(self, context: dict = None) -> GraphResult:
        """支持并行的执行器"""
        self._start_time = time.time()
        ctx = context or {}
        sorted_levels = self._topological_sort_levels()  # 改为分层排序

        for level in sorted_levels:
            if self._parallel_mode and len(level) > 1:
                # 并行执行同一层的节点
                self._run_level_parallel(level, ctx)
            else:
                # 串行执行
                for node_id in level:
                    self._run_node(node_id, ctx)

        # ... 后续逻辑不变

    def _run_level_parallel(self, level: list[str], context: dict):
        """并行执行同一层的节点"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=len(level)) as executor:
            futures = {
                executor.submit(self._run_node_with_deps, node_id, context): node_id
                for node_id in level
            }
            for future in as_completed(futures):
                node_id = futures[future]
                try:
                    future.result(timeout=self._nodes[node_id].get("timeout_s", 300))
                except Exception as e:
                    logger.error("[PARALLEL] %s failed: %s", node_id, e)

    def _topological_sort_levels(self) -> list[list[str]]:
        """分层拓扑排序，返回可并行执行的层级"""
        in_degree = {nid: 0 for nid in self._nodes}
        for nid, node in self._nodes.items():
            for dep in node["deps"]:
                if dep not in in_degree:
                    in_degree[dep] = 0
                in_degree[nid] = in_degree.get(nid, 0) + 1

        levels = []
        queue = [nid for nid, deg in in_degree.items() if deg == 0]

        while queue:
            levels.append(queue[:])
            next_queue = []
            for nid in queue:
                for other_nid, other_node in self._nodes.items():
                    if nid in other_node["deps"]:
                        in_degree[other_nid] -= 1
                        if in_degree[other_nid] == 0:
                            next_queue.append(other_nid)
            queue = next_queue

        return levels if len(sum(levels, [])) == len(self._nodes) else None
```

#### Step 2: write_sections 维度级并行（2天）

**目标：** 每个 SAC 维度独立并行写作

**改动文件：** `pipeline/section_writer.py`

**改动内容：**

```python
# 新增：维度级并行写入
def write_dimensions_parallel(
    self,
    segments: list[dict],
    data_context: dict,
    chart_paths: dict,
    compute_results: dict,
    **kwargs
) -> str:
    """并行写入所有 SAC 维度"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}
    with ThreadPoolExecutor(max_workers=len(segments)) as executor:
        futures = {}
        for seg in segments:
            dim_id = seg.get("dimension_id", f"dim_{seg['index']}")
            future = executor.submit(
                self._write_single_dimension,
                seg, data_context, chart_paths, compute_results, **kwargs
            )
            futures[future] = dim_id

        for future in as_completed(futures):
            dim_id = futures[future]
            try:
                results[dim_id] = future.result(timeout=120)
            except Exception as e:
                logger.error("[DIM-PARALLEL] %s failed: %s", dim_id, e)
                results[dim_id] = f"[维度写作失败: {dim_id}]"

    # 按原始顺序组装
    ordered_text = []
    for seg in segments:
        dim_id = seg.get("dimension_id", f"dim_{seg['index']}")
        ordered_text.append(results.get(dim_id, ""))

    return "\n\n".join(ordered_text)

def _write_single_dimension(
    self,
    segment: dict,
    data_context: dict,
    chart_paths: dict,
    compute_results: dict,
    **kwargs
) -> str:
    """写入单个维度"""
    # 复用现有 _write_segment 逻辑
    return self._write_segment(segment, data_context, chart_paths, compute_results, **kwargs)
```

#### Step 3: 分析层并行（1天）

**目标：** L3 分析层 6 模块并行执行

**改动文件：** `pipeline/e2e_orchestrator.py`

**改动内容：**

```python
# 修改 write_sections 节点，聚合并行层输出
g.add_node(
    "write_sections",
    E2ENodes.write_sections,
    deps=[
        "enrich",           # 数据增强完成
        "charts",           # 图表生成完成
        "compute",          # 计算完成
        "learning",         # 学习闭环完成
        "hypothesis",       # 假设校验完成
        "argument",         # 论证引擎完成
        "scarcity",         # 稀缺性信号完成
        "cross_validate",   # 交叉验证完成
        "research_planner", # 研究规划完成（新增依赖）
    ],
    timeout_s=int(os.environ.get("WRITE_NODE_TIMEOUT_S", "300")),
    desc="write (dimension-level parallel)",
)
```

### 2.3 并行化收益预估

| 层级 | 当前耗时 | 改造后耗时 | 提速 |
|------|----------|------------|------|
| L1 并行层 | 120s | 30s | 75% |
| L2 串行层 | 70s | 70s | 0% |
| L3 分析层 | 65s | 30s | 54% |
| L4 写作层 | 480s | 120s | 75% |
| L5 后处理 | 23s | 23s | 0% |
| **总计** | **758s** | **273s** | **64%** |

---

## 三、定制化改造方案

### 3.1 定制维度设计

```python
@dataclass
class ReportCustomization:
    """报告定制化配置"""
    # 1. 维度权重定制
    dimension_weights: dict[str, float] = None  # {"headline": 1.5, "key_surprise": 2.0}

    # 2. 篇幅控制
    length: str = "standard"  # short / standard / detailed
    max_words: int = None  # 覆盖 length 的精确控制

    # 3. 写作重点
    focus_dimensions: list[str] = None  # ["valuation", "risk"] 重点维度
    skip_dimensions: list[str] = None   # ["governance"] 可跳过维度

    # 4. 风格定制
    style_preset: str = "cicc"  # cicc/gs/ms/mck/bcg/jpm
    style_blend: dict[str, float] = None  # {"cicc": 0.7, "gs": 0.3} 混合风格

    # 5. 数据源偏好
    data_sources: list[str] = None  # ["akshare", "yfinance", "tavily"]

    # 6. 输出格式
    output_formats: list[str] = None  # ["md", "docx", "pdf"]

    # 7. 语气/语言
    tone: str = "formal"  # formal / conversational / technical
    language: str = "zh-CN"  # zh-CN / en-US

    # 8. 附加内容
    include_executive_summary: bool = True
    include_appendix: bool = True
    include_charts: bool = True
```

### 3.2 SAC 维度权重系统

**改动文件：** `core/sacs/__init__.py`

```python
class SACLoader:
    def get_dimension_keywords(self, weights: dict = None) -> dict:
        """获取维度关键词，支持权重定制"""
        dim_keywords = self._load_dimensions()

        if weights:
            for dim_id, weight in weights.items():
                if dim_id in dim_keywords:
                    # 高权重维度：增加关键词密度
                    if weight > 1.0:
                        extra_keywords = self._expand_keywords(dim_keywords[dim_id], weight)
                        dim_keywords[dim_id] = extra_keywords
                    # 低权重维度：减少关键词
                    elif weight < 1.0:
                        dim_keywords[dim_id] = dim_keywords[dim_id][:int(len(dim_keywords[dim_id]) * weight)]

        return dim_keywords

    def _expand_keywords(self, keywords: list, factor: float) -> list:
        """扩展关键词列表"""
        expanded = list(keywords)
        # 添加同义词/相关词
        for kw in keywords:
            synonyms = self._get_synonyms(kw)
            expanded.extend(synonyms[:int(len(synonyms) * (factor - 1))])
        return expanded
```

### 3.3 篇幅控制系统

**改动文件：** `pipeline/section_writer.py`

```python
# 篇幅配置映射
LENGTH_CONFIG = {
    "short": {
        "words_per_dim": 300,
        "min_total": 1500,
        "max_total": 2500,
        "evidence_min": 1,
        "counter_evidence": False,
    },
    "standard": {
        "words_per_dim": 500,
        "min_total": 3000,
        "max_total": 5000,
        "evidence_min": 2,
        "counter_evidence": True,
    },
    "detailed": {
        "words_per_dim": 800,
        "min_total": 6000,
        "max_total": 10000,
        "evidence_min": 3,
        "counter_evidence": True,
    },
}

class SectionWriter:
    def _get_length_config(self, length: str = None) -> dict:
        """获取篇幅配置"""
        length = length or getattr(self, "_length", "standard")
        return LENGTH_CONFIG.get(length, LENGTH_CONFIG["standard"])

    def _build_system_prompt(self, dim_config: dict, length_config: dict) -> str:
        """构建系统提示词，注入篇幅控制"""
        base_prompt = _LLM_SYSTEM_PREFIX

        # 注入篇幅控制
        base_prompt += f"\n## [篇幅] 本维度目标字数: {length_config['words_per_dim']}字"
        base_prompt += f"\n## [证据] 最少证据数: {length_config['evidence_min']}"

        if length_config["counter_evidence"]:
            base_prompt += "\n## [反方] 必须包含反方论证"

        return base_prompt
```

### 3.4 风格混合系统

**改动文件：** `core/style.py`

```python
class StyleCompiler:
    def blend_styles(self, styles: dict[str, float]) -> dict:
        """混合多种机构风格"""
        blended = {
            "sentence_openers": [],
            "vocabulary": [],
            "format_rules": [],
        }

        for style_name, weight in styles.items():
            style_config = self._load_style(style_name)
            for key in blended:
                if key in style_config:
                    # 按权重添加风格元素
                    count = max(1, int(len(style_config[key]) * weight))
                    blended[key].extend(style_config[key][:count])

        return blended
```

### 3.5 定制化接口设计

```python
# 新增文件：pipeline/customization.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ReportRequest:
    """用户报告请求"""
    asset: str
    report_type: str = "industry_deep"
    style: str = "cicc"

    # 定制化选项
    customization: Optional[ReportCustomization] = None

    # 快捷定制
    length: str = "standard"
    focus: list[str] = None
    skip: list[str] = None

    def to_customization(self) -> ReportCustomization:
        """转换为定制化配置"""
        return ReportCustomization(
            dimension_weights=self._parse_weights(),
            length=self.length,
            focus_dimensions=self.focus,
            skip_dimensions=self.skip,
            style_preset=self.style,
        )

    def _parse_weights(self) -> dict:
        """解析维度权重"""
        if not self.focus:
            return None
        return {dim: 2.0 for dim in self.focus}  # 重点维度权重 x2
```

---

## 四、Plan-and-Execute 模式

### 4.1 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Plan Phase（规划阶段）                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Intent Parser → 报告大纲生成 → 用户审批（可选）       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Execute Phase（执行阶段）                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  并行数据采集 → 并行分析 → 并行写作 → 合成            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Review Phase（审查阶段）                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Iron Gate → 用户反馈 → 迭代优化（可选）              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 实现方案

```python
# 新增文件：pipeline/plan_and_execute.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class ReportPlan:
    """报告计划"""
    asset: str
    report_type: str
    dimensions: list[dict]  # [{"id": "headline", "weight": 1.5, "focus": True}]
    estimated_time: int  # 预计耗时（秒）
    data_requirements: list[str]  # 数据需求
    user_feedback: Optional[str] = None  # 用户反馈

class PlanAndExecuteOrchestrator:
    """Plan-and-Execute 编排器"""

    def __init__(self, request: ReportRequest):
        self.request = request
        self.plan: Optional[ReportPlan] = None

    def plan(self) -> ReportPlan:
        """规划阶段"""
        # 1. 意图解析
        intent = self._parse_intent()

        # 2. 生成报告大纲
        dimensions = self._generate_outline(intent)

        # 3. 估算时间
        estimated_time = self._estimate_time(dimensions)

        # 4. 生成数据需求
        data_requirements = self._identify_data_needs(dimensions)

        self.plan = ReportPlan(
            asset=self.request.asset,
            report_type=self.request.report_type,
            dimensions=dimensions,
            estimated_time=estimated_time,
            data_requirements=data_requirements,
        )

        return self.plan

    def execute(self, plan: ReportPlan) -> str:
        """执行阶段"""
        # 1. 并行数据采集
        collected_data = self._collect_data_parallel(plan.data_requirements)

        # 2. 并行分析
        analysis_results = self._analyze_parallel(collected_data, plan.dimensions)

        # 3. 并行写作
        report_text = self._write_parallel(analysis_results, plan.dimensions)

        # 4. 合成
        final_report = self._synthesize(report_text)

        return final_report

    def review(self, report: str) -> tuple[bool, str]:
        """审查阶段"""
        # 1. Iron Gate 校验
        gate_result = self._validate(report)

        # 2. 如果失败，生成反馈
        if not gate_result.passed:
            feedback = self._generate_feedback(gate_result)
            return False, feedback

        return True, report
```

### 4.3 Human-in-the-Loop 接口

```python
# 新增文件：pipeline/human_in_the_loop.py
class HumanInTheLoop:
    """人工审批节点"""

    def __init__(self, auto_approve: bool = False):
        self.auto_approve = auto_approve

    def approve_plan(self, plan: ReportPlan) -> bool:
        """审批报告计划"""
        if self.auto_approve:
            return True

        # 生成计划摘要
        summary = self._format_plan_summary(plan)

        # 输出给用户
        print("\n" + "=" * 60)
        print("  报告计划审批")
        print("=" * 60)
        print(summary)
        print("=" * 60)

        # 等待用户输入
        response = input("\n是否继续执行？(y/n/修改建议): ")

        if response.lower() == 'y':
            return True
        elif response.lower() == 'n':
            return False
        else:
            # 用户提供修改建议
            plan.user_feedback = response
            return self.approve_plan(plan)  # 递归重新审批

    def approve_report(self, report: str) -> tuple[bool, str]:
        """审批报告初稿"""
        if self.auto_approve:
            return True, report

        print("\n" + "=" * 60)
        print("  报告初稿审批")
        print("=" * 60)
        print(report[:2000] + "..." if len(report) > 2000 else report)
        print("=" * 60)

        response = input("\n是否通过？(y/n/修改建议): ")

        if response.lower() == 'y':
            return True, report
        elif response.lower() == 'n':
            return False, report
        else:
            return False, response  # 返回修改建议
```

---

## 五、实施路线图

### Phase 1: 并行化基础（1周）

| 任务 | 耗时 | 优先级 | 依赖 |
|------|------|--------|------|
| AgentGraph 分层拓扑排序 | 1天 | P0 | 无 |
| AgentGraph 并行执行器 | 1天 | P0 | 分层排序 |
| write_sections 维度级并行 | 2天 | P0 | 并行执行器 |
| 并行化单元测试 | 1天 | P1 | 维度级并行 |

**验收标准：**
- [ ] AgentGraph 支持 `parallel_mode=True` 参数
- [ ] 无依赖节点并行执行
- [ ] write_sections 维度级并行
- [ ] 单元测试通过

### Phase 2: 定制化（1周）

| 任务 | 耗时 | 优先级 | 依赖 |
|------|------|--------|------|
| ReportCustomization 数据类 | 0.5天 | P0 | 无 |
| SAC 维度权重系统 | 1天 | P0 | 数据类 |
| 篇幅控制系统 | 1天 | P1 | 数据类 |
| 风格混合系统 | 1天 | P1 | 数据类 |
| 定制化接口 | 0.5天 | P1 | 所有子系统 |

**验收标准：**
- [ ] ReportCustomization 支持所有定制维度
- [ ] 维度权重可配置
- [ ] 篇幅可控制（short/standard/detailed）
- [ ] 风格可混合

### Phase 3: Plan-and-Execute（1周）

| 任务 | 耗时 | 优先级 | 依赖 |
|------|------|--------|------|
| PlanAndExecuteOrchestrator | 2天 | P1 | 并行化 |
| HumanInTheLoop 接口 | 1天 | P2 | 编排器 |
| 意图解析器 | 1天 | P1 | 无 |
| 集成测试 | 1天 | P1 | 所有组件 |

**验收标准：**
- [ ] Plan-and-Execute 模式可用
- [ ] 支持人工审批（可选）
- [ ] 意图解析准确

### Phase 4: 优化与测试（1周）

| 任务 | 耗时 | 优先级 | 依赖 |
|------|------|--------|------|
| 性能基准测试 | 1天 | P1 | 所有改造 |
| 并行化压力测试 | 1天 | P1 | 并行化 |
| 定制化 E2E 测试 | 1天 | P1 | 定制化 |
| 文档更新 | 1天 | P2 | 所有改造 |
| 代码审查 | 1天 | P1 | 所有改造 |

**验收标准：**
- [ ] 并行化耗时 ≤ 20min（3轮）
- [ ] 定制化功能正常
- [ ] 所有测试通过
- [ ] 文档完整

---

## 六、风险与缓解

### 6.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 并行写入导致内容不一致 | 高 | 维度间注入上下文摘要，确保连贯性 |
| 并行执行资源竞争 | 中 | 限制并发数，使用线程池 |
| LLM API 并发限制 | 中 | 实现请求队列 + 重试机制 |
| 定制化参数冲突 | 低 | 参数校验 + 默认值回退 |

### 6.2 质量风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 并行写作降低质量 | 高 | Iron Gate 校验不变，质量门禁前置 |
| 定制化破坏框架完整性 | 中 | SAC 核心维度不可跳过 |
| 风格混合不自然 | 中 | 提供预设混合方案，禁止任意混合 |

### 6.3 实施风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 改造周期超预期 | 中 | 分阶段交付，Phase 1 优先 |
| 现有测试覆盖不足 | 中 | 改造前补充测试 |
| 团队学习成本 | 低 | 提供详细文档 + 示例 |

---

## 七、成功指标

### 7.1 性能指标

| 指标 | 当前值 | 目标值 | 提升 |
|------|--------|--------|------|
| 单轮耗时 | ~15min | ~7min | 53% |
| 3轮耗时 | ~45min | ~20min | 56% |
| 并发维度数 | 1 | 5-14 | 14x |

### 7.2 功能指标

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 定制维度数 | 0 | 8 |
| 支持风格数 | 6 | 6 + 混合 |
| 篇幅选项 | 1 | 3 |
| 人工审批 | 不支持 | 可选 |

### 7.3 质量指标

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| Gate 通过率 | ~85% | ≥90% |
| SAC 覆盖率 | ~75% | ≥80% |
| 用户满意度 | - | ≥4.5/5 |

---

## 八、附录

### 8.1 改动文件清单

| 文件 | 改动类型 | 优先级 |
|------|----------|--------|
| `pipeline/agent_graph.py` | 重构（并行执行器） | P0 |
| `pipeline/section_writer.py` | 重构（维度级并行） | P0 |
| `pipeline/e2e_orchestrator.py` | 重构（并行编排） | P0 |
| `pipeline/customization.py` | 新增（定制化配置） | P0 |
| `pipeline/plan_and_execute.py` | 新增（Plan-and-Execute） | P1 |
| `pipeline/human_in_the_loop.py` | 新增（人工审批） | P2 |
| `core/sacs/__init__.py` | 修改（维度权重） | P1 |
| `core/style.py` | 修改（风格混合） | P1 |
| `tests/test_parallel.py` | 新增（并行测试） | P1 |
| `tests/test_customization.py` | 新增（定制化测试） | P1 |

### 8.2 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PARALLEL_MODE` | `1` | 启用并行执行 |
| `MAX_PARALLEL_WORKERS` | `8` | 最大并行数 |
| `DIM_PARALLEL` | `1` | 启用维度级并行 |
| `AUTO_APPROVE` | `0` | 自动审批（跳过人工） |
| `DEFAULT_LENGTH` | `standard` | 默认篇幅 |
| `DEFAULT_STYLE` | `cicc` | 默认风格 |

### 8.3 兼容性

- **向后兼容**：所有新功能默认关闭，通过环境变量启用
- **API 兼容**：现有 `main.py` 接口不变
- **数据兼容**：现有 SAC YAML 格式不变
- **测试兼容**：现有 500 个测试继续通过

---

> 文档结束 | 版本 1.0 | 2026-08-27
