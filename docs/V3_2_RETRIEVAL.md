# CodePilot V3.2 Retrieval Architecture

CodePilot V3.2 upgrades evidence retrieval while preserving the V3.1 agent, state, evidence, SQLite, and report contracts.

## Architecture

Retrieval still flows through `EvidenceRetriever`; agents do not read files directly and still cite `evidence_id` values only.

1. Level 1 manifest retrieval ranks safe sandbox-selected files by path, role, language, import/symbol hints, dependency signals, and importance score.
2. Level 2 symbol retrieval matches functions, classes, imports, calls, and routes from `DeepContextSummary`.
3. Level 3 snippet retrieval uses the existing lightweight BM25-style lexical scoring plus dependency and symbol boosts to select `EvidenceRecord` values.
4. Level 4 semantic retrieval remains a documented future hook. V3.2 does not add embeddings, vector storage, LangChain, LangGraph, Chroma, or FAISS.

## Context Compression

Prompt evidence is compressed without changing `EvidenceRecord` lineage:

- `evidence_id`, original file path, and original line range are preserved.
- Agent prompts receive line-numbered excerpts centered on query-relevant lines.
- Duplicate evidence ranges are removed before prompt assembly.
- Token budgeting uses compressed excerpts, not full source snippets.
- Compression is deterministic and does not use an LLM.

## Large Repo Mode

`LARGE_REPO_THRESHOLD` defaults to `300`. When supported source files exceed that threshold:

- `SandboxFilter` remains the only file entry point.
- `MAX_FILES` still caps analyzed files after sandbox-safe prioritization.
- analyzed files are tiered as `high`, `medium`, and `low`;
- high priority files keep deeper context windows;
- medium priority files use lighter compressed context windows;
- low priority files are manifest-only and do not enter snippet evidence bundles;
- safe disclosure appears in the `Repository Metrics` appendix.

Small repositories keep `standard` tier behavior.

## Retrieval Metrics

V3.2 records additive, snippet-free retrieval metrics:

- precision-like selected relevance ratio;
- recall-like selected coverage over available relevant snippet candidates;
- retrieval latency;
- compressed token utilization;
- selected evidence count;
- per-agent level counts;
- large repo mode flag.

Metrics are persisted in agent state metadata and aggregated in `ReviewState.metadata`. Evaluation helpers in `evaluation.metrics` expose deterministic retrieval metric aggregation for mock CI.

## Stronger RAG Decision

Measured V3.2 behavior is sufficient for the current CodePilot review workload:

- lexical BM25-style retrieval already exists in-tree and is deterministic;
- symbol and dependency signals provide code-specific context without a new dependency;
- compression reduces prompt pressure while preserving line and evidence lineage;
- large repo mode avoids full-repo prompt expansion by tiering analysis safely;
- retrieval metrics are available for future regression tracking.

Therefore V3.2 does not add a vector database, embedding pipeline, full RAG framework, `rank_bm25`, LangChain, or LangGraph. A stronger retrieval dependency should be reconsidered only if future metrics show poor recall-like coverage on a curated V3.2+ regression set after lightweight lexical, symbol, and file-priority tuning has been exhausted.

## References Studied

Patterns were borrowed, not code:

- Aider repo map and symbol-oriented code context: <https://aider.chat/docs/repomap.html>
- LangGraph state and routing concepts: <https://docs.langchain.com/oss/python/langgraph/graph-api>
- Ragas retrieval and grounding metric concepts: <https://docs.ragas.io/>
- OpenAI Evals regression-style evaluation patterns: <https://github.com/openai/evals>
- SWE-bench benchmark and regression dataset patterns: <https://www.swebench.com/>
