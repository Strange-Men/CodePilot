import type { FormEvent } from "react";
import React from "react";
import { Loader2, Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type ReviewSubmissionFormProps = {
  fieldError: string | null;
  isRunning: boolean;
  llmMode: "mock" | "mimo";
  onLlmModeChange: (mode: "mock" | "mimo") => void;
  onRepoUrlChange: (repoUrl: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  repoUrl: string;
  submitting: boolean;
};

export function ReviewSubmissionForm({
  fieldError,
  isRunning,
  llmMode,
  onLlmModeChange,
  onRepoUrlChange,
  onSubmit,
  repoUrl,
  submitting
}: ReviewSubmissionFormProps) {
  return (
    <form className="space-y-3" onSubmit={onSubmit}>
      <Input
        aria-label="GitHub repository URL"
        aria-describedby={fieldError ? "repo-url-error" : undefined}
        aria-invalid={Boolean(fieldError)}
        value={repoUrl}
        onChange={(event) => onRepoUrlChange(event.target.value)}
        placeholder="https://github.com/user/repo"
        required
        type="url"
      />
      {fieldError ? (
        <p className="text-sm text-destructive" id="repo-url-error">
          {fieldError}
        </p>
      ) : null}
      <div className="space-y-1.5">
        <label className="text-sm font-medium text-foreground" htmlFor="llm-mode-select">
          LLM Mode
        </label>
        <select
          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          id="llm-mode-select"
          value={llmMode}
          onChange={(event) => onLlmModeChange(event.target.value as "mock" | "mimo")}
          disabled={submitting || isRunning}
        >
          <option value="mock">Mock LLM</option>
          <option value="mimo">MiMo Real LLM</option>
        </select>
        <p className="text-xs text-muted-foreground">
          {llmMode === "mock"
            ? "Uses deterministic mock output. No API key required."
            : "Uses backend MiMo configuration. Requires MIMO_API_KEY in backend .env."}
        </p>
      </div>
      <Button className="w-full" disabled={submitting || isRunning} type="submit">
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        Start Review
      </Button>
    </form>
  );
}
