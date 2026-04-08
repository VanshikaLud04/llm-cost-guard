import os, logging
from dataclasses import dataclass
logger = logging.getLogger(__name__)

@dataclass
class NormalizedResponse:
    content: str; input_tokens: int; output_tokens: int; model: str; raw: object

def call_openai(model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
    from openai import OpenAI
    resp = OpenAI(api_key=os.getenv("OPENAI_API_KEY")).chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )

    return NormalizedResponse(resp.choices[0].message.content, resp.usage.prompt_tokens, resp.usage.completion_tokens, model, resp)

def call_anthropic(model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
    import anthropic
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    filtered = [m for m in messages if m["role"] != "system"]
    kwargs = dict(model=model, max_tokens=max_tokens, messages=filtered, temperature=temperature)
    if system:
        kwargs["system"] = system
    resp = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).messages.create(**kwargs)
    return NormalizedResponse(resp.content[0].text, resp.usage.input_tokens, resp.usage.output_tokens, model, resp)

def call_groq(model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
    from groq import Groq
    resp = Groq(api_key=os.getenv("GROQ_API_KEY")).chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return NormalizedResponse(resp.choices[0].message.content, resp.usage.prompt_tokens, resp.usage.completion_tokens, model, resp)

def route_call(model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
    from .pricing import MODEL_PROVIDER
    from .mock_provider import call_mock      
    provider = MODEL_PROVIDER.get(model)
    _MAP = {
        "openai": call_openai,
        "anthropic": call_anthropic,
        "groq": call_groq,
        "mock": call_mock,
    }
    return _MAP[provider](model, messages, temperature, max_tokens)