from datetime import timedelta

import pytest
from sqlalchemy import func, select

from backend.applications import change_status, prepare
from backend.db import Feedback, Job, Snapshot, SourceRecord, now
from backend.normalization import canonical_url, normalized, upsert
from backend.ranking import RuleAnalyzer, extract_skills, rank
from backend.schemas import CanonicalJob
from backend.service import ingest, rerank
from backend.sources import Batch, Demo


def scored(item, profile, prefs, observations=()):
    data = normalized(item)
    analysis = RuleAnalyzer().analyze(data)
    return rank(data, analysis, profile, prefs, now(), observations)


def test_normalization_and_url_identity():
    item = (
        Demo()
        .fetch()
        .jobs[0]
        .model_copy(update={"description": "<p>Build <b>RAG</b></p>", "company": "  Northstar   Labs  "})
    )
    data = normalized(item)
    assert data["description"] == "Build\nRAG"
    assert data["company"] == "Northstar Labs"
    assert canonical_url("https://EXAMPLE.com/job/?utm_source=x&jobId=1") == "https://example.com/job?jobId=1"
    assert canonical_url("https://example.com/job?jobId=1") != canonical_url(
        "https://example.com/job?jobId=2"
    )


def test_cross_source_dedup_and_raw_snapshot(factory):
    a = Demo().fetch().jobs[0]
    b = a.model_copy(
        update={
            "source": "second",
            "external_id": "different",
            "apply_url": str(a.apply_url) + "?utm_source=feed",
            "raw": {"second": True},
        }
    )
    with factory() as s:
        first, duplicate = upsert(s, a)
        assert not duplicate
        second, duplicate = upsert(s, b)
        assert duplicate and second.id == first.id
        upsert(s, a.model_copy(update={"raw": {"changed": True}}))
        s.commit()
        assert s.scalar(select(func.count()).select_from(Job)) == 1
        assert s.scalar(select(func.count()).select_from(SourceRecord)) == 2
        assert s.scalar(select(func.count()).select_from(Snapshot)) == 3
        discovered = first.discovered_at
        upsert(s, a)
        assert first.discovered_at == discovered


def test_similarity_dedup_and_distinct_locations(factory):
    a = Demo().fetch().jobs[0]
    with factory() as s:
        first, _ = upsert(s, a)
        b = a.model_copy(
            update={"source": "mirror", "external_id": "mirror-1", "apply_url": "https://example.org/job/123"}
        )
        mirror, duplicate = upsert(s, b)
        assert duplicate and mirror.id == first.id
        c = b.model_copy(
            update={
                "external_id": "mirror-2",
                "apply_url": "https://example.org/job/456",
                "location": "Boston",
            }
        )
        _, duplicate = upsert(s, c)
        assert not duplicate


def test_reposts_far_apart_remain_separate(factory):
    a = Demo().fetch().jobs[0]
    b = a.model_copy(
        update={
            "source": "second",
            "external_id": "new",
            "apply_url": "https://example.org/new",
            "posted_at": now() - timedelta(days=90),
        }
    )
    with factory() as s:
        upsert(s, a)
        _, duplicate = upsert(s, b)
        assert not duplicate


@pytest.mark.parametrize(
    "title",
    [
        "Senior ML Infrastructure Engineer",
        "Staff ML Infrastructure Engineer",
        "Principal ML Infrastructure Engineer",
    ],
)
def test_seniority_never_automatically_rejects(title, profile, prefs):
    item = Demo().fetch().jobs[1].model_copy(update={"title": title})
    result = scored(item, profile, prefs)
    assert result["decision"] == "APPLY"
    assert result["score"] >= 72
    assert any("7+ years" in s for s in result["gaps"])
    assert "seniority_gap" in result["components"]


def test_responsibility_evidence_beats_keywords(profile, prefs):
    item = Demo().fetch().jobs[0]
    unsupported = item.model_copy(
        update={
            "description": "Responsibilities\nManage a team with direct reports, hiring and people management.\nRequired: Python, AWS, RAG, automated testing."
        }
    )
    assert scored(item, profile, prefs)["score"] > scored(unsupported, profile, prefs)["score"] + 15


