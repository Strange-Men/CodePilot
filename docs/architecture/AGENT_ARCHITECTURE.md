# CodePilot Multi-Agent Architecture

> Version: V3.7
> Last updated: 2026-06-21

## 1. 为什么需要多 Agent

代码审查天然包含多个独立维度：架构设计、代码质量、可维护性、重构机会。单个 prompt 同时覆盖四个维度会产出泛泛而谈的建议。将每个维度交给专项 Agent，配合该维度专属的证据检索策略和 prompt，能产出更具体、更可操作的 findings。

多 Agent 的价值不在于"看起来更智能"，而在于：
- 每个 Agent 的 prompt 更聚焦，输出更具体
- 每个 Agent 的 evidence retrieval query 不同，检索到的代码片段更相关
- Agent 之间并行执行，总延迟约等于最慢的单个 Agent
- 单个 Agent 失败不影响其他 Agent 的产出

## 2. 架构模式

CodePilot 是 **Orchestrator-Workers + Parallelization** 模式，不是自治型 Agent。

```text
ReviewContext (structured)
    │
    ▼
AgentOrchestrator
    │
    ├── ArchitectureAgent ──→ evidence retrieval → LLM → findings
    ├── CodeSmellAgent    ──→ evidence retrieval → LLM → findings
    ├── MaintainabilityAgent ──→ evidence retrieval → LLM → findings
    └── RefactorAgent     ──→ evidence retrieval → LLM → findings
    │
    ▼
Orchestrator: collect → deduplicate → validate → ReviewState
    │
    ▼
ReportComposer → four-section Markdown report
```

关键特征：
- **不是** fully autonomous agent（没有 Agent loop、没有动态子任务分解）
- **不是** Agent 间自由对话（Agent 之间不直接通信）
- **是** Orchestrator-managed fan-out/fan-in workflow
- **是** 固定角色、固定数量、固定流程的 specialist agents

## 3. Agent 角色边界

| Agent | 角色 | 报告分区 | 证据查询策略 | 证据上限 |
|-------|------|----------|-------------|---------|
| ArchitectureAgent | 架构分析 | Architecture Summary | "architecture entry point core module dependency route class function" | 10 |
| CodeSmellAgent | 代码质量 | Code Smells | "complexity duplicate long function too many calls code smell hotspot" | 8 |
| MaintainabilityAgent | 可维护性 | Maintainability Issues | "maintainability dependency fan in fan out orphan hub tests boundary" | 8 |
| RefactorAgent | 重构建议 | Refactoring Suggestions | "refactor extraction boundary interface split simplify dependency" | 8 |

每个 Agent 的边界由以下属性定义：
- `role`: Agent 标识符（如 "ArchitectureAgent"）
- `section`: 对应的报告分区（来自 `contracts/report_sections.json`）
- `category`: finding 分类标签（如 "architecture"）
- `evidence_query`: BM25 检索查询词
- `evidence_limit`: 最大检索证据数

## 4. Agent 输入

每个 Agent 接收的输入是 **结构化上下文**，不是原始源码。

### ReviewContext（共享）

```python
class ReviewContext(BaseModel):
    metadata: RepoMetadata          # 仓库元数据：URL、语言、文件数、摘要
    files: FileAnalysisBundle       # 文件摘要：path, classes, functions, purpose, importance
    dependencies: DependencyStructure  # 依赖图：edges, cycles, hubs, orphans
    insights: InsightReport         # 架构洞察：type, components, hotspots, onboarding
    deep_context: DeepContextSummary  # 符号索引：symbol_index, call_graph, class_hierarchy
    evidence: list[EvidenceRecord]  # 证据记录：evidence_id, file_path, lines, snippet
```

### EvidenceRecord（per-agent 检索结果）

```python
class EvidenceRecord(BaseModel):
    evidence_id: str      # 稳定哈希 ID（ev_{sha256[:20]}）
    file_path: str        # 文件路径
    start_line: int       # 起始行
    end_line: int         # 结束行
    snippet: str          # 代码片段
    kind: str             # "source" 或 "symbol"
    symbols: list[str]    # 相关符号名
```

Agent 不接收整个源文件。EvidenceRetriever 使用 BM25 + symbol index + manifest 检索，压缩后注入 prompt。

## 5. Agent 输出 Schema

