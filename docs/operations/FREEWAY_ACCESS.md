# Freeway collection agreement

Recorded 24 October 2026 (Australia/Melbourne). The owner explicitly confirmed in the implementation chat that an agreed access method exists, identified the frequency as **once a day**, and then selected **Public Quick18 pages once daily**.

Scope: the public HTTPS matrix at `freeway.quick18.com/teetimes/searchmatrix`, one collection cycle per Melbourne calendar day, one combined matrix request per requested date, sequential requests with existing delay/timeout limits. No login, booking or payment actions. No feed credentials are needed for this method. This records the owner's statement; no independent provider correspondence has been supplied.

The published robots exclusions remain the default. An explicit per-request exception is limited to the agreed Freeway matrix host/path and the daily runner; no alternate crawler identity is used. Automatic retry is disabled for this source. The daily runner records an attempt before network work and refuses a second attempt that local day, including after a failed run. Direct `scrapy crawl quick18` cannot enable this exception.

Use a separate Freeway catalog and workflow; never put it in Mandalay's 15-minute collection job. Disable independently with the `FREEWAY_COLLECTION_ENABLED` repository variable and `courses.public_enabled=false` for `freeway`.

The normal 60-minute freshness limit is unchanged. Once-daily collection will leave normal availability stale most of the day. The isolated snapshot demonstration is explicitly historical and does not count toward fresh coverage. A higher frequency requires a new agreement; do not silently extend freshness to 24 hours.

The marketing text states 7 pm/eight days ahead, but browser inspection on 24 October displayed offers on 2 November. Therefore the precise release boundary is unverified and must not be enforced or advertised as a verified cutoff. Empty or unknown responses remain unavailable, never inferred sold out or not released.
