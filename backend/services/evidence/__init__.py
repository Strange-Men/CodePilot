"""Evidence retrieval package.

All public symbols are re-exported here for backward compatibility.
Existing imports like ``from backend.services.evidence import EvidenceRetriever``
continue to work unchanged.
"""

from .models import (
    TOKEN_PATTERN,
    CompressedEvidence,
    ManifestCandidate,
    RetrievalPolicy,
    RetrievalResult,
    RetrievalStats,
)
from .retriever import EvidenceRetriever
from .store import EvidenceStore, build_file_evidence, stable_evidence_id

__all__ = [
    "CompressedEvidence",
    "EvidenceRetriever",
    "EvidenceStore",
    "ManifestCandidate",
    "RetrievalPolicy",
    "RetrievalResult",
    "RetrievalStats",
    "TOKEN_PATTERN",
    "build_file_evidence",
    "stable_evidence_id",
]
