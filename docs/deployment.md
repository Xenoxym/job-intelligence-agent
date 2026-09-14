# Deployment

## Local production-shaped stack

Copy `.env.example` to `.env`, then `docker compose up --build`. UI/API: http://localhost:8000.
Health: `/health`. The app runs Alembic before startup; PostgreSQL is health-gated. Database
port is internal only, web port binds loopback. `docker compose restart` preserves state in
the named volume. Keep one app process/replica; V1 mutation serialization is process-local.

Use `docker compose logs app` and Source health for troubleshooting. Inspect PostgreSQL with
`docker compose exec db psql -U jobs -d jobs`. For a portable backup, avoid PowerShell binary
redirection: `docker compose exec db pg_dump -U jobs -d jobs -Fc -f /tmp/jobs.dump`, then
`docker compose cp db:/tmp/jobs.dump ./artifacts/jobs.dump`. Store backups privately.
Restore to an empty test database first with `pg_restore`; verify before replacing real state.

## Render (single-provider hosted path)

The checked-in `render.yaml` provisions one Docker web service and one managed PostgreSQL
database in the same region. It selects persistent paid tiers, avoiding an expiring trial
database. Review current costs in Render before authorizing resource creation. No cloud
resources have been created by this build.

1. Sign into Render and authorize access to `Xenoxym/job-intelligence-agent`.
2. Choose **New → Blueprint**, select the repository and `render.yaml` on `main`.
3. Review the web/database plans and authorize creation. The Dockerfile builds React, installs
   locked Python dependencies, migrates the managed database and starts one Uvicorn worker.
4. Render generates `API_TOKEN`. Retrieve it privately from the web service's environment.
   `APP_ENV=production` requires at least 32 characters; never paste the value into Git or logs.
5. Open the service's HTTPS URL, enter the token in the dashboard, configure company boards /
   preferences, then Discover jobs. Hosted demo seeding is off by default; Source health can
   load demo fixtures explicitly.
6. Verify `/health`, authenticated `/api/preferences`, discovery, a saved job and status history.
   Redeploy and confirm those records survive. Record the resulting URL in your private notes.

`RENDER_EXTERNAL_HOSTNAME` is added automatically to the allowed-host list. If attaching a
custom domain, set `ALLOWED_HOSTS=localhost,127.0.0.1,your.example.com`. Terminate TLS at Render.
Do not use multiple replicas until a database-backed ingestion/mutation lock is implemented.

To deploy using an API instead of the Render UI, the minimum authorization is a Render API
token and the authorized workspace/owner identifier, plus approval for the selected paid plans.
An existing managed PostgreSQL URL can replace the Blueprint database if preferred. Credentials
must be supplied through the environment or Render secret controls, not source files.

## Scheduled ingestion

Optional GitHub Actions schedule: weekdays at 12:17 UTC. Set repository variable
`JOB_INTELLIGENCE_URL` to the HTTPS base URL and secret `JOB_INTELLIGENCE_API_TOKEN` to its API
token. Missing configuration skips cleanly; already-running ingestion returns 409 and skips.
The task only discovers/ranks jobs and never submits applications.

## Rollback and persistence

Back up PostgreSQL before schema changes. Current schema has one initial Alembic revision;
rolling back application code does not erase the database. Do not run `alembic downgrade base`
against real data. Restore backups into a separate database for disaster recovery validation.
The Render disk is ephemeral; all important application state lives in PostgreSQL.

Reference: https://render.com/docs/blueprint-spec. Availability and prices must be reviewed in
the Render console at deployment time. Actual local checks are in V1_ACCEPTANCE_CRITERIA.md.
