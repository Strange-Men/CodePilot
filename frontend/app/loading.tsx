import React from "react";
import { Loader2 } from "lucide-react";

export default function Loading() {
  return (
    <main className="flex min-h-screen items-center justify-center" role="status">
      <div className="flex items-center gap-3 rounded-lg border border-border bg-card px-5 py-4 text-sm text-muted-foreground shadow-soft">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        Loading CodePilot
      </div>
    </main>
  );
}
