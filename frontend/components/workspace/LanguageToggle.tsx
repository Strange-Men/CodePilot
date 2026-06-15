"use client";

import { Globe } from "lucide-react";
import React from "react";

import { Button } from "@/components/ui/button";
import type { Language } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type LanguageToggleProps = {
  language: Language;
  onLanguageChange: (language: Language) => void;
};

export function LanguageToggle({ language, onLanguageChange }: LanguageToggleProps) {
  function toggle() {
    onLanguageChange(language === "en" ? "zh" : "en");
  }

  return (
    <Button
      aria-label={language === "en" ? "Switch to Chinese" : "切换为英文"}
      className="gap-1.5 font-mono text-xs"
      onClick={toggle}
      size="sm"
      title={language === "en" ? "Switch to Chinese" : "切换为英文"}
      type="button"
      variant="outline"
    >
      <Globe className="h-3.5 w-3.5" />
      <span className={cn(language === "zh" && "text-muted-foreground")}>EN</span>
      <span className="text-muted-foreground">/</span>
      <span className={cn(language === "en" && "text-muted-foreground")}>中</span>
    </Button>
  );
}
