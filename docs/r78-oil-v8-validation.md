# R78 油位v8诊断验证与修复

> 独立核验 Marvis 油位v8 诊断报告 + 修复真实问题
> 日期：2026-08-05

## 核验结论

Marvis 诊断的核心声明**全部属实**（独立代码核验 + 实跑验证）：

| 诊断 | 核验方式 | 结果 |
|------|----------|------|
| 图表全堆附录 | 实跑 IronGate `_check_layout_quality` | ✅ 11 张图全在附录，正文 0 内联 |
| layout_quality severity=warning 放行 | 代码读 `severity="warning"` | ✅ 属实 |
| chart_assembler 兜底静默堆附录 | 代码读 `logger.warning` 非 error | ✅ 属实 |
| v8 绕过 export_report 出口 | v8 md 无管线指纹 | ✅ 属实 |
| VisualGate 未跑 | 实跑 VisualGate score=0（字体 error） | ✅ 属实 |
| AI 标注残留 | md 全文找"内容由AI生成" | ✅ pos 19308 残留 |
| Bold Call Q2 未来时过期 | 读 29/339/358 行 | ✅ 属实 |

## 修复

### 管线级（根治）
1. **`_check_layout_quality` 图表未随文 → error 级**：检测到"附录前 0 内联图"直接返回 severity=error，禁止全量堆附录出厂
2. 新增回归测试验证 v8 被正确拦截

### 产物级（v8 md 修复）
3. **清除 AI 标注残留**：`*（内容由AI生成，仅供参考）*` 删除
4. **Bold Call 时效**：Q2-Q3 未来时 → Q2 验证性语言（"已进入跳升通道，H2 验证触发变量"）

## 未修复（需管线重跑）
- unlisted_threat_map 重绘（需数据源注入必补 7 家）
- v8 DOCX/PDF 重导出（需走标准 exporter + export_report）

## 回归
70 pytest 全绿

## 教训
- 图表堆叠是"LLM 未嵌图 → 兜底静默堆附录 → warning 放行"三道失效链，必须 error 级拦截
- 手动导出绕过 export_report 是 docx 层所有检查失效的根因——产物必须走唯一出口
