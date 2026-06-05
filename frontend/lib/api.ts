import type { ReviewResponse } from "@/lib/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function createReview(repoUrl: string): Promise<{ task_id: string }> {
  const response = await fetch(`${API_BASE}/api/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl })
  });

  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as { task_id: string };
}

export async function getReview(taskId: string): Promise<ReviewResponse> {
  const response = await fetch(`${API_BASE}/api/reviews/${taskId}`);

  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as ReviewResponse;
}

export function getReviewExportUrl(taskId: string): string {
  return `${API_BASE}/api/reviews/${taskId}/export`;
}
