# 2hao + Ollama 本地模型配置

## 你的模型
- 模型: Qwen3.6-27B (Q3KM GGUF量化)
- 路径: D:\Claude\qwen3.6-27b-q3km.gguf
- Modelfile: D:\Claude\Modelfile

## 步骤

### 1. 安装Ollama（如未安装）
```bash
# Windows: 从 https://ollama.com 下载安装
```

### 2. 导入模型
```bash
ollama create qwen3.6-27b -f D:\Claude\Modelfile
```

### 3. 启动服务
```bash
ollama serve
```

### 4. 验证
```bash
# 检查Ollama是否运行
curl http://localhost:11434/api/tags

# 应返回包含 qwen3.6-27b 的JSON
```

### 5. 2hao自动检测
`core/deepseek_client.py` 已添加Ollama自动注册逻辑。
启动2hao管线时,如果Ollama在运行,会自动注册为provider。

## 注意事项
- 27B模型需要16GB+内存
- Ollama API兼容OpenAI格式,无需api_key
- 如果2hao在Docker中运行,需设置 OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
