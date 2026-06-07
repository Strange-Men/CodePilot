export type ReviewStatus =
  | "pending"
  | "cloning"
  | "parsing"
  | "summarizing"
  | "reviewing"
  | "completed"
  | "failed";

export type ReviewResponse = {
  task_id: string;
  repo_url: string;
  status: ReviewStatus;
  error: string | null;
  report_markdown: string | null;
  export_path: string | null;
};

export type APIErrorPayload = {
  error: string;
  code: string;
  detail: string;
};
