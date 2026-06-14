import { Braces, FileSearch, RefreshCcw } from "lucide-react";
import React from "react";

import { EmptyState } from "@/components/workspace/EmptyState";
import type { ReviewEvidenceRefItem, ReviewFindingItem } from "@/lib/types";

type EvidencePanelProps = {
  error: string | null;
  findings: ReviewFindingItem[];
  loading: boolean;
  onRetry: () => void;
};

type EvidenceItem = ReviewEvidenceRefItem & {
  findingTitles: string[];
};

export function EvidencePanel({ error, findings, loading, onRetry }: EvidencePanelProps) {
  if (loading) {
    return (
      <div className="grid gap-4 lg:grid-cols-2" role="status">
        {Array.from({ length: 4 }, (_, index) => (
          <div className="skeleton h-40 rounded-xl" key={index} />
        ))}
        <span className="sr-only">Loading evidence references</span>
      </div>
    );
  }
  if (error) {
    return (
      <EmptyState
        actionLabel="Retry evidence"
        description={error}
        icon={RefreshCcw}
        onAction={onRetry}
        title="Evidence could not be loaded"
      />
    );
  }

  const evidence = collectEvidence(findings);
  if (!evidence.length) {
    return (
      <EmptyState
        description="No structured evidence references were persisted for this review. The Markdown report may contain a legacy appendix."
        icon={FileSearch}
        title="No structured evidence"
      />
    );
  }

  return (
    <div data-structured-evidence>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
            Validated references
          </p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight">Evidence</h2>
        </div>
        <span className="font-mono text-xs text-muted-foreground">{evidence.length} references</span>
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        {evidence.map((item) => (
          <article
            className="rounded-xl border border-border bg-card p-5 shadow-panel"
            data-evidence-id={item.evidence_id}
            key={item.evidence_id}
          >
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/5 text-primary">
                <Braces className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <code className="break-all font-mono text-sm font-semibold text-primary">
                  {item.evidence_id}
                </code>
                <p className="mt-2 break-words font-mono text-xs text-muted-foreground">
                  {formatLocation(item)}
                </p>
              </div>
            </div>
            {item.symbol_name ? (
              <p className="mt-4 text-sm">
                <span className="text-muted-foreground">Symbol:</span>{" "}
                <code className="font-mono">{item.symbol_name}</code>
              </p>
            ) : null}
            <div className="mt-4 border-t border-border pt-3">
              <p className="text-xs font-medium text-muted-foreground">Supports</p>
              <p className="mt-1 text-sm leading-5">{item.findingTitles.join(", ")}</p>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function collectEvidence(findings: ReviewFindingItem[]): EvidenceItem[] {
  const evidence = new Map<string, EvidenceItem>();
  for (const finding of findings) {
    const title = finding.title || finding.description;
    for (const reference of finding.evidence_refs) {
      const current = evidence.get(reference.evidence_id);
      evidence.set(reference.evidence_id, {
        ...reference,
        findingTitles: current
          ? [...new Set([...current.findingTitles, title])]
          : [title]
      });
    }
    for (const evidenceId of finding.evidence_ids) {
      if (!evidence.has(evidenceId)) {
        evidence.set(evidenceId, {
          evidence_id: evidenceId,
          file_path: null,
          symbol_name: null,
          start_line: 0,
          end_line: 0,
          findingTitles: [title]
        });
      }
    }
  }
  return [...evidence.values()];
}

function formatLocation(item: ReviewEvidenceRefItem): string {
  if (!item.file_path) return "Location unavailable";
  if (!item.start_line) return item.file_path;
  const lines = item.end_line && item.end_line !== item.start_line
    ? `${item.start_line}-${item.end_line}`
    : String(item.start_line);
  return `${item.file_path}:${lines}`;
}
