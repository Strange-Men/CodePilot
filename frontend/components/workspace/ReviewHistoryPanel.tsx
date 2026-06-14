"use client";

import { Clock3, LoaderCircle, Trash2, X } from "lucide-react";
import React from "react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { STATUS_LABELS, terminalStatuses } from "@/lib/report";
import type { ReviewResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

type ReviewHistoryPanelProps = {
  error: string | null;
  loading: boolean;
  onDelete: (taskId: string) => Promise<void>;
  onRetry: () => void;
  onSelect: (review: ReviewResponse) => void;
  reviews: ReviewResponse[];
  selectedTaskId: string | null;
};

export function ReviewHistoryPanel({
  error,
  loading,
  onDelete,
  onRetry,
  onSelect,
  reviews,
  selectedTaskId
}: ReviewHistoryPanelProps) {
  const [confirmTaskId, setConfirmTaskId] = useState<string | null>(null);
  const [deletingTaskId, setDeletingTaskId] = useState<string | null>(null);

  async function removeReview(taskId: string) {
    if (confirmTaskId !== taskId) {
      setConfirmTaskId(taskId);
      return;
    }
    setDeletingTaskId(taskId);
    try {
      await onDelete(taskId);
      setConfirmTaskId(null);
    } finally {
      setDeletingTaskId(null);
    }
  }

  return (
    <section aria-labelledby="review-history-title" className="border-t border-border pt-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Saved runs
          </p>
          <h2 className="mt-1 text-sm font-semibold" id="review-history-title">
            Review history
          </h2>
        </div>
        <span className="font-mono text-xs text-muted-foreground">{reviews.length}</span>
      </div>

      {loading ? (
        <div className="mt-4 space-y-2" role="status">
          {Array.from({ length: 3 }, (_, index) => (
            <div className="skeleton h-16 rounded-lg" key={index} />
          ))}
          <span className="sr-only">Loading previous reviews</span>
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
          <p className="text-xs leading-5 text-destructive">{error}</p>
          <Button className="mt-2" onClick={onRetry} size="sm" type="button" variant="outline">
            Retry history
          </Button>
        </div>
      ) : null}

      {!loading && !error && reviews.length === 0 ? (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-dashed border-border p-3 text-xs leading-5 text-muted-foreground">
          <Clock3 className="mt-0.5 h-4 w-4 shrink-0" />
          Completed and in-progress reviews will appear here.
        </div>
      ) : null}

      <div className="mt-4 space-y-2">
        {reviews.map((review) => {
          const selected = selectedTaskId === review.task_id;
          const canDelete = terminalStatuses.includes(review.status);
          const confirming = confirmTaskId === review.task_id;
          return (
            <div
              className={cn(
                "group flex items-stretch gap-1 rounded-lg border p-1 transition-colors duration-200",
                selected ? "border-primary/40 bg-primary/5" : "border-border bg-card hover:bg-muted/60"
              )}
              key={review.task_id}
            >
              <button
                aria-pressed={selected}
                className="min-h-12 min-w-0 flex-1 cursor-pointer rounded-md px-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => onSelect(review)}
                type="button"
              >
                <span className="block truncate text-xs font-semibold">{repositoryName(review.repo_url)}</span>
                <span className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <span className={`h-1.5 w-1.5 rounded-full ${statusDot(review.status)}`} />
                  {STATUS_LABELS[review.status]}
                </span>
              </button>
              {canDelete ? (
                <Button
                  aria-label={confirming ? `Confirm delete ${repositoryName(review.repo_url)}` : `Delete ${repositoryName(review.repo_url)}`}
                  className={cn("self-center", confirming && "px-2 text-destructive")}
                  disabled={deletingTaskId === review.task_id}
                  onClick={() => void removeReview(review.task_id)}
                  size={confirming ? "sm" : "icon"}
                  title={confirming ? "Confirm delete" : "Delete review"}
                  type="button"
                  variant="ghost"
                >
                  {deletingTaskId === review.task_id ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : confirming ? (
                    <>
                      <X className="h-4 w-4" />
                      Confirm
                    </>
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function repositoryName(repoUrl: string): string {
  try {
    return new URL(repoUrl).pathname.split("/").filter(Boolean).slice(0, 2).join("/") || repoUrl;
  } catch {
    return repoUrl;
  }
}

function statusDot(status: ReviewResponse["status"]): string {
  if (status === "completed") return "bg-emerald-500";
  if (status === "failed") return "bg-destructive";
  return "animate-pulse bg-primary";
}
