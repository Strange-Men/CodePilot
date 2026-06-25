export type Language = "en" | "zh";

const dictionaries: Record<Language, Record<string, string>> = {
  en: {
    // Header
    "header.workspace": "Review Workspace",
    "header.tagline": "Evidence-grounded repository analysis",
    "header.queued": "Queued",
    "header.idle": "Idle",

    // Status labels
    "status.pending": "Pending",
    "status.cloning": "Cloning",
    "status.parsing": "Parsing",
    "status.summarizing": "Summarizing",
    "status.reviewing": "Reviewing",
    "status.completed": "Completed",
    "status.failed": "Failed",

    // Control sidebar
    "sidebar.controlPanel": "Control panel",
    "sidebar.repositoryReview": "Repository review",
    "sidebar.description": "Import a public GitHub repository and run the evidence-grounded review pipeline.",
    "sidebar.currentStatus": "Current status",
    "sidebar.notStarted": "Not started",
    "sidebar.exportMarkdown": "Export Markdown",
    "sidebar.exportHint": "Download the current language as a self-contained Markdown report with E1/E2 evidence refs.",

    // Review submission form
    "form.githubRepo": "GitHub repository",
    "form.githubHelp": "Public HTTPS GitHub URLs only.",
    "form.llmMode": "LLM Mode",
    "form.mockLlm": "Mock LLM",
    "form.realLlm": "Real LLM",
    "form.mockDescription": "Uses deterministic mock output. No API key required.",
    "form.realLlmDescription": "Uses backend real LLM configuration. Select a provider configured in backend .env.",
    "form.realLlmProvider": "Real LLM provider",
    "form.providerUnavailable": "This provider requires backend .env configuration.",
    "form.startReview": "Start review",
    "form.reviewInProgress": "Review in progress",

    // Workspace tabs
    "tabs.overview": "Overview",
    "tabs.agents": "Agents",
    "tabs.findings": "Findings",
    "tabs.report": "Report",
    "tabs.evidence": "Evidence",
    "tabs.metrics": "Metrics",
    "tabs.workspaceSections": "Review workspace sections",

    // Tab empty states
    "tabs.noReviewSelected": "No review selected",
    "tabs.noReviewDescription": "Start or select a review to populate this workspace section.",
    "tabs.agentSummariesProcessing": "Agent summaries are still processing",
    "tabs.agentSummariesProcessingDesc": "Persisted counts, confidence, and severity summaries become available after the agent pipeline completes.",
    "tabs.loadingAgentStates": "Loading persisted agent states",
    "tabs.retryAgentStates": "Retry agent states",
    "tabs.agentSummariesLoadError": "Agent summaries could not be loaded",
    "tabs.structuredDataLoadError": "Structured review data could not be loaded.",
    "tabs.findingsBeingValidated": "Findings are being validated",
    "tabs.findingsValidatedDesc": "Findings appear here after the agents finish validation and the review reaches a terminal state.",
    "tabs.evidenceBeingCollected": "Evidence is being collected",
    "tabs.evidenceCollectedDesc": "Validated file, symbol, and line references appear after the review completes.",
    "tabs.metricsStillProcessing": "Metrics are still processing",
    "tabs.metricsProcessingDesc": "Review metrics finalize when structured findings and persisted agent states are available.",
    "tabs.loadingReviewMetrics": "Loading review metrics",
    "tabs.retryMetrics": "Retry metrics",
    "tabs.metricsLoadError": "Metrics could not be loaded",

    // Overview panel
    "overview.startReview": "Start a repository review",
    "overview.startReviewDesc": "Import a public GitHub repository from the control panel. CodePilot will map the repository, run four review agents, and assemble an evidence-grounded report.",
    "overview.currentReview": "Current review",
    "overview.agentsComplete": "Agents complete",
    "overview.findings": "Findings",
    "overview.highRiskItems": "High-risk items",
    "overview.evidenceRefs": "Evidence refs",
    "overview.reviewComplete": "Review complete. Structured agent, finding, evidence, and metric data is ready across the workspace tabs.",
    "overview.reviewFailed": "The latest execution did not complete. Persisted progress remains visible for diagnosis.",
    "overview.reviewInterrupted": "Review interrupted",

    // Agent timeline
    "timeline.executionPipeline": "Execution pipeline",
    "timeline.reviewAgents": "Review agents",
    "timeline.complete": "complete",
    "timeline.findings": "findings",

    // Agent status (also used in timeline and state cards)
    "agentStatus.pending": "pending",
    "agentStatus.running": "running",
    "agentStatus.completed": "completed",
    "agentStatus.failed": "failed",
    "agentStatus.skipped": "skipped",

    // Agent state cards
    "agentCards.notRecorded": "Agent summaries are not recorded",
    "agentCards.notRecordedDesc": "This review predates persisted agent summaries. The report remains available in the Report tab.",
    "agentCards.findings": "Findings",
    "agentCards.evidence": "Evidence",
    "agentCards.avgConfidence": "Avg confidence",
    "agentCards.severity": "Severity",

    // Findings panel
    "findings.structuredData": "Structured review data",
    "findings.heading": "Findings",
    "findings.total": "total",
    "findings.recommendedAction": "Recommended action",
    "findings.impact": "Impact",
    "findings.firstSafeStep": "First safe step",
    "findings.validationTests": "Validation tests",
    "findings.caveat": "Caveat",
    "findings.evidence": "Evidence",
    "findings.confidence": "confidence",
    "findings.noStructured": "No structured findings",
    "findings.noStructuredDesc": "No structured findings were stored for this review. Legacy report content is still available in the Report tab.",
    "findings.retryFindings": "Retry findings",
    "findings.loadError": "Findings could not be loaded",
    "findings.loading": "Loading structured findings",

    // Evidence panel
    "evidence.validatedRefs": "Validated references",
    "evidence.heading": "Evidence",
    "evidence.chainTitle": "Evidence Chain",
    "evidence.references": "references",
    "evidence.symbol": "Symbol:",
    "evidence.supports": "Supports",
    "evidence.supportingFinding": "This evidence supports the location and conclusion of this finding.",
    "evidence.codeLocation": "Code location",
    "evidence.relatedSymbol": "Related symbol",
    "evidence.evidenceType": "Evidence type",
    "evidence.evidenceId": "Evidence ID",
    "evidence.showSnippet": "Show code snippet",
    "evidence.hideSnippet": "Hide code snippet",
    "evidence.snippetNotAvailable": "Only code location info is shown; source snippet is not expanded.",
    "evidence.unlinkedEvidence": "Unlinked evidence",
    "evidence.supportingEvidence": "Supporting evidence",
    "evidence.locationUnavailable": "Location unavailable",
    "evidence.noStructured": "No structured evidence",
    "evidence.noStructuredDesc": "No structured evidence references were persisted for this review. The Markdown report may contain a legacy appendix.",
    "evidence.retryEvidence": "Retry evidence",
    "evidence.loadError": "Evidence could not be loaded",
    "evidence.loading": "Loading evidence references",

    // Metrics panel
    "metrics.telemetry": "Review telemetry",
    "metrics.heading": "Metrics",
    "metrics.findings": "Findings",
    "metrics.evidenceRefs": "Evidence refs",
    "metrics.agentRecords": "Agent records",
    "metrics.avgConfidence": "Avg confidence",
    "metrics.severityDist": "Severity distribution",
    "metrics.riskSignal": "Risk signal",
    "metrics.riskSignalDesc": "Critical or high severity findings that should be triaged before routine cleanup.",
    "metrics.notRecorded": "Metrics are not recorded",
    "metrics.notRecordedDesc": "Structured metrics are unavailable for this legacy review. Use the Report tab for the original analysis.",

    // Report panel
    "report.outline": "Report outline",
    "report.section": "Report section",
    "report.legacyAppendices": "Legacy appendices and repository diagnostics",
    "report.inProgress": "Report generation is in progress",
    "report.noReport": "No report selected",
    "report.inProgressDesc": "The report is assembled after the review agents finish. Runtime progress remains available in Overview and Agents.",
    "report.noReportDesc": "Select a completed review or start a new one to read its Markdown report.",
    "report.sectionNav": "Report section navigation",

    // Review history panel
    "history.savedRuns": "Saved runs",
    "history.heading": "Review history",
    "history.emptyDesc": "Completed and in-progress reviews will appear here.",
    "history.retryHistory": "Retry history",
    "history.loadError": "Review history could not be loaded.",
    "history.confirmDelete": "Confirm delete",
    "history.deleteReview": "Delete review",
    "history.loadingReviews": "Loading previous reviews",
    "history.confirm": "Confirm",

    // Export errors
    "export.reviewNotFound": "Report not found. The backend may have been redeployed and temporary data cleared. Please re-run the review.",
    "export.notReady": "This report is not yet available for export. Please wait for the review to complete or re-run it.",
    "export.networkError": "Export failed. Please check your network connection or try again later.",
    "export.staleHistoryRemoved": "This review no longer exists and has been removed from history.",

    // Error page
    "error.title": "CodePilot could not render this page",
    "error.description": "Your review data is safe. Retry the page, or reload a previous report from history.",
    "error.retry": "Retry",
    "error.providerAuth": "MiMo authentication is not ready. Check the backend API key configuration, then re-run the review.",
    "error.providerNetwork": "The provider or network timed out. The workspace is still usable; wait a moment and re-run the review.",
    "error.providerRateLimit": "The provider rate limit was reached. Please wait a moment before trying again.",
    "error.reviewNoLongerAvailable": "This review is no longer available on the server. It may have been cleared after a restart; re-run the repository review.",
    "error.startReviewFailed": "CodePilot could not start this review. Check the repository URL and try again.",
    "error.deleteReviewFailed": "CodePilot could not delete this review. Try again from history.",
    "error.generic": "Something went wrong. Please try again.",

    // Loading page
    "loading.workspace": "Loading CodePilot workspace",

    // Severity
    "severity.critical": "Critical",
    "severity.high": "High",
    "severity.medium": "Medium",
    "severity.low": "Low",
    "severity.informational": "Informational",

    // Category
    "category.architecture": "Architecture",
    "category.code_smell": "Code Smell",
    "category.maintainability": "Maintainability",
    "category.refactor": "Refactor",

    // Validation status
    "validation.validated": "Validated",
    "validation.failed": "Failed",
    "validation.not_applicable": "N/A"
  },

  zh: {
    // Header
    "header.workspace": "代码审查工作台",
    "header.tagline": "基于证据的仓库分析",
    "header.queued": "排队中",
    "header.idle": "空闲",

    // Status labels
    "status.pending": "等待中",
    "status.cloning": "克隆中",
    "status.parsing": "解析中",
    "status.summarizing": "总结中",
    "status.reviewing": "审查中",
    "status.completed": "已完成",
    "status.failed": "失败",

    // Control sidebar
    "sidebar.controlPanel": "控制面板",
    "sidebar.repositoryReview": "仓库审查",
    "sidebar.description": "导入公开的 GitHub 仓库，运行基于证据的审查流水线。",
    "sidebar.currentStatus": "当前状态",
    "sidebar.notStarted": "未开始",
    "sidebar.exportMarkdown": "导出 Markdown",
    "sidebar.exportHint": "按当前语言导出自包含 Markdown 报告，保留 E1/E2 证据引用。",

    // Review submission form
    "form.githubRepo": "GitHub 仓库",
    "form.githubHelp": "仅支持公开的 HTTPS GitHub URL。",
    "form.llmMode": "模型模式",
    "form.mockLlm": "Mock LLM",
    "form.realLlm": "真实模型",
    "form.mockDescription": "使用确定性 Mock 输出，无需 API Key。",
    "form.realLlmDescription": "使用后端真实模型配置，请选择已配置的模型服务商。",
    "form.realLlmProvider": "模型服务商",
    "form.providerUnavailable": "该模型服务商尚未配置，请在后端 .env 中补充对应 Key、Base URL 和模型名称。",
    "form.startReview": "开始审查",
    "form.reviewInProgress": "审查中",

    // Workspace tabs
    "tabs.overview": "总览",
    "tabs.agents": "Agent",
    "tabs.findings": "问题发现",
    "tabs.report": "报告",
    "tabs.evidence": "证据",
    "tabs.metrics": "指标",
    "tabs.workspaceSections": "审查工作台各分区",

    // Tab empty states
    "tabs.noReviewSelected": "未选择审查",
    "tabs.noReviewDescription": "开始或选择一项审查以填充此工作台分区。",
    "tabs.agentSummariesProcessing": "Agent 摘要处理中",
    "tabs.agentSummariesProcessingDesc": "持久化的计数、置信度和严重性摘要将在 Agent 流水线完成后可用。",
    "tabs.loadingAgentStates": "加载持久化 Agent 状态",
    "tabs.retryAgentStates": "重试 Agent 状态",
    "tabs.agentSummariesLoadError": "无法加载 Agent 摘要",
    "tabs.structuredDataLoadError": "无法加载结构化审查数据。",
    "tabs.findingsBeingValidated": "正在验证问题发现",
    "tabs.findingsValidatedDesc": "Agent 完成验证且审查到达终态后，问题发现将显示在此处。",
    "tabs.evidenceBeingCollected": "正在收集证据",
    "tabs.evidenceCollectedDesc": "审查完成后，已验证的文件、符号和行引用将显示。",
    "tabs.metricsStillProcessing": "指标处理中",
    "tabs.metricsProcessingDesc": "结构化问题发现和持久化 Agent 状态就绪后，审查指标将最终确定。",
    "tabs.loadingReviewMetrics": "加载审查指标",
    "tabs.retryMetrics": "重试指标",
    "tabs.metricsLoadError": "无法加载指标",

    // Overview panel
    "overview.startReview": "开始仓库审查",
    "overview.startReviewDesc": "从控制面板导入公开的 GitHub 仓库。CodePilot 将映射仓库、运行四个审查 Agent，并组装基于证据的报告。",
    "overview.currentReview": "当前审查",
    "overview.agentsComplete": "Agent 已完成",
    "overview.findings": "问题发现",
    "overview.highRiskItems": "高风险问题",
    "overview.evidenceRefs": "证据引用",
    "overview.reviewComplete": "审查完成。结构化 Agent、问题发现、证据和指标数据已在工作台各标签中就绪。",
    "overview.reviewFailed": "最近一次执行未完成。持久化的进度仍可用于诊断。",
    "overview.reviewInterrupted": "审查中断",

    // Agent timeline
    "timeline.executionPipeline": "执行流水线",
    "timeline.reviewAgents": "审查 Agent",
    "timeline.complete": "已完成",
    "timeline.findings": "个问题",

    // Agent status
    "agentStatus.pending": "等待中",
    "agentStatus.running": "运行中",
    "agentStatus.completed": "已完成",
    "agentStatus.failed": "失败",
    "agentStatus.skipped": "已跳过",

    // Agent state cards
    "agentCards.notRecorded": "未记录 Agent 摘要",
    "agentCards.notRecordedDesc": "此审查早于持久化 Agent 摘要功能。报告仍可在「报告」标签中查看。",
    "agentCards.findings": "问题发现",
    "agentCards.evidence": "证据",
    "agentCards.avgConfidence": "平均置信度",
    "agentCards.severity": "严重程度",

    // Findings panel
    "findings.structuredData": "结构化审查数据",
    "findings.heading": "问题发现",
    "findings.total": "共",
    "findings.recommendedAction": "建议",
    "findings.impact": "影响",
    "findings.firstSafeStep": "第一步建议",
    "findings.validationTests": "验证方式",
    "findings.caveat": "注意事项",
    "findings.evidence": "证据",
    "findings.confidence": "置信度",
    "findings.noStructured": "暂无结构化问题",
    "findings.noStructuredDesc": "此审查未存储结构化问题发现。旧版报告内容仍可在「报告」标签中查看。",
    "findings.retryFindings": "重试问题发现",
    "findings.loadError": "无法加载问题发现",
    "findings.loading": "加载结构化问题发现",

    // Evidence panel
    "evidence.validatedRefs": "已验证引用",
    "evidence.heading": "证据",
    "evidence.chainTitle": "证据链",
    "evidence.references": "条引用",
    "evidence.symbol": "符号：",
    "evidence.supports": "支撑问题",
    "evidence.supportingFinding": "该证据用于支撑此问题的定位和结论。",
    "evidence.codeLocation": "代码位置",
    "evidence.relatedSymbol": "相关符号",
    "evidence.evidenceType": "证据类型",
    "evidence.evidenceId": "证据 ID",
    "evidence.showSnippet": "查看代码片段",
    "evidence.hideSnippet": "收起代码片段",
    "evidence.snippetNotAvailable": "当前仅展示代码定位信息，未展开源码片段。",
    "evidence.unlinkedEvidence": "未关联问题的证据",
    "evidence.supportingEvidence": "支撑证据",
    "evidence.locationUnavailable": "位置不可用",
    "evidence.noStructured": "暂无结构化证据",
    "evidence.noStructuredDesc": "此审查未持久化结构化证据引用。Markdown 报告可能包含旧版附录。",
    "evidence.retryEvidence": "重试证据",
    "evidence.loadError": "无法加载证据",
    "evidence.loading": "加载证据引用",

    // Metrics panel
    "metrics.telemetry": "审查遥测",
    "metrics.heading": "指标",
    "metrics.findings": "问题发现",
    "metrics.evidenceRefs": "证据引用",
    "metrics.agentRecords": "Agent 记录",
    "metrics.avgConfidence": "平均置信度",
    "metrics.severityDist": "严重程度分布",
    "metrics.riskSignal": "风险信号",
    "metrics.riskSignalDesc": "应在常规清理前优先处理的严重或高危问题发现。",
    "metrics.notRecorded": "暂无指标记录",
    "metrics.notRecordedDesc": "此旧版审查无结构化指标。请使用「报告」标签查看原始分析。",

    // Report panel
    "report.outline": "报告目录",
    "report.section": "报告章节",
    "report.legacyAppendices": "附录与仓库诊断",
    "report.inProgress": "报告生成中",
    "report.noReport": "未选择报告",
    "report.inProgressDesc": "报告将在审查 Agent 完成后组装。运行时进度仍可在总览和 Agent 中查看。",
    "report.noReportDesc": "选择已完成的审查或开始新的审查以查看其 Markdown 报告。",
    "report.sectionNav": "报告章节导航",

    // Review history panel
    "history.savedRuns": "已保存记录",
    "history.heading": "审查历史",
    "history.emptyDesc": "已完成和进行中的审查将显示在此处。",
    "history.retryHistory": "重试历史",
    "history.loadError": "无法加载审查历史。",
    "history.confirmDelete": "确认删除",
    "history.deleteReview": "删除审查",
    "history.loadingReviews": "加载历史审查",
    "history.confirm": "确认",

    // Export errors
    "export.reviewNotFound": "报告不存在，可能是后端重新部署后临时数据已清空。请重新运行审查。",
    "export.notReady": "当前报告尚不可导出，请等待审查完成或重新运行。",
    "export.networkError": "导出失败，请检查网络或稍后重试。",
    "export.staleHistoryRemoved": "该审查已不存在，已从历史记录中移除。",

    // Error page
    "error.title": "CodePilot 无法渲染此页面",
    "error.description": "您的审查数据是安全的。请重试页面，或从历史记录中重新加载之前的报告。",
    "error.retry": "重试",
    "error.providerAuth": "MiMo 尚未配置完成。请检查后端模型 Key 配置，然后重新运行审查。",
    "error.providerNetwork": "模型服务或网络请求超时。工作台仍可继续使用，请稍后重新运行审查。",
    "error.providerRateLimit": "模型服务触发限流。请稍候再试。",
    "error.reviewNoLongerAvailable": "该审查已不在服务器上，可能在重启后被清理。请重新运行仓库审查。",
    "error.startReviewFailed": "CodePilot 无法启动此审查。请检查仓库 URL 后重试。",
    "error.deleteReviewFailed": "CodePilot 无法删除此审查。请在历史记录中重试。",
    "error.generic": "出现异常，请重试。",

    // Loading page
    "loading.workspace": "加载 CodePilot 工作台",

    // Severity
    "severity.critical": "严重",
    "severity.high": "高",
    "severity.medium": "中",
    "severity.low": "低",
    "severity.informational": "信息",

    // Category
    "category.architecture": "架构",
    "category.code_smell": "代码质量",
    "category.maintainability": "可维护性",
    "category.refactor": "重构",

    // Validation status
    "validation.validated": "已验证",
    "validation.failed": "未通过验证",
    "validation.not_applicable": "不适用"
  }
};

