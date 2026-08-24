# Marvis 执行命令集 R30（模块4/5 数据补齐）

> 2026-08-02 生成。Marvis 在用户机执行（token 免费，akshare 可用）。
> 目标：补齐行业数据（模块4）+ 财务明细（模块5）+ 业绩预告（模块7数据源）

## 1. 行业数据补齐（模块4）

### 1a. industry_chain.json 加 3 行业条目
编辑 `D:\2hao-analyst\data\industry_chain.json`，往 `industries` 数组追加：
```json
{"name": "传感器", "upstream": ["敏感材料", "MEMS芯片", "弹性体特种钢", "MCU芯片"], "midstream": ["称重传感器", "MEMS传感器", "智能传感器模组"], "downstream": ["工业自动化", "汽车电子", "消费电子", "机器人", "医疗设备"], "key_players": ["柯力传感", "韦尔股份", "华工科技", "歌尔股份"], "source": "ai_search 2026"}
{"name": "仪器仪表", "upstream": ["传感器元件", "芯片", "精密机械"], "midstream": ["称重/分析仪器", "工业仪表"], "downstream": ["工业检测", "科研", "医疗"], "key_players": ["柯力传感", "川仪股份", "三川智慧"], "source": "ai_search 2026"}
{"name": "工控", "upstream": ["芯片", "伺服电机", "传感器"], "midstream": ["PLC", "伺服系统", "变频器"], "downstream": ["工厂自动化", "机器人"], "key_players": ["汇川技术", "埃斯顿", "信捷电气"], "source": "ai_search 2026"}
```

### 1b. industry_penetration.json 加传感器条目
往顶层 list 追加：
```json
{"industry": "传感器", "segment": "中国MEMS传感器国产化率", "penetration_pct": 30.0, "as_of": "2025", "life_cycle": "成长期", "growth_curve": "S曲线加速", "source": "..."}
{"industry": "传感器", "segment": "中国智能传感器市场规模增速", "penetration_pct": 12.0, "as_of": "2025", "life_cycle": "成长期", "growth_curve": "线性", "source": "..."}
```

### 1c. industry_drivers.json 加传感器 key
```json
"传感器": ["2025全球传感器市场规模约2000亿美元-Gartner", "• MEMS传感器市场增长XX%", "• 工业传感器国产替代加速", "..."]
```

## 2. 财务明细执行（模块5）

```bash
cd D:\2hao-analyst
# 沪深300 明细（应收/存货/商誉/研发等 30+ 字段）
python scripts/sync_akshare_financials.py --index 000300 --workers 4
# 中证1000 明细
python scripts/sync_akshare_financials.py --index 000852 --workers 4
# 验证柯力
python -c "
import sqlite3
conn = sqlite3.connect('data/financials.db')
fields = [r[0] for r in conn.execute(\"SELECT DISTINCT field FROM financials WHERE code='603662'\").fetchall()]
print('柯力字段数:', len(fields))
for need in ['accountsReceivable','inventory','goodwill','rAndD','operatingCost']:
    print(f'  {need}: {\"✅\" if need in fields else \"❌缺\"}')
"
```

## 3. 业绩预告同步（模块7数据源）

```bash
python scripts/sync_earnings_forecast.py              # 全量业绩预告
python scripts/sync_earnings_forecast.py --code 603662  # 单只
```

## 4. consensus 扩充到 300 只

```bash
python scripts/sync_consensus_estimates.py --all
```

## 完成后回报

1. 传感器/仪器仪表/工控 3 行业条目是否写入
2. 柯力 balance 字段是否 6 → 20+
3. 业绩预告条数
4. consensus 条数（51 → 300）
