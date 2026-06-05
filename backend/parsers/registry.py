from __future__ import annotations

from collections.abc import Callable

from backend.parsers.base import SourceParser
from backend.parsers.javascript_parser import JavaScriptParser, TypeScriptParser
from backend.parsers.python_parser import PythonParser

ParserFactory = Callable[[], SourceParser]


class ParserRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ParserFactory] = {}

    def register(self, language: str, factory: ParserFactory) -> None:
        normalized = self._normalize_language(language)
        self._factories[normalized] = factory

    def create(self, language: str) -> SourceParser:
        normalized = self._normalize_language(language)
        try:
            return self._factories[normalized]()
        except KeyError as exc:
            raise KeyError(f"No parser registered for language: {language}") from exc

    def languages(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    @staticmethod
    def _normalize_language(language: str) -> str:
        return language.strip().lower()


def build_default_parser_registry() -> ParserRegistry:
    registry = ParserRegistry()
    registry.register(PythonParser.language, PythonParser)
    registry.register(JavaScriptParser.language, JavaScriptParser)
    registry.register(TypeScriptParser.language, TypeScriptParser)
    return registry


default_parser_registry = build_default_parser_registry()
