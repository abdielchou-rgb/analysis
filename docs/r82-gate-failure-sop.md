# Gate 失败整改 SOP（R82）

> 目标：禁止"Gate 失败后旁路导出"，建立"失败→定位→修复→重跑"闭环
> 触发：v9 事故（E2E 三轮 Gate 全失败后旁路手动导出）
> 日期：2026-08-06

## 铁律
**Gate 失败 = 报告不可交付。任何旁路导出（手动改稿/跳过 Gate/直接生成 docx）均为违规。**

## 标准流程

```
Gate 失败
  ↓ 1. 收集失败项
  cat output/_gate_prev.md  # 本轮稿
  # 看失败列表（模板/DES/硬凑/数字冲突/来源实体）
  ↓ 2. 先跑 pytest 定位（不手写脚本）
  python -m pytest tests/ -q -k "r79 or r82 or fact" 2>&1 | tail
  ↓ 3. 分类失败
  ├─ 生成端问题（模板句/反方空壳/硬凑数字）→ 改 prompt 或局部重写失败段
  ├─ 数据问题（数字冲突/口径）→ 查单一事实源 enrich-file 修正
  ├─ 来源问题（无实体标注）→ 补具体公司名+日期
  └─ 产物问题（AI标注/空段/图不足）→ 走 export_report 重新导出
  ↓ 4. 修复（局部修订，不全量重写）
  # 只重写失败段，配合 checkpoint 续跑
  ↓ 5. 重跑 Gate
  python pipeline/scheduler.py "标的" --type X --enrich-file data/xxx.json
  ↓ 6. 验证通过才交付
  # IronGate passed + VisualGate passed + 产物验证
```

## 禁止项
- ❌ 手动改 md 绕过 Gate 直接导出 docx
- ❌ Gate 失败后直接交付 _gate_prev.md
- ❌ 手写临时脚本验证（先跑 pytest）

## 允许项
- ✅ 局部修订失败段（_locate_failed_segments 定位）
- ✅ enrich-file 修正数据后回流
- ✅ prompt 调整后重跑

## 验收
Gate passed=true + VisualGate passed + 产物验证（无AI/含图/空段<5%）才可交付
