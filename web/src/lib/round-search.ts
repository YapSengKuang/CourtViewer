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

export type CalendarWindow = { left: number; right: number; top: number; bottom: number };

export function calendarRenderWindow(left: number, top: number, width: number, height: number, clubWidth: number): CalendarWindow {
  // Quantised bounds avoid React work on every scroll pixel. One extra block
  // on every side pre-renders cards before they enter the visible area.
  const block = 256;
  return {
    left: Math.max(0, Math.floor(left / block) * block - block),
    right: Math.ceil((left + Math.max(0, width - clubWidth)) / block) * block + block,
    top: Math.max(0, Math.floor(top / block) * block - block),
    bottom: Math.ceil((top + height) / block) * block + block,
  };
}

export function calendarPositionVisible(position: { left: number; lane: number }, rowTop: number, window: CalendarWindow): boolean {
  const top = rowTop + position.lane * 52 + 16;
  return position.left + SLOT_WIDTH >= window.left && position.left <= window.right
    && top + 44 >= window.top && top <= window.bottom;
}

export function currentTimelineStart(date: string, now: Date, timezone: string): number | undefined {
  const parts = new Intl.DateTimeFormat("en-AU", { timeZone: timezone, year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(now);
  const part = (type: string) => parts.find(p => p.type === type)!.value;
  const today = `${part("year")}-${part("month")}-${part("day")}`;
  return date === today ? Number(part("hour")) * 60 + Number(part("minute")) : undefined;
}

export function timelineBounds(slots: TeeTime[], startAt?: number): { start: number; end: number } {
  const minutes = slots.map(slotMinutes).filter(Number.isFinite);
  const start = startAt ?? Math.floor(Math.min(6 * 60, ...minutes) / 60) * 60;
  return {
    start,
    end: Math.min(24 * 60, Math.ceil(Math.max(start + 1, 20 * 60, ...minutes.map(m => m + 35)) / 60) * 60),
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
  const hour = Math.floor(minutes / 60) % 24;
  const minute = minutes % 60;
  return `${hour % 12 || 12}${minute ? `:${String(minute).padStart(2, "0")}` : ""}${hour < 12 ? "am" : "pm"}`;
}
