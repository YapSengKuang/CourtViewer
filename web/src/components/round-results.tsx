"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { fetchCourses, searchTimelineAvailability } from "@/lib/api";
import { formatPrice, formatTeeTime, formatUpdated } from "@/lib/format";
import { hourLabel, layoutSlots, PIXELS_PER_MINUTE, resultsUrl, roundDates, SLOT_WIDTH, timelineBounds, type RoundDate } from "@/lib/round-search";
import type { CourseChoice, CoverageStatus, HolesChoice, SearchResult, TeeTime } from "@/lib/types";

function coverageLabel(coverage: CoverageStatus | undefined, count: number, players: number) {
  if (!coverage || coverage.status === "unchecked") return "Not checked for this date";
  if (coverage.availability_status === "stale") return "Collection is out of date";
  if (coverage.status === "outside_horizon") return "Outside booking window";
  if (coverage.status !== "complete") return count ? "Partial date coverage" : "Availability unconfirmed";
  if (count) return `${count} tee ${count === 1 ? "time" : "times"}`;
  return coverage.availability_status === "empty" ? "No offers when checked" : `No matches for ${players} ${players === 1 ? "player" : "players"}`;
}

export function RoundResults() {
  const params = useSearchParams();
  const router = useRouter();
  const [days, setDays] = useState<RoundDate[]>([]);
  const [clock, setClock] = useState<number | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [data, setData] = useState<{ courses: CourseChoice[]; result: SearchResult } | null>(null);
  const [selected, setSelected] = useState<TeeTime | null>(null);
  const detailsRef = useRef<HTMLElement | null>(null);
  const dateStripRef = useRef<HTMLElement | null>(null);
  const slotButtonRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => { if (selected) detailsRef.current?.focus(); }, [selected]);
  useEffect(() => {
    const update = () => { setDays(roundDates(new Date())); setClock(Date.now()); };
    update();
    const timer = window.setInterval(update, 60000);
    return () => window.clearInterval(timer);
  }, []);

  const date = params.get("date") ?? days[0]?.value ?? "";
  const players = Number(params.get("players") ?? "2");
  const holes = params.get("holes") ?? "18";
  const valid = days.some(day => day.value === date) && Number.isInteger(players)
    && players >= 1 && players <= 4 && ["9", "18", "any"].includes(holes);
  const ready = days.length > 0;
  useEffect(() => {
    dateStripRef.current?.querySelector<HTMLElement>('[aria-pressed="true"]')
      ?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [date, ready]);

  useEffect(() => {
    if (!ready || !valid) return;
    let active = true;
    async function load() {
      setStatus("loading");
      setSelected(null);
      try {
        const [courses, result] = await Promise.all([
          fetchCourses(), searchTimelineAvailability({ date, players, holes: holes as HolesChoice,
            timeFrom: "00:00", timeTo: "23:59", sort: "starts_at" }, () => active),
        ]);
        if (active) { setData({ courses, result }); setStatus("ready"); }
      } catch {
        if (active) { setData(null); setStatus("error"); }
      }
    }
    void load();
    return () => { active = false; };
  }, [date, players, holes, ready, valid, refresh]);

  function navigate(nextDate = date, nextPlayers = players, nextHoles = holes) {
    router.push(resultsUrl(nextDate, nextPlayers, nextHoles), { scroll: false });
  }
  function closeDetails() {
    setSelected(null);
    slotButtonRef.current?.focus();
  }
  const slots = status === "ready" && data ? data.result.tee_times : [];
  const bounds = timelineBounds(slots);
  const width = (bounds.end - bounds.start) * PIXELS_PER_MINUTE + SLOT_WIDTH;
  const hours = Array.from({ length: (bounds.end - bounds.start) / 60 + 1 }, (_, i) => bounds.start + i * 60);
  const selectedDay = days.find(day => day.value === date);
  const complete = data?.result.coverage.filter(c => c.status === "complete").length ?? 0;

  return (
    <main className="round-shell results-shell">
      <nav className="round-nav" aria-label="Main navigation">
        <Link href="/" className="round-brand"><span className="brand-mark" aria-hidden="true">↗</span> Tee time<span className="brand-dot">.</span></Link>
        <Link href="/" className="back-link">← Plan another round</Link>
      </nav>
      <header className="results-heading">
        <div><p className="eyebrow">YOUR NEXT ROUND</p><h1>A day on the <em>fairway.</em></h1><p>Find a time that works. Book directly with the course.</p></div>
        <div className="results-controls">
          <label>Players<select aria-label="Players" value={players} onChange={e => navigate(date, Number(e.target.value))}>{[1, 2, 3, 4].map(n => <option value={n} key={n}>{n} {n === 1 ? "player" : "players"}</option>)}</select></label>
          <label>Holes<select aria-label="Holes" value={holes} onChange={e => navigate(date, players, e.target.value)}><option value="9">9 holes</option><option value="18">18 holes</option><option value="any">9 or 18</option></select></label>
        </div>
      </header>

      {ready && !valid ? <div className="results-message" role="alert">This search is outside the available date range or has invalid options. <Link href="/">Start a new search</Link>.</div> : <>
        <nav className="date-strip" aria-label="Choose a date" ref={dateStripRef}>
          {days.map(day => <button type="button" key={day.value} aria-pressed={date === day.value}
            aria-label={day.label} onClick={() => navigate(day.value)} className={date === day.value ? "date-tile selected" : "date-tile"}>
            <span>{day.weekday}</span><strong>{day.day}</strong><span>{day.month}</span>
          </button>)}
        </nav>
        <section className="availability-section" aria-label="Tee-time availability">
          <div className="availability-heading">
            <div><h2>{selectedDay?.label ?? "Your tee times"}</h2><p aria-live="polite">{status === "loading" ? "Checking saved tee times…" : status === "error" ? "We couldn’t load availability." : `${slots.length} tee times · ${complete} courses with complete date coverage`}</p></div>
            <button className="refresh-button" type="button" disabled={status === "loading"} onClick={() => setRefresh(n => n + 1)}>↻ Refresh results</button>
          </div>
          <div className="calendar-legend"><span><i className="legend-dot eighteen" />18 holes</span><span><i className="legend-dot nine" />9 holes</span><span className="calendar-hint">Times are local to each course. Scroll to explore →</span></div>
          {status === "loading" ? <div className="results-loading" role="status"><span className="loading-dot" /> Finding your fairway…</div>
            : status === "error" ? <div className="results-message" role="alert">The tee-time service is temporarily unavailable. Try Refresh results.</div>
            : data && <>
              {slots.length === 0 && <p className="no-matches">No matching tee times to display. The course rows below show whether this date has been checked.</p>}
              <div className="tee-calendar" tabIndex={0} role="region" aria-label="Tee-time calendar: time across the top, golf courses down the side. Scroll horizontally for more times.">
                <div className="calendar-grid" style={{ gridTemplateColumns: `var(--club-column) ${width}px` }}>
                  <div className="calendar-corner">GOLF COURSE <span>↓</span></div>
                  <div className="calendar-hours">{hours.map(hour => <span key={hour} style={{ left: (hour - bounds.start) * PIXELS_PER_MINUTE }}>{hourLabel(hour)}</span>)}</div>
                  {data.courses.map((course, index) => {
                    const times = slots.filter(slot => slot.course_slug === course.slug);
                    const coverage = data.result.coverage.find(c => c.slug === course.slug);
                    const layout = layoutSlots(times, bounds.start);
                    const label = holes !== "any" && course.holes_options && !course.holes_options.includes(Number(holes))
                      ? `${holes}-hole availability isn’t collected for this course.`
                      : coverageLabel(coverage, times.length, players);
                    return <div className="calendar-course" key={course.slug}>
                      <div className="club-cell" style={{ minHeight: layout.height }}><span className="club-number">{String(index + 1).padStart(2, "0")}</span><h3>{course.name}</h3><span className={coverage?.status === "complete" ? "course-status checked" : "course-status"}>{label}</span></div>
                      <div className="time-track" style={{ height: layout.height }} aria-label={`${course.name}: ${label}`}>
                        {layout.positions.map(({ slot, left, lane }) => <button
                          type="button" key={`${slot.source_partition}:${slot.source_slot_key}:${slot.holes}`}
                          className={`tee-slot ${slot.holes === 9 ? "nine" : "eighteen"} ${selected === slot ? "active" : ""}`}
                          style={{ left, top: lane * 52 + 16, width: SLOT_WIDTH }}
                          aria-pressed={selected === slot}
                          aria-label={`${course.name}, ${formatTeeTime(slot.starts_at_local)}, ${slot.holes} holes, ${slot.spots_available} spots, ${formatPrice(slot.price_per_player, slot.currency)} per player`}
                          onClick={event => { slotButtonRef.current = event.currentTarget; setSelected(slot); }}>
                          <strong>{formatTeeTime(slot.starts_at_local)}</strong><span>{formatPrice(slot.price_per_player, slot.currency)}</span>
                        </button>)}
                        {!times.length && <p className="empty-track">{label}</p>}
                      </div>
                    </div>;
                  })}
                </div>
              </div>
              <div className="calendar-footer"><span>Select a tee time to view the round and booking details.</span><span>Collected availability · confirmed at booking</span></div>
            </>}
        </section>
        {selected && status === "ready" && <aside className="slot-details" role="dialog" aria-modal="false" aria-label="Selected tee time"
          tabIndex={-1} ref={detailsRef} onKeyDown={event => { if (event.key === "Escape") closeDetails(); }}>
          <div><p className="eyebrow">YOUR TEE TIME</p><h2>{selected.course_name}</h2><p>{selectedDay?.label} · {formatTeeTime(selected.starts_at_local)} · {selected.holes} holes · {selected.spots_available} spots available</p>
            <p className="detail-updated">{clock === null ? "" : formatUpdated(selected.scraped_at, clock, selected.timezone)}</p></div>
          <div className="booking-actions"><div className="booking-price">{formatPrice(selected.price_per_player, selected.currency)}<span>per player / round</span></div><a className="round-primary" href={selected.booking_url} target="_blank" rel="noopener noreferrer">Book with course ↗</a><button type="button" className="detail-close" onClick={closeDetails} aria-label="Close tee-time details">×</button></div>
          <p className="booking-note">Your booking and final availability are confirmed on the course website.</p>
        </aside>}
        <footer className="round-footer"><span>GOOD GOLF. LESS GUESSWORK.</span><span>Dates without collection are labelled “Not checked”.</span></footer>
      </>}
    </main>
  );
}
