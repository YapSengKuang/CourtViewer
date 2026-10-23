"use client";

import { useState } from "react";
import Link from "next/link";
import snapshots from "@/data/freeway-snapshots.json";
import { filterSnapshot, type Snapshot } from "@/lib/snapshots";
import { freewayDateUrl } from "@/lib/provider-links";

const field = "h-11 w-full rounded-xl border border-line bg-card px-3 text-base";

export function FreewaySnapshots() {
  const data: Snapshot[] = snapshots;
  const [date, setDate] = useState(data.at(-1)?.date ?? "");
  const [from, setFrom] = useState("00:00");
  const [to, setTo] = useState("23:59");
  const [players, setPlayers] = useState(1);
  const [holes, setHoles] = useState("any");
  const [page, setPage] = useState(0);
  const snapshot = data.find((entry) => entry.date === date);
  const offers = filterSnapshot(snapshot, from, to, players, holes);
  const url = freewayDateUrl(date);
  const change = (update: () => void) => { update(); setPage(0); };

  return <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
    <Link className="underline" href="/">← Search current tee times</Link>
    <header>
      <p className="font-semibold text-fairway">Snapshot demo</p>
      <h1 className="mt-2 text-3xl font-semibold">Freeway Golf Course</h1>
      <p className="mt-3 font-semibold">Snapshot — check current availability on Freeway</p>
      <p className="mt-2 text-muted">Saved observations, not live availability. Times and spaces may have changed. Each starting tee is a separate group.</p>
    </header>
    <div className="grid gap-3 sm:grid-cols-2">
      <label>Date<input className={field} type="date" value={date} onChange={e => change(() => setDate(e.target.value))} /></label>
      <label>Captured dates<select className={field} value={snapshot ? date : ""} onChange={e => change(() => setDate(e.target.value))}>
        <option value="" disabled>Select a captured date</option>
        {data.map(s => <option key={s.date} value={s.date}>{s.date}</option>)}
      </select></label>
      <label>From<input className={field} type="time" value={from} onChange={e => change(() => setFrom(e.target.value))} /></label>
      <label>To<input className={field} type="time" value={to} onChange={e => change(() => setTo(e.target.value))} /></label>
      <label>Players<select className={field} value={players} onChange={e => change(() => setPlayers(Number(e.target.value)))}>{[1,2,3,4].map(n => <option key={n}>{n}</option>)}</select></label>
      <label>Holes<select className={field} value={holes} onChange={e => change(() => setHoles(e.target.value))}><option value="any">Any</option><option value="9">9</option><option value="18">18</option></select></label>
    </div>
    {url && <a className="inline-flex min-h-11 items-center justify-center rounded-full bg-fairway px-5 text-fairway-ink" href={url} target="_blank" rel="noopener noreferrer">Check current times</a>}
    <section aria-live="polite" className="flex flex-col gap-3">
      {snapshot ? <>
        <p className="rounded-xl border border-line bg-card p-4">Captured {new Intl.DateTimeFormat("en-AU", {timeZone: snapshot.timezone, dateStyle: "medium", timeStyle: "long"}).format(new Date(snapshot.captured_at))} ({snapshot.timezone}). Historical snapshots remain visible here.</p>
        <p className="text-sm text-muted">AUD per player, per round. Standard rates only; final fees are confirmed by Freeway. Spaces shown are from the capture.</p>
        {from > to ? <p role="alert">The start of the window has to be before the end.</p> : <p>{offers.length ? `${offers.length} matching captured offers` : "No captured offers match these filters. This does not mean sold out."}</p>}
        {offers.slice(page * 20, (page + 1) * 20).map(offer => <article key={offer.id} className="rounded-2xl border border-line bg-card p-4">
          <h2 className="text-lg font-semibold">{offer.local_time} · {offer.starting_course}</h2>
          <p>{offer.holes} holes · {offer.spots_available} spaces at capture · AUD ${offer.price_per_player} per player / round</p>
        </article>)}
        {offers.length > 20 && <nav aria-label="Snapshot pages" className="flex items-center justify-between"><button className="min-h-11 px-4 disabled:opacity-40" disabled={!page} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page + 1} of {Math.ceil(offers.length / 20)}</span><button className="min-h-11 px-4 disabled:opacity-40" disabled={(page + 1) * 20 >= offers.length} onClick={() => setPage(page + 1)}>Next</button></nav>}
      </> : <p>No snapshot captured for this date</p>}
    </section>
  </main>;
}
