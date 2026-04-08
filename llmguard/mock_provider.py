import time
from .providers import NormalizedResponse

MOCK_RESPONSES = [
    "Mock response: The answer is 42.",
    "Mock response: That's an interesting question!",
    "Mock response: I'm a mock provider — no API key needed.",
]

_call_count = 0

def call_mock(model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
    global _call_count
    response = MOCK_RESPONSES[_call_count % len(MOCK_RESPONSES)]
    _call_count += 1
    time.sleep(0.1)  # simulate latency
    return NormalizedResponse(
        content=response,
        input_tokens=50,
        output_tokens=15,
        model=model,
        raw=None
    )