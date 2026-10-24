export interface SnapshotOffer {
  id: string;
  starts_at: string;
  local_time: string;
  starting_course: string;
  holes: number;
  spots_available: number;
  price_per_player: string;
  currency: string;
  booking_url: string;
}

export interface Snapshot {
  kind: string;
  date: string;
  timezone: string;
  captured_at: string;
  source_url: string;
  offers: SnapshotOffer[];
}

export function filterSnapshot(snapshot: Snapshot | undefined, from: string, to: string, players: number, holes: string) {
  if (!snapshot || from > to || !Number.isInteger(players) || players < 1 || players > 4) return [];
  return snapshot.offers.filter((offer) => offer.local_time >= from && offer.local_time <= to
    && offer.spots_available >= players && (holes === "any" || offer.holes === Number(holes)));
}
