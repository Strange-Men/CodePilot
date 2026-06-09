import React from "react";
import { Github, RefreshCcw } from "lucide-react";

import { MarkdownContent } from "@/components/MarkdownContent";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  legacyReportAppendixSections,
  orderedSections,
  parseReport,
  reportClosingSections,
  reportOverviewSections
} from "@/lib/report";

type ReportRendererProps = {
  isRunning: boolean;
  reportMarkdown: string | null | undefined;
};

export function ReportRenderer({ isRunning, reportMarkdown }: ReportRendererProps) {
  const sections = parseReport(reportMarkdown || "");

  if (reportMarkdown) {
    return (
      <>
        {[...reportOverviewSections, ...legacyReportAppendixSections].map((section) =>
          sections[section] ? (
            <Card key={section}>
              <CardHeader>
                <CardTitle>{section}</CardTitle>
              </CardHeader>
              <CardContent>
                <MarkdownContent>{sections[section]}</MarkdownContent>
              </CardContent>
            </Card>
          ) : null
        )}
        {orderedSections.map((section) => (
          <Card key={section}>
            <CardHeader>
              <CardTitle>{section}</CardTitle>
            </CardHeader>
            <CardContent>
              <MarkdownContent>{sections[section] || "No findings returned."}</MarkdownContent>
            </CardContent>
          </Card>
        ))}
        {reportClosingSections.map((section) =>
          sections[section] ? (
            <Card key={section}>
              <CardHeader>
                <CardTitle>{section}</CardTitle>
              </CardHeader>
              <CardContent>
                <MarkdownContent>{sections[section]}</MarkdownContent>
              </CardContent>
            </Card>
          ) : null
        )}
      </>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Review Report</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex min-h-[280px] flex-col items-center justify-center gap-3 rounded-md border border-dashed border-border bg-background p-8 text-center">
          {isRunning ? <RefreshCcw className="h-8 w-8 animate-spin text-primary" /> : <Github className="h-8 w-8 text-muted-foreground" />}
          <p className="max-w-md text-sm leading-6 text-muted-foreground">
            {isRunning
              ? "CodePilot is cloning, parsing, summarizing, and reviewing the repository."
              : "Start a review to see the generated architecture, smell, maintainability, and refactoring sections here."}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
