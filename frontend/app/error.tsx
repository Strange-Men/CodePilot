"use client";

import React, { useEffect } from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLanguage } from "@/hooks/useLanguage";
import { t } from "@/lib/i18n";

export default function ErrorPage({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [language] = useLanguage();

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-screen max-w-xl items-center px-5">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>{t(language, "error.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start gap-3 text-sm text-muted-foreground">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
            <p>{t(language, "error.description")}</p>
          </div>
          <Button onClick={reset} type="button">
            <RefreshCcw className="h-4 w-4" />
            {t(language, "error.retry")}
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
