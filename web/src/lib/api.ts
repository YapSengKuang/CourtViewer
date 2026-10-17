import type { CourseChoice, CourseHealth, SearchInput, SearchResult, TeeTime } from "@/lib/types";

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
  return (await searchAvailability(input)).tee_times;
}

export async function searchAvailability(input: SearchInput): Promise<SearchResult> {
  if (SUPABASE_URL || SUPABASE_KEY) {
    return rpc<SearchResult>("golf_search_v2", {
      p_date: input.date,
      p_time_from: input.timeFrom,
      p_time_to: input.timeTo,
      p_players: input.players,
      p_holes: input.holes === "any" ? null : Number(input.holes),
      p_limit: 100,
      p_offset: input.offset ?? 0,
      p_sort: input.sort ?? "starts_at",
      p_course_slug: input.courseSlug || null,
    });
  }
  const params = new URLSearchParams({
    date: input.date,
    time_from: input.timeFrom,
    time_to: input.timeTo,
    players: String(input.players),
    sort: input.sort ?? "starts_at",
    limit: "100",
    offset: String(input.offset ?? 0),
  });
  if (input.courseSlug) params.set("course_slug", input.courseSlug);
  if (input.holes !== "any") {
    params.set("holes", input.holes);
  }
  const response = await fetch(`${API_URL}/api/tee-times?${params.toString()}`);
  if (!response.ok) {
    throw new Error("Search failed");
  }
  const body = (await response.json()) as Partial<SearchResult> & { tee_times: TeeTime[] };
  return { tee_times: body.tee_times, has_more: body.has_more ?? false, coverage: body.coverage ?? [] };
}

export async function fetchCourses(): Promise<CourseChoice[]> {
  if (SUPABASE_URL || SUPABASE_KEY) {
    return (await rpc<{ courses: CourseChoice[] }>("golf_courses")).courses;
  }
  const response = await fetch(`${API_URL}/api/courses`, { signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error("Course list unavailable");
  return ((await response.json()) as { courses: CourseChoice[] }).courses;
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
