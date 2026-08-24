"""2hao-analyst Harness — 验证、合约、文档生成

架构：
  harness/
    validator.py      — 环境验证（import链/语法/P0扫描）
    pipeline_contract.py — 管线合约定义
    generate_docs.py  — SDD 文档生成（从代码自动生成文档）

用法：
  python -m harness.validator          # 运行全部验证
  python -m harness.generate_docs      # 生成最新文档
"""
