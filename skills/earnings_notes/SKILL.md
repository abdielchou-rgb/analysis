---
name: earnings_notes
description: 业绩点评——SAC earnings_notes，季报/年报点评，快速响应，财务验证+预期差+评级，简洁高密度
---

# 业绩点评 Skill

## 触发
报告类型为 earnings_notes（季报/年报点评）时加载。

## SAC 框架（core/sacs/sac_earnings_notes.yaml）
业绩点评维度：营收/净利/毛利率/现金流 验证 + 预期差 + 评级。

## 快速响应定位
- **简洁高密度**（区别于深度报告）：核心数字 + 同比环比 + 预期差 + 一句话判断
- 目标：财报发布后快速给结论

## 必用模块
- **财务验证**（three_statement + data_caliber）：营收/净利/毛利率/现金流 勾稽，口径检测
- **预期差**（earnings_surprise / anti_consensus）：实际 vs 一致预期
- **预测闭环**（prediction_loop）：验证历史预测准确性
- **单位经济学**（unit_economics）：关键比率

## 财务纪律
- 数字必须可复算（同比/环比/毛利率）
- 数据标注 A/E/F/B
- 单季 vs 全年口径区分（避免"全年毛利率34.5% vs 单季5%"冲突）

## 结构（快评版）
核心结论（一句话）→ 业绩数据（表）→ 预期差 → 驱动因素 → 风险提示 → 评级

## 写作姿态
加载 author_pose skill（快评更要克制，无空话）
