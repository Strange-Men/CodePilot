import type { FormEvent } from "react";
import React from "react";
import { FlaskConical, Github, KeyRound, Loader2, Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Language } from "@/lib/i18n";
import { t, tp } from "@/lib/i18n";
import type { LlmMode, LlmProvider, LlmProviderOption } from "@/lib/types";

type ReviewSubmissionFormProps = {
  fieldError: string | null;
  isRunning: boolean;
  language: Language;
  llmMode: LlmMode;
  llmProvider?: LlmProvider;
  llmProviders?: LlmProviderOption[];
  onLlmModeChange: (mode: LlmMode) => void;
  onLlmProviderChange?: (provider: LlmProvider) => void;
  onRepoUrlChange: (repoUrl: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  repoUrl: string;
  submitting: boolean;
};

export function ReviewSubmissionForm({
  fieldError,
  isRunning,
  language,
  llmMode,
  llmProvider = "mimo",
  llmProviders = [
    { value: "mimo", label: "MiMo" },
    { value: "doubao", label: "豆包 / Doubao" },
    { value: "deepseek", label: "DeepSeek" }
  ],
  onLlmModeChange,
  onLlmProviderChange = () => undefined,
  onRepoUrlChange,
  onSubmit,
  repoUrl,
  submitting
}: ReviewSubmissionFormProps) {
  const selectedProvider = llmProviders.find((provider) => provider.value === llmProvider);
  const providerUnavailable = llmMode === "mimo" && selectedProvider?.available === false;

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <div className="space-y-2">
        <label className="text-xs font-semibold text-foreground" htmlFor="repo-url">
          {t(language, "form.githubRepo")}
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
          {t(language, "form.githubHelp")}
        </p>
      </div>
      {fieldError ? (
        <p className="text-xs leading-5 text-destructive" id="repo-url-error" role="alert">
          {fieldError}
        </p>
      ) : null}
      <div className="space-y-2">
        <span className="text-xs font-semibold text-foreground" id="llm-mode-label">
          {t(language, "form.llmMode")}
        </span>
        <div
          aria-labelledby="llm-mode-label"
          className="grid grid-cols-2 gap-2 rounded-xl border border-border bg-panel p-1"
          role="radiogroup"
        >
          <ModeButton
            active={llmMode === "mock"}
            disabled={submitting || isRunning}
            icon={FlaskConical}
            label={t(language, "form.mockLlm")}
            onClick={() => onLlmModeChange("mock")}
          />
          <ModeButton
            active={llmMode === "mimo"}
            disabled={submitting || isRunning}
            icon={KeyRound}
            label={t(language, "form.realLlm")}
            onClick={() => onLlmModeChange("mimo")}
          />
        </div>
        <p className="text-xs leading-5 text-muted-foreground">
          {llmMode === "mock"
            ? t(language, "form.mockDescription")
            : t(language, "form.realLlmDescription")}
        </p>
        {llmMode === "mimo" ? (
          <div className="space-y-2">
            <label className="text-xs font-semibold text-foreground" htmlFor="llm-provider">
              {t(language, "form.realLlmProvider")}
            </label>
            <select
              className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              disabled={submitting || isRunning}
              id="llm-provider"
              onChange={(event) => onLlmProviderChange(event.target.value as LlmProvider)}
              value={llmProvider}
            >
              {llmProviders.map((provider) => (
                <option key={provider.value} value={provider.value}>
                  {provider.label}
                </option>
              ))}
            </select>
            {providerUnavailable ? (
              <p className="text-xs leading-5 text-muted-foreground" role="status">
                {tp(language, "form.providerUnavailable", { provider: selectedProvider?.label ?? llmProvider })}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
      <Button className="w-full" disabled={submitting || isRunning} type="submit">
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        {isRunning ? t(language, "form.reviewInProgress") : t(language, "form.startReview")}
      </Button>
    </form>
  );
}

function ModeButton({
  active,
  disabled,
  icon: Icon,
  label,
  onClick,
}: {
  active: boolean;
  disabled: boolean;
  icon: typeof FlaskConical;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-checked={active}
      className={`flex min-h-11 items-center justify-center gap-2 rounded-lg px-2 text-xs font-semibold transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
        active
          ? "bg-card text-foreground shadow-sm"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
      disabled={disabled}
      onClick={onClick}
      role="radio"
      type="button"
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}
