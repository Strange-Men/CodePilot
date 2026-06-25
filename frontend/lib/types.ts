export type ReviewStatus =
  | "pending"
  | "cloning"
  | "parsing"
  | "summarizing"
  | "reviewing"
  | "completed"
  | "failed";

export type AgentProgressStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export type LlmMode = "mock" | "mimo";

export type LlmProvider = "mimo" | "doubao" | "deepseek";

export type LlmProviderOption = {
  value: LlmProvider;
  label: string;
  available?: boolean;
};

export type AgentProgressItem = {
  order: number;
  label: string;
  agent_id: string;
  status: AgentProgressStatus;
  findings_count: number | null;
  evidence_count: number | null;
  error: string | null;
};

export type ReviewProgressSnapshot = {
  current_phase: string;
  current_agent_id: string | null;
  total_agents: number;
  completed_agents: number;
  agents: AgentProgressItem[];
};

export type ReviewResponse = {
  task_id: string;
  repo_url: string;
  status: ReviewStatus;
  error: string | null;
  report_markdown: string | null;
  export_path: string | null;
  progress?: ReviewProgressSnapshot | null;
};

export type ReviewEvidenceRefItem = {
  evidence_id: string;
  file_path: string | null;
  symbol_name: string | null;
  start_line: number;
  end_line: number;
};

export type ReviewFindingItem = {
  finding_id: string;
  finding_index: number;
  section: string;
  title: string;
  description: string;
  severity: string;
  category: string | null;
  confidence: number;
  recommendation: string | null;
  files: string[];
  evidence_ids: string[];
  evidence_refs: ReviewEvidenceRefItem[];
  validation_status: string | null;
  impact: string | null;
  first_step: string | null;
  validation_tests: string[];
  confidence_rationale: string | null;
  caveat: string | null;
};

export type ReviewFindingsResponse = {
  task_id: string;
  findings: ReviewFindingItem[];
  evidence_display_map: Record<string, string>;
};

export type SeverityMix = {
  critical: number;
  high: number;
  medium: number;
  low: number;
};

export type ReviewAgentStateItem = {
  order: number;
  agent_id: string;
  label: string;
  status: string;
  findings_count: number;
  evidence_count: number;
  severity_mix: SeverityMix;
  average_confidence: number | null;
  error: string | null;
};

export type ReviewAgentStatesResponse = {
  task_id: string;
  agents: ReviewAgentStateItem[];
};

export type APIErrorPayload = {
  error: string;
  code: string;
  detail: string;
};
