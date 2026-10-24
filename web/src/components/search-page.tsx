"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { TeeTimeCard } from "@/components/tee-time-card";
import { fetchCourses, searchAvailability } from "@/lib/api";
import { todayInputValue } from "@/lib/format";
import type { CourseChoice, CoverageStatus, HolesChoice, SearchInput, SortChoice, TeeTime } from "@/lib/types";

const fieldClass =
  "h-11 w-full rounded-xl border border-line bg-card px-3 text-base text-foreground";

export function SearchPage() {
  const [date, setDate] = useState("");
  const [timeFrom, setTimeFrom] = useState("06:00");
  const [timeTo, setTimeTo] = useState("18:00");
  const [holes, setHoles] = useState<HolesChoice>("any");
  const [players, setPlayers] = useState(1);
  const [sort, setSort] = useState<SortChoice>("starts_at");
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [teeTimes, setTeeTimes] = useState<TeeTime[]>([]);
  const [courses, setCourses] = useState<CourseChoice[]>([]);
  const [courseSlug, setCourseSlug] = useState("");
  const [coverage, setCoverage] = useState<CoverageStatus[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [submitted, setSubmitted] = useState<SearchInput | null>(null);
  const [page, setPage] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    // The prerender cannot call new Date() during render. The browser fills the date after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- local calendar date is only known in the browser
    setDate(todayInputValue(new Date()));
    let active = true;
    fetchCourses().then((rows) => { if (active) setCourses(rows); }).catch(() => {});
    return () => { active = false; requestId.current += 1; };
  }, []);

  const selected = courses.find((course) => course.slug === courseSlug);
  const minDate = selected?.date_from ?? courses.map((course) => course.date_from).filter(Boolean).sort()[0];
  const maxDate = selected?.date_to ?? courses.map((course) => course.date_to).filter(Boolean).sort().at(-1);

  async function runSearch(input: SearchInput) {
    const id = ++requestId.current;
    setStatus("loading");
    setMessage(null);
    try {
      const result = await searchAvailability(input);
      if (id !== requestId.current) return;
      setTeeTimes(result.tee_times);
      setCoverage(result.coverage);
      setHasMore(result.has_more);
      setSubmitted(input);
      setPage(Math.floor((input.offset ?? 0) / 100));
      setStatus("ready");
    } catch {
      if (id !== requestId.current) return;
      setTeeTimes([]);
      setStatus("error");
      setMessage("The tee time service is temporarily unavailable. Please try again later.");
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // An invalid new submission must also invalidate an older in-flight search.
    requestId.current += 1;
    if (timeFrom > timeTo) {
      setStatus("error");
      setMessage("The start of the window has to be before the end.");
      return;
    }
    if (!Number.isInteger(players) || players < 1 || players > 4) {
      setStatus("error");
      setMessage("Enter between 1 and 4 players.");
      return;
    }
    void runSearch({ date, timeFrom, timeTo, holes, players, courseSlug, sort, offset: 0 });
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 sm:py-10">
      <header>
        <p className="text-sm font-medium uppercase tracking-wide text-fairway">Golf</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Tee times</h1>
        <p className="mt-2 text-muted">Open slots across the courses we watch. Booking stays on the course site.</p>
      </header>

      <form className="grid grid-cols-1 gap-3 sm:grid-cols-2" onSubmit={onSubmit}>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Date
          <input className={fieldClass} type="date" value={date} min={minDate} max={maxDate} required onChange={(event) => setDate(event.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Players
          <input
            className={fieldClass}
            type="number"
            min={1}
            max={4}
            value={players}
            required
            onChange={(event) => setPlayers(event.target.valueAsNumber)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          From
          <input className={fieldClass} type="time" value={timeFrom} required onChange={(event) => setTimeFrom(event.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          To
          <input className={fieldClass} type="time" value={timeTo} required onChange={(event) => setTimeTo(event.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium sm:col-span-2">
          Holes
          <select className={fieldClass} value={holes} onChange={(event) => setHoles(event.target.value as HolesChoice)}>
            <option value="any">Any</option>
            <option value="9">9</option>
            <option value="18">18</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Course
          <select className={fieldClass} value={courseSlug} onChange={(event) => setCourseSlug(event.target.value)}>
            <option value="">All courses</option>
            {courses.map((course) => <option key={course.slug} value={course.slug}>{course.name}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Sort results
          <select className={fieldClass} value={sort} onChange={(event) => setSort(event.target.value as SortChoice)}>
            <option value="starts_at">Time</option>
            <option value="price">Currency, then price</option>
          </select>
        </label>
        <p className="text-sm text-muted sm:col-span-2">Choose today through two weeks ahead. Times are local to each course. Final availability is confirmed on the course website.</p>
        {selected?.release_note && <p className="text-sm text-muted sm:col-span-2">{selected.release_note}</p>}
        <button
          className="h-11 rounded-full bg-fairway text-sm font-medium text-fairway-ink sm:col-span-2"
          type="submit"
        >
          Search
        </button>
      </form>

      <section aria-live="polite" className="flex flex-col gap-3">
        {status === "ready" ? (
          <p className="text-muted">{coverage.length > 0
            ? `${coverage.filter((course) => course.status === "complete").length} of ${coverage.length} courses have fresh, complete date coverage.`
            : "Date coverage is unknown. An empty result does not confirm all courses are fully booked."}</p>
        ) : null}
        {status === "ready" && coverage.some((course) => course.status !== "complete") ? (
          <ul className="text-sm text-muted">{coverage.filter((course) => course.status !== "complete").map((course) => (
            <li key={course.slug}>{course.name}: {course.availability_status === "stale" ? "observations are older than 60 minutes; check the provider for current times" : course.availability_status === "unavailable" ? "source unavailable or unverified for this date" : course.status === "outside_horizon" ? "outside booking horizon" : course.status === "unchecked" ? "not checked for this date" : "partially checked, stale or unavailable"}</li>
          ))}</ul>
        ) : null}
        {status === "loading" ? <p className="text-muted">Searching tee times…</p> : null}
        {status === "ready" && coverage.filter(course => course.availability_status === "empty").map(course => <p key={course.slug}>{course.name}: no offers were available when this date was checked.</p>)}
        {status === "error" && message ? <p className="text-fairway">{message}</p> : null}
        {status === "ready" && teeTimes.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-line bg-card px-4 py-8 text-center text-muted">
            No tee times in that window.
          </p>
        ) : null}
        {status === "ready"
          ? teeTimes.map((teeTime) => (
              <TeeTimeCard
                key={`${teeTime.course_slug}-${teeTime.starts_at}-${teeTime.holes}-${teeTime.source_partition}-${teeTime.source_slot_key}`}
                teeTime={teeTime}
              />
            ))
          : null}
        {status === "ready" && page >= 100 && hasMore ? <p>Narrow your search window to see more results.</p> : null}
        {status === "ready" && submitted && (page > 0 || hasMore) ? (
          <nav aria-label="Search result pages" className="flex items-center justify-between gap-4">
            <button className="h-11 px-4 disabled:opacity-40" disabled={page === 0} onClick={() => void runSearch({ ...submitted, offset: (page - 1) * 100 })}>Previous</button>
            <span>Page {page + 1}</span>
            <button className="h-11 px-4 disabled:opacity-40" disabled={!hasMore || page >= 100} onClick={() => void runSearch({ ...submitted, offset: (page + 1) * 100 })}>Next</button>
          </nav>
        ) : null}
      </section>
    </main>
  );
}