export function t(language: Language, key: string): string {
  const value = dictionaries[language]?.[key];
  if (value !== undefined) return value;
  return dictionaries.en[key] ?? key;
}

const STATUS_KEYS: Record<string, string> = {
  pending: "status.pending",
  cloning: "status.cloning",
  parsing: "status.parsing",
  summarizing: "status.summarizing",
  reviewing: "status.reviewing",
  completed: "status.completed",
  failed: "status.failed"
};

export function getLocalizedStatusLabels(language: Language): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [status, key] of Object.entries(STATUS_KEYS)) {
    result[status] = t(language, key);
  }
  return result;
}

// ---------------------------------------------------------------------------
// Severity localization
// ---------------------------------------------------------------------------

const SEVERITY_KEYS: Record<string, string> = {
  critical: "severity.critical",
  high: "severity.high",
  medium: "severity.medium",
  low: "severity.low",
  informational: "severity.informational",
};

export function getLocalizedSeverity(language: Language, severity: string): string {
  const key = SEVERITY_KEYS[severity.toLowerCase()];
  return key ? t(language, key) : severity;
}

// ---------------------------------------------------------------------------
// Category localization
// ---------------------------------------------------------------------------

const CATEGORY_KEYS: Record<string, string> = {
  architecture: "category.architecture",
  code_smell: "category.code_smell",
  maintainability: "category.maintainability",
  refactor: "category.refactor",
};

export function getLocalizedCategory(language: Language, category: string): string {
  const key = CATEGORY_KEYS[category.toLowerCase()];
  return key ? t(language, key) : category;
}

// ---------------------------------------------------------------------------
// Validation status localization
// ---------------------------------------------------------------------------

const VALIDATION_STATUS_KEYS: Record<string, string> = {
  validated: "validation.validated",
  failed: "validation.failed",
  not_applicable: "validation.not_applicable",
};

export function getLocalizedValidationStatus(language: Language, status: string): string {
  const key = VALIDATION_STATUS_KEYS[status.toLowerCase()];
  return key ? t(language, key) : status;
}
