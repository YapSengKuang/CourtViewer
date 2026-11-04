"use client";

import { useEffect, useState } from "react";
import { nextCollectionTime } from "@/lib/collection-schedule";

export function CollectionNotice({ courseSlug }: { courseSlug: string }) {
  const [nextCheck, setNextCheck] = useState<Date | null>(null);

  useEffect(() => {
    const update = () => setNextCheck(nextCollectionTime(new Date()));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="mt-2 space-y-1 text-sm text-muted">
      {(!courseSlug || courseSlug === "club-mandalay") && (
        <p>
          Mandalay is checked every 15 minutes.
          {nextCheck && <> Next scheduled check: <time dateTime={nextCheck.toISOString()}>{new Intl.DateTimeFormat("en-AU", {
            timeZone: "Australia/Melbourne", hour: "numeric", minute: "2-digit", timeZoneName: "short",
          }).format(nextCheck)}</time>.</>}
          {" "}Checks can be delayed. Search again after collection finishes to see updated results.
        </p>
      )}
      {(!courseSlug || courseSlug === "freeway") && <p>Freeway is checked once daily.</p>}
    </div>
  );
}
