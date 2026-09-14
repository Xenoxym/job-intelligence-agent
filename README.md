# Scout — Personal Job Intelligence

A working V1 for Chengqian Luo: discover US AI/ML opportunities, explain candidate fit,
prepare fact-grounded applications, track outcomes and improve prioritization. No LLM key
is required. Applications are always reviewed and manually submitted by the user.

## Start locally

Requires Docker Desktop / Docker Engine with Compose. From this repository:

```sh
cp .env.example .env
docker compose up --build
```

PowerShell uses `Copy-Item .env.example .env`. Open **http://localhost:8000**.
API health: http://localhost:8000/health. Interactive API: http://localhost:8000/docs.
The first run migrates PostgreSQL and loads eight clearly labelled synthetic jobs.
The `postgres_data` named volume preserves jobs, profile/preferences, drafts, notes and outcomes
across container restarts/rebuilds. `docker compose down` preserves it; `down -v` deletes it.

Use **Discover jobs** for live ATS and freehire ingestion. **Source health** reports every
provider's success/failure, new/duplicate/ranked counts and timing. Demo jobs can be filtered
out with **Real jobs only**. Demo feedback never influences real-job rankings.

## Daily workflow

1. Check **New in 24 hours**, or the ranked opportunities. Search by company, role or skill;
   filter geography, work mode, recommendation, source, family, status and demo/real data.
2. Open a job for score components, responsibilities, seniority, evidence, gaps and provenance.
3. Save it, or dismiss it. Dismissed jobs stay retrievable through the status filter.
4. **Prepare application** recommends a resume category and drafts a cover letter plus verified
   screening answers. Unknown legal and personal facts stay unresolved. Review the actual resume.
5. Open the original application. Submit manually in your normal browser, then record **applied**.
6. Record OA, recruiter, interview, rejection or offer and notes. Rankings update immediately;
   details show exactly which observed outcomes changed the score.

**Preferences** edits structured JSON with server validation. Candidate edits invalidate old
drafts so stale facts cannot silently persist. Export the profile for the local browser helper.
Do not put private profile exports or resumes into version control.

## Architecture

```text
JobSpy aggregator ─┐
Greenhouse/Lever/  ├─ CanonicalJob → normalization/dedup → JD rules → ranking
Ashby ATS         │                         │                     │
freehire discovery┘                    PostgreSQL ← drafts/status/feedback
                                                                  │
                                          FastAPI + React dashboard
```

One Python 3.12 service serves the API and built React/TypeScript SPA. SQLAlchemy 2 + Alembic
manage PostgreSQL. SQLite is an optional native fallback and test backend. A single process /
worker serializes mutations; read requests remain available during ingestion. Use one web
replica in V1. There are no separate workers or distributed infrastructure.

Domain files in `backend/`: `schemas`, `sources`, `normalization`, `ranking`, `applications`,
`browser_assist`, `service`, `db`, `api`. Frontend in `frontend/src`; contract/regression tests
in `tests`; runnable smoke tools in `scripts`. Durable policy is in `PROJECT_SPEC.md`,
`AGENTS.md` and `docs/`.

Raw provenance is stored per external source id; changed payloads add historical snapshots.
Dedup uses ATS identities, canonical URLs and conservative company/title/location/description
similarity with a posting-date window. Repeated runs retain first discovery times and status.
Source runs are isolated; one bad record/provider does not roll back successful providers.

## Matching and preparation

Scoring combines required skill coverage, evidence strength, responsibility groups, role family,
geography, freshness and explicit company preferences. Component weights and reasons are
returned by the API. Higher gap/effort dimensions mean more uncertainty; they are diagnostic
rather than direct positive weights. Senior/Staff titles and years requirements never trigger
automatic rejection. Required eligibility language forces review instead of guessing eligibility.

The latest outcome per job contributes a smoothed role-family/work-mode prior, capped at ten
points. Repeating an outcome adds history but does not multiply training observations. This is
an interpretable heuristic, not a calibrated probability of success. See `docs/matching_policy.md`.
Rule-based JD extraction can miss nuanced requirements: inspect the full original description.

## Browser assistance

This is a **local helper**, not a cloud browser or mass submission service:

```sh
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m backend.browser_assist --url "https://jobs.lever.co/COMPANY/JOB_ID/apply" --profile /path/to/exported-profile.json
```

