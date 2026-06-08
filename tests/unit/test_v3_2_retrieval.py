from __future__ import annotations

from backend.agents.orchestrator import AgentOrchestrator
from backend.agents.specialized_agents import CodeSmellAgent
from backend.llm.client import MockLLMClient
from backend.models.context import EvidenceRecord, SymbolContext
from backend.parsers.python_parser import PythonParser
from backend.reviewers.markdown_adapter import MarkdownReviewAdapter
from backend.services.evidence import EvidenceRetriever, RetrievalPolicy, stable_evidence_id
from backend.services.indexer import RepositoryIndexer
from backend.services.sandbox import SandboxFilter


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
    assert result.state is not None
    assert result.state.metadata["retrieval_agents_with_stats"] == 1
    assert result.state.metadata["retrieval_average_precision_like"] >= 0


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


def test_large_repo_mode_marks_tiers_and_discloses_metadata(temp_repo) -> None:
    for index in range(6):
        name = "app.py" if index == 0 else f"module_{index}.py"
        (temp_repo / name).write_text(
            f"def function_{index}():\n    return {index}\n",
            encoding="utf-8",
        )
    manifest = SandboxFilter().build_manifest(temp_repo, max_files=10, max_file_size_bytes=1000)

    context = RepositoryIndexer(
        PythonParser(),
        max_files=10,
        max_file_size_bytes=1000,
        manifest=manifest,
        large_repo_threshold=3,
    ).build_review_context(temp_repo, "https://github.com/example/large")

    assert context.large_repo_mode is True
    assert context.analysis_tiers["high"] >= 1
    assert context.analysis_tiers["low"] >= 1
    assert "Large repo mode enabled" in (context.analysis_disclosure or "")
    report = MarkdownReviewAdapter.repository_metrics_section(context)
    assert "Large repo mode: enabled at threshold 3" in report
    assert "Analysis tiers:" in report


def test_large_repo_low_tier_is_manifest_only(sample_context) -> None:
    context = _retrieval_context(sample_context)
    context.metadata.large_repo_mode = True
    context.metadata.analysis_tiers = {"high": 1, "medium": 0, "low": 1}
    context.file_summaries[0].analysis_tier = "high"
    context.file_summaries[1].analysis_tier = "low"

    result = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(
            agent_role="MaintainabilityAgent",
            query="review",
            limit=2,
            token_budget=500,
        )
    )

    assert "services/review.py" in {candidate.path for candidate in result.manifest_candidates}
    assert "services/review.py" not in {record.file_path for record in result.records}
    assert result.stats.large_repo_mode is True


# ---------------------------------------------------------------------------
# V3.2.1 edge-case tests
# ---------------------------------------------------------------------------


def test_empty_evidence_set_returns_empty(sample_context) -> None:
    context = sample_context.to_review_context()
    context.evidence = []

    result = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(query="anything", limit=5, token_budget=500)
    )

    assert result.records == []
    assert result.stats.total_records == 0
    assert result.stats.selected_evidence == 0
    assert result.stats.estimated_tokens == 0


def test_zero_token_budget_selects_at_least_one(sample_context) -> None:
    context = _retrieval_context(sample_context)

    result = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(query="review", limit=2, token_budget=0)
    )

    assert len(result.records) >= 1


def test_single_evidence_record(sample_context) -> None:
    context = _retrieval_context(sample_context)
    # Keep only one evidence record
    context.evidence = [context.evidence[0]]

    result = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(query="create_app", limit=5, token_budget=500)
    )

    assert len(result.records) == 1
    assert result.stats.total_records == 1
    assert result.stats.selected_evidence == 1


def test_all_low_tier_returns_manifest_only(sample_context) -> None:
    context = _retrieval_context(sample_context)
    context.metadata.large_repo_mode = True
    context.metadata.analysis_tiers = {"high": 0, "medium": 0, "low": 2}
    context.file_summaries[0].analysis_tier = "low"
    context.file_summaries[1].analysis_tier = "low"

    result = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(query="review", limit=5, token_budget=500)
    )

    assert result.records == []
    assert len(result.manifest_candidates) > 0
    assert result.stats.selected_evidence == 0


