import type { CourseHealth, SearchInput, TeeTime } from "@/lib/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function searchTeeTimes(input: SearchInput): Promise<TeeTime[]> {
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
  const response = await fetch(`${API_URL}/api/health`);
  if (!response.ok) {
    throw new Error("Health check failed");
  }
  const body = (await response.json()) as { courses: CourseHealth[] };
  return body.courses;
}
