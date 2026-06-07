# Architecture

CodePilot V2.6 is a modular monolith with a FastAPI backend and Next.js frontend.

The review flow is:

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
  -> PromptTemplate / PromptRenderer / TokenBudgeter
  -> LLMClient
  -> StructuredReviewDraft
  -> MarkdownReviewAdapter
  -> four-section report plus repository appendices
  -> SQLite and Markdown export
```

`RepositoryContext` remains available as the flat V2.5 compatibility model. Production indexing and review orchestration use `ReviewContext`; adapters convert at extension boundaries without changing API responses, the SQLite schema, or report output.

Prompt construction lives in `backend/prompts/`. `ReportGenerator` coordinates rendering, LLM invocation, normalization, and export. `MarkdownReviewAdapter` converts between current Markdown and `StructuredReviewDraft`, preserving the four required report sections while creating a future structured-review boundary.

`DependencyGraph`, parser registration, and `ReviewPipeline` remain the core V2 execution path. The in-process `ReviewTaskRunner` still uses two worker threads, and FastAPI lifespan now drains the executor during application shutdown.

See `docs/V3_READINESS.md` for the supported future migration points and current boundaries.
