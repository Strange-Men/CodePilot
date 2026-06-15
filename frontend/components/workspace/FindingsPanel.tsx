import { FileWarning, RefreshCcw } from "lucide-react";
import React from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/workspace/EmptyState";
import type { ReviewFindingItem } from "@/lib/types";
import { cn } from "@/lib/utils";

type FindingsPanelProps = {
  error: string | null;
  findings: ReviewFindingItem[];
  loading: boolean;
  onRetry: () => void;
};

export function FindingsPanel({ error, findings, loading, onRetry }: FindingsPanelProps) {
  if (loading) return <PanelSkeleton rows={3} />;
  if (error) {
    return (
      <EmptyState
        actionLabel="Retry findings"
        description={error}
        icon={RefreshCcw}
        onAction={onRetry}
        title="Findings could not be loaded"
      />
    );
  }
  if (!findings.length) {
    return (
      <EmptyState
        description="No structured findings were stored for this review. Legacy report content is still available in the Report tab."
        icon={FileWarning}
        title="No structured findings"
      />
    );
  }

  return (
    <div className="space-y-4" data-structured-findings>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
            Structured review data
          </p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight">Findings</h2>
        </div>
        <span className="rounded-full border border-border bg-card px-3 py-1 font-mono text-xs text-muted-foreground">
          {findings.length} total
        </span>
      </div>

      {findings.map((finding) => (
        <article
          className="rounded-xl border border-border bg-card p-5 shadow-panel"
          data-finding-id={finding.finding_id}
          key={finding.finding_id}
        >
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={finding.severity} />
            <span className="text-xs text-muted-foreground">{finding.section}</span>
            <span className="ml-auto font-mono text-xs text-muted-foreground">
              {Math.round(finding.confidence * 100)}% confidence
            </span>
          </div>
          <h3 className="mt-4 text-base font-semibold tracking-tight">
            {finding.title || finding.description}
          </h3>
          {finding.title && finding.description ? (
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
              {finding.description}
            </p>
          ) : null}
          {finding.files.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {finding.files.map((file) => (
                <code
                  className="rounded-md border border-border bg-panel px-2 py-1 font-mono text-xs"
                  key={file}
                >
                  {file}
                </code>
              ))}
            </div>
          ) : null}
          {finding.recommendation ? (
            <div className="mt-4 border-l-2 border-primary/60 pl-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">Recommended action</p>
              <p className="mt-1 text-sm leading-6">{finding.recommendation}</p>
            </div>
          ) : null}
          {finding.impact ? (
            <div className="mt-3 border-l-2 border-amber-400/60 pl-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">Impact</p>
              <p className="mt-1 text-sm leading-6">{finding.impact}</p>
            </div>
          ) : null}
          {finding.first_step ? (
            <div className="mt-3 border-l-2 border-emerald-400/60 pl-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">First safe step</p>
              <p className="mt-1 text-sm leading-6">{finding.first_step}</p>
            </div>
          ) : null}
          {finding.validation_tests.length ? (
            <div className="mt-3 pl-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Validation tests</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {finding.validation_tests.map((test) => (
                  <code
                    className="rounded-md border border-border bg-panel px-2 py-0.5 font-mono text-xs"
                    key={test}
                  >
                    {test}
                  </code>
                ))}
              </div>
            </div>
          ) : null}
          {finding.caveat ? (
            <div className="mt-3 rounded-md border border-dashed border-muted-foreground/30 bg-muted/30 px-4 py-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Caveat</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{finding.caveat}</p>
            </div>
          ) : null}
          {finding.evidence_ids.length ? (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
              <span className="text-muted-foreground">Evidence</span>
              {finding.evidence_ids.map((evidenceId) => (
                <code
                  className="rounded-md border border-primary/25 bg-primary/5 px-2 py-1 font-mono font-semibold text-primary"
                  key={evidenceId}
                >
                  {evidenceId}
                </code>
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const normalized = severity.toLowerCase();
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide",
        severityStyles[normalized] || severityStyles.informational
      )}
      data-severity={normalized}
    >
      {severity}
    </span>
  );
}

const severityStyles: Record<string, string> = {
  critical: "border-red-300 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300",
  high: "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-900 dark:bg-orange-950/50 dark:text-orange-300",
  medium: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300",
  low: "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-900 dark:bg-sky-950/50 dark:text-sky-300",
  informational: "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
};

function PanelSkeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-4" role="status">
      <div className="skeleton h-8 w-44 rounded-lg" />
      {Array.from({ length: rows }, (_, index) => (
        <div className="rounded-xl border border-border bg-card p-5" key={index}>
          <div className="skeleton h-5 w-28 rounded" />
          <div className="skeleton mt-5 h-6 w-2/3 rounded" />
          <div className="skeleton mt-3 h-4 w-full rounded" />
          <div className="skeleton mt-2 h-4 w-4/5 rounded" />
        </div>
      ))}
      <span className="sr-only">Loading structured findings</span>
    </div>
  );
}
