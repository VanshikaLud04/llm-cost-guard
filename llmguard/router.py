from abc import ABC, abstractmethod
from typing import List

class AbstractRouter(ABC):
    @abstractmethod
    def select_model(self, prompt: str, allowed_models: List[str]) -> str:
        pass

class RuleRouter(AbstractRouter):
    def select_model(self, prompt: str, allowed_models: List[str]) -> str:
        if not allowed_models:
            return "gpt-4o-mini" # Fallback if empty policy
            
        prompt_lower = prompt.lower()
        # Heuristic 1: Code generation tasks
        if "def " in prompt_lower or "class " in prompt_lower or "import " in prompt_lower:
            for m in ["claude-3-5-sonnet-20240620", "gpt-4o"]:
                if m in allowed_models:
                    return m
                    
        # Heuristic 2: Short fast questions
        if len(prompt) < 100:
            for m in ["gpt-4o-mini", "llama3"]:
                if m in allowed_models:
                    return m
                    
        # Default
        return allowed_models[0]
