import { FileText, RefreshCcw } from "lucide-react";
import React from "react";

import { MarkdownContent } from "@/components/MarkdownContent";
import { EmptyState } from "@/components/workspace/EmptyState";
import {
  architectureGraphSection,
  legacyReportAppendixSections,
  parseReport
} from "@/lib/report";

type ReportPanelProps = {
  isRunning: boolean;
  reportMarkdown: string | null | undefined;
};

const deEmphasizedSections = new Set([
  ...legacyReportAppendixSections,
  "Evidence Appendix",
  architectureGraphSection
]);

export function ReportPanel({ isRunning, reportMarkdown }: ReportPanelProps) {
  if (!reportMarkdown) {
    return (
      <EmptyState
        description={
          isRunning
            ? "The report is assembled after the review agents finish. Runtime progress remains available in Overview and Agents."
            : "Select a completed review or start a new one to read its Markdown report."
        }
        icon={isRunning ? RefreshCcw : FileText}
        title={isRunning ? "Report generation is in progress" : "No report selected"}
      />
    );
  }

  const parsed = parseReport(reportMarkdown);
  const sections = Object.entries(parsed).filter(
    ([title, content]) => content.trim() && !deEmphasizedSections.has(title)
  );
  const appendices = Object.entries(parsed).filter(
    ([title, content]) => content.trim() && deEmphasizedSections.has(title)
  );

  if (!sections.length) {
    return (
      <article className="rounded-xl border border-border bg-card p-5 shadow-panel sm:p-7">
        <MarkdownContent>{reportMarkdown}</MarkdownContent>
      </article>
    );
  }

  return (
    <div className="grid gap-5 min-[1200px]:grid-cols-[220px_minmax(0,1fr)]">
      <aside className="hidden min-[1200px]:block">
        <nav
          aria-label="Report section navigation"
          className="sticky top-24 rounded-xl border border-border bg-card p-3 shadow-panel"
        >
          <p className="px-2 pb-2 font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Report outline
          </p>
          {sections.map(([title]) => (
            <a
              className="block rounded-lg px-2 py-2 text-sm text-muted-foreground transition-colors duration-200 hover:bg-muted hover:text-foreground"
              href={`#report-${slugify(title)}`}
              key={title}
            >
              {title}
            </a>
          ))}
        </nav>
      </aside>
      <div className="min-w-0 space-y-4">
        {sections.map(([title, content]) => (
          <section
            className="scroll-mt-24 rounded-xl border border-border bg-card p-5 shadow-panel sm:p-7"
            id={`report-${slugify(title)}`}
            key={title}
          >
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">
              Report section
            </p>
            <h2 className="mt-2 text-xl font-semibold tracking-tight">{title}</h2>
            <div className="mt-5">
              <MarkdownContent>{content}</MarkdownContent>
            </div>
          </section>
        ))}
        {appendices.length ? (
          <details className="rounded-xl border border-border bg-card shadow-panel">
            <summary className="min-h-11 cursor-pointer px-5 py-3 text-sm font-semibold text-muted-foreground transition-colors duration-200 hover:text-foreground sm:px-7">
              Legacy appendices and repository diagnostics
            </summary>
            <div className="space-y-5 border-t border-border p-5 sm:p-7">
              {appendices.map(([title, content]) => (
                <section key={title}>
                  <h2 className="text-sm font-semibold">{title}</h2>
                  <div className="mt-3">
                    <MarkdownContent>{content}</MarkdownContent>
                  </div>
                </section>
              ))}
            </div>
          </details>
        ) : null}
      </div>
    </div>
  );
}

function slugify(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}
