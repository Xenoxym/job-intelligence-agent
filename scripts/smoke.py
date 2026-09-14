"""Exercise the running API using synthetic jobs only; safe to repeat."""

import argparse
import json
import os
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    token = os.getenv("API_TOKEN")
    with httpx.Client(
        base_url=args.base_url, headers={"Authorization": f"Bearer {token}"} if token else {}, timeout=180
    ) as c:
        assert c.get("/health").json()["status"] == "ok"
        assert c.get("/").status_code == 200
        if args.verify_only:
            marker = json.loads(Path("artifacts/persistence-marker.json").read_text())
            job = c.get(f"/api/jobs/{marker['job_id']}").json()
            assert job["status"] == marker["status"]
            assert job["preparation"]["resume_variant"] == marker["resume_variant"]
            assert any(e["note"] == "API smoke: verified outcome" for e in job["history"])
            print("PASS: health, UI and application/preparation/history survived restart")
            return
        response = c.post("/api/ingest", json={"demo": True})
        response.raise_for_status()
        jobs = c.get("/api/jobs", params={"demo": "true"}).json()["jobs"]
        job = next(j for j in jobs if j["title"] == "Applied AI Engineer")
        path = f"/api/jobs/{job['id']}"
        if job["status"] not in ["applied", "oa", "recruiter", "interview", "rejected", "offer"]:
            c.post(
                path + "/status", json={"status": "saved", "note": "API smoke: shortlist"}
            ).raise_for_status()
        prepared = c.post(path + "/prepare")
        prepared.raise_for_status()
        assert prepared.json()["screening_answers"]["sponsorship"]["answer"] is None
        for status in ["applied", "interview"]:
            c.post(
                path + "/status", json={"status": status, "note": "API smoke: verified outcome"}
            ).raise_for_status()
        c.post("/api/rerank").raise_for_status()
        result = c.get(path).json()
        assert result["ranking"]["feedback_adjustment"] > 0
        assert result["sources"] and result["history"]
        Path("artifacts").mkdir(exist_ok=True)
        Path("artifacts/persistence-marker.json").write_text(
            json.dumps(
                {
                    "job_id": job["id"],
                    "status": "interview",
                    "resume_variant": prepared.json()["resume_variant"],
                }
            )
        )
        print("PASS: ingest > normalize > rank > inspect > save > prepare > applied > interview > rerank")


if __name__ == "__main__":
    main()
