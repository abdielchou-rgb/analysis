# Prompt 版本管理

> 本目录记录所有用于 LLM 调用的系统提示词（system prompt）。
> 每个 prompt 有独立版本号，修改必须更新版本号和日期。

## 注册的 Prompt

| ID | 用途 | 版本 | 最后更新 | 位置 |
|----|------|------|----------|------|
| section_writer_v4 | SAC 三段式写作主 prompt | v4.2 | 2026-07-28 | pipeline/section_writer.py:_build_prompt_v4 |
| section_writer_sys | 系统角色 prompt | v2.1 | 2026-07-28 | pipeline/section_writer.py:_call_llm |
| iron_gate_critic | IronGate LLM 评分 prompt | v1.0 | 2026-07-25 | pipeline/iron_gate.py:_run_critic_agent |
| style_cicc | 中金风格注入 | v1.0 | 2026-07-20 | core/knowledge_injector.py |
| style_gs | 高盛风格注入 | v1.0 | 2026-07-20 | core/knowledge_injector.py |

## 修改规则

1. 修改 prompt 后更新版本号和日期
2. 在 CHANGELOG.md 中记录
3. 运行 `python -m harness.property_test` 确保不破坏属性测试
