"""Evidence retrieval data models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.models.context import EvidenceRecord

TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")


@dataclass(frozen=True)
class ManifestCandidate:
    path: str
    role: str
    language: str
    score: float
    tier: str = "standard"


@dataclass(frozen=True)
class RetrievalPolicy:
    agent_role: str = "EvidenceGroundedAgent"
    query: str = ""
    limit: int = 8
    token_budget: int = 2000
    manifest_limit: int = 24
    symbol_limit: int = 16
    snippet_limit: int | None = None
    compression_window_lines: int = 18
    max_snippet_chars: int = 900


@dataclass(frozen=True)
class CompressedEvidence:
    evidence_id: str
    file_path: str
    start_line: int
    end_line: int
    excerpt_start_line: int
    excerpt_end_line: int
    snippet: str
    truncated: bool
    estimated_tokens: int


@dataclass(frozen=True)
class RetrievalStats:
    agent_role: str
    query: str
    total_records: int
    manifest_candidates: int
    symbol_matches: int
    selected_evidence: int
    candidate_paths: int
    latency_ms: float
    estimated_tokens: int
    token_budget: int
    token_utilization: float
    precision_like: float
    recall_like: float
    large_repo_mode: bool = False
    level_counts: dict[str, int] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, str | int | float | bool | None]:
        return {
            "retrieval_agent_role": self.agent_role,
            "retrieval_total_records": self.total_records,
            "retrieval_manifest_candidates": self.manifest_candidates,
            "retrieval_symbol_matches": self.symbol_matches,
            "retrieval_selected_evidence": self.selected_evidence,
            "retrieval_candidate_paths": self.candidate_paths,
            "retrieval_latency_ms": round(self.latency_ms, 3),
            "retrieval_estimated_tokens": self.estimated_tokens,
            "retrieval_token_budget": self.token_budget,
            "retrieval_token_utilization": round(self.token_utilization, 4),
            "retrieval_precision_like": round(self.precision_like, 4),
            "retrieval_recall_like": round(self.recall_like, 4),
            "retrieval_large_repo_mode": self.large_repo_mode,
            "retrieval_level_1_manifest": self.level_counts.get("manifest", 0),
            "retrieval_level_2_symbol": self.level_counts.get("symbol", 0),
            "retrieval_level_3_snippet": self.level_counts.get("snippet", 0),
        }


@dataclass(frozen=True)
class RetrievalResult:
    records: list[EvidenceRecord]
    manifest_candidates: list[ManifestCandidate]
    symbol_paths: set[str]
    stats: RetrievalStats
