"""
2hao-analyst v1.2 - LLM Provider Abstraction Layer

Design: Provider switching layer supporting DeepSeek / OpenAI / Ollama
Default: DeepSeek (via DEEPSEEK_API_KEY env var)
Fallback: auto-failover to next available provider when primary fails

Usage:
    from core.llm_provider import LLMProvider
    provider = LLMProvider()
    response = provider.chat(messages)
"""

import logging
import os
import time

import requests

logger = logging.getLogger("2hao.llm_provider")


class LLMProvider:
    """LLM Provider abstraction - supports multi-provider with auto-fallback"""

    PROVIDERS = {
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "models": {"chat": "deepseek-chat", "reasoner": "deepseek-reasoner"},
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "OPENAI_API_KEY",
            "models": {"chat": "gpt-4o", "reasoner": "o1-mini"},
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "api_key_env": None,
            "models": {"chat": "llama3", "reasoner": "llama3"},
        },
    }

    def __init__(self, preferred_provider: str = "deepseek"):
        self.preferred = preferred_provider
        self._current_provider = preferred_provider
        self._available_providers = self._discover_providers()

    def _discover_providers(self) -> list:
        available = []
        order = [self.preferred] + [p for p in self.PROVIDERS if p != self.preferred]
        for name in order:
            cfg = self.PROVIDERS[name]
            if cfg["api_key_env"]:
                key = os.environ.get(cfg["api_key_env"], "")
                if key:
                    available.append(name)
            else:
                available.append(name)
        if not available:
            available.append("deepseek")
        return available

    def chat(self, messages, model=None, temperature=0.3, max_tokens=8192, stream=False):
        provider_name = self._current_provider or self.preferred
        last_error = None

        if provider_name in self._available_providers:
            try:
                return self._call_provider(provider_name, messages, model, temperature, max_tokens, stream)
            except Exception as e:
                last_error = e

        for name in self._available_providers:
            if name == provider_name:
                continue
            try:
                result = self._call_provider(name, messages, model, temperature, max_tokens, stream)
                self._current_provider = name
                return result
            except Exception as e:
                last_error = e

        raise last_error or RuntimeError("No LLM provider available")

    def _call_provider(self, provider_name, messages, model=None, temperature=0.3, max_tokens=8192, stream=False):
        cfg = self.PROVIDERS[provider_name]
        base_url = cfg["base_url"]
        api_key = os.environ.get(cfg["api_key_env"], "") if cfg["api_key_env"] else ""
        if model is None:
            model = cfg["models"]["chat"]

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = "Bearer " + api_key

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        for attempt in range(3):
            try:
                resp = requests.post(base_url + "/chat/completions", headers=headers, json=payload, timeout=180)
                resp.raise_for_status()
                data = resp.json()
                return {
                    "choices": [{"message": {"content": data["choices"][0]["message"]["content"]}}],
                    "model": data.get("model", model),
                    "usage": data.get("usage", {}),
                }
            except Exception:
                if attempt < 2:
                    time.sleep(2**attempt)
                else:
                    raise

    def reason(self, question, context=""):
        messages = [
            {"role": "system", "content": "You are a top analyst skilled in deep reasoning."},
            {"role": "user", "content": "Context: " + context + "\n\nQuestion: " + question},
        ]
        try:
            result = self.chat(
                messages, model=self.PROVIDERS[self._current_provider]["models"]["reasoner"], temperature=0.2
            )
            return result["choices"][0]["message"]["content"]
        except Exception:
            return ""
