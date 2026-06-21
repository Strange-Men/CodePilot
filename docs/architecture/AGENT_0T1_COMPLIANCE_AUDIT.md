# CodePilot Agent_0T1 Compliance Audit

> Audited against: `D:\Claude_skill\Agent_0T1\Agent_0T1.md`
> Audit date: 2026-06-21
> CodePilot version: V3.7

## 1. 当前多 Agent 架构概览

CodePilot 当前架构模式：**Orchestrator-Workers + Parallelization（组合模式）**

具体来说：

- **Orchestrator**：`AgentOrchestrator`（`backend/agents/orchestrator.py`）负责调度 4 个专项 Agent，管理执行模式（serial / parallel / grouped），收集结果，去重 findings，记录状态。
- **Workers**：4 个专项 Agent（ArchitectureAgent、CodeSmellAgent、MaintainabilityAgent、RefactorAgent），每个继承自 `EvidenceGroundedAgent` 基类，有独立的角色、证据查询策略、报告分区。
- **协作方式**：Agent 之间不直接通信。Orchestrator 将共享的 `ReviewContext` 注入每个 Agent，Agent 独立产出结构化 findings，Orchestrator 负责收集、去重、状态记录。
- **不是自治型 Agent**：没有 Agent loop、没有动态子任务分解、没有 Agent 间自由对话、没有工具调用循环。

对应 Agent_0T1 Skill 的 Pattern 分类：

| Pattern | 是否匹配 |
|---------|----------|
| A. Single LLM Call | 否 |
| B. Prompt Chaining | 部分（evidence retrieval → LLM → validation 是链式的） |
| C. Routing | 否 |
| D. Parallelization | 是（4 个 Agent 可并行） |
| E. Orchestrator-Workers | 是（Orchestrator 调度 Workers） |
| F. Evaluator-Optimizer | 否 |
| G. Autonomous Agent Loop | 否 |

**真实判断**：CodePilot 是 **Orchestrator-managed parallel specialist agents**，不是 fully autonomous multi-agent system。

## 2. 对照 Agent_0T1 Skill 的检查表

| Skill 要求 | 当前实现 | 是否符合 | 证据文件 | 问题 | 建议 |
|---|---|---|---|---|---|
| **Task Definition** | 明确定义：输入 GitHub URL，输出四段式审查报告 | ✅ 符合 | `backend/tasks/pipeline.py`, `README.md` | 无 | 无 |
| **Agent Necessity** | 4 个维度（架构/质量/可维护性/重构）确实需要独立视角 | ✅ 符合 | `backend/agents/specialized_agents.py` | 无 | 无 |
| **MVP Scope** | V3.7 封板，scope 清晰，non-goals 明确（无 LangGraph、无 MCP、无 vector RAG） | ✅ 符合 | `.harness/GOAL.md`, `.harness/ROADMAP.md` | 无 | 无 |
| **Agent Contract** | 每个 Agent 有 role、section、category、evidence_query、evidence_limit，输入输出由 Pydantic schema 定义 | ⚠️ 部分符合 | `backend/agents/evidence_agent.py`, `backend/agents/specialized_agents.py` | Contract 是隐式的（在代码中），没有独立的 Agent Contract 文档 | 补文档 |
| **Context Design** | 结构化 `ReviewContext`，不发送原始源码；EvidenceRetriever 做 BM25 检索 + 压缩 | ✅ 符合 | `backend/models/context.py`, `backend/services/evidence/retriever.py` | 无 | 无 |
| **Tool Design** | EvidenceRetriever 是唯一"工具"，有明确的输入输出、权限（只读）、超时 | ✅ 符合 | `backend/services/evidence/retriever.py` | 无 | 无 |
| **Workflow Pattern** | Orchestrator-Workers + Parallelization，固定 4 个 Agent，非动态分解 | ✅ 符合 | `backend/agents/orchestrator.py` | 无 | 无 |
| **State and Memory** | `ReviewState` 跟踪 task_id、agent_results、validated_findings、errors、metadata；无长期记忆 | ✅ 符合 | `backend/models/review_state.py` | 无 | 无 |
| **Guardrails** | FindingValidator 验证 evidence_id 存在；StructuredLLMClient 重试 + JSON 校验；evidence_id 过滤；token budget 限制 | ✅ 符合 | `backend/agents/finding_validator.py`, `backend/llm/structured.py` | 无 | 无 |
| **Evaluation** | `evaluation/` 模块有 quality_metrics、costs、comparison、dataset harness；`tests/unit/` 覆盖 orchestrator、grouped mode、pipeline | ✅ 符合 | `evaluation/`, `tests/unit/test_orchestrator_concurrency.py` | 无正式 eval dataset（有 fixtures 但非 golden labels） | 记录为已知限制 |
| **Observability** | 结构化 performance_event 日志；AgentExecutionState 记录 status/duration/tokens/calls；CostTracker | ✅ 符合 | `backend/agents/orchestrator.py`, `backend/llm/structured.py` | 无可视化 dashboard | 记录为已知限制 |
| **Release Boundary** | Mock mode 默认可用；tests pass；CI green；known limitations documented | ✅ 符合 | `backend/core/config.py`, `.harness/RELEASE_RULES.md` | 无 | 无 |
| **Output Schema / Pydantic** | `RawLLMFinding`、`ReviewFinding`、`StructuredReviewDraft`、`AgentExecutionState` 全部 Pydantic 校验 | ✅ 符合 | `backend/models/structured_review.py`, `backend/models/review_state.py` | 无 | 无 |
| **Mock Mode** | `MockLLMClient` 默认启用，确定性输出，不需要 credentials | ✅ 符合 | `backend/llm/client.py` | 无 | 无 |

