import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getReviewExportUrl } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/report";
import type { ReviewResponse, ReviewStatus } from "@/lib/types";

type ReviewStatusDisplayProps = {
  error: string | null;
  isRunning: boolean;
  review: ReviewResponse | null;
  taskId: string | null;
};

export function ReviewStatusDisplay({ error, isRunning, review, taskId }: ReviewStatusDisplayProps) {
  return (
    <div className="mt-5 space-y-3">
      <StatusRow label="Task" value={taskId || "Not started"} />
      <StatusRow label="Status" value={review ? STATUS_LABELS[review.status] : "Idle"} />
      {isRunning && review ? <ProgressRail status={review.status} /> : null}
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
      {review?.status === "completed" ? (
        <Button asChild className="w-full" variant="outline">
          <a href={getReviewExportUrl(review.task_id)}>
            <Download className="h-4 w-4" />
            Export Markdown
          </a>
        </Button>
      ) : null}
    </div>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md bg-background px-3 py-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate font-medium">{value}</span>
    </div>
  );
}

function ProgressRail({ status }: { status: ReviewStatus }) {
  const statuses: ReviewStatus[] = ["pending", "cloning", "parsing", "summarizing", "reviewing", "completed"];
  const activeIndex = statuses.indexOf(status);
  return (
    <div className="grid grid-cols-6 gap-1" aria-label="Review progress">
      {statuses.map((item, index) => (
        <div
          className={`h-2 rounded-sm ${index <= activeIndex ? "bg-primary" : "bg-muted"}`}
          key={item}
          title={STATUS_LABELS[item]}
        />
      ))}
    </div>
  );
}
