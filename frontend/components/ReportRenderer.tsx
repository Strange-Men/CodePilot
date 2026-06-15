import React from "react";

import { ReportPanel } from "@/components/workspace/ReportPanel";
import type { Language } from "@/lib/i18n";

type ReportRendererProps = {
  isRunning: boolean;
  language?: Language;
  reportMarkdown: string | null | undefined;
};

export function ReportRenderer({ isRunning, language, reportMarkdown }: ReportRendererProps) {
  return <ReportPanel isRunning={isRunning} language={language || "en"} reportMarkdown={reportMarkdown} />;
}
