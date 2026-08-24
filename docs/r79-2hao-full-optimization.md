# 2号分析师全量优化方案

> 目标：从"结构正确的模板机"进化为"有洞察、有信息增量、像人的分析师"
> 触发：油位报告圆桌评审——模板痕迹严重、激励倒挂、零一手调研、无全局整合
> 本文档：整合此前所有评审发现（r78-ai-template-critique / r79-reform-plan / r79-no-primary-data）为一份可执行的完整优化方案
> 执行对象：Marvis
> 日期：2026-08-05

---

## 一、现状诊断一句话

**2hao 能产出"结构满分"的报告，但产出不了"有洞察"的报告——因为激励结构奖励格式、惩罚留白，数据层零一手调研，写作层无全局整合。**

| 层级 | 现状 | 病根 |
|------|------|------|
| 写作层 | 模板套话复读、概率机械标注 | 激励倒挂逼 LLM 填充格式 |
| 结构层 | Bold Call 四处不一致、数据双口径 | 分段并行生成，无总编辑 |
| 评估层 | Gate 全绿但报告不合格 | 查格式信号，不查内容质量 |
| 数据层 | 零一手调研、纯二手推导 | 无访谈/招标/现场采集通道 |
| 闭环层 | 评审问题修一个复发一个 | 无"问题→机制→防再犯"沉淀 |

---

## 二、优化总纲

### 原则

1. **激励是根**：不重建激励，改 prompt 是治标
2. **先止血，再免疫，后重建**：P0 拦截模板 → P1 重建激励 → P2 补数据 → P3 全局整合
3. **测试先行**：每项整改先写回归测试，防复发
4. **允许诚实留白**：数据不足给 credit，而非逼硬凑
5. **二手极致化**：无一手数据时，用三角验证/供应链拆解/招标穿透/对标国做出分析优势

### 阶段

```
P0 止血（1-2天）→ P1 激励重建（3-5天）→ P2 数据通道（1-2周）→ P3 全局整合（持续）
```

---

## 三、P0：止血——让报告先"能见人"

### P0-1 模板句黑名单拦截
- **问题**：10 个万能过渡句全报告复读 3-8 次
- **方案**：`core/template_blacklist.py` 维护黑名单（初始 10 条）→ Style Compiler 扫描命中触发局部重写 → IronGate `_check_template_phrases`（≥2 warning / ≥4 error）
- **涉及**：`core/style.py`、`pipeline/checks/content_format_mixin.py`、`pipeline/iron_gate.py`
- **验收**：油位报告拦截 ≥6 条；新增 `test_r79_template_blacklist.py`

### P0-2 Bold Call 单一事实源
- **问题**：Bold Call 四处定义不一致
- **方案**：report_blueprint 存第一处 Bold Call → Gate `_check_bold_call_consistency` 比对全文（时间窗口/核心变量/增速不一致 → error）→ section_writer 注入"引用开头定义，不得重定义"
- **涉及**：`core/report_blueprint.py`、`pipeline/checks/analysis_mixin.py`
- **验收**：油位报告拦截 Bold Call 冲突；新增 `test_r79_bold_call_consistency.py`

### P0-3 市场规模口径统一
- **问题**：全球 32.5 vs 46 亿美元双口径
- **方案**：`_check_cross_section_consistency` 扩展覆盖市场规模/行业增速（偏差 >20% → error）→ section_writer 注入"统一全口径"
- **涉及**：`core/data_caliber.py`、`pipeline/checks/analysis_mixin.py`
- **验收**：拦截双口径；新增 `test_r79_caliber_consistency.py`

### P0-4 产物卫生
- **问题**：AI 标注残留、图表堆附录、重复表、空标题
- **方案**：所有执行路径强制走 export_report（禁绕过）→ `_check_duplicate_content` 查重复表 → `_check_completeness_scan` 查孤立标题
- **涉及**：`export/report_gate.py`、`pipeline/checks/content_format_mixin.py`
- **验收**：油位报告拦截全部卫生问题

---

## 四、P1：激励重建——治本

### P1-1 Gate 从"查格式"转向"查洞察"
- **问题**：判断密度数判断词，被刷分
- **方案**：`_check_judgment_density` 升级为洞察四要素检测：
  - 非显而易见（非常识复述）
  - 可证伪（有明确证伪条件）
  - 有数据支撑（锚定具体数字+来源）
  - 有信息增量（预期差/独家数据）
- 检测"常识复述"（"受益于政策""需求增长"无锚点）→ 降分
- 引入语义变体检测（sentence-transformers）防同义刷分
- **涉及**：`pipeline/checks/analysis_mixin.py`
- **验收**：常识复述降分、有锚点判断通过

### P1-2 反方论证从"概率机械"改为"论证强度"
- **问题**：每个反方机械标"概率30%"
- **方案**：`_check_counterargument_strength` 扩展——反方必须有具体机制（"国际巨头设中国厂+降价15%"）→ 概率无支撑降分 → section_writer 注入"用风险可控/不容忽视+理由"
- **涉及**：`pipeline/checks/analysis_mixin.py`、`pipeline/section_writer.py`
- **验收**：空壳概率反方降分

