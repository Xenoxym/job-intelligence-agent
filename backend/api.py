import logging
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text

from backend.applications import change_status, prepare
from backend.db import (
    Feedback,
    IngestRun,
    Job,
    Setting,
    SourceRecord,
    StatusEvent,
    make_engine,
    now,
    session_factory,
)
from backend.schemas import IngestRequest, Preferences, Profile, StatusUpdate
from backend.service import bootstrap, configuration, ingest, rerank
from backend.sources import Demo, configured_sources


def create_app(engine=None, seed_demo=None):
    engine = engine or make_engine()
    factory = session_factory(engine)
    mutation_lock = threading.Lock()
    token = os.getenv("API_TOKEN", "")
    if os.getenv("APP_ENV") == "production" and len(token) < 32:
        raise RuntimeError("Production requires API_TOKEN with at least 32 characters")

    @asynccontextmanager
    async def lifespan(app):
        with factory() as session:
            bootstrap(session)
            empty = not session.scalar(select(func.count()).select_from(Job))
        demo = seed_demo if seed_demo is not None else os.getenv("SEED_DEMO", "true").lower() == "true"
        if empty and demo:
            ingest(factory, [Demo()])
        yield

    app = FastAPI(title="Job Intelligence", version="0.1.0", lifespan=lifespan)
    app.state.factory = factory

    @app.middleware("http")
    async def response_security(request, call_next):
        # Local tokenless mode still blocks cross-origin mutations / DNS rebinding.
        if request.url.path.startswith("/api") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            allowed = {str(request.base_url).rstrip("/"), "http://localhost:5173", "http://127.0.0.1:5173"}
            if origin and origin not in allowed:
                from starlette.responses import JSONResponse

                return JSONResponse({"detail": "Cross-origin mutation denied"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    from starlette.middleware.trustedhost import TrustedHostMiddleware

    hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if render_host:
        hosts.append(render_host)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    def auth(request: Request):
        if token and not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {token}"):
            raise HTTPException(401, "Enter the configured API token")

    def session_dep():
        with factory() as session:
            yield session

    def locked():
        if not mutation_lock.acquire(blocking=False):
            raise HTTPException(409, "Another update is running; retry shortly")
        try:
            yield
        finally:
            mutation_lock.release()

    api = APIRouter(prefix="/api", dependencies=[Depends(auth)])

    def get_job(session, job_id):
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job

    def summary(job):
        return {
            "id": job.id,
            **job.data,
            "status": job.status,
            "discovered_at": job.discovered_at,
            "updated_at": job.updated_at,
            "analysis": job.analysis,
            "ranking": job.ranking,
        }

    @app.get("/health")
    def health():
        with factory() as session:
            session.execute(text("SELECT 1"))
            session.execute(select(Setting.key).limit(1))
        return {"status": "ok"}

    @api.get("/jobs")
    def jobs(
        q: str = "",
        status: str = "",
        decision: str = "",
        work_mode: str = "",
        family: str = "",
        source: str = "",
        location: str = "",
        view: str = "ranked",
        demo: bool | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        session=Depends(session_dep),
    ):
        query = select(Job)
        if status:
            query = query.where(Job.status == status)
        elif view in {"ranked", "today"}:
            query = query.where(Job.status != "dismissed")
        if demo is not None:
            query = query.where(Job.is_demo == demo)
        if view == "today":
            query = query.where(Job.discovered_at >= now() - timedelta(hours=24))
        if view == "pipeline":
            query = query.where(Job.status.notin_(["new", "reviewed", "dismissed"]))
        rows = []
        for job in session.scalars(query):
            d = job.data
            if q.lower() not in f"{job.company} {job.title} {d['description']}".lower():
                continue
            if decision and job.ranking.get("decision") != decision:
                continue
            if work_mode and d["work_mode"] != work_mode:
                continue
            if family and job.analysis.get("role_family") != family:
                continue
            if location and location.lower() not in d["location"].lower():
                continue
            if source and not session.scalar(
                select(SourceRecord.id).where(
                    SourceRecord.job_id == job.id, SourceRecord.source.contains(source)
                )
            ):
                continue
            rows.append(summary(job))
        rows.sort(key=lambda x: x["ranking"].get("score", 0), reverse=True)
        return {"total": len(rows), "jobs": rows[offset : offset + limit]}

    @api.get("/jobs/{job_id}")
    def detail(job_id: int, session=Depends(session_dep)):
        job = get_job(session, job_id)
        sources = [
            {
                "id": s.id,
                "source": s.source,
                "external_id": s.external_id,
                "source_url": s.source_url,
                "first_seen": s.first_seen,
                "last_seen": s.last_seen,
                "raw": s.raw,
            }
            for s in session.scalars(select(SourceRecord).where(SourceRecord.job_id == job_id))
        ]
        history = [
            {
                "id": e.id,
                "previous": e.previous,
                "status": e.status,
                "note": e.note,
                "created_at": e.created_at,
            }
            for e in session.scalars(
                select(StatusEvent).where(StatusEvent.job_id == job_id).order_by(StatusEvent.id.desc())
            )
        ]
        return {**summary(job), "preparation": job.preparation, "sources": sources, "history": history}

    @api.post("/jobs/{job_id}/status", dependencies=[Depends(locked)])
    def update_status(job_id: int, body: StatusUpdate, session=Depends(session_dep)):
        job = get_job(session, job_id)
        try:
            change_status(session, job, body.status, body.note)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        session.flush()
        rerank(session)
        session.commit()
        return summary(job)

    @api.post("/jobs/{job_id}/prepare", dependencies=[Depends(locked)])
    def preparation(job_id: int, session=Depends(session_dep)):
        job = get_job(session, job_id)
        profile, _ = configuration(session)
        job.preparation = prepare(job, profile)
        if job.status in {"new", "reviewed", "saved", "dismissed", "preparing", "ready_to_apply"}:
            change_status(session, job, "preparing", "Generated a fact-grounded draft; user review required")
        session.commit()
        return job.preparation

    @api.get("/profile")
    def profile(session=Depends(session_dep)):
        return configuration(session)[0]

    @api.put("/profile", dependencies=[Depends(locked)])
    def set_profile(body: Profile, session=Depends(session_dep)):
        session.get(Setting, "profile").value = body.model_dump()
        # Existing drafts contain old facts and must be prepared again after edits.
        for job in session.scalars(select(Job).where(Job.preparation.is_not(None))):
            job.preparation = None
            if job.status == "ready_to_apply":
                change_status(session, job, "preparing", "Profile changed; review a fresh draft")
        rerank(session)
        session.commit()
        return body

    @api.get("/preferences")
    def preferences(session=Depends(session_dep)):
        return configuration(session)[1]

    @api.put("/preferences", dependencies=[Depends(locked)])
    def set_preferences(body: Preferences, session=Depends(session_dep)):
        session.get(Setting, "preferences").value = body.model_dump()
        rerank(session)
        session.commit()
        return body

    @api.post("/ingest", dependencies=[Depends(locked)])
    def run_ingest(body: IngestRequest, session=Depends(session_dep)):
        _, prefs = configuration(session)
        return {"runs": ingest(factory, [Demo()] if body.demo else configured_sources(prefs))}

    @api.post("/rerank", dependencies=[Depends(locked)])
    def run_rerank(session=Depends(session_dep)):
        count = rerank(session)
        session.commit()
        return {"ranked": count}

    @api.get("/stats")
    def stats(session=Depends(session_dep)):
        counts = dict(session.execute(select(Job.status, func.count()).group_by(Job.status)).all())
        runs = [
            {
                "id": r.id,
                "source": r.source,
                "status": r.status,
                "discovered": r.discovered,
                "deduplicated": r.deduplicated,
                "ranked": r.ranked,
                "errors": r.errors,
                "message": r.message,
                "duration_ms": r.duration_ms,
                "started_at": r.started_at,
            }
            for r in session.scalars(select(IngestRun).order_by(IngestRun.id.desc()).limit(30))
        ]
        return {
            "total": sum(counts.values()),
            "statuses": counts,
            "feedback_count": session.scalar(select(func.count()).select_from(Feedback)),
            "runs": runs,
        }

    app.include_router(api)
    dist = Path(__file__).resolve().parents[1] / "frontend/dist"
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/")
    def index():
        if not (dist / "index.html").exists():
            raise HTTPException(503, "Frontend not built; run npm ci and npm run build in frontend")
        return FileResponse(dist / "index.html")

    return app


logging.basicConfig(level=logging.INFO, format="%(message)s")
app = create_app()
