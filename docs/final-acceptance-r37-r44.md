# 2hao 最终端到端验收 — R37-R44 全链路（2026-08-02）

> 背景：R37 数据补采 + R38-R44 代码修复已全部落地，需在**用户机联网环境**做最终端到端验收。
> 沙箱无法完成（缺 akshare/联网数据/DeepSeek 真实调用），必须在用户机执行。

---

## 一、验收目标

用最新管线重跑柯力传感，验证 R37-R44 全量修复在**真实报告**上的完整链路效果：

1. R37 补采数据（netProfit 覆盖 5218 只）是否进入报告链路
2. R38 财务门禁能否"生成时即拦截"（而非事后复评）
3. R39 数据契约（统一提取层）产出合理预测（EPS/毛利率无幻觉）
4. R42 报告拟人化（无 AI 免责声明）+ 静态目录
5. R43 目录完整性（一级+二级+三级）
6. R44 渲染层目检在真实 docx 上的表现

---

## 二、执行步骤

### 步骤 1：确认环境

```bash
cd D:\2hao-analyst
python -c "import akshare; print('akshare', akshare.__version__)"
python -c "import requests; print('requests OK')"
# 确认 DEEPSEEK_API_KEY 存在（.env 已配置）
grep -c "DEEPSEEK_API_KEY" .env
```

### 步骤 2：跑柯力传感报告（核心验收）

```bash
python pipeline/scheduler.py "柯力传感" --type listed_company
```

**预期**：
- 数据充足性检查通过（R37 补采后柯力财务明细齐全）
- 维度并行 + R30 模块注入生效（勾稽/预期差/对标矩阵/估值交叉验证进正文）
- Gate 通过或仅剩可解释的内容级 warning

### 步骤 3：验证产出文件

```bash
# 1. 检查四件套生成
ls -la output/柯力传感_cicc.* 2>/dev/null

# 2. 检查 docx 无空段/无空白页（R40 渲染层目检）
python -c "
import zipfile, re
z = zipfile.ZipFile('output/柯力传感_cicc.docx')
xml = z.read('word/document.xml').decode('utf-8')
paras = re.findall(r'<w:p\b[^>]*>(.*?)</w:p>', xml, re.S)
empty = sum(1 for p in paras if not re.sub(r'<[^>]+>', '', p).strip())
print(f'空段数: {empty}（应 < 15%）')
print(f'图片数: {xml.count(chr(60)+chr(119)+chr(58)+chr(100)+chr(114)+chr(97)+chr(119)+chr(105)+chr(110)+chr(103)+chr(62))}')"

# 3. 检查目录完整（R42/R43）
python -c "
from export.docx_exporter import add_static_toc
md = open('output/柯力传感_cicc.md', encoding='utf-8').read()
import re
h1 = sum(1 for l in md.split(chr(10)) if l.strip().startswith('# ') and not l.strip().startswith('## '))
print(f'一级章节数: {h1}')"

# 4. 检查无 AI 免责声明（R42）
python -c "
md = open('output/柯力传感_cicc.md', encoding='utf-8').read()
print('含免责声明:', '免责声明' in md or '仅供参考' in md or '不构成投资建议' in md)"
```

### 步骤 4：Gate 门禁复评

```bash
python -c "
import sys; sys.path.insert(0, '.')
from pipeline.iron_gate import IronGate
gate = IronGate('output/柯力传感_cicc.md', 'listed_company', 'cicc', asset='柯力传感')
report = gate.run_all()
print('PASSED:', report.passed)
print('SCORE:', round(report.overall_score, 4))
for c in report.checks:
    if not c.passed:
        print(f'  FAIL: {c.name} ({c.score:.2f}) {c.details[:80]}')"
```

**预期**：
- 历史 P0（毛利率矛盾/PE 口径）应被 R38 拦截并修正（新报告不再含矛盾）
- 剩余失败项应仅为可解释的内容级项（如有）

### 步骤 5：预测模型合理性抽查（R39 数据契约）

```bash
python -c "
import sys; sys.path.insert(0, '.')
from core.compute.predict_model import build_forecast, build_forecast_summary
dd = open('output/柯力传感_data_dict.json', encoding='utf-8').read()
import json
fc = build_forecast({'chart_data': json.loads(dd)}, 'listed_company')
print(build_forecast_summary(fc)[:300])"
```

**预期**：EPS 合理（非 0/非天文数字）、毛利率 ~45%（柯力真实水平，非 5% 兜底、非 46.9% 幻觉）

---

## 三、验收通过标准

| # | 检查项 | 通过标准 |
|---|--------|----------|
| 1 | 四件套生成 | md/docx/pdf/pptx 全部存在 |
| 2 | docx 空段率 | < 15%（无空白页） |
| 3 | 目录 | 含一级章节（# 一、等 6+ 个）+ 小节 |
| 4 | AI 免责声明 | 不含"免责声明/仅供参考/不构成投资建议" |
| 5 | Gate 评分 | ≥ 0.90（历史内容级项如 so_what 允许 warning） |
| 6 | 预测模型 | EPS 合理、毛利率 ~45% |
| 7 | R38 拦截 | 新报告不含毛利率/PE 矛盾（若含则生成时被拦截） |

---

## 四、注意事项

- **耗时**：完整跑柯力约 20-40 分钟（维度并行 + 多次 LLM 调用）
- **联网要求**：需 akshare（数据源）+ DeepSeek API（写作）+ tavily（如需 enrich）
- **若 Gate 失败**：查看失败项，区分"内容问题"（报告真有问题需人工修正）vs"门禁误报"（代码 bug 需报告）
- **日志**：`logs/` 下会生成 `柯力传感_*` 运行日志，可用于排查

---

## 五、验收后产物

| 产物 | 路径 |
|------|------|
| 柯力报告四件套 | `D:\2hao-analyst\output\柯力传感_cicc.*` |
| Gate 报告 | 步骤 4 输出 |
| 执行总结 | `D:\Marvis\output\柯力传感最终验收报告_20260802.md` |
