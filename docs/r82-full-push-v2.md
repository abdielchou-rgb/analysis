# R82 全量推进 v2——执行记录

> 落地 v9 优化后未完成项（来源实体化 + Gate SOP）
> 日期：2026-08-06

## 已落地 2 项

### 1. 来源标注实体化（pipeline/checks/data_quality_mixin.py + iron_gate.py）
- 新增 `_check_source_entity`（error级）：拦截"来源：公司年报/公司公告/券商研究报告"等无实体标注
- v9 实测拦截 4 处空泛标注
- 实体化标注（"柯力传感2025年报"）通过
- **根治"标注幻觉"**——比不标注更危险的空泛来源

### 2. Gate 失败整改 SOP（docs/r82-gate-failure-sop.md）
- 铁律：Gate 失败 = 不可交付，禁旁路导出
- 标准流程：收集失败→先跑pytest定位→分类→局部修复→重跑→验证
- 禁止项：手动改稿绕过/交付_gate_prev/手写脚本
- **根治"旁路导出"**（v9事故）

## 回归
- 55 pytest 全绿

## 累计（R82 v1+v2）
- 行业键防串标（精确匹配+别名表+白名单）
- provider 路由（子进程加载env+启动诊断）
- 权限确认疲劳（allow列表+可信源+一键脚本）
- 终产物AI复核（导出后扫描）
- 数字单一事实源（data_single_source+Gate检查）
- 行业报告估值纪律（禁虚构EPS）
- 来源标注实体化（拦截空泛标注）
- Gate失败SOP（禁旁路）

## 未落地（需续）
- 外部真实研报 golden（5-10份，破除自我印证）
- LLM-as-judge rubric 评估（替代数关键词）
