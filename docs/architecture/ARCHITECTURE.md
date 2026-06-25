# Architecture

CodePilot V3.7 is a modular monolith with a FastAPI backend and Next.js frontend.

## Review Flow

```text
Parser Registry
  -> direct or CompositeSourceParser
  -> ParsedSourceFile
  -> RepositoryIndexer
  -> ReviewContext
       RepoMetadata
       FileAnalysisBundle
       DependencyStructure
       InsightReport
       DeepContextSummary
       EvidenceRecord[]
  -> AgentOrchestrator
       ├── ArchitectureAgent  (evidence retrieval → LLM → findings)
       ├── CodeSmellAgent     (evidence retrieval → LLM → findings)
       ├── MaintainabilityAgent (evidence retrieval → LLM → findings)
       └── RefactorAgent      (evidence retrieval → LLM → findings)
  -> FindingValidator (evidence grounding)
  -> HumanReadableReportComposer
  -> four-section report + agent summary + evidence appendix
  -> SQLite and Markdown export
```

## Multi-Agent Architecture

V3 introduced an Orchestrator-managed multi-agent review workflow. The Orchestrator dispatches four specialist agents in parallel, each responsible for one review dimension (architecture, code quality, maintainability, refactoring). Agents share a structured ReviewContext and EvidenceStore but do not communicate directly. Each agent retrieves its own evidence subset using BM25 scoring, calls the LLM with a focused prompt, and produces structured findings. The Orchestrator collects, deduplicates, and validates all findings before report composition.

See `docs/architecture/AGENT_ARCHITECTURE.md` for the full multi-agent architecture documentation.

## Context Engineering

No raw source code is sent to the LLM. CodePilot parses source into structured summaries (file purpose, symbols, dependencies, routes), builds a dependency graph, generates architectural insights, and creates evidence records with stable IDs. The EvidenceRetriever uses BM25 + symbol index + manifest retrieval to select relevant evidence snippets within token budgets. LLM output is validated against Pydantic schemas, and every finding must reference a valid evidence_id.

## Module Structure

`RepositoryContext` remains available as the flat V2.5 compatibility model. Production indexing and review orchestration use `ReviewContext`; adapters convert at extension boundaries without changing API responses, the SQLite schema, or report output.

Prompt construction lives in `backend/prompts/`. `ReportGenerator` coordinates rendering, LLM invocation, normalization, and export. `MarkdownReviewAdapter` converts between current Markdown and `StructuredReviewDraft`, preserving the four required report sections while creating a future structured-review boundary.

`DependencyGraph`, parser registration, and `ReviewPipeline` remain the core execution path. The in-process `ReviewTaskRunner` uses a `ThreadPoolExecutor`, and FastAPI lifespan drains the executor during application shutdown.

## Mock / Real LLM

Mock mode is the default (`USE_MOCK_LLM=true`). It provides deterministic structured output without credentials. Real mode uses an OpenAI-compatible client with exponential backoff retries. The selectable Real LLM providers are MiMo (`mimo`), Doubao (`doubao`), and DeepSeek (`deepseek`), with MiMo as the default provider for backward compatibility.

Provider credentials live only in the backend environment:

```text
MIMO_API_KEY / MIMO_BASE_URL / MIMO_MODEL_NAME
DOUBAO_API_KEY / DOUBAO_BASE_URL / DOUBAO_MODEL_NAME
DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL_NAME
```

The frontend sends the selected provider value to the backend and never stores API keys. Provider availability is exposed through `GET /api/llm/providers` as value, label, and availability only. Both Mock and Real modes produce the same Pydantic-validated output schema.

## Evaluation

`evaluation/` provides a deterministic quality harness with five quality dimensions, per-agent cost/latency tracking, and optional real-LLM mode. See `evaluation/README.md` for details.
