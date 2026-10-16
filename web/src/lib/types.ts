export type TeeTime = {
  source_partition: string;
  source_slot_key: string;
  course_slug: string;
  course_name: string;
  address: string | null;
  lat: number | null;
  lng: number | null;
  timezone: string;
  holes: number;
  price_per_player: string;
  currency: string;
  starts_at: string;
  starts_at_local: string;
  spots_available: number;
  booking_url: string;
  scraped_at: string;
};

export type CourseHealth = {
  slug: string;
  name: string;
  last_success_at: string | null;
  last_item_count: number | null;
  last_error: string | null;
};

export type HolesChoice = "any" | "9" | "18";
export type SortChoice = "starts_at" | "price";

export type SearchInput = {
  date: string;
  timeFrom: string;
  timeTo: string;
  holes: HolesChoice;
  players: number;
};
