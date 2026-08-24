# 2hao-analyst 推理部署方案

## 环境约束
- CPU: Intel Core Ultra 7 270K Plus
- RAM: 4GB (3.5GB 可用)
- GPU: 无
- OS: Ubuntu 22.04 (VM)
- 已配置 API Key: DeepSeek / Qwen / OpenRouter / SiliconFlow

## 方案对比

| 方案 | 类型 | 约束解码 | 内存 | 延迟 | 当前状态 |
|------|------|----------|------|------|----------|
| **A: 云端API+补全** | API | 否 | <100MB | ~35s/段 | ✅ 已运行 |
| **B: Ollama+1.5B** | 本地 | 否 | ~2GB | ~60s/段 | 🔧 可安装 |
| **C: xgrammar** | 混合 | 是(验证层) | <500MB | +1s/调用 | 🔧 可安装 |
| **D: vLLM+14B** | 本地 | 是(解码层) | 16GB+GPU | ~2s/段 | ❌ 需升级 |

## 当前推荐

### 短期: 方案A(已有) + 方案B(备选)

保留现有云端API架构,安装Ollama作为L3降级时的后备写作引擎。
4 provider circuit breaker已就绪。

### 中期: 方案C可选

xgrammar可以为API返回加schema验证层:
```
定义schema → 调DeepSeek → xgrammar验证 → 不符合自动重试
```
不依赖GPU,内存占用<500MB。

### 长期: 方案D

当环境升级到16GB+RAM+GPU时:
- vLLM + Qwen2.5-14B-Instruct
- xgrammar constrained decoding(数学保证格式遵守)
- 零API依赖,零超时
