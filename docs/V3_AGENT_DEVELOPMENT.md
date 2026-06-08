# V3 Agent Development

An agent in CodePilot is role + prompt + context + internal skills + LLM provider + structured output + validator + orchestrator.

## Rules

- Agents must consume `ReviewContext` and `EvidenceRetriever`; they must not read repository files directly.
- Findings must include valid `evidence_ids`.
- Agents must not invent file paths, line ranges, snippets, or unsupported tools.
- Agent failures must be isolated by `AgentOrchestrator`.
- New agents should subclass `EvidenceGroundedAgent`, set `role`, `section`, `category`, `evidence_query`, and `evidence_limit`, then add tests for validation and dedup behavior.

## Current Agents

- `ArchitectureAgent`: architecture boundaries, entry points, core modules, dependency shape.
- `CodeSmellAgent`: complexity and smell-oriented evidence.
- `MaintainabilityAgent`: dependency, hub, orphan, and test-boundary evidence.
- `RefactorAgent`: extraction and boundary simplification evidence.

## Evaluation

V3.0 evaluation is mock-only in CI. Real LLM evaluation is optional and manual because it has cost and flakiness risk.
