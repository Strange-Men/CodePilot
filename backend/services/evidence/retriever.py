"""Evidence retriever with BM25 scoring and compression."""

from __future__ import annotations

import math
import time
from collections import Counter
from dataclasses import replace

from backend.models.context import EvidenceRecord, ReviewContext

from .models import (
    TOKEN_PATTERN,
    CompressedEvidence,
    ManifestCandidate,
    RetrievalPolicy,
    RetrievalResult,
    RetrievalStats,
)


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
        # O(1) tier and summary lookups (precomputed once)
        self._tier_cache: dict[str, str] = {
            s.path: getattr(s, "analysis_tier", "standard") for s in context.file_summaries
        }
        self._summary_by_path: dict[str, object] = {s.path: s for s in context.file_summaries}

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 8,
        candidate_paths: set[str] | None = None,
    ) -> list[EvidenceRecord]:
        return self.retrieve_with_policy(
            RetrievalPolicy(query=query, limit=limit),
            candidate_paths=candidate_paths,
        ).records

    def retrieve_with_policy(
        self,
        policy: RetrievalPolicy,
        *,
        candidate_paths: set[str] | None = None,
    ) -> RetrievalResult:
        started_at = time.perf_counter()
        query_tokens = self._tokens(policy.query)
        manifest_candidates = self._manifest_retrieval(query_tokens, limit=policy.manifest_limit)
        manifest_paths = {candidate.path for candidate in manifest_candidates}
        symbol_paths = self._symbol_retrieval(query_tokens, limit=policy.symbol_limit)
        merged_candidate_paths = self._merge_candidate_paths(candidate_paths, manifest_paths, symbol_paths)
        scored = self._snippet_retrieval(query_tokens, merged_candidate_paths)
        selected, compressed = self._select_records(scored, policy)
        latency_ms = (time.perf_counter() - started_at) * 1000
        stats = self._build_stats(
            policy,
            query_tokens,
            manifest_candidates,
            symbol_paths,
            scored,
            selected,
            compressed,
            merged_candidate_paths,
            latency_ms,
        )
        return RetrievalResult(
            records=selected,
            manifest_candidates=manifest_candidates,
            symbol_paths=symbol_paths,
            stats=stats,
        )

    def _manifest_retrieval(self, query_tokens: list[str], *, limit: int) -> list[ManifestCandidate]:
        candidates: list[ManifestCandidate] = []
        for summary in self.context.file_summaries:
            search_text = " ".join(
                [
                    summary.path,
                    summary.file_role,
                    summary.importance_label,
                    summary.purpose,
                    " ".join(summary.classes),
                    " ".join(summary.functions),
                    " ".join(summary.imports),
                ]
            )
            overlap = len(set(query_tokens).intersection(self._tokens(search_text)))
            score = summary.importance_score + overlap * 12 + summary.fan_in * 2 + summary.fan_out
            if query_tokens and overlap == 0:
                score *= 0.25
            candidates.append(
                ManifestCandidate(
                    path=summary.path,
                    role=summary.file_role,
                    language=self._language_for_path(summary.path),
                    score=score,
                    tier=getattr(summary, "analysis_tier", "standard"),
                )
            )
        return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.path))[:limit]

    def _symbol_retrieval(self, query_tokens: list[str], *, limit: int) -> set[str]:
        if not query_tokens:
            return set()
        scored_paths: Counter[str] = Counter()
        query_set = set(query_tokens)
        for symbols in self.context.deep_context.symbol_index.values():
            for symbol in symbols:
                symbol_tokens = self._tokens(
                    " ".join(
                        [
                            symbol.name,
                            symbol.kind,
                            symbol.file_path,
                            " ".join(symbol.params),
                            symbol.return_type or "",
                            " ".join(symbol.decorators),
                            " ".join(symbol.calls),
                            " ".join(symbol.bases),
                        ]
                    )
                )
                overlap = len(query_set.intersection(symbol_tokens))
                if overlap:
                    scored_paths[symbol.file_path] += overlap
        for summary in self.context.file_summaries:
            route_text = " ".join(f"{route.method} {route.path} {route.handler}" for route in summary.routes)
            import_text = " ".join(summary.imports)
            summary_text = f"{route_text} {import_text} {' '.join(summary.call_refs)}"
            overlap = len(query_set.intersection(self._tokens(summary_text)))
            if overlap:
                scored_paths[summary.path] += overlap
        return {
            path
            for path, _score in sorted(scored_paths.items(), key=lambda item: (-item[1], item[0]))[:limit]
        }

    def _snippet_retrieval(
        self,
        query_tokens: list[str],
        candidate_paths: set[str] | None,
    ) -> list[tuple[float, str, EvidenceRecord]]:
        scored: list[tuple[float, str, EvidenceRecord]] = []
        for record, tokens in zip(self.records, self.document_tokens, strict=True):
            if candidate_paths is not None and record.file_path not in candidate_paths:
                continue
            if self._analysis_tier(record.file_path) == "low":
                continue
            score = self._bm25(query_tokens, tokens)
            score += self._dependency_score(record.file_path, query_tokens)
            score += self._symbol_score(record, query_tokens)
            scored.append((score, record.evidence_id, record))
        return sorted(scored, key=lambda item: (-item[0], item[1]))

    def _select_records(
        self,
        scored: list[tuple[float, str, EvidenceRecord]],
        policy: RetrievalPolicy,
    ) -> tuple[list[EvidenceRecord], list[CompressedEvidence]]:
        limit = policy.snippet_limit or policy.limit
        selected: list[EvidenceRecord] = []
        compressed: list[CompressedEvidence] = []
        seen: set[str] = set()
        seen_ranges: set[tuple[str, int, int]] = set()
        estimated_tokens = 0
        token_ceiling = max(policy.token_budget, 1)
        for score, _evidence_id, record in scored:
            if record.evidence_id in seen:
                continue
            range_key = (record.file_path, record.start_line, record.end_line)
            if range_key in seen_ranges:
                continue
            if score <= 0 and policy.query:
                continue
            comp = self.compress_for_prompt(record, policy.query, policy=policy)
            record_tokens = comp.estimated_tokens
            if selected and estimated_tokens + record_tokens > token_ceiling:
                continue
            selected.append(record)
            compressed.append(comp)
            seen.add(record.evidence_id)
            seen_ranges.add(range_key)
            estimated_tokens += record_tokens
            if len(selected) >= limit:
                break
        return selected, compressed

    @staticmethod
    def _merge_candidate_paths(
        explicit_paths: set[str] | None,
        manifest_paths: set[str],
        symbol_paths: set[str],
    ) -> set[str] | None:
        merged = set(manifest_paths) | set(symbol_paths)
        if explicit_paths is not None:
            merged = merged.intersection(explicit_paths)
        return merged or explicit_paths

    def _build_stats(
        self,
        policy: RetrievalPolicy,
        query_tokens: list[str],
        manifest_candidates: list[ManifestCandidate],
        symbol_paths: set[str],
        scored: list[tuple[float, str, EvidenceRecord]],
        selected: list[EvidenceRecord],
        compressed: list[CompressedEvidence],
        candidate_paths: set[str] | None,
        latency_ms: float,
    ) -> RetrievalStats:
        relevant_available = [record for score, _evidence_id, record in scored if score > 0 or not query_tokens]
        selected_relevant = {
            record.evidence_id
            for score, _evidence_id, record in scored
            if record in selected and (score > 0 or not query_tokens)
        }
        # Use pre-compressed results instead of recompressing
        estimated_tokens = sum(comp.estimated_tokens for comp in compressed)
        selected_count = len(selected)
        precision_like = len(selected_relevant) / selected_count if selected_count else 1.0
        recall_like = len(selected_relevant) / len(relevant_available) if relevant_available else 1.0
        token_budget = max(policy.token_budget, 1)
        return RetrievalStats(
            agent_role=policy.agent_role,
            query=policy.query,
            total_records=len(self.records),
            manifest_candidates=len(manifest_candidates),
            symbol_matches=len(symbol_paths),
            selected_evidence=selected_count,
            candidate_paths=len(candidate_paths or set()),
            latency_ms=latency_ms,
            estimated_tokens=estimated_tokens,
            token_budget=policy.token_budget,
            token_utilization=min(1.0, estimated_tokens / token_budget),
            precision_like=precision_like,
            recall_like=recall_like,
            large_repo_mode=self.context.large_repo_mode,
            level_counts={
                "manifest": len(manifest_candidates),
                "symbol": len(symbol_paths),
                "snippet": selected_count,
            },
        )

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
        summary = self._summary_by_path.get(file_path)
        if summary is None:
            return 0.0
        path_tokens = set(self._tokens(file_path))
        overlap = len(path_tokens.intersection(query_tokens))
        return overlap * 0.5 + min(2.0, summary.fan_in * 0.15 + summary.fan_out * 0.1)

    def _symbol_score(self, record: EvidenceRecord, query_tokens: list[str]) -> float:
        if not query_tokens:
            return 0.0
        symbol_tokens = set(self._tokens(" ".join(record.symbols)))
        return len(symbol_tokens.intersection(query_tokens)) * 1.25

    def compress_for_prompt(
        self,
        record: EvidenceRecord,
        query: str,
        *,
        policy: RetrievalPolicy | None = None,
    ) -> CompressedEvidence:
        policy = policy or RetrievalPolicy(query=query)
        if self.context.large_repo_mode and self._analysis_tier(record.file_path) == "medium":
            policy = replace(
                policy,
                compression_window_lines=max(4, policy.compression_window_lines // 2),
                max_snippet_chars=max(240, policy.max_snippet_chars // 2),
            )
        return self._compress_record_for_prompt(record, query, policy=policy)

    @classmethod
    def _compress_record_for_prompt(
        cls,
        record: EvidenceRecord,
        query: str,
        *,
        policy: RetrievalPolicy,
    ) -> CompressedEvidence:
        lines = record.snippet.splitlines()
        if not lines:
            return CompressedEvidence(
                evidence_id=record.evidence_id,
                file_path=record.file_path,
                start_line=record.start_line,
                end_line=record.end_line,
                excerpt_start_line=record.start_line,
                excerpt_end_line=record.end_line,
                snippet="",
                truncated=False,
                estimated_tokens=12,
            )
        query_tokens = set(cls._tokens(query))
        if not query_tokens:
            query_tokens = set(cls._tokens(f"{' '.join(record.symbols)} {record.file_path}"))
        center_index = cls._best_line_index(lines, query_tokens)
        window = max(1, policy.compression_window_lines)
        half_window = max(1, window // 2)
        start_index = max(0, center_index - half_window)
        end_index = min(len(lines), start_index + window)
        start_index = max(0, end_index - window)
        excerpt_lines = lines[start_index:end_index]
        excerpt = cls._number_excerpt_lines(excerpt_lines, record.start_line + start_index)
        truncated = start_index > 0 or end_index < len(lines)
        if len(excerpt) > policy.max_snippet_chars:
            excerpt = excerpt[: policy.max_snippet_chars].rstrip() + "\n..."
            truncated = True
        return CompressedEvidence(
            evidence_id=record.evidence_id,
            file_path=record.file_path,
            start_line=record.start_line,
            end_line=record.end_line,
            excerpt_start_line=record.start_line + start_index,
            excerpt_end_line=record.start_line + end_index - 1,
            snippet=excerpt,
            truncated=truncated,
            estimated_tokens=max(1, len(excerpt) // 4) + len(record.symbols) * 2 + 16,
        )

    def _analysis_tier(self, path: str) -> str:
        if not self.context.large_repo_mode:
            return "standard"
        return self._tier_cache.get(path, "low")

    @classmethod
    def _best_line_index(cls, lines: list[str], query_tokens: set[str]) -> int:
        if not query_tokens:
            return 0
        scored = [
            (len(query_tokens.intersection(cls._tokens(line))), index)
            for index, line in enumerate(lines)
        ]
        score, index = max(scored, key=lambda item: (item[0], -item[1]))
        return index if score > 0 else 0

    @staticmethod
    def _number_excerpt_lines(lines: list[str], start_line: int) -> str:
        return "\n".join(
            f"{line_number}: {line}"
            for line_number, line in enumerate(lines, start=start_line)
        )

    @staticmethod
    def _search_text(record: EvidenceRecord) -> str:
        return f"{record.file_path} {' '.join(record.symbols)} {record.snippet}"

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]

    @staticmethod
    def _language_for_path(path: str) -> str:
        suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        return {
            "py": "python",
            "js": "javascript",
            "jsx": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
        }.get(suffix, "source")
