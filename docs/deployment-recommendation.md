# 2hao-analyst 推理部署推荐

> 基于当前环境(Intel Core Ultra 7, 4GB RAM, 无GPU)

---

## 当前架构（可行但有限制）

```
2hao管线 → DeepSeek API(云端) → IronGate(本地) → StyleCompiler(本地) → export(本地)
```

**优势**: 零配置、LLM质量好(deepseek-chat)
**劣势**: shell 45s超时、API 401波动、网络延迟、无法使用constrained decoding

---

## 推荐路线

### Phase 1: 维持云端API + xgrammar schea验证(轻量改造)

```bash
pip install xgrammar
```

xgrammar是一个轻量的constrained decoding库,不依赖GPU。
用在API返回后的验证层: 定义输出schema,如果API返回不符合schema,自动重试。

```
调用DeepSeek → xgrammar验证输出是否符合schema → 不符合则自动修正/重试
```

不需要本地推理服务器,只需要在post-process层加schema验证。

### Phase 2: 本地Ollama(离线能力)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama run qwen2.5:1.5b
```

本地模型用于:
- L3降级时的紧急写作(当DeepSeek不可用、返回质量差时的后备)
- IronGate检查(已经本地,无延迟)
- 短文本分类(categorization、data extraction)

### Phase 3: 升级内存+GPU(完整本地部署)

当环境升级到16GB+内存+GPU时:
- vLLM + xgrammar: 完整constrained decoding,数学保证格式遵守
- Qwen2.5-14B-Instruct: 当前DeepSeek水平的替代
- 完整离线运行,零外部依赖

---

## 关键决策: constrained decoding的必要性

2hao的核心问题是"LLM看到了SoWhat要求但没执行"。
constrained decoding在解码层面**保证**输出符合schema。
xgrammar+DeepSeek的组合可以做post-hoc验证:
  不是decode时约束,而是生成后验证——但比纯prompt好。

Long-term,如果2hao的价值被验证,vLLM+GPU+14B是终极方案。
Short-term,维持当前架构 + xgrammar验证是最快路径。
