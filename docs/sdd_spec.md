# 2hao-analyst SDD 规格说明书

> 自动生成时间：$(date)
> 生成器：harness/generate_docs.py

## 规格 vs 代码 vs 文档 映射

| 规格层 | 代码位置 | 文档位置 |
|--------|----------|----------|
| 管线合约 | harness/pipeline_contract.py | CLAUDE.md / README.md |
| SAC 框架 | core/sacs/*.yaml | AGENTS.md / SKILL.md |
| 验证规则 | harness/validator.py | pre-commit-config.yaml |
| 质量门禁 | pipeline/iron_gate.py | SKILL.md |

## 变化追踪

修改代码合约后，执行以下命令同步文档：

```bash
python harness/generate_docs.py  # 重新生成所有文档
python harness/validator.py       # 验证一致性
```
