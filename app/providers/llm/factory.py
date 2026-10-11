"""LLM provider factory."""
from __future__ import annotations

from app.core.settings import get_settings
from app.providers.llm.providers import (
    AnthropicProvider, GeminiProvider, LLMProvider,
    MockLLMProvider, OllamaProvider, OpenAIProvider,
)


def get_llm_provider(override: str | None = None) -> LLMProvider:
    """Return the configured LLM provider."""
    settings = get_settings()
    provider_name = override or settings.llm.provider

    if provider_name == "mock":
        return MockLLMProvider()
    elif provider_name == "ollama" or provider_name == "local":
        lc = settings.llm.local
        return OllamaProvider(
            model=lc.model,
            base_url=lc.base_url,
            temperature=lc.temperature,
            max_tokens=lc.max_tokens,
            timeout=lc.timeout_seconds,
        )
    elif provider_name == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set in environment.")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.llm.openai_model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
        )
    elif provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set in environment.")
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.llm.anthropic_model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
        )
    elif provider_name == "gemini":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not set in environment.")
        return GeminiProvider(
            api_key=settings.google_api_key,
            model=settings.llm.gemini_model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
