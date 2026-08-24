# P0 数据丰富度 — 修复补充说明书（第 2 轮）

> 交接给 Marvis。上一轮（2026-08-01）交付的数据已由主分析 agent 验收，发现 3 个质量问题需要修复。
> 生成日期：2026-08-01

---

## 验收结论摘要

上一轮"量"达标（同步脚本跑通、批处理完成），但**质量未达标**，3 个问题必须修复后才能进管线：

| # | 问题 | 严重度 | 位置 |
|---|------|--------|------|
| 1 | 公司事件库是空壳（数值全 0、ticker 空） | **P0** | `data/company_events.db` |
| 2 | 行业基线混入 test 调试脏数据 | **P1** | `data/industry_baselines.json` |
| 3 | 研报提取率低 + 深交所/分红未完成 | **P1** | `temp/agent_extract_batch1.json` |

---

## 修复 1：company_events 空壳数据（P0，必须修）

### 问题证据
- `earnings` 表 51 行，但 `revenue=0.0`、`net_profit=0.0`、`report_date=''` —— 全是空值
- `share_changes` 表 27 行，但 `ticker=''`、`shareholder=''`、`change_shares=0.0`
- `dividends` 0 行、`announcements` 0 行

### 根因（已定位）
1. **`sync_earnings` 用错接口**：`ak.stock_financial_report_sina(stock=..., symbol="资产负债表")` 返回的是**资产负债表**，没有"营业总收入/净利润"列（那在利润表里）。`row.get("营业总收入", 0)` 永远拿 0，`float(... or 0)` 把缺失值写成 0.0。
   - **修法**：改用利润表接口 `ak.stock_financial_report_sina(stock=..., symbol="利润表")`，或换 `ak.stock_financial_abstract_ths`（同花顺摘要，含营业总收入/净利润）。
2. **`sync_share_changes` 列名不匹配**：`stock_share_hold_change_sse` 返回的实际列名与脚本假设的 `"代码"/"变动日期"/"股东名称"` 不一致，`row.get(...)` 全拿空字符串。
   - **修法**：先打印 `dfs.columns` 确认实际列名，再映射。akshare 该接口列名可能是 `"证券代码"/"股东名称"/"变动开始日期"` 等。
3. **空行也写库**：`INSERT OR REPLACE` / `INSERT OR IGNORE` 在数值全 0 或关键字段为空时**仍写入**。
   - **修法（强制）**：入库前校验——关键字段（ticker、日期、数值）任一为空或数值==0 且原本无值 → **跳过**，不写库，并计入 failed 待重试。

### 强制规范（FP2 数据零编造）
```
每条数据入库前必须通过有效性校验：
  - ticker/日期 非空
  - 数值字段：revenue/net_profit 等不能为 0.0（除非真实为 0 且来源明确）
  - 校验失败 → 跳过入库 + 打印 [SKIP] 原因
  - 清理现有空壳数据：DELETE FROM earnings WHERE revenue=0 AND net_profit=0;
```

### 验收标准
- `earnings` 每行 `revenue>0` 或 `net_profit>0`（至少一个真实值）
- `share_changes` 每行 `ticker` 非空且为 6 位代码
- 无 0.0/空字符串残留

---

## 修复 2：行业基线 test 脏数据（P1）

### 问题证据
`data/industry_baselines.json` 的 `sectors` 里有 3 条：
```json
{"sector_name": "test_0"}, {"sector_name": "test_1"}, {"sector_name": "test_2"}
```
这是调试残留，无任何有效字段。

### 修法
1. 检查 `scripts/sync_industry_baselines.py` 是否有 `test_` 调试代码，删除
2. 清理现有数据：从 `industry_baselines.json` 移除所有 `sector_name` 以 `test` 开头的条目
3. 重跑 `python scripts/sync_industry_baselines.py` 生成干净库

### 验收标准
- `sectors` 里无任何 `test` 开头条目
- 338 个行业全部有效（PE/PB/股息率 至少一项非空，缺失的标记 null 而非 0）

---

## 修复 3：研报提取率 + 深交所/分红（P1）

### 问题证据
- `agent_extract_batch1.json` 11 条里：2 扫描空 + 6 状态未知 + 2 重复跳过 + 1 空替换
- 2,155 份 PDF 只提取 162 份有效（7.5%）
- 报告"待跟进"承认：深交所增减持超时、分红未执行

### 修法
1. **深交所增减持**：`stock_share_hold_change_szse` 加更长重试（5 次退避 3s），或拆小批量避开限流
2. **分红数据**：逐 ticker 调 `ak.stock_dividents_cninfo`，写入 `dividends` 表（同样过有效性校验）
3. **扫描版研报**：`temp/agent_extract_batch1.json` 里状态为 `scanned_or_empty` 的，用 Marvis agent 的 OCR/增强提取能力重试（不是简单正则）

---

## 完成检查清单

- [ ] `data/company_events.db` 无空壳行（earnings 有真实值、share_changes ticker 非空）
- [ ] `data/industry_baselines.json` 无 test 条目
- [ ] 深交所增减持补齐、分红表有数据
- [ ] 每项改动后跑读回验证（count + 抽样）

## 参考资料
- 现有脚本：`scripts/sync_company_events.py` / `scripts/sync_industry_baselines.py`
- 数据规范：见原说明书第 2 节（source 标注 / 幂等 / 分批 / 异常隔离）
