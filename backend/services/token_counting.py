from __future__ import annotations

import re

try:
    import tiktoken
except ModuleNotFoundError:
    tiktoken = None


class FallbackEncoding:
    name = "codepilot_fallback"

    def encode(self, text: str) -> list[str]:
        return re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)

    def decode(self, tokens: list[str]) -> str:
        return " ".join(tokens)


class PromptTokenCounter:
    def __init__(self, model: str) -> None:
        if tiktoken is None:
            self.encoding = FallbackEncoding()
            return
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
