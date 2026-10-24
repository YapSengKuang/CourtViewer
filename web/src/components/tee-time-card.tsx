import { formatPrice, formatSpots, formatTeeTime, formatUpdated } from "@/lib/format";
import type { TeeTime } from "@/lib/types";

type TeeTimeCardProps = {
  teeTime: TeeTime;
};

export function TeeTimeCard({ teeTime }: TeeTimeCardProps) {
  const location = teeTime.address ?? "Address not listed yet";
  return (
    <article className="flex flex-col gap-4 rounded-2xl border border-line bg-card p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="text-2xl font-semibold tracking-tight">{formatTeeTime(teeTime.starts_at_local)}</p>
        <h2 className="mt-1 text-lg font-medium">{teeTime.course_name}</h2>
        {teeTime.course_slug === "freeway" && <p className="text-sm font-medium">Starting course: {teeTime.source_slot_key.startsWith("1599:") ? "Back 9" : "Freeway"}</p>}
        <p className="text-sm text-muted">{location}</p>
        <p className="mt-2 text-sm text-muted">
          {teeTime.timezone} · {teeTime.holes} holes · {formatSpots(teeTime.spots_available)} ·{" "}
          {formatUpdated(teeTime.scraped_at)}
        </p>
      </div>
      <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end">
        <p className="text-xl font-semibold">{formatPrice(teeTime.price_per_player, teeTime.currency)}<span className="block text-sm font-normal text-muted">per player / round</span></p>
        <a
          className="inline-flex h-11 items-center justify-center rounded-full bg-fairway px-5 text-sm font-medium text-fairway-ink"
          href={teeTime.booking_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Book
        </a>
      </div>
    </article>
  );
}
