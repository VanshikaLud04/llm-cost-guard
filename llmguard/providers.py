import os, logging
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

@dataclass
class NormalizedResponse:
    content: str; input_tokens: int; output_tokens: int; model: str; raw: object

class LLMProvider(ABC):
    @abstractmethod
    def call(self, model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
        pass

    def stream(self, model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024):
        raise NotImplementedError("Streaming not supported by this provider adapter yet.")

class OpenAIAdapter(LLMProvider):
    def call(self, model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
        from openai import OpenAI
        from .config import settings
        resp = OpenAI(api_key=settings.OPENAI_API_KEY).chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return NormalizedResponse(resp.choices[0].message.content, resp.usage.prompt_tokens, resp.usage.completion_tokens, model, resp)

    async def stream(self, model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024):
        from openai import AsyncOpenAI
        from .config import settings
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        stream_resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        
        input_tokens = sum(len(m["content"]) // 4 for m in messages)
        output_tokens = 0
        
        async for chunk in stream_resp:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                output_tokens += 1
                yield text, input_tokens, output_tokens

class ClaudeAdapter(LLMProvider):
    def call(self, model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
        import anthropic
        from .config import settings
        system = next((m["content"] for m in messages if m["role"] == "system"), None)
        filtered = [m for m in messages if m["role"] != "system"]
        kwargs = dict(model=model, max_tokens=max_tokens, messages=filtered, temperature=temperature)
        if system:
            kwargs["system"] = system
        resp = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY).messages.create(**kwargs)
        return NormalizedResponse(resp.content[0].text, resp.usage.input_tokens, resp.usage.output_tokens, model, resp)

class GroqAdapter(LLMProvider):
    def call(self, model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
        from groq import Groq
        from .config import settings
        resp = Groq(api_key=settings.GROQ_API_KEY).chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return NormalizedResponse(resp.choices[0].message.content, resp.usage.prompt_tokens, resp.usage.completion_tokens, model, resp)

class MockAdapter(LLMProvider):
    def call(self, model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
        from .mock_provider import call_mock
        return call_mock(model, messages, temperature, max_tokens)

def get_provider_adapter(provider_name: str) -> LLMProvider:
    adapters = {
        "openai": OpenAIAdapter(),
        "anthropic": ClaudeAdapter(),
        "groq": GroqAdapter(),
        "mock": MockAdapter(),
    }
    return adapters.get(provider_name)

def route_call(model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
    from .pricing import MODEL_PROVIDER
    provider_name = MODEL_PROVIDER.get(model)
    adapter = get_provider_adapter(provider_name)
    if not adapter:
        raise ValueError(f"No adapter found for provider: {provider_name}")
    return adapter.call(model, messages, temperature, max_tokens)

def route_stream(model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024):
    from .pricing import MODEL_PROVIDER
    provider_name = MODEL_PROVIDER.get(model)
    adapter = get_provider_adapter(provider_name)
    if not adapter:
        raise ValueError(f"No adapter found for provider: {provider_name}")
    return adapter.stream(model, messages, temperature, max_tokens)