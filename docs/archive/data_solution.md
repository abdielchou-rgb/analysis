# 2号分析师数据采集解决方案

## 问题诊断

当前数据采集存在三个根本断裂：

### 断裂1：两套数据系统不互通

pipeline 的 DataCollector 从未调用过 data_manager。后者虽然慢但能返回真实市场数据。

### 断裂2：结构化财务数据从web到图表的映射缺失

data_manager返回的是DataPoint对象（股价、实时行情），不是图表需要的{year: value}格式。

### 断裂3：缓存层缺失

每次运行都从头抓取，同一标的重复耗时。cache_manager.py存在但未集成。

## 修复方案

### P0：修复DataCollector -> data_manager桥接（2小时）

collect()末尾添加：
- 提取股票代码
- 调用data_manager.get_data(asset_code=xxx)
- 将market/consensus数据注入result

### P1：构建Web-to-Data提取层（3小时）

在DataCollector中添加_extract_financials_from_web()：
1. crawl4ai搜索财务数据
2. DeepSeek提取结构化JSON
3. 映射到chart_id格式
4. ChartPlanner接收真实数据

### P2：缓存层集成（1小时）

1. cache_manager对提取结果做LRU缓存
2. 同一标的24小时内不重复搜索

### P3：数据源冗余（2小时）

扩展搜索源：
- Tavily MCP（已配置但管线未调用）
- Exa MCP
- 东方财富API直接抓取

## 实施优先级

第1步：P0桥接 -> 至少拿到实时行情数据
第2步：P1提取 -> 拿到财务数据，图表从占位图变为真实数据
第3步：P0+P1测试 -> 写一份报告验证数据流
第4步：P2缓存 + P3冗余 -> 稳定性和速度优化

## 预期效果

修复后芯联集成报告的图表将从：
- 5张占位图 + 空数据
- 变为：5张真实图表 + 数据交叉验证 + 来源标注
