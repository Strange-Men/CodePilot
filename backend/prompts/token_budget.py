from __future__ import annotations

from backend.services.token_counting import PromptTokenCounter


class TokenBudgeter:
    def __init__(self, budget: int, model: str = "gpt-4o-mini") -> None:
        self.budget = budget
        self.counter = PromptTokenCounter(model)

    def count(self, prompt: str) -> int:
        return self.counter.count(prompt)

    def fit(self, prompt: str) -> str:
        return self.counter.fit_complete_lines(prompt, self.budget)
