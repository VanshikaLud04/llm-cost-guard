class LLMCostGuardException(Exception): pass
class BudgetExceededException(LLMCostGuardException): pass
class DailyBudgetExceededException(LLMCostGuardException): pass
class UnknownModelException(LLMCostGuardException): pass
class AllModelsExhaustedException(LLMCostGuardException): pass