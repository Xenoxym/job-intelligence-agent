import json
import logging
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from backend.db import Feedback, IngestRun, Job, Setting, now
from backend.normalization import upsert, utc
from backend.ranking import RuleAnalyzer, rank
from backend.schemas import Preferences, Profile

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("ingestion")


def bootstrap(session):
    if not session.get(Setting, "profile"):
        profile = Profile.model_validate_json((ROOT / "config/candidate.json").read_text(encoding="utf-8"))
        session.add(Setting(key="profile", value=profile.model_dump()))
    if not session.get(Setting, "preferences"):
        session.add(Setting(key="preferences", value=Preferences().model_dump()))
    session.commit()


def configuration(session):
    return Profile.model_validate(session.get(Setting, "profile").value), Preferences.model_validate(
        session.get(Setting, "preferences").value
    )


def rerank(session):
    profile, prefs = configuration(session)
    observations = [{"outcome": f.outcome, "features": f.features} for f in session.scalars(select(Feedback))]
    count = 0
    for job in session.scalars(select(Job)):
        job.analysis = RuleAnalyzer().analyze(job.data)
        job.ranking = rank(job.data, job.analysis, profile, prefs, job.discovered_at, observations)
        count += 1
    session.flush()
    return count


def ingest(factory, sources):
    results = []
    for source in sources:
        start = time.monotonic()
        with factory() as session:
            _, prefs = configuration(session)
            last = session.scalar(
                select(IngestRun)
                .where(IngestRun.source == source.name, IngestRun.status == "ok")
                .order_by(IngestRun.id.desc())
            )
            since = (
                (utc(last.started_at) - timedelta(hours=24))
                if last
                else now() - timedelta(hours=prefs.lookback_hours)
            )
            run = IngestRun(
                source=source.name, status="running", discovered=0, deduplicated=0, ranked=0, errors=0
            )
            session.add(run)
            session.commit()
            try:
                batch = source.fetch(since)
                run.errors = batch.rejected
                for item in batch.jobs:
                    try:
                        with session.begin_nested():
                            _, duplicate = upsert(session, item)
                        run.deduplicated += int(duplicate)
                        run.discovered += int(not duplicate)
                        run.ranked += 1
                    except Exception as exc:
                        run.errors += 1
                        log.warning(
                            json.dumps(
                                {"event": "record_failed", "source": source.name, "type": type(exc).__name__}
                            )
                        )
                run.status = "partial" if run.errors else "ok"
                session.commit()
            except Exception as exc:
                session.rollback()
                run = session.get(IngestRun, run.id)
                run.status, run.errors = "failed", 1
                # Avoid persisting provider request URLs, tokens or untrusted error bodies.
                run.message = f"{type(exc).__name__}: source failed; check network, provider availability and optional dependency configuration"
            run.duration_ms = round((time.monotonic() - start) * 1000)
            session.commit()
            summary = {
                k: getattr(run, k)
                for k in [
                    "id",
                    "source",
                    "status",
                    "discovered",
                    "deduplicated",
                    "ranked",
                    "errors",
                    "message",
                    "duration_ms",
                ]
            }
            log.info(json.dumps({"event": "ingestion", **summary}))
            results.append(summary)
    with factory() as session:
        rerank(session)
        session.commit()
    return results