## 3. 目前做得好的地方

1. **Evidence-grounded 机制设计扎实**：每个 finding 必须绑定 evidence_id，FindingValidator 验证 evidence_id 确实存在，不允许 LLM 编造文件路径或行号。这是真正的 guardrail。

2. **结构化上下文而非原始代码**：ReviewContext 包含 RepoMetadata、FileAnalysisBundle、DependencyStructure、InsightReport、DeepContextSummary、EvidenceRecord，LLM 只接收结构化摘要和压缩后的 evidence snippets，不接收原始源文件。

3. **Pydantic schema 校验完整**：从 RawLLMFinding 到 ReviewFinding 到 AgentExecutionState，全链路 Pydantic 校验，JSON parse failure 有重试机制。

4. **三种执行模式**：serial、parallel（ThreadPoolExecutor）、grouped（2 次 LLM 调用产出 4 个 Agent 结果），可根据场景选择。

5. **Mock/Real LLM 双模式**：MockLLMClient 有结构化输出支持（generate_structured_findings、generate_grouped_structured_findings），deterministic 且不需要 credentials。

6. **状态管理清晰**：ReviewState → AgentExecutionState → PersistedReviewState，safe_snapshot() 做序列化时的脱敏和裁剪。

7. **评估体系**：evaluation/ 模块有 quality metrics、cost tracking、comparison、dataset-based harness。

8. **测试覆盖**：test_orchestrator_concurrency.py、test_grouped_mode.py、test_pipeline_all_agents_failed.py、test_review_state.py 覆盖了关键路径。

9. **Per-agent 可观测性**：每个 Agent 的 duration、tokens、LLM calls、retrieval stats 全部记录在 AgentExecutionState.metadata 中。

## 4. 不符合或不足的地方

### P0：会导致系统错误或简历表达风险

**无 P0 问题。** 当前实现和文档表达基本一致，没有"简历上说了但代码没实现"的风险。

### P1：架构表达不清或实现缺少边界

1. **`docs/architecture/ARCHITECTURE.md` 严重过时**
   - 文件仍写着 "CodePilot V2.6"，但项目已是 V3.7
   - 没有提及 multi-agent 架构、evidence system、orchestrator
   - 证据：`docs/architecture/ARCHITECTURE.md:1`

2. **缺少独立的 Agent Contract 文档**
   - Agent 的 role、input、output、failure behavior 全在代码中，没有独立文档
   - 面试时如果被问 "你的 Agent contract 是什么"，需要翻代码才能回答
   - 建议：创建 `docs/architecture/AGENT_ARCHITECTURE.md`

3. **README 中 Agent 角色名称不一致**
   - README 写 "CodeQuality Agent"，代码中是 "CodeSmellAgent"
   - 证据：`README.md:35` vs `backend/agents/specialized_agents.py:7`

### P2：后续优化项，不影响当前封板

