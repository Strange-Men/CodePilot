"use client";

import { useCallback, useEffect, useState } from "react";

import type { Language } from "@/lib/i18n";

const STORAGE_KEY = "codepilot.lang";

/** Detect default language from browser locale. Returns "zh" for zh browsers, "en" otherwise. */
export function detectBrowserLanguage(): Language {
  if (typeof navigator === "undefined") return "en";
  const lang = navigator.language || (navigator as { userLanguage?: string }).userLanguage || "";
  return lang.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function readStoredLanguage(): Language {
  if (typeof window === "undefined") return "en";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "zh" || stored === "en") return stored;
  return detectBrowserLanguage();
}

export function useLanguage(): [Language, (language: Language) => void] {
  const [language, setLanguageState] = useState<Language>("en");

  useEffect(() => {
    setLanguageState(readStoredLanguage());
  }, []);

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage unavailable (SSR, private browsing quota)
    }
  }, []);

  return [language, setLanguage];
}
