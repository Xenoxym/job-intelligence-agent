from fastapi.testclient import TestClient

from backend.api import create_app


def test_complete_workflow(client, engine):
    assert client.get("/health").json() == {"status": "ok"}
    jobs = client.get("/api/jobs").json()["jobs"]
    assert len(jobs) == 8
    job = next(j for j in jobs if j["title"] == "Applied AI Engineer")
    path = f"/api/jobs/{job['id']}"
    assert client.post(path + "/status", json={"status": "ready_to_apply"}).status_code == 409
    assert client.post(path + "/status", json={"status": "interview"}).status_code == 409
    for status in ["reviewed", "saved", "dismissed", "saved"]:
        assert client.post(path + "/status", json={"status": status}).status_code == 200
    prep = client.post(path + "/prepare").json()
    assert prep["screening_answers"]["sponsorship"]["answer"] is None
    for status in ["ready_to_apply", "applied", "oa", "recruiter", "interview", "rejected", "offer"]:
        r = client.post(path + "/status", json={"status": status, "note": f"Recorded {status}"})
        assert r.status_code == 200, r.text
    detail = client.get(path).json()
    assert detail["ranking"]["score"] > job["ranking"]["score"]
    assert detail["sources"][0]["raw"]["synthetic"]
    assert detail["history"][0]["note"] == "Recorded offer"
    assert client.get("/api/jobs?view=pipeline").json()["total"] == 1
    assert client.post("/api/ingest", json={"demo": True}).json()["runs"][0]["discovered"] == 0
    assert client.get("/api/stats").json()["feedback_count"] == 1
    with TestClient(create_app(engine, seed_demo=False)) as restarted:
        assert restarted.get(path).json()["status"] == "offer"
        assert restarted.get(path).json()["preparation"] is not None


def test_config_filters_and_validation(client):
    assert client.get("/api/jobs?q=Ray").json()["total"] >= 1
    assert client.get("/api/jobs?demo=false").json()["total"] == 0
    assert client.get("/api/jobs?work_mode=remote").json()["total"] == 1
    assert client.get("/api/jobs?location=Seattle").json()["total"] == 1
    assert client.get("/api/jobs?source=synthetic").json()["total"] == 8
    assert client.get("/api/jobs?limit=1").json()["total"] == 8
    assert client.get("/api/jobs?limit=1").json()["jobs"].__len__() == 1
    assert client.get("/api/jobs/999").status_code == 404
    prefs = client.get("/api/preferences").json()
    prefs["application_mode"] = "auto"
    assert client.put("/api/preferences", json=prefs).status_code == 422
    prefs["application_mode"] = "review"
    prefs["locations"] = ["Seattle"]
    assert client.put("/api/preferences", json=prefs).status_code == 200
    assert client.get("/api/preferences").json()["locations"] == ["Seattle"]
    prefs["greenhouse_boards"] = ["../../localhost"]
    assert client.put("/api/preferences", json=prefs).status_code == 422
    assert client.post("/api/jobs/1/status", json={"status": "fabricated"}).status_code == 422


def test_profile_updates_invalidate_old_drafts(client):
    path = "/api/jobs/1"
    client.post(path + "/prepare")
    client.post(path + "/status", json={"status": "ready_to_apply"})
    profile = client.get("/api/profile").json()
    profile["email"] = "candidate@example.com"
    assert client.put("/api/profile", json=profile).status_code == 200
    detail = client.get(path).json()
    assert detail["preparation"] is None
    assert detail["status"] == "preparing"
    assert (
        client.post(path + "/prepare").json()["screening_answers"]["email"]["answer"]
        == "candidate@example.com"
    )


def test_auth_and_origin_protection(engine, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "a" * 40)
    monkeypatch.setenv("APP_ENV", "production")
    with TestClient(create_app(engine, seed_demo=False)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/profile").status_code == 401
        assert client.get("/api/profile", headers={"Authorization": "Bearer " + "a" * 40}).status_code == 200
        assert (
            client.post(
                "/api/rerank",
                headers={"Origin": "https://evil.example", "Authorization": "Bearer " + "a" * 40},
            ).status_code
            == 403
        )
        assert client.get("/health", headers={"Host": "evil.example"}).status_code == 400


def test_production_fails_closed(engine, monkeypatch):
    import pytest

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("API_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        create_app(engine)
