"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { roundDates, resultsUrl, type RoundDate } from "@/lib/round-search";

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
    <main className="round-shell">
      <nav className="round-nav" aria-label="Main navigation">
        <Link href="/" className="round-brand"><span className="brand-mark" aria-hidden="true">↗</span> Tee time<span className="brand-dot">.</span></Link>
        <span className="region-label">MELBOURNE & SURROUNDS</span>
      </nav>
      <section className="round-hero">
        <div className="hero-copy">
          <p className="eyebrow">A LITTLE LESS SEARCHING. A LITTLE MORE GOLF.</p>
          <h1>Find your<br /><em>next round.</em></h1>
          <p className="hero-description">Your favourite courses, one clear view.<br />Pick a day. Bring your people. Find your tee time.</p>
        </div>
        <div className="course-art" aria-hidden="true">
          <div className="contour contour-one" /><div className="contour contour-two" /><div className="contour contour-three" />
          <div className="art-green"><span className="flag-pole" /><span className="flag" /><span className="cup" /></div>
          <div className="art-ball" /><span className="art-caption">A good day starts on the green.</span>
        </div>
      </section>
      <section className="round-planner" aria-labelledby="planner-title">
        <div className="planner-heading"><h2 id="planner-title">Let’s plan your round</h2><span>Three choices. Then you’re on your way.</span></div>
        <form onSubmit={submit} className="planner-form">
          <label><span className="field-eyebrow">01 / WHEN</span><span className="field-title">What day works?</span>
            <select aria-label="Date" value={selectedDate} onChange={e => setDate(e.target.value)} required disabled={!days.length}>
              {!days.length && <option value="">Loading dates…</option>}
              {days.map(day => <option key={day.value} value={day.value}>{day.label}</option>)}
            </select>
          </label>
          <label><span className="field-eyebrow">02 / WHO</span><span className="field-title">How many players?</span>
            <select aria-label="Players" value={players} onChange={e => setPlayers(e.target.value)}>{[1, 2, 3, 4].map(n => <option key={n} value={n}>{n} {n === 1 ? "player" : "players"}</option>)}</select>
          </label>
          <label><span className="field-eyebrow">03 / THE ROUND</span><span className="field-title">How many holes?</span>
            <select aria-label="Holes" value={holes} onChange={e => setHoles(e.target.value)}><option value="9">9 holes</option><option value="18">18 holes</option><option value="any">9 or 18 holes</option></select>
          </label>
          <button className="round-primary" type="submit" disabled={!selectedDate}>Find tee times <span aria-hidden="true">↗</span></button>
        </form>
        <p className="planner-footnote">Plan from today to 14 days ahead. Final availability and booking are confirmed with the course.</p>
      </section>
      <footer className="round-footer"><span>GOOD GOLF. LESS GUESSWORK.</span><span>Compare here. Book directly with the course.</span></footer>
    </main>
  );
}