Agent 输出通过 Pydantic schema 严格校验：

### RawLLMFinding（LLM 原始输出）

```python
class RawLLMFinding(BaseModel):
    title: str
    description: str
    category: str                    # 必须匹配 Agent 的 category
    severity: str                    # "high" | "medium" | "low"
    confidence: float                # 0.0-1.0
    evidence_ids: list[str]          # 必须引用有效的 evidence_id
    recommendation: str | None
    impact: str | None
    first_step: str | None
    validation_tests: list[str]
    confidence_rationale: str | None
    caveat: str | None
    display: DisplayFields | None    # 双语展示字段（en/zh）
```

### ReviewFinding（验证后）

在 RawLLMFinding 基础上增加：
- `section`: 报告分区
- `files`: 涉及文件列表（从 evidence_id 解析）
- `evidence`: 证据引用说明（从 evidence_id 解析）

### FindingValidator 校验规则

1. `section` 必须在 `REPORT_SECTIONS` 中
2. `evidence_ids` 不能为空
3. 每个 `evidence_id` 必须在 EvidenceStore 中存在
4. 任一 evidence_id 无效 → 整个 finding 被丢弃

## 6. Agent 协作方式

Agent 之间 **不直接通信**。协作通过 Orchestrator 和共享状态实现：

```text
Orchestrator.run(state: ReviewState) → ReviewState

1. 为每个 Agent 创建实例，注入 LLMClient 和配置
2. 调用 agent.review(context) → StructuredReviewDraft
   - Agent 内部：evidence retrieval → prompt rendering → LLM call → parse → validate
3. 收集所有 Agent 的 findings 和 agent_states
4. 去重：基于 (category, title, evidence_ids) 的 key 匹配
5. 写入 state.validated_findings
6. 返回 ReviewState
```

三种执行模式：
- **serial**：逐个执行，调试用
- **parallel**：ThreadPoolExecutor 并发执行，生产用
- **grouped**：2 次 LLM 调用产出 4 个 Agent 结果（Group 1: Architecture+Maintainability, Group 2: CodeSmell+Refactor），节省 LLM 调用次数

## 7. 共享上下文

所有 Agent 共享同一个 `ReviewContext` 实例，包含：

| 数据 | 来源 | 用途 |
|------|------|------|
| RepoMetadata | Indexer | 仓库身份、语言、文件数、摘要 |
| FileAnalysisBundle | Indexer + Parsers | 文件摘要、入口点、核心模块 |
| DependencyGraph | DependencyGraph service | 依赖边、循环、hub、orphan |
| InsightEngine | Insights service | 架构概述、风险热点、重构候选 |
| DeepContext | DeepContext service | 符号索引、调用图、类层次 |
| EvidenceStore | EvidenceBuilder | 稳定 evidence_id → EvidenceRecord 映射 |

每个 Agent 从共享 EvidenceStore 中通过 BM25 检索自己需要的 evidence 子集。

## 8. 状态管理

### ReviewState（运行时状态）

```python
class ReviewState(BaseModel):
    task_id: str | None
    context: ReviewContext
    evidence_bundles: dict[str, list[EvidenceRecord]]  # per-agent evidence
    agent_results: list[AgentExecutionState]            # per-agent 执行状态
    validated_findings: list[ReviewFinding]             # 去重后的 findings
    errors: dict[str, str]                              # per-agent 错误
    metadata: dict[str, ...]                            # orchestrator metadata
```

### AgentExecutionState（per-agent 状态）

```python
class AgentExecutionState(BaseModel):
    agent_id: str                # "ArchitectureAgent"
    status: AgentStatus          # "completed" | "failed"
    findings: list[ReviewFinding]
    error: str | None
    evidence_ids: list[str]
    prompt_tokens: int | None
    completion_tokens: int | None
    llm_calls: int | None
    validation_status: ValidationStatus  # "validated" | "failed"
    metadata: dict[str, ...]     # retrieval stats, duration, etc.
```

### 持久化

`ReviewState.safe_snapshot()` 生成 `PersistedReviewState`，用于 SQLite 存储和 API 响应。snapshot 会裁剪大字段（如 snippet）并保留 evidence_id 引用。

**注意**：没有长期记忆。状态仅限单次 review task。没有跨任务的 user memory 或 knowledge base。

