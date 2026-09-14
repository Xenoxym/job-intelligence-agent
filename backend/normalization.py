import hashlib
import html
import json
import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from sqlalchemy import select

from backend.db import Job, Snapshot, SourceRecord, now
from backend.schemas import CanonicalJob


def plain(value: str) -> str:
    soup = BeautifulSoup(html.unescape(value or ""), "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def company_key(value: str) -> str:
    return re.sub(r"\s+(inc|llc|ltd|corporation|corp)$", "", key(value))


def canonical_url(value: str) -> str:
    u = urlsplit(str(value))
    host = (u.hostname or "").lower()
    segments = u.path.strip("/").split("/")
    if host in {"jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com"} and len(segments) >= 2:
        provider = "ashby" if "ashbyhq" in host else "lever"
        return f"ats:{provider}:{segments[0].lower()}:{segments[1]}"
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io", "boards.eu.greenhouse.io"}:
        match = re.search(r"/jobs/(\d+)", u.path)
        if match:
            return f"ats:greenhouse:{match.group(1)}"
    query = [
        (k, v)
        for k, v in parse_qsl(u.query)
        if not k.lower().startswith("utm_") and k.lower() not in {"source", "ref", "referrer", "gh_src"}
    ]
    return urlunsplit(("https", u.netloc.lower(), u.path.rstrip("/"), urlencode(sorted(query)), ""))


def utc(value):
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def normalized(item: CanonicalJob) -> dict:
    data = item.model_dump(mode="json", exclude={"raw"})
    data["description"] = plain(item.description)
    data["company"] = re.sub(r"\s+", " ", item.company).strip()
    data["title"] = re.sub(r"\s+", " ", item.title).strip()
    if data["work_mode"] == "unknown":
        location = item.location.lower()
        data["work_mode"] = (
            "hybrid" if "hybrid" in location else "remote" if "remote" in location else "unknown"
        )
    return data


def find_duplicate(session, data):
    same_url = session.scalar(
        select(Job).where(Job.apply_key == canonical_url(data["apply_url"]), Job.is_demo == data["is_demo"])
    )
    if same_url and (
        same_url.apply_key.startswith("ats:")
        or (same_url.company_key == company_key(data["company"]) and same_url.title_key == key(data["title"]))
    ):
        return same_url
    candidates = session.scalars(
        select(Job).where(
            Job.company_key == company_key(data["company"]),
            Job.title_key == key(data["title"]),
            Job.is_demo == data["is_demo"],
        )
    )
    for job in candidates:
        old = job.data
        # Conservative fallback: distinct locations or short descriptions remain separate.
        if key(old["location"]) != key(data["location"]) or len(data["description"]) < 100:
            continue
        dates = utc(old.get("posted_at")), utc(data.get("posted_at"))
        if all(dates) and abs((dates[0] - dates[1]).days) > 14:
            continue
        if SequenceMatcher(None, old["description"].lower(), data["description"].lower()).ratio() >= 0.93:
            return job
    return None


def upsert(session, item):
    data = normalized(item)
    record = session.scalar(
        select(SourceRecord).where(
            SourceRecord.source == item.source, SourceRecord.external_id == item.external_id
        )
    )
    job = session.get(Job, record.job_id) if record else find_duplicate(session, data)
    duplicate = job is not None
    if not job:
        job = Job(
            company=data["company"],
            title=data["title"],
            company_key=company_key(data["company"]),
            title_key=key(data["title"]),
            apply_key=canonical_url(data["apply_url"]),
            data=data,
            is_demo=item.is_demo,
        )
        session.add(job)
        session.flush()
    elif data["source"] == job.data["source"] or len(data["description"]) > len(job.data["description"]):
        job.data = data
        job.company, job.title = data["company"], data["title"]
        job.company_key, job.title_key = company_key(data["company"]), key(data["title"])
        job.apply_key = canonical_url(data["apply_url"])
    job.updated_at = now()
    raw = item.raw or item.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()
    if not record:
        record = SourceRecord(
            job_id=job.id,
            source=item.source,
            external_id=item.external_id,
            source_url=str(item.source_url),
            raw=raw,
            content_hash=digest,
        )
        session.add(record)
        session.flush()
        session.add(Snapshot(source_record_id=record.id, raw=raw))
    elif digest != record.content_hash:
        record.raw, record.content_hash = raw, digest
        record.source_url = str(item.source_url)
        session.add(Snapshot(source_record_id=record.id, raw=raw))
    record.last_seen = now()
    return job, duplicate
