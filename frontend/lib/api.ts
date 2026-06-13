import type { APIErrorPayload, ReviewResponse } from "@/lib/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function createReview(repoUrl: string, llmMode: string = "mock"): Promise<{ task_id: string; llm_mode: string }> {
  const response = await fetch(`${API_BASE}/api/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl, llm_mode: llmMode })
  });

  if (!response.ok) throw await createApiError(response);
  return (await response.json()) as { task_id: string; llm_mode: string };
}

export async function getReview(taskId: string): Promise<ReviewResponse> {
  const response = await fetch(`${API_BASE}/api/reviews/${taskId}`);

  if (!response.ok) throw await createApiError(response);
  return (await response.json()) as ReviewResponse;
}

export async function listReviews(limit = 50): Promise<ReviewResponse[]> {
  const response = await fetch(`${API_BASE}/api/reviews?limit=${limit}`);

  if (!response.ok) throw await createApiError(response);
  return (await response.json()) as ReviewResponse[];
}

export function getReviewExportUrl(taskId: string): string {
  return `${API_BASE}/api/reviews/${taskId}/export`;
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
