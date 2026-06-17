import { FileWarning, RefreshCcw } from "lucide-react";
import React from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/workspace/EmptyState";
import { formatEvidenceDisplayRef } from "@/lib/evidence";
import type { Language } from "@/lib/i18n";
import { getLocalizedSeverity, t } from "@/lib/i18n";
import type { ReviewFindingItem } from "@/lib/types";
import { cn } from "@/lib/utils";

type FindingsPanelProps = {
  error: string | null;
  findings: ReviewFindingItem[];
  evidenceDisplayMap?: Record<string, string>;
  language: Language;
  loading: boolean;
  onRetry: () => void;
};

export function FindingsPanel({ error, findings, evidenceDisplayMap = {}, language, loading, onRetry }: FindingsPanelProps) {
  if (loading) return <PanelSkeleton language={language} rows={3} />;
  if (error) {
    return (
      <EmptyState
        actionLabel={t(language, "findings.retryFindings")}
        description={error}
        icon={RefreshCcw}
        onAction={onRetry}
        title={t(language, "findings.loadError")}
      />
    );
  }
  if (!findings.length) {
    return (
      <EmptyState
        description={t(language, "findings.noStructuredDesc")}
        icon={FileWarning}
        title={t(language, "findings.noStructured")}
      />
    );
  }

  return (
    <div className="space-y-4" data-structured-findings>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
            {t(language, "findings.structuredData")}
          </p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight">{t(language, "findings.heading")}</h2>
        </div>
        <span className="rounded-full border border-border bg-card px-3 py-1 font-mono text-xs text-muted-foreground">
          {language === "zh" ? `${t(language, "findings.total")} ${findings.length} 项` : `${findings.length} ${t(language, "findings.total")}`}
        </span>
      </div>

      {findings.map((finding) => (
        <article
          className="rounded-xl border border-border bg-card p-5 shadow-panel transition-colors duration-200 hover:border-primary/25 sm:p-6"
          data-finding-id={finding.finding_id}
          key={finding.finding_id}
        >
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge language={language} severity={finding.severity} />
            <span className="text-xs text-muted-foreground">{finding.section}</span>
            <span className="ml-auto font-mono text-xs text-muted-foreground">
              {t(language, "findings.confidence")} {Math.round(finding.confidence * 100)}%
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
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">{t(language, "findings.recommendedAction")}</p>
              <p className="mt-1 text-sm leading-6">{finding.recommendation}</p>
            </div>
          ) : null}
          {finding.impact ? (
            <div className="mt-3 border-l-2 border-amber-400/60 pl-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">{t(language, "findings.impact")}</p>
              <p className="mt-1 text-sm leading-6">{finding.impact}</p>
            </div>
          ) : null}
          {finding.first_step ? (
            <div className="mt-3 border-l-2 border-emerald-400/60 pl-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">{t(language, "findings.firstSafeStep")}</p>
              <p className="mt-1 text-sm leading-6">{finding.first_step}</p>
            </div>
          ) : null}
          {finding.validation_tests.length ? (
            <div className="mt-3 pl-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t(language, "findings.validationTests")}</p>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {finding.validation_tests.map((test) => (
                  <li className="text-sm leading-5" key={test}>
                    {isCommandOrPath(test) ? (
                      <code className="rounded-md border border-border bg-panel px-1.5 py-0.5 font-mono text-xs">{test}</code>
                    ) : (
                      test
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {finding.caveat ? (
            <div className="mt-3 rounded-md border border-dashed border-muted-foreground/30 bg-muted/30 px-4 py-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t(language, "findings.caveat")}</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{finding.caveat}</p>
            </div>
          ) : null}
          {finding.evidence_ids.length ? (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
              <span className="text-muted-foreground">{t(language, "findings.evidence")}</span>
              {finding.evidence_ids.map((evidenceId) => (
                <code
                  className="rounded-md border border-primary/25 bg-primary/5 px-2 py-1 font-mono font-semibold text-primary"
                  key={evidenceId}
                >
                  {formatEvidenceDisplayRef(evidenceId, evidenceDisplayMap)}
                </code>
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

export function SeverityBadge({ language, severity }: { language: Language; severity: string }) {
  const normalized = severity.toLowerCase();
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide",
        severityStyles[normalized] || severityStyles.informational
      )}
      data-severity={normalized}
    >
      {getLocalizedSeverity(language, severity)}
    </span>
  );
}

/** Check if text looks like a command or file path (should stay code-styled). */
function isCommandOrPath(text: string): boolean {
  const trimmed = text.trim();
  // Starts with a command-like prefix
  if (/^(python|npm|pip|pytest|git|cd|ls|cat|grep|make|cargo|go|java|node)\b/i.test(trimmed)) return true;
  // Contains file path patterns
  if (/[\\/][\w.-]+\.\w+/.test(trimmed)) return true;
  // Looks like a shell command
  if (/^\$|^>\s/.test(trimmed)) return true;
  return false;
}

const severityStyles: Record<string, string> = {
  critical: "border-red-300 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300",
  high: "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-900 dark:bg-orange-950/50 dark:text-orange-300",
  medium: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300",
  low: "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-900 dark:bg-sky-950/50 dark:text-sky-300",
  informational: "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
};

function PanelSkeleton({ language, rows }: { language: Language; rows: number }) {
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
      <span className="sr-only">{t(language, "findings.loading")}</span>
    </div>
  );
}
