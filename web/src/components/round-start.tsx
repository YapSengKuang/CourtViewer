"use client";

import { RoundBrand } from "@/components/round-brand";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { roundDates, resultsUrl, type RoundDate } from "@/lib/round-search";
import { ThemeToggle } from "@/components/theme-toggle";

export function RoundStart() {
  const router = useRouter();
  const [days, setDays] = useState<RoundDate[]>([]);
  const [date, setDate] = useState("");
  const [players, setPlayers] = useState("2");
  const [holes, setHoles] = useState("18");
  useEffect(() => {
    const update = () => setDays(roundDates(new Date()));
    update();
    const timer = window.setInterval(update, 60000);
    return () => window.clearInterval(timer);
  }, []);
  const selectedDate = days.some(day => day.value === date) ? date : days[0]?.value ?? "";
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedDate) router.push(resultsUrl(selectedDate, Number(players), holes));
  }
  return (
    <main className="round-shell start-shell">
      <nav className="round-nav" aria-label="Main navigation">
        <div className="nav-start"><ThemeToggle /><RoundBrand /></div>
      </nav>
      <div className="start-content">
      <header className="round-hero compact-hero">
        <div className="hero-copy">
          <h1>Find your <em>next round.</em></h1>
        </div>
      </header>
      <section className="round-planner" aria-label="Plan your round">
        <form onSubmit={submit} className="planner-form">
          <label><span className="field-title">Pick a date</span>
            <select aria-label="Date" value={selectedDate} onChange={e => setDate(e.target.value)} required disabled={!days.length}>
              {!days.length && <option value="">Loading dates…</option>}
              {days.map(day => <option key={day.value} value={day.value}>{day.label}</option>)}
            </select>
          </label>
          <label><span className="field-title">How many players?</span>
            <select aria-label="Players" value={players} onChange={e => setPlayers(e.target.value)}>{[1, 2, 3, 4].map(n => <option key={n} value={n}>{n} {n === 1 ? "player" : "players"}</option>)}</select>
          </label>
          <label><span className="field-title">How many holes?</span>
            <select aria-label="Holes" value={holes} onChange={e => setHoles(e.target.value)}><option value="9">9 holes</option><option value="18">18 holes</option><option value="any">9 or 18 holes</option></select>
          </label>
          <button className="round-primary" type="submit" disabled={!selectedDate}>Find tee times</button>
        </form>
      </section>
      </div>
    </main>
  );
}
