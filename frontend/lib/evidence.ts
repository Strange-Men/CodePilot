export function formatEvidenceDisplayRef(
  evidenceId: string,
  displayMap: Record<string, string> = {}
): string {
  const mapped = displayMap[evidenceId] || evidenceId;
  if (/^\[E\d+\]$/.test(mapped)) return mapped;
  if (/^E\d+$/.test(mapped)) return `[${mapped}]`;
  if (/^ev_[a-z0-9_-]+$/i.test(mapped)) return "[E?]";
  return mapped;
}
