"""Optional scheduled ingestion of an existing authenticated deployment."""

import os

import httpx

url, token = os.getenv("JOB_INTELLIGENCE_URL"), os.getenv("API_TOKEN")
if not url or not token:
    print("Skipped: deployment URL / API token not configured")
else:
    response = httpx.post(
        url.rstrip("/") + "/api/ingest",
        json={"demo": False},
        headers={"Authorization": f"Bearer {token}"},
        timeout=600,
    )
    if response.status_code == 409:
        print("Skipped: ingestion already running")
    else:
        response.raise_for_status()
        for run in response.json()["runs"]:
            print(f"{run['source']}: {run['status']}; new={run['discovered']}; errors={run['errors']}")
