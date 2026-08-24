# Marvis 全量财务明细同步命令集（R27）

> 2026-08-02 生成。Marvis 在用户机执行（token 免费，akshare 可用）。
> 目标：沪深300(000300) + 中证1000(000852) = 1300 只核心标的的**完整三表明细**。

## 背景

现有 financials.db 5259 只股票但**平均仅 13.4 字段/只**，最丰富也才 26 字段。
关键明细（应收账款/存货/商誉/研发费用/营业成本/费用明细）**全部缺失**——
这是柯力传感报告 10 处"待核实"的系统性根因。

已扩展 `scripts/sync_akshare_financials.py`：
- 字段映射 10 → **38 个**（profit 17 + balance 16 + cashflow 5）
- 新增 `--index` 参数支持沪深300/中证1000
- 新增东财利润表明细拉取 `_fetch_em_profit`
- 新增 `get_index_constituents()` 指数成分读取

## 执行命令（按顺序）

### 1. 沪深300 全量明细（300 只）
```bash
cd D:\2hao-analyst
python scripts/sync_akshare_financials.py --index 000300 --workers 4
```

### 2. 中证1000 全量明细（1000 只）
```bash
python scripts/sync_akshare_financials.py --index 000852 --workers 4
```

### 3. 单只验证（柯力传感）
```bash
python scripts/sync_akshare_financials.py 603662
```

## 验证（跑完任意一步后）

### 柯力传感字段是否补全
```bash
python -c "
import sqlite3
conn = sqlite3.connect('data/financials.db')
fields = [r[0] for r in conn.execute(\"SELECT DISTINCT field FROM financials WHERE code='603662'\").fetchall()]
print('柯力字段数:', len(fields))
for need in ['accountsReceivable','inventory','goodwill','rAndD','operatingCost','sellExpense']:
    print(f'  {need}: {\"✅\" if need in fields else \"❌缺\"}')
"
```
应看到 `accountsReceivable/inventory/goodwill/rAndD` 等 ✅。

### 覆盖统计
```bash
python scripts/sync_akshare_financials.py --status
```
期望：字段数从 13.4 → 30+，覆盖仍 5000+ 只。

## 东财字段名对照（已映射，勿改）

**资产负债表**（stock_balance_sheet / 东财 RPT_F10_FINANCE_GBALANCE）：
- TOTAL_ASSETS→总资产, TOTAL_LIABILITIES→总负债, TOTAL_EQUITY→股东权益合计
- MONETARYFUNDS→货币资金, ACCOUNTS_RECE→应收账款, NOTE_RECE→应收票据
- INVENTORY→存货, GOODWILL→商誉, FIXED_ASSET→固定资产, INTANGIBLE_ASSET→无形资产
- SHORT_LOAN→短期借款, LONG_LOAN→长期借款, ACCOUNTS_PAYABLE→应付账款
- ADVANCE_RECE→预收款项, TOTAL_CURRENT_LIAB→流动负债合计, TOTAL_NONCURRENT_LIAB→非流动负债合计

**利润表**（东财 RPT_F10_FINANCE_GINCOME）：
- TOTAL_OPERATE_INCOME→营业总收入, OPERATE_INCOME→营业收入
- TOTAL_OPERATE_COST→营业总成本, OPERATE_COST→营业成本
- R_D_EXPENSE→研发费用, SALE_EXPENSE→销售费用, MANAGE_EXPENSE→管理费用
- FINANCE_EXPENSE→财务费用, OPERATE_PROFIT→营业利润, TOTAL_PROFIT→利润总额
- NETPROFIT→净利润, INCOME_TAX→所得税费用, BASIC_EPS→基本每股收益, DEDUCT_NETPROFIT→扣非净利润

**现金流量表**（东财 RPT_F10_FINANCE_GCASHFLOW）：
- NETCASH_OPERATE→经营活动净额, NETCASH_INVEST→投资净额, NETCASH_FINANCE→筹资净额
- CASH_RECV_SG_RS→销售收现, CONSTRUCT_LONG_ASSET→购建长期资产支付

## 注意

1. **东财接口限流**：workers 建议 2-4。中证1000 共 1000 只 × 3 表，约 3000 次请求，分批自动跑（BATCH=200）
2. **若接口断连**（RemoteDisconnected）：等待几分钟重试，或降 workers
3. **单位**：全部为元（与 Baostock 对齐）。毛利/ROE 仍存比值
4. **不覆盖已有数据**：`_merge_statements` 对已有字段不覆盖，akshare 源优先
5. **柯力传感验证优先**：跑完沪深300即可先验证柯力（603662 在沪深300），确认明细补全

## 完成后回报

1. 沪深300/中证1000 分别同步了多少只、新增多少字段
2. 柯力传感字段补全确认（上面验证命令输出）
3. 是否有失败股票及失败原因（限流/接口变更）
