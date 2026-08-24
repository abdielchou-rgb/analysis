# 2hao-analyst 快速上手指南

> 目标：用最短时间让2hao-analyst稳定产出机构级深度报告
> 基于FP1-FP7宪法裁决链：FP4 → FP2a → FP2b → FP6 → FP7 → FP5 → FP3 → FP1

---

## 一、如何写报告

### 标准命令（一键执行）

```bash
cd D:\2hao-analyst
set ENFORCE_GATE=true
python pipeline/scheduler.py "宁德时代 300750.SZ" --type listed_company --style cicc
```

参数说明：
- `asset` = 标的名称+股票代码(上市公司) / 公司名(非上市) / 行业名+行业分析
- `--type` = `listed_company` / `unlisted_company` / `industry_deep` / `earnings_notes`
- `--style` = `cicc` / `goldman_sachs` / `mckinsey` / `bcg` / `jpm` / `ms`

### 输出

```
output/{标的}_{风格}.docx  — 完成报告(通过IronGate+VisualGate)
output/{标的}_{风格}.md    — Markdown原文
```

### 快速体验(不依赖akshare)

如果akshare未安装，系统会自动降级到：
1. Tavily搜索+DeepSeek提取财务数据
2. 东方财富/Sina公开API(零依赖)

---

## 二、迭代升级计划

### 第1步：安装akshare(30分钟)

```bash
# 方式1: 标准安装
pip install akshare

# 方式2: 使用镜像(国内环境)
pip install akshare -i https://pypi.tuna.tsinghua.edu.cn/simple

# 方式3: 仅安装核心依赖(跳过可选)
pip install akshare --no-deps
```

安装后测试:
```bash
python -c "import akshare; print(akshare.__version__)"
```

**为什么急需**：akshare提供结构化财务数据(营收/利润/毛利率等精确数值)，
绕过Tavily的文本提取。直接影响IronGate的data_traceability评分(当前0.05→预期0.6+)。

---

### 第2步：跑3份报告积累数据(1小时)

```bash
python pipeline/scheduler.py "宁德时代 300750.SZ" --type listed_company --style cicc
python pipeline/scheduler.py "汇川技术 300124.SZ" --type listed_company --style cicc
python pipeline/scheduler.py "人形机器人传感器" --type industry_deep --style cicc
```

每份报告产出：
- learning_loop DB记录(evolution data)
- ForwardPicks记录(Bold Call跟踪)
- gate score记录(Quality baseline)

3份后FP3-D6(持续维度)开始可测。

---

### 第3步：激活debate协议(2小时, 80行代码)

在section_writer中增加Bold Call辩论：

```
bull agent: 写Bold Call(200字,看多论证)
bear agent: 写反方(200字,看空论证)  
judge: 综合输出(200字,概率加权)
```

FP3-D5(协作维度)从0%→50%。

---

### 第4步：整理代码库(1小时)

```bash
# 归档遗产代码(14K行)
mv compute/V30_compute/ archive/
mv compute/V30_tools/ archive/

# 删除已废弃文件
rm pipeline/content_enforcer.py
```

代码量从72K→~55K行，FP1(系统本质)更清晰。

---

## 三、什么时候该做什么

| 阶段 | 动作 | 代码量 | FP受益 |
|------|------|--------|--------|
| 本周 | 装akshare | 1行 | FP2a+20pp |
| 本周 | 跑3份报告 | 3个命令 | FP3-D6+FP5 |
| 本月 | debate协议 | 80行 | FP3-D5 0→50% |
| 本月 | 剪枝 | 删文件 | FP1 |
| 季度 | 每周跑10份 | 持续 | FP5数据积累 |

## 四、模板报告

```bash
# 上市公司
python scheduler.py "宁德时代 300750.SZ" --type listed_company --style cicc
python scheduler.py "汇川技术 300124.SZ" --type listed_company --style cicc
python scheduler.py "中芯国际 688981.SH" --type listed_company --style cicc
python scheduler.py "华工科技 000988.SZ" --type listed_company --style cicc

# 非上市
python scheduler.py "比亚迪半导体" --type unlisted_company --style cicc
python scheduler.py "蚂蚁集团" --type unlisted_company --style cicc

# 行业分析
python scheduler.py "人形机器人传感器" --type industry_deep --style cicc
python scheduler.py "新能源储能" --type industry_deep --style cicc
```
