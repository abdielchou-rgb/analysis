# R77 P0 全量修复 — 反馈桥断裂治本

> 基于油位传感器 v0.86 Gate 8轮失败深度复盘
> 实施日期：2026-08-06

## 变更清单

| # | 文件 | 变更内容 |
|---|------|---------|
| A1 | `pipeline/fail_segment_locator.py` | 归因正则收窄：data_conflicts 去掉"口径"；annotation_types 去掉"来源标注"；新增 market_size_consistency / source_entity 独立匹配 |
| A1 | `pipeline/fail_segment_locator.py` | 失败指纹检测：同一指纹出现≥3次→降级警告，不触发全量重写（对标 AgentGuard-LLM） |
| A2 | `pipeline/fail_segment_locator.py` | 死角段定位：从 Gate feedback 解析"死角段: xxx"标记→映射段索引→段级重写 |
| A2 | `pipeline/checks/analysis_mixin.py` | `_check_so_what_chain` details 追加"死角段: 段标题/首句"信息 |

## 语法验证

```
OK: pipeline/fail_segment_locator.py (ast.parse)
OK: pipeline/checks/analysis_mixin.py (ast.parse)
```

## 修复效果

| 修复前（v0.86） | 修复后 |
|----------------|--------|
| "口径"误匹配 data_conflicts → 全量重写 | market_size_consistency 独立匹配 → 可定位到具体段 |
| "来源标注空泛"误匹配 annotation_types → 全量重写 | source_entity 独立匹配 → 可定位 |
| so_what_chain 死角段无定位 → 每次全量重写 | Gate 产出死角段标题 → fail_locator 段级重写 |
| 同失败反复出现 → 无限重试 | 指纹≥3次 → 降级警告 → 不触发重写 |
