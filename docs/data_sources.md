# Sources

Adapters return CanonicalJob only; downstream logic does not read provider payloads.
Raw JSON and each external id/source URL are retained as source records; refreshed snapshots
retain their previous versions. Bounded lookback plus idempotent upserts handles overlapping runs.
Each provider/board is isolated, with per-record savepoints and persisted run statistics.

- JobSpy aggregator (optional dependency python-jobspy, MIT): https://github.com/speedyapply/JobSpy
  Uses documented scrape_jobs; site blocking/rate limits remain possible. No CAPTCHA bypass.
- Greenhouse: https://docs.greenhouse.io/job-board.html — public board read endpoints.
- Lever: https://github.com/lever/postings-api — public postings, not application submission.
- Ashby: https://developers.ashbyhq.com/docs/public-job-posting-api — public board postings.
- Broad discovery: https://freehire.me/docs/api — public search/list, paginated data envelope.

ATS boards must be configured; public endpoints do not discover all companies by themselves.
freehire supplies broad discovery. Workday and ats-scrapers are not V1 dependencies: native
public endpoints cover three ATS systems without copying upstream code. No upstream code
is vendored. Respect provider terms/rate limits. Completeness, freshness and salary cannot
be guaranteed; always verify the original listing. Synthetic demo data is labelled throughout.
