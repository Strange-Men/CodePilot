import type { FormEvent } from "react";
import React from "react";
import { Loader2, Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type ReviewSubmissionFormProps = {
  fieldError: string | null;
  isRunning: boolean;
  onRepoUrlChange: (repoUrl: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  repoUrl: string;
  submitting: boolean;
};

export function ReviewSubmissionForm({
  fieldError,
  isRunning,
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
      <Button className="w-full" disabled={submitting || isRunning} type="submit">
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        Start Review
      </Button>
    </form>
  );
}
