import { Braces, ChevronDown, ChevronRight, Copy, FileSearch, RefreshCcw } from "lucide-react";
import React, { useState } from "react";

import { EmptyState } from "@/components/workspace/EmptyState";
import { SeverityBadge } from "@/components/workspace/FindingsPanel";
import type { Language } from "@/lib/i18n";
import { t } from "@/lib/i18n";
import type { ReviewEvidenceRefItem, ReviewFindingItem } from "@/lib/types";

type EvidencePanelProps = {
  error: string | null;
  findings: ReviewFindingItem[];
  evidenceDisplayMap?: Record<string, string>;
  language: Language;
  loading: boolean;
  onRetry: () => void;
};

type FindingEvidenceGroup = {
  finding: ReviewFindingItem;
  evidence: ReviewEvidenceRefItem[];
};

export function EvidencePanel({ error, findings, evidenceDisplayMap = {}, language, loading, onRetry }: EvidencePanelProps) {
  if (loading) {
    return (
      <div className="grid gap-4 lg:grid-cols-2" role="status">
        {Array.from({ length: 4 }, (_, index) => (
          <div className="skeleton h-40 rounded-xl" key={index} />
        ))}
        <span className="sr-only">{t(language, "evidence.loading")}</span>
      </div>
    );
  }
  if (error) {
    return (
      <EmptyState
        actionLabel={t(language, "evidence.retryEvidence")}
        description={error}
        icon={RefreshCcw}
        onAction={onRetry}
        title={t(language, "evidence.loadError")}
      />
    );
  }

  const { groups, unlinked } = groupEvidenceByFinding(findings);
  const totalEvidence = groups.reduce((sum, g) => sum + g.evidence.length, 0) + unlinked.length;

  if (!totalEvidence) {
    return (
      <EmptyState
        description={t(language, "evidence.noStructuredDesc")}
        icon={FileSearch}
        title={t(language, "evidence.noStructured")}
      />
    );
  }

  return (
    <div data-structured-evidence>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
            {t(language, "evidence.validatedRefs")}
          </p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight">
            {language === "zh" ? t(language, "evidence.chainTitle") : t(language, "evidence.heading")}
          </h2>
        </div>
        <span className="font-mono text-xs text-muted-foreground">
          {totalEvidence} {t(language, "evidence.references")}
        </span>
      </div>

      <div className="mt-5 space-y-4">
        {groups.map((group) => (
          <FindingEvidenceCard
            finding={group.finding}
            evidence={group.evidence}
            evidenceDisplayMap={evidenceDisplayMap}
            language={language}
            key={group.finding.finding_id}
          />
        ))}
        {unlinked.length ? (
          <section className="rounded-xl border border-dashed border-muted-foreground/30 bg-muted/20 p-5">
            <h3 className="text-sm font-semibold text-muted-foreground">
              {t(language, "evidence.unlinkedEvidence")}
            </h3>
            <div className="mt-3 space-y-3">
              {unlinked.map((item) => (
                <EvidenceItemCard item={item} evidenceDisplayMap={evidenceDisplayMap} language={language} key={item.evidence_id} />
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}

function FindingEvidenceCard({
  finding,
  evidence,
  evidenceDisplayMap,
  language,
}: {
  finding: ReviewFindingItem;
  evidence: ReviewEvidenceRefItem[];
  evidenceDisplayMap: Record<string, string>;
  language: Language;
}) {
  return (
    <section className="rounded-xl border border-border bg-card shadow-panel">
      {/* Finding header */}
      <div className="border-b border-border px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge language={language} severity={finding.severity} />
          <span className="ml-auto font-mono text-xs text-muted-foreground">
            {Math.round(finding.confidence * 100)}%
          </span>
        </div>
        <h3 className="mt-2 text-sm font-semibold tracking-tight">
          {finding.title || finding.description}
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          {t(language, "evidence.supportingEvidence")}：{evidence.length} {t(language, "evidence.references")}
        </p>
      </div>

      {/* Evidence items */}
      <div className="divide-y divide-border">
        {evidence.map((item) => (
          <EvidenceItemCard item={item} evidenceDisplayMap={evidenceDisplayMap} language={language} key={item.evidence_id} />
        ))}
      </div>
    </section>
  );
}

function EvidenceItemCard({ item, evidenceDisplayMap, language }: { item: ReviewEvidenceRefItem; evidenceDisplayMap: Record<string, string>; language: Language }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(item.evidence_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API may not be available
    }
  };

  const displayRef = evidenceDisplayMap[item.evidence_id] || item.evidence_id;

  return (
    <div className="px-5 py-4" data-evidence-id={item.evidence_id}>
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/5 text-primary font-mono text-xs font-bold">
          {displayRef}
        </div>
        <div className="min-w-0 flex-1">
          {/* Code location */}
          <p className="font-mono text-xs text-muted-foreground">
            {t(language, "evidence.codeLocation")}：
            <span className="text-foreground">{formatLocation(item, language)}</span>
          </p>

          {/* Symbol */}
          {item.symbol_name ? (
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              {t(language, "evidence.relatedSymbol")}：
              <code className="ml-1 rounded border border-border bg-panel px-1.5 py-0.5 text-foreground">
                {item.symbol_name}
              </code>
            </p>
          ) : null}

          {/* Supporting finding explanation */}
          <p className="mt-2 text-xs text-muted-foreground">
            {t(language, "evidence.supportingFinding")}
          </p>

          {/* Evidence ID — secondary, copyable */}
          <div className="mt-2 flex items-center gap-2">
            <span className="font-mono text-[10px] text-muted-foreground/70">
              {t(language, "evidence.evidenceId")}:
            </span>
            <code className="rounded border border-border bg-panel px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              {item.evidence_id}
            </code>
            <button
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              onClick={handleCopy}
              title={t(language, "evidence.evidenceId")}
              type="button"
            >
              <Copy className="h-3 w-3" />
              {copied ? "✓" : ""}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function groupEvidenceByFinding(findings: ReviewFindingItem[]): {
  groups: FindingEvidenceGroup[];
  unlinked: ReviewEvidenceRefItem[];
} {
  const groups: FindingEvidenceGroup[] = [];
  const seenEvidenceIds = new Set<string>();

  for (const finding of findings) {
    const evidence: ReviewEvidenceRefItem[] = [];
    for (const ref of finding.evidence_refs) {
      if (!seenEvidenceIds.has(ref.evidence_id)) {
        seenEvidenceIds.add(ref.evidence_id);
        evidence.push(ref);
      }
    }
    // Also include evidence_ids that don't have refs
    for (const evidenceId of finding.evidence_ids) {
      if (!seenEvidenceIds.has(evidenceId)) {
        seenEvidenceIds.add(evidenceId);
        evidence.push({
          evidence_id: evidenceId,
          file_path: null,
          symbol_name: null,
          start_line: 0,
          end_line: 0,
        });
      }
    }
    if (evidence.length) {
      groups.push({ finding, evidence });
    }
  }

  // Collect any evidence that wasn't linked to a finding
  const unlinked: ReviewEvidenceRefItem[] = [];
  // (In practice, all evidence should be linked to findings)

  return { groups, unlinked };
}

function formatLocation(item: ReviewEvidenceRefItem, language: Language): string {
  if (!item.file_path) return t(language, "evidence.locationUnavailable");
  if (!item.start_line) return item.file_path;
  const lines = item.end_line && item.end_line !== item.start_line
    ? `${item.start_line}-${item.end_line}`
    : String(item.start_line);
  return `${item.file_path}:${lines}`;
}
