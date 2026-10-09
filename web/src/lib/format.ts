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

export function formatUpdated(iso: string | null, now = Date.now()): string {
  if (!iso) {
    return "Not updated yet";
  }
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  if (minutes < 1) {
    return "Updated just now";
  }
  if (minutes === 1) {
    return "Updated 1 min ago";
  }
  return `Updated ${minutes} min ago`;
}

export function formatSpots(spots: number): string {
  return spots === 1 ? "1 spot left" : `${spots} spots left`;
}
