import type { FormEvent } from "react";
import React from "react";
import { Github, Loader2, Play } from "lucide-react";

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
    <form className="space-y-4" onSubmit={onSubmit}>
      <div className="space-y-2">
        <label className="text-xs font-semibold text-foreground" htmlFor="repo-url">
          GitHub repository
        </label>
        <div className="relative">
          <Github className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" />
          <Input
            aria-describedby={fieldError ? "repo-url-error" : "repo-url-help"}
            aria-invalid={Boolean(fieldError)}
            className="pl-9"
            id="repo-url"
            value={repoUrl}
            onChange={(event) => onRepoUrlChange(event.target.value)}
            placeholder="https://github.com/user/repo"
            required
            type="url"
          />
        </div>
        <p className="text-xs leading-5 text-muted-foreground" id="repo-url-help">
          Public HTTPS GitHub URLs only.
        </p>
      </div>
      {fieldError ? (
        <p className="text-xs leading-5 text-destructive" id="repo-url-error" role="alert">
          {fieldError}
        </p>
      ) : null}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-foreground" htmlFor="llm-mode-select">
          LLM Mode
        </label>
        <select
          className="flex h-11 w-full cursor-pointer rounded-lg border border-input bg-card px-3 py-2 text-base transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/25 disabled:cursor-not-allowed disabled:opacity-50 sm:text-sm"
          id="llm-mode-select"
          value={llmMode}
          onChange={(event) => onLlmModeChange(event.target.value as "mock" | "mimo")}
          disabled={submitting || isRunning}
        >
          <option value="mock">Mock LLM</option>
          <option value="mimo">MiMo Real LLM</option>
        </select>
        <p className="text-xs leading-5 text-muted-foreground">
          {llmMode === "mock"
            ? "Uses deterministic mock output. No API key required."
            : "Uses backend MiMo configuration. Requires MIMO_API_KEY in backend .env."}
        </p>
      </div>
      <Button className="w-full" disabled={submitting || isRunning} type="submit">
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        {isRunning ? "Review in progress" : "Start review"}
      </Button>
    </form>
  );
}
