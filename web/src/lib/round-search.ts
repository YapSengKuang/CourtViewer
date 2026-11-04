import type { TeeTime } from "@/lib/types";

export type RoundDate = { value: string; label: string; weekday: string; day: string; month: string };

export function roundDates(now: Date): RoundDate[] {
  return Array.from({ length: 15 }, (_, offset) => {
    // Local calendar arithmetic keeps the window correct across daylight saving.
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset, 12);
    const weekday = date.toLocaleDateString("en-AU", { weekday: "short" });
    const day = String(date.getDate());
    const month = date.toLocaleDateString("en-AU", { month: "short" });
    return {
      value: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${day.padStart(2, "0")}`,
      label: `${offset === 0 ? "Today" : offset === 1 ? "Tomorrow" : weekday}, ${day} ${month}`,
      weekday: offset === 0 ? "Today" : offset === 1 ? "Tomorrow" : weekday, day, month,
    };
  });
}

export function resultsUrl(date: string, players: number, holes: string): string {
  return `/results?${new URLSearchParams({ date, players: String(players), holes })}`;
}

export function slotMinutes(slot: TeeTime): number {
  const match = slot.starts_at_local.match(/T(\d{2}):(\d{2})/);
  if (!match || Number(match[1]) > 23 || Number(match[2]) > 59) return NaN;
  return Number(match[1]) * 60 + Number(match[2]);
}

export const PIXELS_PER_MINUTE = 3;
export const SLOT_WIDTH = 82;

export function timelineBounds(slots: TeeTime[]): { start: number; end: number } {
  const minutes = slots.map(slotMinutes).filter(Number.isFinite);
  return {
    start: Math.floor(Math.min(6 * 60, ...minutes) / 60) * 60,
    end: Math.min(24 * 60, Math.ceil(Math.max(20 * 60, ...minutes.map(m => m + 35)) / 60) * 60),
  };
}

export function layoutSlots(slots: TeeTime[], start: number) {
  const laneEnds: number[] = [];
  const positions = slots.filter(slot => Number.isFinite(slotMinutes(slot))).sort((a, b) => slotMinutes(a) - slotMinutes(b)
    || a.holes - b.holes || a.source_slot_key.localeCompare(b.source_slot_key)).map(slot => {
    const left = (slotMinutes(slot) - start) * PIXELS_PER_MINUTE;
    let lane = laneEnds.findIndex(end => end <= left);
    if (lane < 0) lane = laneEnds.length;
    laneEnds[lane] = left + SLOT_WIDTH + 6;
    return { slot, left, lane };
  });
  return { positions, height: Math.max(112, laneEnds.length * 52 + 32) };
}

export function hourLabel(minutes: number): string {
  const hour = (minutes / 60) % 24;
  return `${hour % 12 || 12}${hour < 12 ? "am" : "pm"}`;
}
