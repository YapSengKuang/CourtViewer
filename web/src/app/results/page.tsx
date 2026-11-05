import { Suspense } from "react";
import { RoundResults } from "@/components/round-results";

export default function Results() {
  return <Suspense fallback={<main className="round-shell"><p className="results-loading">Getting your round ready…</p></main>}><RoundResults /></Suspense>;
}