def test_preferred_skills_not_required(profile, prefs):
    item = Demo().fetch().jobs[4]
    result = scored(item, profile, prefs)
    assert "CUDA" not in result["missing_skills"]
    assert "C++" not in result["missing_skills"]


def test_skill_boundaries():
    assert "Ray" not in extract_skills("array spray xray")
    assert "Java" not in extract_skills("JavaScript")
    assert "C++" in extract_skills("Use C++ and Python.")


def test_unknown_eligibility_requires_review(profile, prefs):
    result = scored(Demo().fetch().jobs[3], profile, prefs)
    assert result["decision"] == "REVIEW"
    assert any("eligibility" in x for x in result["gaps"])


def test_missing_description_not_apply(profile, prefs):
    item = Demo().fetch().jobs[0].model_copy(update={"description": ""})
    assert scored(item, profile, prefs)["decision"] != "APPLY"


def test_unknown_location_not_us_remote(profile, prefs):
    item = Demo().fetch().jobs[0].model_copy(update={"location": "Remote", "work_mode": "remote"})
    assert scored(item, profile, prefs)["components"]["location_fit"]["score"] < 70


def test_source_failure_and_bad_record_isolation(factory):
    class Failed:
        name = "failed"

        def fetch(self, since=None):
            raise TimeoutError("private token must not be logged")

    class Mixed:
        name = "mixed"

        def fetch(self, since=None):
            return Batch([object(), Demo().fetch().jobs[0]])

    runs = ingest(factory, [Failed(), Mixed(), Demo()])
    assert [r["status"] for r in runs] == ["failed", "partial", "ok"]
    assert runs[1]["discovered"] == 1
    assert "private" not in runs[0]["message"]
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(Job)) == 8


def test_feedback_persists_is_idempotent_and_changes_ranking(factory):
    ingest(factory, [Demo()])
    with factory() as s:
        job = s.scalar(select(Job).where(Job.title == "Applied AI Engineer"))
        base = job.ranking["score"]
        change_status(s, job, "applied")
        change_status(s, job, "interview")
        change_status(s, job, "interview", "Same outcome, another note")
        s.flush()
        rerank(s)
        s.commit()
        assert job.ranking["score"] > base
        assert s.scalar(select(func.count()).select_from(Feedback)) == 1
        assert job.ranking["feedback_explanation"][0]["observations"] == 1
        with pytest.raises(ValueError):
            change_status(s, job, "new")
    with factory() as s:
        assert s.get(Job, job.id).status == "interview"


def test_demo_feedback_never_changes_real_rank(profile, prefs):
    job = Demo().fetch().jobs[0].model_copy(update={"is_demo": False})
    observations = [
        {
            "outcome": "offer",
            "features": {"role_family": "agentic_ai", "work_mode": "hybrid", "is_demo": True},
        }
    ]
    assert scored(job, profile, prefs, observations)["feedback_adjustment"] == 0


def test_preparation_never_invents_facts(factory, profile):
    ingest(factory, [Demo()])
    with factory() as s:
        job = s.scalar(select(Job))
        result = prepare(job, profile)
        for key in [
            "years_experience",
            "sponsorship",
            "work_authorization",
            "citizenship",
            "clearance",
            "salary_requirement",
            "demographics",
            "relocation",
            "email",
        ]:
            assert result["screening_answers"][key]["answer"] is None
            assert result["screening_answers"][key]["needs_review"]
        assert "3.93" in result["cover_letter"]
        assert result["resume_variant"] in profile.resume_variants


def test_canonical_rejects_non_http_url():
    with pytest.raises(ValueError):
        CanonicalJob(
            external_id="x",
            source="x",
            company="x",
            title="x",
            source_url="javascript:alert(1)",
            apply_url="file:///etc/passwd",
        )