It opens a visible, temporary Chromium session, loads a public HTTPS page, disconnects its
network before filling uniquely labelled name/email/phone fields with verified values, and
reports unresolved required controls. It never clicks submit or checks attestations. Custom
controls, resume uploads, CAPTCHA and unsupported forms need manual handling. Pages that rely
on live POST requests may not fully load. Review there, then use your normal browser to submit.
No cookies or browser sessions are persisted. `application_mode=auto` is intentionally rejected.
A future submission strategy must add an explicit authorization gate; source/ranking code need
not change. The analyzer uses a protocol so future semantic providers can replace deterministic rules.

## Native development / SQLite fallback

```sh
python -m venv .venv
# Activate .venv (Windows: .venv\Scripts\Activate.ps1)
python -m pip install -r requirements.lock
python -m pip install -e '.[dev]'
cd frontend
npm ci
npm run build
cd ..
alembic upgrade head
uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Default native database: `jobs.db` in the repository root (ignored by Git). Set `DATABASE_URL`
in the process environment for both Alembic and Uvicorn to use PostgreSQL instead. Compose
reads `.env`; native commands do not automatically load it. Use `npm run dev` in `frontend`
for Vite at http://localhost:5173, which proxies API calls to port 8000.

## Validation

```sh
pytest -q
ruff check backend migrations scripts tests
ruff format --check backend migrations scripts tests
alembic check
cd frontend
npm run check
npm run format:check
npm run build
cd ..
python scripts/smoke.py
python scripts/browser_smoke.py
docker compose restart
docker compose up -d --wait
python scripts/smoke.py --verify-only
```

Smoke scripts operate on demo jobs; browser tests also use an isolated local form fixture.
Screenshots and restart markers go into ignored `artifacts/`. `scripts/live_sources.py` is an
optional read-only network check. CI runs backend tests/lint, frontend checks/build, actual
container build, migrations, browser workflow and restart persistence.

## Sources, licensing and limitations

- [JobSpy](https://github.com/speedyapply/JobSpy), MIT, via `python-jobspy`, provides the aggregator
  adapter. Enable it in Preferences. Dependency is included in the container lock; native minimal
  installs can add `pip install -e '.[aggregator]'`. Providers can block requests or return
  weak matches; no CAPTCHA/proxy bypass is implemented.
- [Greenhouse](https://docs.greenhouse.io/job-board.html),
  [Lever](https://github.com/lever/postings-api), and
  [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api) use public read endpoints.
  Set company board slugs in Preferences. Defaults: Anthropic and OpenAI. Not all employers use
  these ATS systems, and a board slug may change. Greenhouse posted dates may be unavailable.
- [freehire](https://freehire.me/docs/api) provides broad discovery with full descriptions,
  country filters, bounded pagination and an overlapping first-recorded lookback window.
  Ignored provider filters cause a visible source error rather than silently widening results.
- `ats-scrapers` was evaluated as an alternative; native endpoints are used instead. No upstream
  scraper source is copied. See `THIRD_PARTY_NOTICES.md` and `docs/data_sources.md`.

Live data is best-effort, not an exhaustive index. Each source has a configured result cap;
raise it or narrow searches when needed. ATS feeds are rescanned and upserted because public
APIs do not uniformly support deltas; freehire and JobSpy use lookback windows. Older openings
may remain in storage after closing, so verify the application URL before investing effort.
Malformed records are counted, not accepted. Salary interval/currency remain unknown when absent.

## Hosted deployment and security

`render.yaml` defines one Docker service and managed PostgreSQL. Follow `docs/deployment.md`.
Hosted resources can incur charges and are not provisioned automatically by local setup.
Production refuses startup without a 32+ character API token. The UI asks for the token and
keeps it in tab session storage. API access is bearer-authenticated; no multiuser accounts in V1.
Local Compose binds only `127.0.0.1`; do not change to public exposure without authentication.
Secrets belong in environment variables, never Git. Raw job descriptions render as text,
not trusted HTML. Job descriptions are data, never executable instructions.

Optional weekday ingestion runs in GitHub Actions only when `JOB_INTELLIGENCE_URL` repository
variable and `JOB_INTELLIGENCE_API_TOKEN` secret are configured. Otherwise it exits successfully
with a skipped message. Current validation evidence is in `V1_ACCEPTANCE_CRITERIA.md`.
