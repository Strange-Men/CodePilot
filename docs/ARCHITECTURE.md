# Architecture

CodePilot is a modular monolith.

The FastAPI backend owns cloning, repository indexing, task state, report generation, and Markdown export. SQLite stores review task status and final report content. A small in-process background runner moves tasks through `pending`, `cloning`, `parsing`, `summarizing`, `reviewing`, `completed`, and `failed`.

Parsing is routed through a parser registry and parser protocol. The only registered parser is the existing Python parser, which indexes Python files only. Tree-sitter extracts classes, functions, imports, and docstrings for concise file summaries, with AST fallback. Those summaries become repository context; raw repository source is never sent to the LLM.

The Next.js frontend starts reviews, polls task status every two seconds, displays clear failures, renders the four report sections, and links to Markdown export.
