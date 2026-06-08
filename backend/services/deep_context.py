from __future__ import annotations

from collections import defaultdict

from backend.models.context import DeepContextSummary, SymbolContext
from backend.parsers.base import ParsedSourceFile


class DeepContextEngine:
    def build(self, parsed_files: list[ParsedSourceFile]) -> DeepContextSummary:
        symbol_index: dict[str, list[SymbolContext]] = defaultdict(list)
        file_contexts: dict[str, list[str]] = {}
        call_graph: dict[str, list[str]] = {}
        class_hierarchy: dict[str, list[str]] = {}

        for parsed in parsed_files:
            file_symbols: list[str] = []
            for function in parsed.function_details:
                symbol = SymbolContext(
                    name=function.name,
                    kind="function",
                    file_path=parsed.path,
                    start_line=function.start_line,
                    end_line=function.end_line,
                    params=function.params,
                    return_type=function.return_type,
                    decorators=function.decorators,
                    docstring=function.docstring,
                    calls=function.calls,
                )
                symbol_index[function.name].append(symbol)
                file_symbols.append(function.name)
                call_graph[f"{parsed.path}:{function.name}"] = list(function.calls)
            for class_detail in parsed.class_details:
                symbol = SymbolContext(
                    name=class_detail.name,
                    kind="class",
                    file_path=parsed.path,
                    start_line=class_detail.start_line,
                    end_line=class_detail.end_line,
                    decorators=class_detail.decorators,
                    docstring=class_detail.docstring,
                    bases=class_detail.bases,
                )
                symbol_index[class_detail.name].append(symbol)
                file_symbols.append(class_detail.name)
                class_hierarchy[f"{parsed.path}:{class_detail.name}"] = list(class_detail.bases)
            file_contexts[parsed.path] = file_symbols

        return DeepContextSummary(
            symbol_index=dict(sorted(symbol_index.items())),
            file_contexts=dict(sorted(file_contexts.items())),
            call_graph=dict(sorted(call_graph.items())),
            class_hierarchy=dict(sorted(class_hierarchy.items())),
        )