### P1-3 允许并奖励诚实留白
- **问题**：系统惩罚留白，逼硬凑
- **方案**：
  - 留白声明机制：section_writer 允许"数据不足，明确留白：<维度>（原因）"
  - 留白 credit：已声明留白维度不判缺失 + 报告获"诚实标注"加分
  - 反硬凑：无来源+具体数字的维度 → 降分
- **涉及**：`pipeline/section_writer.py`、`pipeline/checks/coverage_mixin.py`
- **验收**：留白通过且加分、硬凑拦截

### P1-4 评估器与生成器解耦
- **问题**：Gate 用 SAC 查，LLM 用 SAC 写，自己出题自己考
- **方案**：引入外部参照系（methodology_backtest_deep 金牌标准）+ 黄金样本对比（洞察密度/套话率/一手占比 vs 金牌报告）+ 对侧 provider 写作质量校验
- **涉及**：`pipeline/iron_gate.py`、`tests/golden/`
- **验收**：油位报告套话率 vs 金牌报告显著偏高触发 warning

---

## 五、P2：数据通道——补"分析优势"

### P2-1 公开数据穿透采集器（无一手数据的核心打法）

| 采集器 | 数据源 | 打法 |
|--------|--------|------|
| `core/procurement_miner.py` | 政府采购网/公共资源交易/中石化电子招标 | 招标量/中标价/厂商（"公开的一手数据"） |
| `core/supply_chain_bom.py` | 招股书/专利/供应商报价 | BOM 级成本结构 |
| `core/analogous_market.py` | 美国 EPA/欧盟/日本数据 | 对标国历史轨迹 |
| `core/financial_reverse.py` | 上市公司分部报告 | 行业规模/份额反推 |

### P2-2 深度分析模块

| 模块 | 功能 | 打法 |
|------|------|------|
| `core/triangulation.py` | 三法交叉验证市场规模 | 三角验证 |
| `core/policy_chain.py` | 政策→执行率→招标→订单传导链 | 政策传导 |
| `core/supply_signal.py` | 产能利用率/价格指数/交货周期 | 供给端信号 |

### P2-3 Gate "深度质量"检查

| 检查 | 检测 |
|------|------|
| `_check_triangulation` | 关键指标是否三法验证（≥2法） |
| `_check_policy_chain` | 政策结论是否有可追踪指标 |
| `_check_bom_depth` | 利润池是否有 BOM 支撑 |
| `_check_analogous` | 增速预测是否有对标国锚 |
| `_check_procurement` | 竞争格局是否有招标数据 |

### P2-4 报告"方法论标注"注入
- section_writer 注入：每个关键判断标注"用什么方法得到"（三角验证/供应链拆解/对标国/招标穿透/财务反推）
- 报告加"数据方法"小节：本节 = 自上而下+自下而上+对标国，交叉区间 X-Y 亿美元

---

## 六、P3：全局整合与风格

### P3-1 总编辑环节（Editor-in-Chief）
- 新增 `_global_edit` 节点：全段生成后，全局 LLM 接收全文+审查清单（统一口径/Bold Call 单一/删套话/调详略/加独到判断）
- 全局编辑后重跑 IronGate
- **涉及**：`pipeline/e2e_orchestrator.py`
- **验收**：编辑后无口径冲突、无 Bold Call 重复、模板句显著减少

### P3-2 机构风格库（写作风格层）
- `core/style_profiles.py` 从格式控制扩展到写作风格：段落节奏/详略偏好/语气/行业黑话密度
- **涉及**：`core/style_profiles.py`、`pipeline/section_writer.py`

### P3-3 评审意见回流为机制
- 新建 `docs/roundtable-backlog.md`：评审问题 → 对应机制 → 落地状态
- 每个问题必须映射到"防再犯机制"才关闭

---

## 七、执行顺序与回归

### Marvis 执行顺序
```
P0-1 模板句 → P0-2 Bold Call → P0-3 口径 → P0-4 卫生
→ P1-1 洞察 → P1-2 反方 → P1-3 留白 → P1-4 解耦
→ P2-1 招标采集 → P2-2 三角验证 → P2-3 政策链 → P2-4 供给信号
→ P3-1 总编辑 → P3-2 风格库 → P3-3 回流
```

### 每项 Checklist
1. 读问题 → 2. 读涉及文件 → 3. **先写回归测试** → 4. 改代码 → 5. 跑测试+全量回归 → 6. 更新 roundtable-backlog → 7. 油位报告验收

### 回归命令
```bash
cd D:\2hao-analyst
python -m pytest tests/test_r79_*.py -q
python -m pytest tests/test_fact_quality.py tests/test_e2e_keli.py tests/test_r77_*.py tests/test_r78_*.py -q
python tests/test_data_enrichment.py
```

---

## 八、整改后预期

| 维度 | 整改前 | 整改后 |
|------|--------|--------|
| 模板句 | 10 句复读 3-8 次 | 0 句 |
| Bold Call | 4 处不一致 | 1 处 |
| 市场规模 | 双口径冲突 | 三法交叉验证 |
| 反方论证 | "概率30%"空壳 | 具体机制+强度 |
| 留白 | 硬凑填充 | 诚实标注+credit |
| 一手数据 | 0% | 招标/价格穿透≥10% |
| 总编辑 | 无 | 全局编辑统一 |
| 风格 | AI 模板风 | 可感知机构风格 |
| 深度方法 | 孤零零结论 | 方法+验证+可追踪信号 |
