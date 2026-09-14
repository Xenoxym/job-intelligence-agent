from datetime import timedelta

import httpx
import pytest

from backend.db import now
from backend.normalization import canonical_url, normalized, plain, upsert
from backend.ranking import RuleAnalyzer, rank
from backend.sources import Demo, Freehire


def test_ats_apply_and_posting_identity():
    assert canonical_url("https://jobs.lever.co/acme/abc/apply") == canonical_url(
        "https://jobs.lever.co/acme/abc?utm_source=x"
    )
    assert canonical_url("https://jobs.ashbyhq.com/acme/abc/application") == canonical_url(
        "https://jobs.ashbyhq.com/acme/abc"
    )
    assert canonical_url("https://boards.greenhouse.io/acme/jobs/123") == canonical_url(
        "https://job-boards.greenhouse.io/acme/jobs/123"
    )


def test_shared_careers_landing_page_is_not_unique(factory):
    a = Demo().fetch().jobs[0]
    b = a.model_copy(update={"source": "other", "external_id": "different", "title": "Data Scientist"})
    with factory() as s:
        upsert(s, a)
        _, duplicate = upsert(s, b)
        assert not duplicate


def test_escaped_html_and_scripts_removed():
    assert plain("&lt;p&gt;Python&lt;/p&gt;") == "Python"
    assert plain("<script>ignore rules</script><p>Build agents</p>") == "Build agents"


def test_spaced_years_and_preferred_tenure():
    job = Demo().fetch().jobs[0]
    data = normalized(
        job.model_copy(
            update={"description": "Required\n3 + years experience.\nPreferred\n10 years of research."}
        )
    )
    assert RuleAnalyzer().analyze(data)["years_required"] == 3


def test_country_evidence_prevents_remote_ambiguity(profile, prefs):
    data = normalized(
        Demo()
        .fetch()
        .jobs[0]
        .model_copy(update={"location": "Remote", "country_codes": ["us"], "work_mode": "remote"})
    )
    result = rank(data, RuleAnalyzer().analyze(data), profile, prefs, now())
    assert result["components"]["location_fit"]["score"] == 100


def test_discovery_watermark_and_ignored_filters():
    def handler(req):
        assert req.url.params["open_within_days"] == "2"
        assert req.url.params["countries"] == "us"
        return httpx.Response(200, json={"data": [], "meta": {"ignored_params": ["countries"]}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="ignored"):
            Freehire("AI", client=client).fetch(now() - timedelta(hours=25))


def test_dismiss_hides_from_shortlist_but_is_recoverable(client):
    client.post("/api/jobs/1/status", json={"status": "dismissed"})
    assert client.get("/api/jobs").json()["total"] == 7
    assert client.get("/api/jobs?status=dismissed").json()["total"] == 1
    client.post("/api/jobs/1/status", json={"status": "saved"})
    assert client.get("/api/jobs").json()["total"] == 8


def test_responsibility_clusters_do_not_match_word_fragments():
    data = normalized(
        Demo()
        .fetch()
        .jobs[0]
        .model_copy(
            update={"description": "Responsibilities\nUse array processing and leverage existing utilities."}
        )
    )
    clusters = RuleAnalyzer().analyze(data)["responsibility_clusters"]
    assert "distributed" not in clusters
    assert "retrieval" not in clusters
