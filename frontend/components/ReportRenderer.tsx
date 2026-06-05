import { Github, RefreshCcw } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { orderedSections, parseReport } from "@/lib/report";

type ReportRendererProps = {
  isRunning: boolean;
  reportMarkdown: string | null | undefined;
};

export function ReportRenderer({ isRunning, reportMarkdown }: ReportRendererProps) {
  const sections = parseReport(reportMarkdown || "");

  if (reportMarkdown) {
    return (
      <>
        {orderedSections.map((section) => (
          <Card key={section}>
            <CardHeader>
              <CardTitle>{section}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="whitespace-pre-wrap text-sm leading-6 text-foreground">{sections[section] || "No findings returned."}</div>
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
