# R78 中美竞争维度全量优化

> 对标高盛政策时间线 / 大摩双轨情景 / 中金国产替代映射
> 日期：2026-08-05

## 新建模块

### core/geopolitical_engine.py
- 政策时间线：按日期排序的管制/关税/补贴事件
- 双轨情景：脱钩加速 vs 缓和，各给概率（事件方向驱动）
- 国产替代传导：受影响环节 → 受益方向
- 量化指标：对美暴露度 / 自主可控度（0-10）
- build_injection() 生成 section_writer 注入块

### data/geo_events.json
- 8 条中美政策事件（BIS 管制/AI 芯片/矿产反制/大基金），带 source + date + direction
- WebSearch 采集 + 知识库补充

## 接线

### section_writer
- 新增 `geo_str` 注入块（对标 R76 的 ss/cc/sf/cf 模式）
- 从 asset 关键词推断行业 → geopolitical_engine 分析 → 注入 prompt

### IronGate
- 新增 `_check_geopolitical_depth`（warning 级）：事件是硬门槛——
  有具体政策事件（日期/实体清单/BIS）+ 量化影响 + 传导路径 才算深度
- 浅层"只提地缘"→ 不通过（score 0.3）

## 实测

- 半导体：8 事件，脱钩加速 85%，对美暴露度 8.0/10，自主可控 4.8/10
- 注入块 702 字，含时间线+双轨情景+替代传导+量化指标

## 回归

- 新增 test_r78_geopolitical.py（6 项）
- 38 pytest 全绿
