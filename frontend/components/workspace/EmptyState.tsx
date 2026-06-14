import type { LucideIcon } from "lucide-react";
import React from "react";

import { Button } from "@/components/ui/button";

type EmptyStateProps = {
  actionLabel?: string;
  description: string;
  icon: LucideIcon;
  onAction?: () => void;
  title: string;
};

export function EmptyState({
  actionLabel,
  description,
  icon: Icon,
  onAction,
  title
}: EmptyStateProps) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-border bg-panel/60 px-6 py-10 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground shadow-sm">
        <Icon className="h-5 w-5" />
      </div>
      <h3 className="mt-4 text-base font-semibold tracking-tight">{title}</h3>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">{description}</p>
      {actionLabel && onAction ? (
        <Button className="mt-5" onClick={onAction} type="button" variant="outline">
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}
