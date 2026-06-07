"use client";

import React, { useEffect } from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ErrorPage({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-screen max-w-xl items-center px-5">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>CodePilot could not render this page</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start gap-3 text-sm text-muted-foreground">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
            <p>Your review data is safe. Retry the page, or reload a previous report from history.</p>
          </div>
          <Button onClick={reset} type="button">
            <RefreshCcw className="h-4 w-4" />
            Retry
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
