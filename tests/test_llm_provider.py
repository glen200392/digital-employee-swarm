"""LLM Provider 測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.llm_provider import LLMProvider, LLMProviderType


class TestLLMProvider:
    """LLMProvider 測試（離線模式）"""

    def test_defaults_to_offline(self):
        """無 API Key 時應 fallback 到 offline"""
        llm = LLMProvider()
        assert llm.active_provider == LLMProviderType.OFFLINE

    def test_is_llm_available_false_offline(self):
        llm = LLMProvider()
        assert llm.is_llm_available is False

    def test_provider_name_offline(self):
        llm = LLMProvider()
        assert llm.provider_name == "offline"

    def test_chat_returns_empty_offline(self):
        """離線模式 chat() 回傳空字串"""
        llm = LLMProvider()
        result = llm.chat("test prompt", system_prompt="test")
        assert result == ""

    def test_get_status(self):
        llm = LLMProvider()
        status = llm.get_status()
        assert status["active"] == "offline"
        assert status["is_llm"] is False
        assert status["offline_mode"] is True
        assert isinstance(status["available"], list)

    def test_preferred_offline(self):
        llm = LLMProvider(preferred=LLMProviderType.OFFLINE)
        assert llm.active_provider == LLMProviderType.OFFLINE
