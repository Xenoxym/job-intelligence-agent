import json

import httpx
import pytest

from backend.sources import ATS, Freehire, JobSpy, get_json


@pytest.mark.parametrize(
    ("provider", "payload"),
    [
        (
            "greenhouse",
            {
                "jobs": [
                    {
                        "id": 123,
                        "title": "AI Engineer",
                        "content": "<p>Build agents</p>",
                        "location": {"name": "New York"},
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
                    }
                ]
            },
        ),
        (
            "lever",
            [
                {
                    "id": "123",
                    "text": "ML Engineer",
                    "descriptionPlain": "Build inference",
                    "lists": [{"text": "Required", "content": "Python"}],
                    "categories": {"location": "Seattle", "commitment": "Full-time"},
                    "createdAt": 1700000000000,
                    "hostedUrl": "https://jobs.lever.co/acme/123",
                    "applyUrl": "https://jobs.lever.co/acme/123/apply",
                }
            ],
        ),
        (
            "ashby",
            {
                "jobs": [
                    {
                        "id": "123",
                        "title": "Research Engineer",
                        "descriptionPlain": "Train models",
                        "location": "US Remote",
                        "isRemote": True,
                        "publishedAt": "2026-09-01T00:00:00Z",
                        "jobUrl": "https://jobs.ashbyhq.com/acme/123",
                        "applyUrl": "https://jobs.ashbyhq.com/acme/123/application",
                    }
                ]
            },
        ),
    ],
)
def test_ats_adapters(provider, payload):
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))) as client:
        batch = ATS(provider, "acme", client=client).fetch()
    assert len(batch.jobs) == 1
    assert batch.jobs[0].raw
    assert batch.jobs[0].provider == provider


def test_freehire_pagination_and_invalid_record():
    requests = []

    def handler(req):
        requests.append(req)
        offset = int(req.url.params["offset"])
        rows = [
            {
                "public_slug": str(offset + i),
                "company": "Acme",
                "title": "AI Engineer",
                "description": "Build agents",
                "location": "USA",
                "url": f"https://example.com/jobs/{offset + i}",
            }
            for i in range(100 if offset == 0 else 2)
        ]
        if offset:
            rows.append({"bad": "shape"})
        return httpx.Response(200, json={"data": rows, "meta": {"total": 103}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        batch = Freehire("AI Engineer", limit=200, client=client).fetch()
    assert len(requests) == 2
    assert len(batch.jobs) == 102
    assert batch.rejected == 1
    assert requests[0].url.params["q_fields"] == "title"


def test_retry_transient_only(monkeypatch):
    monkeypatch.setattr("backend.sources.time.sleep", lambda _: None)
    codes = iter([429, 503, 200])
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(next(codes), json={"ok": True}))
    ) as client:
        assert get_json(client, "https://example.com") == {"ok": True}
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(403))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            get_json(client, "https://example.com")


def test_jobspy_maps_output(monkeypatch):
    from types import SimpleNamespace

    rows = [
        {
            "id": "i",
            "company": "Acme",
            "title": "AI Engineer",
            "description": "Build agents",
            "location": "USA",
            "job_url": "https://example.com/i",
            "is_remote": True,
            "date_posted": "2026-09-01",
        }
    ]
    monkeypatch.setattr(
        "backend.sources.subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(rows)),
    )
    batch = JobSpy("AI Engineer").fetch()
    assert batch.jobs[0].work_mode == "remote"
    assert batch.jobs[0].raw == rows[0]
