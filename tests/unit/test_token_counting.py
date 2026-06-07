from __future__ import annotations

import tiktoken

from backend.services.token_counting import PromptTokenCounter


def test_token_count_matches_model_encoding() -> None:
    text = "Review Python, JavaScript, and TypeScript modules."
    counter = PromptTokenCounter("gpt-4o-mini")
    expected = len(tiktoken.encoding_for_model("gpt-4o-mini").encode(text))

    assert counter.count(text) == expected


def test_token_count_handles_unicode_and_punctuation() -> None:
    text = "入口: 核心模块 -> service.ts; risk?"
    counter = PromptTokenCounter("gpt-4o-mini")

    assert counter.count(text) == len(counter.encoding.encode(text))
    assert counter.count(text) > 0


def test_fit_complete_lines_preserves_formatting_within_exact_budget() -> None:
    counter = PromptTokenCounter("gpt-4o-mini")
    text = "First heading\n- important relationship\n- lower priority detail"
    budget = counter.count("First heading\n- important relationship")

    fitted = counter.fit_complete_lines(text, budget)

    assert fitted == "First heading\n- important relationship"
    assert counter.count(fitted) <= budget


def test_fit_complete_lines_truncates_first_oversized_line_by_tokens() -> None:
    counter = PromptTokenCounter("gpt-4o-mini")

    fitted = counter.fit_complete_lines("one two three four five", 2)

    assert fitted
    assert counter.count(fitted) <= 2


def test_unknown_model_uses_stable_fallback_encoding() -> None:
    counter = PromptTokenCounter("future-unknown-model")

    assert counter.encoding.name == "cl100k_base"
    assert counter.count("repository insight") > 0
