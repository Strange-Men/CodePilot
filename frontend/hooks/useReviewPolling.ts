"use client";

import { useEffect, useRef } from "react";

import { getReview } from "@/lib/api";
import { terminalStatuses } from "@/lib/report";
import type { ReviewResponse } from "@/lib/types";

type UseReviewPollingOptions = {
  taskId: string | null;
  onReview: (review: ReviewResponse) => void;
  onError: (error: string) => void;
};

export function useReviewPolling({ taskId, onReview, onError }: UseReviewPollingOptions) {
  const pollingTimerRef = useRef<number | null>(null);

  useEffect(() => {
    function clearPolling() {
      if (pollingTimerRef.current !== null) {
        window.clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    }

    clearPolling();
    if (!taskId) return;

    const activeTaskId = taskId;
    let cancelled = false;
    async function poll() {
      try {
        const data = await getReview(activeTaskId);
        if (!cancelled) {
          onReview(data);
          onError(data.error || "");
          if (terminalStatuses.includes(data.status)) {
            clearPolling();
          }
        }
      } catch (err) {
        if (!cancelled) onError(err instanceof Error ? err.message : "Unable to fetch review status.");
      }
    }

    poll();
    pollingTimerRef.current = window.setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearPolling();
    };
  }, [taskId, onReview, onError]);
}
