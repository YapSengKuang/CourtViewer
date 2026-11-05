"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { formatPrice, formatTeeTime } from "@/lib/format";
import { calendarRenderWindow, calendarPositionVisible, hourLabel, PIXELS_PER_MINUTE, SLOT_WIDTH, type CalendarWindow, type layoutSlots } from "@/lib/round-search";
import type { TeeTime } from "@/lib/types";

export type CalendarRow = {
  slug: string; name: string; label: string; checked: boolean;
  layout: ReturnType<typeof layoutSlots>;
};

function slotKey(slot: TeeTime) {
  return `${slot.course_slug}:${slot.source_partition}:${slot.source_slot_key}:${slot.holes}`;
}

type Props = {
  rows: CalendarRow[]; hours: number[]; start: number; width: number;
  selected: TeeTime | null;
  onSelect: (slot: TeeTime, button: HTMLButtonElement) => void;
};

export function TeeCalendar({ rows, hours, start, width, selected, onSelect }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [renderWindow, setRenderWindow] = useState<CalendarWindow | null>(null);
  const [keyboardNavigation, setKeyboardNavigation] = useState(false);
  const [focusedKey, setFocusedKey] = useState<string | null>(null);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    let frame: number | null = null;
    function measure() {
      frame = null;
      const bounds = element!.getBoundingClientRect();
      const next = calendarRenderWindow(element!.scrollLeft, -bounds.top,
        element!.clientWidth, window.innerHeight,
        parseFloat(getComputedStyle(element!).getPropertyValue("--club-column")) || 208);
      // Horizontal overflow owns the native sticky context. Move only the two
      // header cells so their time labels also stay visible during page scroll.
      const headerOffset = Math.min(Math.max(0, -bounds.top), Math.max(0, bounds.height - 48));
      element!.style.setProperty("--calendar-header-offset", `${headerOffset}px`);
      setRenderWindow(previous => previous && previous.left === next.left && previous.right === next.right
        && previous.top === next.top && previous.bottom === next.bottom ? previous : next);
    }
    function schedule() {
      if (frame === null) frame = requestAnimationFrame(measure);
    }
    function pointerScroll() {
      setKeyboardNavigation(false);
    }
    element.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule, { passive: true });
    window.addEventListener("wheel", pointerScroll, { passive: true });
    const observer = new ResizeObserver(schedule);
    observer.observe(element);
    schedule();
    return () => {
      element.removeEventListener("scroll", schedule);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      window.removeEventListener("wheel", pointerScroll);
      observer.disconnect();
      if (frame !== null) cancelAnimationFrame(frame);
    };
  }, []);

  const rowOffsets = useMemo(() => {
    let top = 48; // Sticky time-header height; preserve the complete scroll range.
    const offsets: number[] = [];
    for (const row of rows) {
      offsets.push(top);
      top += row.layout.height;
    }
    return offsets;
  }, [rows]);
  return <div className="tee-calendar" tabIndex={0} ref={scrollRef} role="region" data-render-mode={keyboardNavigation ? "keyboard" : "windowed"}
    aria-label="Tee-time calendar: time across the top, golf courses down the side. Scroll horizontally for more times."
    onKeyDownCapture={event => {
      // Restore the full tab sequence before the browser chooses its next target.
      if (event.key === "Tab" && !keyboardNavigation) flushSync(() => setKeyboardNavigation(true));
    }}
    onPointerDownCapture={() => setKeyboardNavigation(false)}>
    <div className="calendar-grid" style={{ width: `max(100%, calc(var(--club-column) + ${width}px))`, gridTemplateColumns: "var(--club-column) minmax(0, 1fr)" }}>
      <div className="calendar-corner">GOLF COURSE <span>↓</span></div>
      <div className="calendar-hours">{hours.map(hour => <span key={hour} style={{ left: (hour - start) * PIXELS_PER_MINUTE }}>{hourLabel(hour)}</span>)}</div>
      {rows.map((row, index) => {
        const top = rowOffsets[index];
        const visible = row.layout.positions.filter(position => keyboardNavigation
          || position.slot === selected || slotKey(position.slot) === focusedKey
          || (renderWindow && calendarPositionVisible(position, top, renderWindow)));
        return <div className="calendar-course" key={row.slug}>
          <div className="club-cell" style={{ minHeight: row.layout.height }}>
            <span className="club-number">{String(index + 1).padStart(2, "0")}</span><h3>{row.name}</h3>
            <span className={row.checked ? "course-status checked" : "course-status"}>{row.label}</span>
          </div>
          <div className="time-track" style={{ height: row.layout.height }} aria-label={`${row.name}: ${row.label}`}>
            {visible.map(({ slot, left, lane }) => <button type="button" key={slotKey(slot)}
              className={`tee-slot ${slot.holes === 9 ? "nine" : "eighteen"} ${selected === slot ? "active" : ""}`}
              style={{ left, top: lane * 52 + 16, width: SLOT_WIDTH }} aria-pressed={selected === slot}
              aria-label={`${row.name}, ${formatTeeTime(slot.starts_at_local)}, ${slot.holes} holes, ${slot.spots_available} spots, ${formatPrice(slot.price_per_player, slot.currency)} per player`}
              onFocus={() => setFocusedKey(slotKey(slot))}
              onBlur={() => setFocusedKey(null)}
              onClick={event => onSelect(slot, event.currentTarget)}>
              <strong>{formatTeeTime(slot.starts_at_local)}</strong><span>{formatPrice(slot.price_per_player, slot.currency)} · {slot.holes}h</span>
            </button>)}
            {!row.layout.positions.length && <p className="empty-track">{row.label}</p>}
          </div>
        </div>;
      })}
    </div>
  </div>;
}
