# LLM Provider 接口合约

> 所有 LLM 调用必须通过此接口。禁止直接调用第三方 SDK。

## 接口定义

```python
# core/deepseek_client.py — 多 Provider 注册与调用

def call_llm(messages: list[dict], model: str = "auto",
             temperature: float = 0.35, max_tokens: int = 4096) -> dict:
    """
    调用最优可用 LLM。
    
    Args:
        messages: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        model: "auto"=自动选择 / 指定模型名
        temperature: 采样温度 (0.0-1.0)
        max_tokens: 最大输出 token
    
    Returns:
        {"choices": [{"message": {"content": "..."}}], "model": "used-model", ...}
    
    Raises:
        RuntimeError: 所有 provider 都失败时
    """

def score_text(text: str, rubric: str, model: str = "auto") -> dict:
    """用 LLM 对文本评分"""

def generate_report_section(prompt: str, style: str = "cicc") -> str:
    """生成报告段落（自动注入风格）"""
```

## Provider 优先级

| 优先级 | Provider | 模型 | 用途 |
|--------|----------|------|------|
| 0 (最高) | DeepSeek Direct | deepseek-chat | 主写作 |
| 0 | DeepSeek Direct | deepseek-reasoner | 深度推理 |
| 1 | 阿里云 Qwen | qwen-plus / qwen-max | 中文写作（备用） |
| 2 | OpenRouter | deepseek/deepseek-chat | 全球 fallback |

## 禁止

1. 禁止在 section_writer / iron_gate 中直接调用 `requests.post("https://api.deepseek.com/...")`
2. 禁止硬编码 API endpoint URL
3. 禁止在非 LLM 模块中 import openai SDK
