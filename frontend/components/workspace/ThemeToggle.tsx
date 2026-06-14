"use client";

import { Moon, Sun } from "lucide-react";
import React from "react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

type Theme = "light" | "dark";

export function nextTheme(theme: Theme): Theme {
  return theme === "dark" ? "light" : "dark";
}

export function applyTheme(
  theme: Theme,
  root: Pick<HTMLElement, "classList"> = document.documentElement,
  storage: Pick<Storage, "setItem"> = localStorage
) {
  root.classList.toggle("dark", theme === "dark");
  storage.setItem("codepilot-theme", theme);
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
  }, []);

  function toggleTheme() {
    const next = nextTheme(theme);
    applyTheme(next);
    setTheme(next);
  }

  return (
    <Button
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      onClick={toggleTheme}
      size="icon"
      title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      type="button"
      variant="outline"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
