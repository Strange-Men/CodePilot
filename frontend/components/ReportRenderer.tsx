import React from "react";

import { ReportPanel } from "@/components/workspace/ReportPanel";

type ReportRendererProps = {
  isRunning: boolean;
  reportMarkdown: string | null | undefined;
};

export function ReportRenderer({ isRunning, reportMarkdown }: ReportRendererProps) {
  return <ReportPanel isRunning={isRunning} reportMarkdown={reportMarkdown} />;
}
