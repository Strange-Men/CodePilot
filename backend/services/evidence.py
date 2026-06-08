from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from backend.models.context import EvidenceRecord, ReviewContext
from backend.parsers.base import ParsedSourceFile
from backend.services.sandbox import SandboxFile

TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")


def stable_evidence_id(file_path: str, start_line: int, end_line: int, snippet: str) -> str:
    normalized = "\n".join(line.rstrip() for line in snippet.strip().splitlines())
    normalized_path = file_path.replace("\\", "/")
    payload = f"{normalized_path}:{start_line}:{end_line}:{normalized}".encode()
    return f"ev_{hashlib.sha256(payload).hexdigest()[:20]}"


class EvidenceStore:
    def __init__(self, records: list[EvidenceRecord] | None = None) -> None:
        self._records: dict[str, EvidenceRecord] = {}
        for record in records or []:
            self.add(record)

    def add(self, record: EvidenceRecord) -> None:
        existing = self._records.get(record.evidence_id)
        if existing is not None and existing != record:
            raise ValueError(f"Evidence ID collision: {record.evidence_id}")
        self._records[record.evidence_id] = record

    def resolve(self, evidence_id: str) -> EvidenceRecord:
        try:
            return self._records[evidence_id]
        except KeyError as exc:
            raise KeyError(f"Unknown evidence_id: {evidence_id}") from exc

    def all(self) -> list[EvidenceRecord]:
        return list(self._records.values())

    @classmethod
    def from_context(cls, context: ReviewContext) -> EvidenceStore:
        return cls(context.evidence)


def build_file_evidence(
    sandbox_file: SandboxFile,
    parsed: ParsedSourceFile,
    *,
    chunk_lines: int = 40,
) -> list[EvidenceRecord]:
    lines = sandbox_file.content.splitlines()
    ranges: list[tuple[int, int, str, list[str]]] = []
    for symbol in [*parsed.function_details, *parsed.class_details]:
        if symbol.start_line <= 0:
            continue
        ranges.append(
            (
                symbol.start_line,
                min(symbol.end_line or symbol.start_line, len(lines)),
                "symbol",
                [symbol.name],
            )
        )
    if not ranges:
        ranges.extend(
            (start, min(start + chunk_lines - 1, len(lines)), "source", [])
            for start in range(1, len(lines) + 1, chunk_lines)
        )

    records: list[EvidenceRecord] = []
    for start, end, kind, symbols in ranges:
        snippet = "\n".join(lines[start - 1 : end]).strip()
        if not snippet:
            continue
        records.append(
            EvidenceRecord(
                evidence_id=stable_evidence_id(sandbox_file.path, start, end, snippet),
                file_path=sandbox_file.path,
                start_line=start,
                end_line=end,
                snippet=snippet,
                kind=kind,
                symbols=symbols,
            )
        )
    return records


class EvidenceRetriever:
    def __init__(self, context: ReviewContext) -> None:
        self.context = context
        self.records = context.evidence
        self.document_tokens = [self._tokens(self._search_text(record)) for record in self.records]
        self.document_frequency = Counter(
            token
            for tokens in self.document_tokens
            for token in set(tokens)
        )
        self.average_length = (
            sum(len(tokens) for tokens in self.document_tokens) / len(self.document_tokens)
            if self.document_tokens
            else 1.0
        )

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 8,
        candidate_paths: set[str] | None = None,
    ) -> list[EvidenceRecord]:
        query_tokens = self._tokens(query)
        scored: list[tuple[float, str, EvidenceRecord]] = []
        for record, tokens in zip(self.records, self.document_tokens, strict=True):
            if candidate_paths is not None and record.file_path not in candidate_paths:
                continue
            score = self._bm25(query_tokens, tokens)
            score += self._dependency_score(record.file_path, query_tokens)
            scored.append((score, record.evidence_id, record))
        return [
            record
            for score, _evidence_id, record in sorted(scored, key=lambda item: (-item[0], item[1]))[:limit]
            if score > 0 or not query_tokens
        ]

    def _bm25(self, query_tokens: list[str], document_tokens: list[str]) -> float:
        frequencies = Counter(document_tokens)
        score = 0.0
        document_count = max(1, len(self.records))
        length = max(1, len(document_tokens))
        for token in set(query_tokens):
            frequency = frequencies[token]
            if not frequency:
                continue
            document_frequency = self.document_frequency[token]
            inverse_document_frequency = math.log(
                1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = frequency + 1.5 * (0.25 + 0.75 * length / self.average_length)
            score += inverse_document_frequency * (frequency * 2.5 / denominator)
        return score

    def _dependency_score(self, file_path: str, query_tokens: list[str]) -> float:
        summary = next(
            (summary for summary in self.context.file_summaries if summary.path == file_path),
            None,
        )
        if summary is None:
            return 0.0
        path_tokens = set(self._tokens(file_path))
        overlap = len(path_tokens.intersection(query_tokens))
        return overlap * 0.5 + min(2.0, summary.fan_in * 0.15 + summary.fan_out * 0.1)

    @staticmethod
    def _search_text(record: EvidenceRecord) -> str:
        return f"{record.file_path} {' '.join(record.symbols)} {record.snippet}"

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]
