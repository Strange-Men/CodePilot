from __future__ import annotations

from backend.agents.orchestrator import AgentOrchestrator
from backend.agents.specialized_agents import CodeSmellAgent
from backend.llm.client import MockLLMClient
from backend.models.context import EvidenceRecord, SymbolContext
from backend.services.evidence import EvidenceRetriever, RetrievalPolicy, stable_evidence_id


def _retrieval_context(sample_context):
    context = sample_context.to_review_context()
    context.file_summaries[0].imports = ["services.review"]
    context.file_summaries[0].symbols = [
        SymbolContext(
            name="create_app",
            kind="function",
            file_path="app.py",
            start_line=1,
            end_line=3,
            calls=["review"],
        )
    ]
    context.deep_context.symbol_index = {
        "create_app": context.file_summaries[0].symbols,
        "review": [
            SymbolContext(
                name="review",
                kind="function",
                file_path="services/review.py",
                start_line=1,
                end_line=4,
            )
        ],
    }
    context.evidence = [
        EvidenceRecord(
            evidence_id=stable_evidence_id("app.py", 1, 3, "def create_app():\n    return review()"),
            file_path="app.py",
            start_line=1,
            end_line=3,
            snippet="def create_app():\n    return review()",
            kind="symbol",
            symbols=["create_app"],
        ),
        EvidenceRecord(
            evidence_id=stable_evidence_id(
                "services/review.py",
                1,
                4,
                "def review(items):\n    return [item for item in items]",
            ),
            file_path="services/review.py",
            start_line=1,
            end_line=4,
            snippet="def review(items):\n    return [item for item in items]",
            kind="symbol",
            symbols=["review"],
        ),
    ]
    return context


def test_tiered_retrieval_returns_manifest_symbol_and_snippet_levels(sample_context) -> None:
    context = _retrieval_context(sample_context)

    result = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(
            agent_role="ArchitectureAgent",
            query="review service architecture",
            limit=2,
            token_budget=500,
        )
    )

    assert result.manifest_candidates
    assert "services/review.py" in {candidate.path for candidate in result.manifest_candidates}
    assert "services/review.py" in result.symbol_paths
    assert result.records[0].file_path == "services/review.py"
    assert result.stats.level_counts == {
        "manifest": len(result.manifest_candidates),
        "symbol": len(result.symbol_paths),
        "snippet": len(result.records),
    }
    assert result.stats.semantic_status == "future_hook"


def test_existing_retrieve_interface_remains_compatible(sample_context) -> None:
    context = _retrieval_context(sample_context)

    records = EvidenceRetriever(context).retrieve("review service", limit=1)

    assert len(records) == 1
    assert isinstance(records[0], EvidenceRecord)


def test_agent_retrieval_policy_is_persistable_without_snippets(sample_context) -> None:
    context = _retrieval_context(sample_context)
    result = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[CodeSmellAgent],
    ).review(context)

    state = result.agent_states[0]
    assert state.metadata["retrieval_agent_role"] == "CodeSmellAgent"
    assert state.metadata["retrieval_level_1_manifest"] > 0
    assert state.metadata["retrieval_level_3_snippet"] > 0
    assert "def create_app" not in state.model_dump_json()
    assert "return [item for item in items]" not in state.model_dump_json()


def test_context_compression_keeps_evidence_lineage_and_relevant_lines(sample_context) -> None:
    context = _retrieval_context(sample_context)
    long_snippet = "\n".join(
        [
            "def oversized():",
            *[f"    value_{index} = {index}" for index in range(1, 30)],
            "    return review(value_29)",
        ]
    )
    record = EvidenceRecord(
        evidence_id=stable_evidence_id("services/large.py", 10, 40, long_snippet),
        file_path="services/large.py",
        start_line=10,
        end_line=40,
        snippet=long_snippet,
        kind="symbol",
        symbols=["oversized"],
    )

    compressed = EvidenceRetriever(context).compress_for_prompt(
        record,
        "review",
        policy=RetrievalPolicy(query="review", compression_window_lines=6, max_snippet_chars=400),
    )

    assert compressed.evidence_id == record.evidence_id
    assert compressed.start_line == 10
    assert compressed.end_line == 40
    assert compressed.excerpt_start_line > record.start_line
    assert compressed.truncated is True
    assert "return review(value_29)" in compressed.snippet
    assert "value_1 = 1" not in compressed.snippet


def test_retrieval_token_budget_uses_compressed_evidence(sample_context) -> None:
    context = _retrieval_context(sample_context)
    context.evidence.append(
        EvidenceRecord(
            evidence_id=stable_evidence_id("services/large.py", 1, 80, "\n".join(["review()"] * 80)),
            file_path="services/large.py",
            start_line=1,
            end_line=80,
            snippet="\n".join(["review()"] * 80),
            kind="source",
            symbols=["review"],
        )
    )

    result = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(
            agent_role="CodeSmellAgent",
            query="review",
            limit=3,
            token_budget=160,
            compression_window_lines=4,
            max_snippet_chars=180,
        )
    )

    assert len(result.records) >= 2
    assert result.stats.estimated_tokens <= 160
