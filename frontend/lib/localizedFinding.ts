import type { Language } from "@/lib/i18n";
import { t } from "@/lib/i18n";
import type { ReviewFindingItem } from "@/lib/types";

type FindingTextField =
  | "title"
  | "description"
  | "recommendation"
  | "impact"
  | "first_step"
  | "caveat"
  | "confidence_rationale";

const commonEnglishWords = new Set([
  "a", "an", "and", "are", "as", "be", "before", "by", "can", "check",
  "code", "common", "continue", "could", "differences", "document", "existing",
  "examine", "for", "functionality", "impact", "implementation", "improves", "in",
  "is", "may", "not", "of", "or", "protocols", "recommendation", "run", "rules",
  "should", "tests", "the", "this", "to", "using", "validation", "with", "without"
]);

export function getLocalizedFindingText(
  finding: ReviewFindingItem,
  field: FindingTextField,
  language: Language
): string | null {
  const value = finding[field];
  if (!value) return null;
  if (language !== "zh") return value;
  return isEnglishProse(value) ? t(language, "common.notAvailable") : value;
}

export function getLocalizedFindingTitle(finding: ReviewFindingItem, language: Language): string {
  return (
    getLocalizedFindingText(finding, "title", language)
    || getLocalizedFindingText(finding, "description", language)
    || t(language, "common.notAvailable")
  );
}

export function getLocalizedValidationTests(finding: ReviewFindingItem, language: Language): string[] {
  if (language !== "zh") return finding.validation_tests;
  return finding.validation_tests.map((item) =>
    isCommandOrPath(item) || !isEnglishProse(item) ? item : t(language, "common.notAvailable")
  );
}

export function localizedAgentError(error: string | null, language: Language): string | null {
  if (!error) return null;
  if (language !== "zh") return error;
  return isEnglishProse(error) ? t(language, "error.generic") : error;
}

function isEnglishProse(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed) return false;
  if (/[\u4e00-\u9fff]/.test(trimmed)) return false;
  if (isCommandOrPath(trimmed)) return false;
  if (/^\[E\d+\]$/.test(trimmed)) return false;

  const words = trimmed.match(/[A-Za-z]+/g) || [];
  if (words.length >= 2 && words.every((word) => word.length > 1)) return true;

  let consecutive = 0;
  for (const word of words) {
    if (commonEnglishWords.has(word.toLowerCase())) {
      consecutive += 1;
      if (consecutive >= 2) return true;
    } else {
      consecutive = 0;
    }
  }
  return false;
}

function isCommandOrPath(text: string): boolean {
  const trimmed = text.trim();
  if (/^(python|npm|pip|pytest|git|cd|ls|cat|grep|make|cargo|go|java|node)\b/i.test(trimmed)) return true;
  if (/[\\/][\w.-]+/.test(trimmed)) return true;
  if (/^[\w.-]+\.(py|ts|tsx|js|jsx|json|md|toml|yml|yaml|css|html)$/.test(trimmed)) return true;
  if (/^\$|^>\s/.test(trimmed)) return true;
  return false;
}
