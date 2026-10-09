"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { TeeTimeCard } from "@/components/tee-time-card";
import { fetchHealth, searchTeeTimes } from "@/lib/api";
import { todayInputValue } from "@/lib/format";
import type { CourseHealth, HolesChoice, SearchInput, SortChoice, TeeTime } from "@/lib/types";

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
  const [health, setHealth] = useState<CourseHealth[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    // The prerender cannot call new Date() during render. The browser fills the date after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- local calendar date is only known in the browser
    setDate(todayInputValue(new Date()));
  }, []);

  const updatedBySlug = useMemo(() => {
    const map = new Map<string, string | null>();
    for (const course of health) {
      map.set(course.slug, course.last_success_at);
    }
    return map;
  }, [health]);

  const ordered = useMemo(() => {
    const copy = [...teeTimes];
    copy.sort((left, right) => {
      if (sort === "price") {
        const priceDelta = Number(left.price_per_player) - Number(right.price_per_player);
        if (priceDelta !== 0) {
          return priceDelta;
        }
      }
      return left.starts_at.localeCompare(right.starts_at);
    });
    return copy;
  }, [sort, teeTimes]);

  async function runSearch(input: SearchInput) {
    setStatus("loading");
    setMessage(null);
    try {
      const [times, healthRows] = await Promise.all([
        searchTeeTimes(input),
        fetchHealth().catch(() => [] as CourseHealth[]),
      ]);
      setTeeTimes(times);
      setHealth(healthRows);
      setStatus("ready");
    } catch {
      setTeeTimes([]);
      setStatus("error");
      setMessage("The tee time service is not reachable. Start the API and try again.");
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (timeFrom > timeTo) {
      setStatus("error");
      setMessage("The start of the window has to be before the end.");
      return;
    }
    if (!Number.isFinite(players) || players < 1) {
      setStatus("error");
      setMessage("Enter at least 1 player.");
      return;
    }
    void runSearch({ date, timeFrom, timeTo, holes, players });
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
          <input className={fieldClass} type="date" value={date} required onChange={(event) => setDate(event.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Players
          <input
            className={fieldClass}
            type="number"
            min={1}
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
        <button
          className="h-11 rounded-full bg-fairway text-sm font-medium text-fairway-ink sm:col-span-2"
          type="submit"
        >
          Search
        </button>
      </form>

      <section aria-live="polite" className="flex flex-col gap-3">
        {status === "ready" && ordered.length > 0 ? (
          <div className="flex gap-2">
            <SortButton current={sort} value="starts_at" onSelect={setSort}>
              Time
            </SortButton>
            <SortButton current={sort} value="price" onSelect={setSort}>
              Price
            </SortButton>
          </div>
        ) : null}
        {status === "loading" ? <p className="text-muted">Searching tee times…</p> : null}
        {status === "error" && message ? <p className="text-fairway">{message}</p> : null}
        {status === "ready" && ordered.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-line bg-card px-4 py-8 text-center text-muted">
            No tee times in that window.
          </p>
        ) : null}
        {status === "ready"
          ? ordered.map((teeTime) => (
              <TeeTimeCard
                key={`${teeTime.course_slug}-${teeTime.starts_at}-${teeTime.holes}`}
                teeTime={teeTime}
                updatedAt={updatedBySlug.get(teeTime.course_slug) ?? null}
              />
            ))
          : null}
      </section>
    </main>
  );
}

function SortButton({
  current,
  value,
  onSelect,
  children,
}: {
  current: SortChoice;
  value: SortChoice;
  onSelect: (value: SortChoice) => void;
  children: string;
}) {
  const selected = current === value;
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={
        selected
          ? "h-10 rounded-full bg-foreground px-4 text-sm font-medium text-background"
          : "h-10 rounded-full border border-line bg-card px-4 text-sm font-medium"
      }
      onClick={() => onSelect(value)}
    >
      {children}
    </button>
  );
}