## 9. Evidence-grounded 机制

这是 CodePilot 最核心的 guardrail：

### 证据生成

```text
源文件 → ParsedSourceFile → build_file_evidence() → EvidenceRecord[]
  - 按符号（function/class）分块，每块生成稳定 evidence_id
  - evidence_id = ev_{sha256(file_path:start_line:end_line:snippet)[:20]}
```

### 证据检索

```text
Agent.evidence_query → EvidenceRetriever.retrieve_with_policy()
  Level 1: Manifest retrieval（文件级匹配）
  Level 2: Symbol retrieval（符号级匹配）
  Level 3: Snippet retrieval（BM25 文本匹配）
  → 合并候选路径 → BM25 排序 → token budget 内选择 → 压缩
```

### 证据绑定

```text
LLM 输出 → RawLLMFinding.evidence_ids
  → FindingValidator.validate()
    → EvidenceStore.resolve(evidence_id)  # 必须存在
    → 生成 ReviewFinding.files 和 ReviewFinding.evidence
```

**关键约束**：LLM 不能发明 evidence_id。如果 LLM 输出的 evidence_id 在 EvidenceStore 中不存在，整个 finding 被丢弃。

## 10. Guardrails

| 层级 | 机制 | 文件 |
|------|------|------|
| 输入验证 | Pydantic model 校验所有输入 | `backend/models/context.py` |
| 证据绑定 | FindingValidator 验证 evidence_id 存在 | `backend/agents/finding_validator.py` |
| 输出校验 | RawLLMFinding Pydantic 校验 + JSON parse 重试 | `backend/llm/structured.py` |
| Evidence 过滤 | 只保留 prompt 中提供的 evidence_id | `backend/llm/structured.py:_filter_allowed` |
| Token 限制 | per-agent token budget（默认 2000） | `backend/agents/evidence_agent.py` |
| 重试机制 | LLM 调用失败最多重试 3 次，指数退避 | `backend/llm/client.py` |
| 执行隔离 | 单个 Agent 失败不影响其他 Agent | `backend/agents/orchestrator.py` |
| Mock 模式 | 默认 USE_MOCK_LLM=true，确定性输出 | `backend/core/config.py` |

## 11. Mock / Real LLM 双模式

### Mock 模式（默认）

```python
class MockLLMClient:
    def generate_structured_findings(prompt) -> list[RawLLMFinding]
    def generate_grouped_structured_findings(prompt) -> dict[str, dict]
```

- 不需要 API key
- 从 prompt 中提取 evidence_id，生成确定性 finding
- 支持单 Agent 和 grouped 两种模式
- 用于 CI、demo、本地开发

### Real 模式

```python
class OpenAICompatibleClient:
    def generate_review(prompt) -> str  # 原始 LLM 输出
```

- 需要 OPENAI_API_KEY 或 MIMO_API_KEY
- 支持 OpenAI 和 MiMo 两种模型服务商
- 重试：408, 409, 429, 5xx → 最多 3 次指数退避
- StructuredLLMClient 包装 JSON 解析和 Pydantic 校验

## 12. 当前限制

1. **固定 Agent 数量和角色**：4 个 Agent 是硬编码的，不支持动态添加新审查维度
2. **无 Agent 间交叉验证**：每个 Agent 独立产出 findings，没有 Evaluator-Optimizer 反馈循环
3. **无长期记忆**：没有跨任务的 user preference 或历史 review knowledge
4. **Python-only parser（主要）**：虽然有 JavaScript/TypeScript parser，但 Python 解析最成熟
5. **单机执行**：ThreadPoolExecutor 在单进程内，不支持分布式执行
6. **无 golden eval dataset**：有 quality metrics 但没有 expected findings 的标注数据

## 13. 后续可演进方向

以下方向已在 `.harness/ROADMAP.md` 中记录，但不在 V3.7 scope 内：

- 动态 Agent 注册（通过配置而非代码添加新审查维度）
- Agent 间交叉验证（Evaluator-Optimizer 模式）
- 向量检索增强（当 BM25 不足以覆盖语义相似性时）
- 分布式 Agent 执行（当单机成为瓶颈时）
- LangGraph 集成（当需要条件路由、循环、持久化恢复时）

**重要**：这些是未来选项，不是当前需要。当前架构已满足 V3.7 的所有目标。
