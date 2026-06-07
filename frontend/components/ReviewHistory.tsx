import React from "react";
import { Clock3, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { STATUS_LABELS } from "@/lib/report";
import type { ReviewResponse } from "@/lib/types";

type ReviewHistoryProps = {
  error: string | null;
  loading: boolean;
  onSelect: (review: ReviewResponse) => void;
  reviews: ReviewResponse[];
  selectedTaskId: string | null;
};

export function ReviewHistory({
  error,
  loading,
  onSelect,
  reviews,
  selectedTaskId
}: ReviewHistoryProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Review History</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading previous reviews
          </div>
        ) : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {!loading && !error && reviews.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock3 className="h-4 w-4" />
            Completed and in-progress reviews will appear here.
          </div>
        ) : null}
        <div className="space-y-2">
          {reviews.map((review) => (
            <Button
              aria-pressed={selectedTaskId === review.task_id}
              className="h-auto w-full justify-start px-3 py-2 text-left"
              key={review.task_id}
              onClick={() => onSelect(review)}
              type="button"
              variant={selectedTaskId === review.task_id ? "default" : "outline"}
            >
              <span className="min-w-0">
                <span className="block truncate">{repositoryName(review.repo_url)}</span>
                <span className="block text-xs opacity-75">{STATUS_LABELS[review.status]}</span>
              </span>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function repositoryName(repoUrl: string): string {
  try {
    const parts = new URL(repoUrl).pathname.split("/").filter(Boolean);
    return parts.slice(0, 2).join("/") || repoUrl;
  } catch {
    return repoUrl;
  }
}