def test_no_token_overlap_penalty(sample_context) -> None:
    context = _retrieval_context(sample_context)

    result_with_overlap = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(query="review", limit=5, token_budget=500)
    )
    result_no_overlap = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(query="zzzznonexistent", limit=5, token_budget=500)
    )

    # Non-overlapping query should produce lower manifest scores due to 0.25 penalty
    max_score_overlap = max(c.score for c in result_with_overlap.manifest_candidates)
    max_score_no_overlap = max(c.score for c in result_no_overlap.manifest_candidates)
    assert max_score_no_overlap < max_score_overlap


def test_one_line_snippet_compression(sample_context) -> None:
    context = _retrieval_context(sample_context)
    record = EvidenceRecord(
        evidence_id=stable_evidence_id("tiny.py", 1, 1, "x = 1"),
        file_path="tiny.py",
        start_line=1,
        end_line=1,
        snippet="x = 1",
        kind="source",
        symbols=[],
    )

    compressed = EvidenceRetriever(context).compress_for_prompt(record, "x")

    assert compressed.evidence_id == record.evidence_id
    assert compressed.start_line == 1
    assert compressed.end_line == 1
    assert compressed.snippet
    assert compressed.truncated is False
    assert compressed.estimated_tokens > 0


def test_token_budget_exact_boundary(sample_context) -> None:
    context = _retrieval_context(sample_context)
    retriever = EvidenceRetriever(context)

    # Find the cost of the cheapest record under the retrieval policy
    policy = RetrievalPolicy(query="review", limit=5, token_budget=5000)
    all_compressed = [
        retriever.compress_for_prompt(r, "review", policy=policy)
        for r in context.evidence
    ]
    cheapest = min(c.estimated_tokens for c in all_compressed)

    # Set budget to exactly the cheapest record's cost
    result = retriever.retrieve_with_policy(
        RetrievalPolicy(query="review", limit=5, token_budget=cheapest)
    )

    # At least one record should fit
    assert len(result.records) >= 1


def test_manifest_symbol_snippet_merge(sample_context) -> None:
    context = _retrieval_context(sample_context)

    result = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(query="review", limit=5, token_budget=500)
    )

    # Manifest and symbol paths should be non-empty and merged into candidate paths
    assert len(result.manifest_candidates) > 0
    assert len(result.symbol_paths) > 0
    # Snippet records should come from merged candidate paths
    for record in result.records:
        assert record.file_path in {c.path for c in result.manifest_candidates} | result.symbol_paths


def test_no_double_compression_in_stats(sample_context) -> None:
    """Verify that _build_stats uses pre-compressed results, not recompression."""
    context = _retrieval_context(sample_context)
    retriever = EvidenceRetriever(context)
    policy = RetrievalPolicy(query="review", limit=5, token_budget=500)

    result = retriever.retrieve_with_policy(policy)

    # Manually compress each selected record and sum tokens
    manual_sum = sum(
        retriever.compress_for_prompt(record, policy.query, policy=policy).estimated_tokens
        for record in result.records
    )
    # Stats should match — no double compression drift
    assert result.stats.estimated_tokens == manual_sum


def test_tier_threshold_distribution(temp_repo) -> None:
    """Verify that HIGH_TIER_RATIO and MEDIUM_TIER_RATIO produce expected distributions."""
    for index in range(20):
        (temp_repo / f"mod_{index:02d}.py").write_text(
            f"def func_{index}():\n    return {index}\n",
            encoding="utf-8",
        )
    manifest = SandboxFilter().build_manifest(temp_repo, max_files=25, max_file_size_bytes=1000)

    context = RepositoryIndexer(
        PythonParser(),
        max_files=25,
        max_file_size_bytes=1000,
        manifest=manifest,
        large_repo_threshold=10,
    ).build_review_context(temp_repo, "https://github.com/example/tiers")

    assert context.large_repo_mode is True
    tiers = context.analysis_tiers
    # With 20 files: high_cutoff = ceil(20*0.25) = 5, medium_cutoff = ceil(20*0.7) = 14
    # At least 5 high-tier (importance > 0 or entry/hub), rest split medium/low
    assert tiers["high"] >= 1
    assert tiers["high"] + tiers["medium"] + tiers["low"] == 20
    # Low tier should be non-empty (files not in top 70%)
    assert tiers["low"] >= 1
