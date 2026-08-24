# 推理部署方案总结

## 环境
- CPU: Intel Ultra 7 270K Plus | RAM: 4GB(3.5GB可用) | GPU: 无

## 4方案

| 方案 | 类型 | 约束解码 | 内存 | 延迟 | 状态 |
|------|------|----------|------|------|------|
| A | 云端API + StyleCompiler补全 | 否 | <100MB | 35s/段 | ✅ 已运行 |
| B | Ollama + Qwen2.5:1.5b | 否 | ~2GB | 60s/段 | 🔧 可装 |
| C | xgrammar + 云端API | 是(验证层) | <500MB | +1s | 🔧 可装 |
| D | vLLM + Qwen2.5-14B + GPU | 是(解码层) | 16GB+ | 2s/段 | ❌ 需升级 |

## 建议
方案A已完全就绪(4个provider + 22条StyleCompiler + 35项IronGate)。  
方案B/C可根据需要选装。  
方案D需要环境升级。  
