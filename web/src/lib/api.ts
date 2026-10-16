import type { CourseHealth, SearchInput, TeeTime } from "@/lib/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

async function rpc<T>(name: string, args: Record<string, unknown> = {}): Promise<T> {
  if (!SUPABASE_URL || !SUPABASE_KEY) {
    throw new Error("Supabase configuration is incomplete");
  }
  const response = await fetch(`${SUPABASE_URL.replace(/\/$/, "")}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: SUPABASE_KEY },
    body: JSON.stringify(args),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("Search service unavailable");
  return response.json() as Promise<T>;
}

export async function searchTeeTimes(input: SearchInput): Promise<TeeTime[]> {
  if (SUPABASE_URL || SUPABASE_KEY) {
    const body = await rpc<{ tee_times: TeeTime[] }>("golf_search", {
      p_date: input.date,
      p_time_from: input.timeFrom,
      p_time_to: input.timeTo,
      p_players: input.players,
      p_holes: input.holes === "any" ? null : Number(input.holes),
      p_limit: 200,
      p_offset: 0,
    });
    return body.tee_times;
  }
  const params = new URLSearchParams({
    date: input.date,
    time_from: input.timeFrom,
    time_to: input.timeTo,
    players: String(input.players),
  });
  if (input.holes !== "any") {
    params.set("holes", input.holes);
  }
  const response = await fetch(`${API_URL}/api/tee-times?${params.toString()}`);
  if (!response.ok) {
    throw new Error("Search failed");
  }
  const body = (await response.json()) as { tee_times: TeeTime[] };
  return body.tee_times;
}

export async function fetchHealth(): Promise<CourseHealth[]> {
  if (SUPABASE_URL || SUPABASE_KEY) {
    return (await rpc<{ courses: CourseHealth[] }>("golf_health")).courses;
  }
  const response = await fetch(`${API_URL}/api/health`);
  if (!response.ok) {
    throw new Error("Health check failed");
  }
  const body = (await response.json()) as { courses: CourseHealth[] };
  return body.courses;
}
