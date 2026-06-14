import React from "react";

export default function Loading() {
  return (
    <main className="min-h-dvh bg-background p-4 sm:p-6" role="status">
      <div className="mx-auto max-w-[1600px] space-y-5">
        <div className="skeleton h-16 rounded-xl" />
        <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
          <div className="skeleton h-[680px] rounded-xl" />
          <div className="space-y-5">
            <div className="skeleton h-14 rounded-xl" />
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="skeleton h-28 rounded-xl" />
              <div className="skeleton h-28 rounded-xl" />
              <div className="skeleton h-28 rounded-xl" />
            </div>
            <div className="skeleton h-[430px] rounded-xl" />
          </div>
        </div>
        <span className="sr-only">Loading CodePilot workspace</span>
      </div>
    </main>
  );
}
