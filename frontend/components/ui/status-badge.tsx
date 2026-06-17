import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Clock3,
  LoaderCircle,
  MinusCircle,
} from "lucide-react";
import React from "react";

import { cn } from "@/lib/utils";

type StatusBadgeStatus = "pending" | "queued" | "running" | "completed" | "failed" | "skipped" | "warning" | "idle";

type StatusBadgeProps = {
  className?: string;
  label: string;
  pulse?: boolean;
  size?: "sm" | "md";
  status: StatusBadgeStatus | string;
};

const statusStyles: Record<StatusBadgeStatus, string> = {
  pending: "border-border bg-muted/50 text-muted-foreground",
  queued: "border-border bg-muted/50 text-muted-foreground",
  running: "border-primary/35 bg-primary/10 text-primary",
  completed: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
  failed: "border-destructive/35 bg-destructive/10 text-destructive",
  skipped: "border-border bg-muted/40 text-muted-foreground",
  warning: "border-amber-500/35 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  idle: "border-border bg-card text-muted-foreground",
};

export function StatusBadge({
  className,
  label,
  pulse,
  size = "md",
  status,
}: StatusBadgeProps) {
  const normalized = normalizeStatus(status);
  const Icon = statusIcon(normalized);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-semibold",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "min-h-8 px-3 py-1 text-xs",
        statusStyles[normalized],
        className
      )}
      data-status-badge={normalized}
    >
      <Icon className={cn("h-3.5 w-3.5", (pulse || normalized === "running") && "animate-pulse")} />
      {label}
    </span>
  );
}

function normalizeStatus(status: string): StatusBadgeStatus {
  if (status === "cloning" || status === "parsing" || status === "summarizing" || status === "reviewing") {
    return "running";
  }
  if (status in statusStyles) return status as StatusBadgeStatus;
  return "idle";
}

function statusIcon(status: StatusBadgeStatus) {
  if (status === "completed") return CheckCircle2;
  if (status === "failed") return AlertTriangle;
  if (status === "running") return LoaderCircle;
  if (status === "skipped") return MinusCircle;
  if (status === "warning") return AlertTriangle;
  if (status === "queued" || status === "pending") return Clock3;
  return Circle;
}