1. **无正式 eval dataset with golden labels**
   - 有 fixtures 和 quality metrics，但没有 "expected findings" 的 golden dataset
   - 不影响封板，但影响 Agent 质量的量化评估

2. **无 Agent 可视化 dashboard**
   - 状态记录在日志和 SQLite 中，但没有实时 dashboard
   - 前端有 Agent Summary 表格，但不是实时监控

3. **Agent 间无交叉验证**
   - 每个 Agent 独立产出 findings，没有 Evaluator-Optimizer 模式的反馈循环
   - 当前去重只基于 (category, title, evidence_ids) 的 key 匹配

## 5. 是否需要修改代码

**不需要，只补文档。**

当前代码实现已经符合 Agent_0T1 Skill 的核心要求。问题主要在文档层面：
- 架构文档过时
- 缺少 Agent Contract 文档
- README 中一个小的命名不一致

## 6. 最小优化计划

| 序号 | 优化项 | 类型 | 风险 | 文件 |
|------|--------|------|------|------|
| 1 | 创建 AGENT_ARCHITECTURE.md | 文档 | 无 | `docs/architecture/AGENT_ARCHITECTURE.md` |
| 2 | 更新 ARCHITECTURE.md 从 V2.6 到 V3.7 | 文档 | 无 | `docs/architecture/ARCHITECTURE.md` |
| 3 | 修正 README 中 "CodeQuality Agent" → "CodeSmell Agent" | 文档 | 极低 | `README.md` |

## 7. 面试表达建议

### 这个项目的多 Agent 该怎么真实描述

> CodePilot uses an **Orchestrator-managed multi-agent review workflow**. The Orchestrator dispatches four specialist agents — Architecture, CodeSmell, Maintainability, and Refactor — each responsible for one review dimension. Agents don't talk to each other; they share a structured ReviewContext and EvidenceStore, produce independent structured findings, and the Orchestrator collects, deduplicates, and validates them before report composition.

### 哪些词可以说

- Multi-Agent Review Workflow ✅
- Orchestrator-managed specialist agents ✅
- Evidence-grounded structured findings ✅
- Mock / Real LLM dual mode ✅
- Structured context engineering (not raw code) ✅
- BM25-based evidence retrieval ✅
- Pydantic schema validation ✅
- Per-agent observability (duration, tokens, calls) ✅
- Parallel agent execution ✅
- Deterministic mock mode for CI/demo ✅

### 哪些词不能说

- ❌ Fully autonomous agent（不是自治型，是固定 workflow）
- ❌ Complete vector RAG（用的是 BM25 + symbol index，不是向量数据库）
- ❌ MCP tool system（MCP 是可选注册，不是核心架构）
- ❌ LangGraph agent graph（明确 deferred）
- ❌ Agent-to-agent communication（Agent 间不直接通信）
- ❌ Long-term memory（只有 task-level state，没有跨任务记忆）
- ❌ Dynamic task decomposition（Agent 数量和角色是固定的）

### 如果被问 "Agent 之间怎么通信"

> Agents don't communicate directly. The Orchestrator manages a shared ReviewState that contains the ReviewContext (structured repository metadata, file summaries, dependency graph, evidence records). Each agent reads from this shared state independently, retrieves its own evidence using BM25 scoring, calls the LLM with its specialized prompt, and produces structured findings. The Orchestrator then collects all findings, deduplicates them, and passes them to the ReportComposer. It's a fan-out/fan-in pattern, not a message-passing system.

### 如果被问 "为什么需要多 Agent"

> Code review has multiple independent dimensions — architecture, code quality, maintainability, refactoring. Each dimension benefits from a specialized prompt and evidence retrieval strategy. A single prompt trying to cover all four dimensions produces generic, shallow output. Separate agents with focused prompts and per-agent evidence retrieval produce more specific, actionable findings. The cost is acceptable because agents run in parallel and share the same context.

### 如果被问 "你的 Agent 有什么 guardrails"

> Three layers. First, evidence grounding: every finding must reference a valid evidence_id, and the FindingValidator rejects any finding whose evidence_id doesn't exist in the store. LLM cannot invent file paths or line numbers. Second, output schema validation: all LLM output goes through Pydantic model validation with retry on parse failure. Third, operational guardrails: per-agent token budgets, max retries with exponential backoff, and mock mode as the default for deterministic testing.
