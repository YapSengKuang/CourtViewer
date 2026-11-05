// Match .github/workflows/collect.yml: 7,22,37,52 * * * * (UTC).
// These are scheduled start times, not confirmed collection completion times.
export function nextCollectionTime(now: Date): Date {
  const interval = 15 * 60 * 1000;
  const offset = 7 * 60 * 1000;
  return new Date((Math.floor((now.getTime() - offset) / interval) + 1) * interval + offset);
}
