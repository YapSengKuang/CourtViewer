export function todayInputValue(now: Date): string {
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

export function formatTeeTime(startsAtLocal: string): string {
  const match = startsAtLocal.match(/T(\d{2}):(\d{2})/);
  if (!match) {
    return startsAtLocal;
  }
  const hour = Number(match[1]);
  const minute = match[2];
  const suffix = hour >= 12 ? "PM" : "AM";
  const hour12 = hour % 12 || 12;
  return `${hour12}:${minute} ${suffix}`;
}

export function formatPrice(amount: string, currency: string): string {
  const value = Number(amount);
  if (Number.isNaN(value)) {
    return amount;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(value);
}

export function formatUpdated(iso: string | null, now = Date.now(), timezone = "Australia/Melbourne"): string {
  if (!iso) {
    return "Last update unknown";
  }
  const updated = new Date(iso);
  if (!Number.isFinite(updated.getTime())) return "Last update unknown";
  const minutes = Math.max(0, Math.floor((now - updated.getTime()) / 60000));
  const age = minutes < 1 ? "just now" : minutes < 60 ? `${minutes} min ago`
    : `${Math.floor(minutes / 60)} hr ago`;
  const timestamp = new Intl.DateTimeFormat("en-AU", {
    timeZone: timezone, day: "numeric", month: "short", year: "numeric",
    hour: "numeric", minute: "2-digit", timeZoneName: "short",
  }).format(updated);
  return `Last updated ${timestamp} (${age})`;
}

export function formatSpots(spots: number): string {
  return spots === 1 ? "1 spot left" : `${spots} spots left`;
}
