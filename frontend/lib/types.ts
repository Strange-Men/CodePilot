export type ReviewStatus =
  | "pending"
  | "cloning"
  | "parsing"
  | "summarizing"
  | "reviewing"
  | "completed"
  | "failed";

export type AgentProgressStatus = "pending" | "running" | "completed" | "failed" | "skipped";

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

export type APIErrorPayload = {
  error: string;
  code: string;
  detail: string;
};
