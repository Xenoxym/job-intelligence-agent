# V1 acceptance ledger

## Local acceptance — verified 2026-09-14

- [x] Durable project documentation and candidate/matching/source/deployment policy
- [x] Docker Compose starts UI/API/PostgreSQL; migrations and restart persistence verified
- [x] Three source classes, retries, incremental ingestion and failure isolation
- [x] Canonical normalization, cross-source deduplication and preserved raw provenance
- [x] Editable structured candidate profile and search/location preferences
- [x] Explainable dimensions, strengths/gaps, seniority and decision labels
- [x] Senior/Staff/YOE never cause automatic rejection
- [x] Ranked/new jobs, search/filters, details, save/dismiss and pipeline UI
- [x] Preparation, resume recommendation and fact-only screening answers
- [x] Playwright assistance with review-before-submit and unknown fields unresolved
- [x] Persistent status history, notes, feedback and explainable reranking
- [x] Automated backend tests, frontend checks/build and workflow smoke pass
- [x] CI configuration including container validation; .env.example; architecture/licenses
- [x] Hosted strategy ready; exact missing authorization documented in BLOCKERS.md
- [ ] Actual hosted service deployed and verified — Render authorization not available

## Evidence

| Check | Executed result |
| --- | --- |
| `pytest -q` | 37 passed; includes API restart persistence, scoring/non-rejection, source contracts, dedup/provenance, feedback, word-boundary regressions and security |
| `ruff check backend migrations scripts tests` | Passed |
| `ruff format --check backend migrations scripts tests` | Passed, 22 Python files |
| `npm run check`, `npm run format:check`, `npm run build` | Passed; TypeScript + Prettier + Vite production bundle |
| `alembic upgrade head`, `alembic check` | Passed on SQLite fallback |
| `docker compose up --build -d --wait --wait-timeout 180` | Built final Linux image, migrated PostgreSQL, both services healthy |
| `docker compose exec -T app alembic check` | PostgreSQL schema matches model |
| `python scripts/smoke.py` | Ingest → normalize → rank → inspect → save → prepare → applied → interview → rerank |
| `python scripts/browser_smoke.py` | Desktop/mobile UI, filters, preparation, tracking, preferences and local autofill fixture passed; zero page errors |
| `docker compose restart`, then `docker compose up -d --wait` | Both services healthy after restart |
| `python scripts/smoke.py --verify-only` | Application status, preparation and history persisted through restart |
| Read-only live adapter checks | Greenhouse, Ashby and freehire each returned 3 canonical records with no malformed records; Lever request succeeded with zero matching roles on sampled board |
| Optional JobSpy query | Dependency installed; bounded 3-record query returned canonical records, no malformed records; upstream relevance varies |
| Full live ingestion through running API | 200 real jobs persisted from two ATS boards and two freehire searches; all four runs healthy, zero malformed records |
| Visual QA | Desktop 1440px and mobile 390px screenshots inspected; mobile filters fixed and rerun; no horizontal overflow |

Screenshots and persistence markers are in ignored `artifacts/`. Automated tests use fixtures
and do not rely on external job sites. External reads are documented smoke observations, not
claims of exhaustive provider coverage. Native dependency deprecation warnings are non-failing.

GitHub Actions run [34818075685](https://github.com/Xenoxym/job-intelligence-agent/actions/runs/34818075685)
passed all three jobs: backend, frontend and full container/browser/restart stack. The subsequent
responsibility-word-boundary regression is covered by the 37-test local suite and is revalidated
on push through the same workflow. The optional ingestion script also verified a clean skip
without deployment secrets. Cloud deployment is not claimed complete.
