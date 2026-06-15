"use client";

import { useCallback, useEffect, useState } from "react";

import type { Language } from "@/lib/i18n";

const STORAGE_KEY = "codepilot-language";

function readStoredLanguage(): Language {
  if (typeof window === "undefined") return "en";
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === "zh" ? "zh" : "en";
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
