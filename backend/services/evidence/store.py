"""Evidence store and file evidence builder."""

from __future__ import annotations

import hashlib

from backend.models.context import EvidenceRecord, ReviewContext
from backend.parsers.base import ParsedSourceFile
from backend.services.sandbox import SandboxFile


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
