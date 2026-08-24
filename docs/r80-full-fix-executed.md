# R80 全量修复执行记录

> 基于 r80-master-engineering-plan.md，Phase 0/1/2/3/5 核心项落地
> 日期：2026-08-06

## 已落地（9 项）

### Phase 0 交付止血
- 产物验证：export_report 增加 PDF 大小/图片、DOCX 空段率验证，不达标阻断
  - 油位重做报告 PDF 851KB 含图 ✅、docx 空段 2% ✅

### Phase 1 生成端约束（一次写对）
- 反方三段式 prompt：6 处注入"情境→机制→杀伤力"，禁止"概率XX%"空壳
- 数据纪律 prompt：无依据数字不写改留白，(E) 必须带估算依据

### Phase 2 评估端独立
- 外部 golden 对比脚本 tests/golden/compare_to_external.py（2hao vs 真实研报同指标对比）

### Phase 3 数据端穿透 + 合规
- 来源分级：core/data_contract.py 增加 classify_source（公开A/付费B/敏感C）+ 敏感不入正文校验
- 三角验证注入：section_writer 调用 triangulation，市场规模三法交叉

### Phase 5 系统端治理
- 预测回测闭环：core/backtest.py（到期对账 + 命中率 + 校准曲线）
- token 预算制：e2e 记录 elapsed + token_budget

## 回归
97 pytest 全绿

## 未落地（需续）
- 外部研报样本采集（golden_external 空，需下载真实券商PDF）
- 唯一渲染管线（pandoc+模板，当前仍多路径）
- LibreOffice 安装（PDF 已含图，但需固化）
- 架构瘦身（复杂度预算/加一删一）
- roundtable-backlog 固化
