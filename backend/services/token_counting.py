from __future__ import annotations

import tiktoken


class PromptTokenCounter:
    def __init__(self, model: str) -> None:
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def fit_complete_lines(self, text: str, budget: int) -> str:
        if budget <= 0:
            return ""

        selected_lines: list[str] = []
        for line in text.splitlines():
            candidate = "\n".join([*selected_lines, line])
            if self.count(candidate) > budget:
                break
            selected_lines.append(line)
        if selected_lines:
            return "\n".join(selected_lines)

        tokens = self.encoding.encode(text)
        return self.encoding.decode(tokens[:budget]).rstrip()
