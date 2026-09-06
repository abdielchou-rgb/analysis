# PIPELINE FACTS

> 本文件由 harness/generate_docs.py 从代码实时生成（pre-commit 强制同步）。
> 手改无效——事实变更请改代码本身。生成时间见文件尾。

## IronGate
- 注册检查方法数（checks/）：103
- run_all 引用检查数：103
- 迁移完整性：OK
- 合约 min_score：0.55

## SAC
- decision_memo: 12 维
- earnings_notes: 5 维
- industry_deep: 26 维
- listed_company: 20 维
- unlisted_company: 26 维

## LLM Providers（priority 越小越优先）
- opencode_go: 1
- deepseek: 2
- zhipu: 3
- openrouter: 4
- opencode_zen: 5
- ollama_local: 9
- agent_provider: 10

## 阈值来源
- calibrated_thresholds.json: 存在
