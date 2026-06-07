import { Github, RefreshCcw } from "lucide-react";

import { MarkdownContent } from "@/components/MarkdownContent";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { orderedSections, parseReport, repositoryMetricsSection } from "@/lib/report";

type ReportRendererProps = {
  isRunning: boolean;
  reportMarkdown: string | null | undefined;
};

export function ReportRenderer({ isRunning, reportMarkdown }: ReportRendererProps) {
  const sections = parseReport(reportMarkdown || "");

  if (reportMarkdown) {
    return (
      <>
        {sections[repositoryMetricsSection] ? (
          <Card>
            <CardHeader>
              <CardTitle>{repositoryMetricsSection}</CardTitle>
            </CardHeader>
            <CardContent>
              <MarkdownContent>{sections[repositoryMetricsSection]}</MarkdownContent>
            </CardContent>
          </Card>
        ) : null}
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
