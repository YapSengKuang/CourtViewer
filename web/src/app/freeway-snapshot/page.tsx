import Link from "next/link";
import { FreewaySnapshots } from "@/components/freeway-snapshots";

export default function Page() {
  return process.env.NEXT_PUBLIC_FREEWAY_SNAPSHOT_ENABLED === "true"
    ? <FreewaySnapshots />
    : <main className="mx-auto max-w-3xl p-8"><h1>Freeway snapshot demo is disabled</h1><Link href="/">Return to tee time search</Link></main>;
}
