/** Public navigation only: this does not fetch or claim provider availability. */
export function freewayDateUrl(date: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  const parsed = new Date(`${date}T00:00:00Z`);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date) return null;
  return `https://freeway.quick18.com/teetimes/searchmatrix?teedate=${date.replaceAll("-", "")}`;
}
