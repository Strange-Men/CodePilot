import type {
  APIErrorPayload,
  LlmProvider,
  LlmProviderOption,
  ReviewAgentStatesResponse,
  ReviewFindingsResponse,
  ReviewResponse
} from "@/lib/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function createReview(
  repoUrl: string,
  llmMode: string = "mock",
  llmProvider: LlmProvider = "mimo"
): Promise<{ task_id: string; llm_mode: string; llm_provider?: LlmProvider | null }> {
  const payload: Record<string, string> = { repo_url: repoUrl, llm_mode: llmMode };
  if (llmMode !== "mock") payload.llm_provider = llmProvider;

  const response = await fetch(`${API_BASE}/api/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) throw await createApiError(response);
  return (await response.json()) as { task_id: string; llm_mode: string; llm_provider?: LlmProvider | null };
}

export async function getLlmProviders(): Promise<LlmProviderOption[]> {
  const response = await fetch(`${API_BASE}/api/llm/providers`);

  if (!response.ok) throw await createApiError(response);
  return (await response.json()) as LlmProviderOption[];
}

export async function getReview(taskId: string, opts?: { lang?: string }): Promise<ReviewResponse> {
  const langParam = opts?.lang && opts.lang !== "en" ? `?lang=${encodeURIComponent(opts.lang)}` : "";
  const response = await fetch(`${API_BASE}/api/reviews/${taskId}${langParam}`);

  if (!response.ok) throw await createApiError(response);
  return (await response.json()) as ReviewResponse;
}

export async function getReviewFindings(taskId: string, opts?: { lang?: string }): Promise<ReviewFindingsResponse> {
  const langParam = opts?.lang && opts.lang !== "en" ? `?lang=${encodeURIComponent(opts.lang)}` : "";
  const response = await fetch(`${API_BASE}/api/reviews/${taskId}/findings${langParam}`);

  if (!response.ok) throw await createApiError(response);
  return (await response.json()) as ReviewFindingsResponse;
}

export async function getReviewAgentStates(taskId: string): Promise<ReviewAgentStatesResponse> {
  const response = await fetch(`${API_BASE}/api/reviews/${taskId}/agent-states`);

  if (!response.ok) throw await createApiError(response);
  return (await response.json()) as ReviewAgentStatesResponse;
}

export async function deleteReview(taskId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/reviews/${taskId}`, {
    method: "DELETE"
  });

  if (!response.ok) throw await createApiError(response);
}

export async function listReviews(limit = 50): Promise<ReviewResponse[]> {
  const response = await fetch(`${API_BASE}/api/reviews?limit=${limit}`);

  if (!response.ok) throw await createApiError(response);
  return (await response.json()) as ReviewResponse[];
}

export function getReviewExportUrl(taskId: string, opts?: { lang?: string }): string {
  const langParam = opts?.lang && opts.lang !== "en" ? `?lang=${encodeURIComponent(opts.lang)}` : "";
  return `${API_BASE}/api/reviews/${taskId}/export${langParam}`;
}

export type ExportResult = {
  blob: Blob;
  filename: string;
};

export async function exportReview(taskId: string, opts?: { lang?: string }): Promise<ExportResult> {
  const langParam = opts?.lang && opts.lang !== "en" ? `?lang=${encodeURIComponent(opts.lang)}` : "";
  const response = await fetch(`${API_BASE}/api/reviews/${taskId}/export${langParam}`);

  if (!response.ok) {
    throw await createApiError(response);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition");
  let filename = `codepilot-review-${taskId.slice(0, 8)}-${opts?.lang || "en"}.md`;

  if (disposition) {
    const match = disposition.match(/filename="?([^";\n]+)"?/);
    if (match?.[1]) {
      filename = match[1];
    }
  }

  return { blob, filename };
}

export class CodePilotApiError extends Error {
  code: string;
  detail: string;

  constructor(payload: APIErrorPayload) {
    super(payload.detail || payload.error);
    this.name = "CodePilotApiError";
    this.code = payload.code;
    this.detail = payload.detail;
  }
}

async function createApiError(response: Response): Promise<CodePilotApiError> {
  try {
    const payload = (await response.json()) as Partial<APIErrorPayload>;
    return new CodePilotApiError({
      error: payload.error || `Request failed with status ${response.status}`,
      code: payload.code || "request_failed",
      detail: payload.detail || payload.error || "The request could not be completed."
    });
  } catch {
    return new CodePilotApiError({
      error: `Request failed with status ${response.status}`,
      code: "request_failed",
      detail: "The server returned an unreadable error response."
    });
  }
}
