# CodePilot V3.4 Report Quality

V3.4 improves how existing structured findings are classified, composed, displayed, and evaluated. It does not add
agents, change the API or SQLite schema, execute repository code, or require a real LLM.

## Report Composer

`HumanReadableReportComposer` is used by the V3 single-agent and multi-agent engines. The V2 engine continues to use
`MarkdownReviewAdapter`.

V3 reports now present:

1. Executive Summary and the top five bounded risks.
2. Repository type, major components, and analyzed scope.
3. A cautious static description of the entry-point-to-core flow.
4. A compact architecture map with readable dependency cycle groups.
5. Agent status, finding counts, severity mix, confidence, and evidence counts.
6. Findings grouped by agent.
7. The original four contract sections in their original order.
8. An action plan with concrete files, validated symbols, first steps, risk, evidence, and validation tests.
9. A snippet-free evidence appendix and compact repository metrics.

The API still returns `report_markdown`; Markdown export behavior and the four required headings are unchanged.

## Classification And Signal Changes

- Repository classification distinguishes Python libraries, web frameworks, backend APIs, CLI tools, frontend apps,
  SDK/client libraries, test-heavy repositories, docs-heavy repositories, and mixed full-stack applications.
- Web-framework signals take priority over the presence of a `cli.py`, preventing Flask-like repositories from being
  classified as CLI-only.
- User-facing rankings prioritize production files. Test-only hotspots are shown separately.
- Long strongly connected dependency groups are rendered as bounded cycle groups rather than repeated path chains.

## Agent Visibility

The report composer consumes optional `AgentExecutionState` values already produced by V3. Agent summary and finding
tables remain safe when an agent fails or state is absent. Evidence references contain IDs, paths, line ranges, kinds,
and symbols; source snippets are never rendered or persisted.

The frontend recognizes the additive V3.4 sections and renders them as the existing Card and Markdown table components.
No API expansion or large UI redesign was required.

## Deterministic Quality Evaluation

Run:

```powershell
python -m evaluation.report_quality
```

The mock-only suite checks:

- Flask-like classification is not CLI-only.
- Test files do not outrank production recommendations.
- Long circular dependencies are summarized readably.
- Agent summaries and grouped findings are visible.
- Recommendations include evidence, first steps, and validation tests.
- Every finding has a valid `evidence_id`.
- Reports remain bounded and contain each main overview/appendix once.
- Evidence snippets are not exposed.

The V3.4 implementation result is 8/8 checks passed. The deterministic sample report is 5,516 characters and 102 lines.

## Before And After

Before V3.4, a typical mock report consisted mainly of four generic sections plus repeated metrics and graph details.
Agent execution was persisted but not visible in the main report, and recommendations often lacked a concrete starting
file or validation path.

After V3.4, the same structured results lead with repository identity and top risks, expose agent status and evidence,
retain the four compatible sections, and end with a bounded action plan and safe evidence appendix.

## Known Limitations

- Repository type and responsibility labels remain deterministic static heuristics.
- Mock findings demonstrate grounding and report behavior, not deep semantic understanding.
- Related tests are matched by file and symbol names; dynamic test selection is not inferred.
- Real-LLM quality, comparative model scoring, and human preference studies remain outside V3.4.
- The frontend still renders report Markdown rather than receiving a new structured report API.

## V3.5 Readiness

V3.5 can build a real-LLM evaluation platform around the stable structured findings, AgentExecutionState, safe evidence
references, and deterministic quality checks. It should add versioned datasets, model/provider run metadata, human or
rubric scoring, and cost/latency comparison without replacing the V3.4 composer or weakening mock-only CI.
