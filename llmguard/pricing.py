MODEL_PROVIDER: dict[str, str] = {
    "gpt-4o": "openai", "gpt-4o-mini": "openai", "gpt-3.5-turbo": "openai",
    "claude-3-5-sonnet-20241022": "anthropic",
    "claude-3-opus-20240229": "anthropic",
    "claude-3-haiku-20240307": "anthropic",
    "claude-haiku-4-5": "anthropic",          
    "llama3-70b-8192": "groq", "llama3-8b-8192": "groq", "mixtral-8x7b-32768": "groq",
    "llama-3.1-8b-instant": "groq",  
    "mock-instant": "mock",     
    "mock-large": "mock",         
}

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.000005, "output": 0.000015},
    "gpt-4o-mini": {"input": 0.00000015, "output": 0.00000060},
    "gpt-3.5-turbo": {"input": 0.0000005, "output": 0.0000015},
    "claude-3-5-sonnet-20241022": {"input": 0.000003, "output": 0.000015},
    "claude-3-opus-20240229": {"input": 0.000015, "output": 0.000075},
    "claude-3-haiku-20240307": {"input": 0.00000025, "output": 0.00000125},
    "claude-haiku-4-5": {"input": 0.00000025, "output": 0.00000125}, 
    "llama3-70b-8192": {"input": 0.00000059, "output": 0.00000079},
    "llama3-8b-8192": {"input": 0.00000005, "output": 0.00000008},
    "mixtral-8x7b-32768": {"input": 0.00000024, "output": 0.00000024},
    "llama-3.1-8b-instant": {"input": 0.00000005, "output": 0.00000008}, 
    "mock-instant": {"input": 0.000001, "output": 0.000002},  
    "mock-large":   {"input": 0.000005, "output": 0.000010}, 
}

FALLBACK_CHAIN: list[str] = [
    "gpt-4o",
    "claude-3-5-sonnet-20241022",
    "gpt-4o-mini",
    "claude-haiku-4-5",          
    "llama3-70b-8192",
    "llama-3.1-8b-instant",    
    "mock-instant",   
]
