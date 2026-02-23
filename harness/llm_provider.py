"""
LLM Provider 抽象層
統一的 LLM 呼叫介面，支援三大廠商 + 離線回退。

Provider 優先順序：Claude → GPT → Gemini → Offline Template
自動偵測哪些 API Key 可用，選擇最佳 Provider。
"""

import os
from typing import Optional, Dict, Any
from enum import Enum


class LLMProviderType(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    OFFLINE = "offline"


class LLMProvider:
    """
    三大 LLM 統一介面。
    自動偵測可用的 API Key，fallback 到離線模板。
    """

    def __init__(self, preferred: Optional[LLMProviderType] = None):
        self._clients: Dict[LLMProviderType, Any] = {}
        self.active_provider: Optional[LLMProviderType] = None
        self._init_providers(preferred)

    def _init_providers(self, preferred: Optional[LLMProviderType]):
        """依照優先順序初始化可用的 Provider"""
        # 優先使用指定的 Provider
        order = [
            LLMProviderType.ANTHROPIC,
            LLMProviderType.OPENAI,
            LLMProviderType.GOOGLE,
        ]
        if preferred and preferred != LLMProviderType.OFFLINE:
            order = [preferred] + [p for p in order if p != preferred]

        for provider_type in order:
            client = self._try_init(provider_type)
            if client is not None:
                self._clients[provider_type] = client
                if self.active_provider is None:
                    self.active_provider = provider_type

        # Fallback
        if self.active_provider is None:
            self.active_provider = LLMProviderType.OFFLINE

    def _try_init(self, provider_type: LLMProviderType) -> Optional[Any]:
        """嘗試初始化單一 Provider"""
        try:
            if provider_type == LLMProviderType.ANTHROPIC:
                key = os.getenv("ANTHROPIC_API_KEY", "")
                if not key:
                    return None
                import anthropic
                return anthropic.Anthropic(api_key=key)

            elif provider_type == LLMProviderType.OPENAI:
                key = os.getenv("OPENAI_API_KEY", "")
                if not key:
                    return None
                import openai
                return openai.OpenAI(api_key=key)

            elif provider_type == LLMProviderType.GOOGLE:
                key = os.getenv("GOOGLE_API_KEY", "")
                if not key:
                    return None
                import google.generativeai as genai
                genai.configure(api_key=key)
                return genai.GenerativeModel("gemini-2.0-flash")

        except ImportError:
            return None
        except Exception:
            return None

        return None

    @property
    def is_llm_available(self) -> bool:
        """是否有可用的 LLM（非 Offline）"""
        return self.active_provider != LLMProviderType.OFFLINE

    @property
    def provider_name(self) -> str:
        """目前使用的 Provider 名稱"""
        return self.active_provider.value if self.active_provider else "none"

    def chat(self, prompt: str, system_prompt: str = "",
             max_tokens: int = 2048) -> str:
        """
        發送聊天請求。
        自動使用最佳可用的 Provider。
        無 LLM 時回傳空字串（由呼叫端處理 fallback）。
        """
        if self.active_provider == LLMProviderType.OFFLINE:
            return ""

        try:
            if self.active_provider == LLMProviderType.ANTHROPIC:
                return self._chat_anthropic(prompt, system_prompt, max_tokens)
            elif self.active_provider == LLMProviderType.OPENAI:
                return self._chat_openai(prompt, system_prompt, max_tokens)
            elif self.active_provider == LLMProviderType.GOOGLE:
                return self._chat_google(prompt, system_prompt, max_tokens)
        except Exception as e:
            print(f"  [LLM] {self.active_provider.value} 呼叫失敗: {e}")
            # 嘗試切換到其他可用 Provider
            return self._fallback_chat(prompt, system_prompt, max_tokens)

        return ""

    def _chat_anthropic(self, prompt: str, system_prompt: str,
                        max_tokens: int) -> str:
        """Anthropic Claude API 呼叫"""
        client = self._clients[LLMProviderType.ANTHROPIC]
        kwargs = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        response = client.messages.create(**kwargs)
        return response.content[0].text

    def _chat_openai(self, prompt: str, system_prompt: str,
                     max_tokens: int) -> str:
        """OpenAI GPT API 呼叫"""
        client = self._clients[LLMProviderType.OPENAI]
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def _chat_google(self, prompt: str, system_prompt: str,
                     max_tokens: int) -> str:
        """Google Gemini API 呼叫"""
        client = self._clients[LLMProviderType.GOOGLE]
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = client.generate_content(full_prompt)
        return response.text

    def _fallback_chat(self, prompt: str, system_prompt: str,
                       max_tokens: int) -> str:
        """嘗試其他可用 Provider"""
        for provider_type, client in self._clients.items():
            if provider_type != self.active_provider:
                old = self.active_provider
                self.active_provider = provider_type
                try:
                    result = self.chat(prompt, system_prompt, max_tokens)
                    if result:
                        print(f"  [LLM] 已切換到 {provider_type.value}")
                        return result
                except Exception:
                    pass
                self.active_provider = old
        return ""

    def get_status(self) -> Dict[str, Any]:
        """取得 LLM Provider 狀態"""
        available = list(self._clients.keys())
        return {
            "active": self.provider_name,
            "available": [p.value for p in available],
            "is_llm": self.is_llm_available,
            "offline_mode": not self.is_llm_available,
        }
