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

const zhSafeText: Record<FindingTextField, string> = {
  title: "问题需要进一步确认",
  description: "建议结合相关代码位置进一步确认该问题，并在修改前补充必要测试。",
  recommendation: "建议结合相关代码位置进一步确认该问题，并在修改前补充必要测试。",
  impact: "该问题可能增加维护成本或引入行为不一致风险。",
  first_step: "建议先运行相关测试，并确认受影响模块的当前行为。",
  caveat: "修改前请确认该逻辑是否存在兼容性约束。",
  confidence_rationale: "该判断基于当前结构化证据和报告上下文。"
};

const zhSafeValidationTest = "建议运行相关测试，并重点检查受影响模块的边界行为。";

export function getLocalizedFindingText(
  finding: ReviewFindingItem,
  field: FindingTextField,
  language: Language
): string | null {
  if (language === "zh") {
    const value = finding.display?.zh?.[field] || finding[field];
    if (isUsableZhText(value)) return value;
    return zhSafeText[field] || t(language, "common.notAvailable");
  }

  return finding.display?.en?.[field] || finding[field] || null;
}

export function getLocalizedFindingTitle(finding: ReviewFindingItem, language: Language): string {
  return (
    getLocalizedFindingText(finding, "title", language)
    || getLocalizedFindingText(finding, "description", language)
    || t(language, "common.notAvailable")
  );
}

export function getLocalizedValidationTests(finding: ReviewFindingItem, language: Language): string[] {
  if (language !== "zh") return finding.display?.en?.validation_tests?.length ? finding.display.en.validation_tests : finding.validation_tests;

  const tests = finding.display?.zh?.validation_tests?.length
    ? finding.display.zh.validation_tests
    : finding.validation_tests;
  if (!tests.length) return [];

  return tests.map((item) =>
    isCommandOrPath(item) || isUsableZhText(item) ? item : zhSafeValidationTest
  );
}

export function localizedAgentError(error: string | null, language: Language): string | null {
  if (!error) return null;
  if (language !== "zh") return error;
  return isEnglishProse(error) ? t(language, "error.generic") : error;
}

function isUsableZhText(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0 && !isEnglishProse(value);
}

function isEnglishProse(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed) return false;
  if (/[\u4e00-\u9fff]/.test(trimmed)) return false;
  if (isCommandOrPath(trimmed)) return false;
  if (/^\[E\d+\]$/.test(trimmed)) return false;

  const words = trimmed.match(/[A-Za-z]+/g) || [];
  if (!/[\u4e00-\u9fff]/.test(trimmed) && words.length >= 2) return true;
  if (words.length > 8) return true;

  let consecutive = 0;
  for (const word of words) {
    if (commonEnglishWords.has(word.toLowerCase())) {
      consecutive += 1;
      if (consecutive > 8) return true;
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

const commonEnglishWords = new Set([
  "a", "an", "and", "are", "as", "be", "before", "by", "can", "check",
  "code", "common", "continue", "could", "differences", "document", "existing",
  "examine", "for", "functionality", "impact", "implementation", "improves", "in",
  "is", "may", "not", "of", "or", "protocols", "recommendation", "run", "rules",
  "should", "tests", "the", "this", "to", "using", "validation", "with", "without"
]);
