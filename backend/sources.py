import json
import math
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx

from backend.db import now
from backend.normalization import utc
from backend.schemas import CanonicalJob


@dataclass
class Batch:
    jobs: list[CanonicalJob] = field(default_factory=list)
    rejected: int = 0


class Source(Protocol):
    name: str

    def fetch(self, since: datetime | None = None) -> Batch: ...


def get_json(client, url, params=None):
    for attempt in range(3):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            retry = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in {
                429,
                500,
                502,
                503,
                504,
            }
            if attempt == 2 or not retry:
                raise
            time.sleep(min(2**attempt, 4))


def date(value):
    if value in (None, "", "NaT"):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class ATS:
    def __init__(self, provider, board, limit=100, client=None):
        self.provider, self.board, self.limit = provider, board, limit
        self.name = f"{provider}:{board}"
        self.client = client

    def fetch(self, since=None):
        urls = {
            "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{self.board}/jobs?content=true",
            "lever": f"https://api.lever.co/v0/postings/{self.board}?mode=json",
            "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{self.board}?includeCompensation=true",
        }
        with httpx.Client(timeout=20, follow_redirects=False) as owned:
            payload = get_json(self.client or owned, urls[self.provider])
        rows = payload if self.provider == "lever" else payload["jobs"]
        batch = Batch()
        # Scan the whole bounded public board so relevant roles are not hidden by ordering.
        from backend.ranking import role_family

        for row in rows:
            try:
                job = self.parse(row)
                if role_family(job.title) != "other":
                    batch.jobs.append(job)
                    if len(batch.jobs) >= self.limit:
                        break
            except (ValueError, TypeError, KeyError):
                batch.rejected += 1
        return batch

    def parse(self, row):
        common = {
            "source": self.name,
            "company": self.board,
            "company_id": self.board,
            "provider": self.provider,
            "raw": row,
        }
        if self.provider == "greenhouse":
            return CanonicalJob(
                **common,
                external_id=str(row["id"]),
                title=row["title"],
                description=row.get("content", ""),
                location=row.get("location", {}).get("name") or "Unknown",
                source_url=row["absolute_url"],
                apply_url=row["absolute_url"],
            )
        if self.provider == "lever":
            categories = row.get("categories") or {}
            lists = "\n".join(f"{x.get('text', '')}\n{x.get('content', '')}" for x in row.get("lists", []))
            salary = row.get("salaryRange") or {}
            return CanonicalJob(
                **common,
                external_id=row["id"],
                title=row["text"],
                description=(row.get("descriptionPlain") or row.get("description", "")) + "\n" + lists,
                location=categories.get("location") or "Unknown",
                employment_type=categories.get("commitment"),
                work_mode=row.get("workplaceType")
                if row.get("workplaceType") in {"remote", "hybrid", "on-site"}
                else "unknown",
                posted_at=date(row.get("createdAt")),
                source_url=row["hostedUrl"],
                apply_url=row["applyUrl"],
                salary_min=salary.get("min"),
                salary_max=salary.get("max"),
                salary_currency=salary.get("currency"),
                salary_interval=salary.get("interval"),
            )
        return CanonicalJob(
            **common,
            external_id=str(row.get("id") or row["jobUrl"]),
            title=row["title"],
            description=row.get("descriptionPlain") or row.get("descriptionHtml", ""),
            location=row.get("location") or "Unknown",
            work_mode="remote" if row.get("isRemote") else "unknown",
            employment_type=row.get("employmentType"),
            posted_at=date(row.get("publishedAt")),
            source_url=row["jobUrl"],
            apply_url=row["applyUrl"],
        )


class Freehire:
    def __init__(self, query, limit=50, client=None, countries=None):
        self.name = f"freehire:{query}"
        self.query, self.limit, self.client = query, limit, client
        self.countries = countries if countries is not None else ["us"]

    def fetch(self, since=None):
        batch = Batch()
        with httpx.Client(timeout=20) as owned:
            for offset in range(0, self.limit, 100):
                payload = get_json(
                    self.client or owned,
                    "https://freehire.me/api/v1/agent/jobs/search",
                    {
                        "q": f'"{self.query}"',
                        "q_fields": "title",
                        "description_format": "text",
                        "limit": min(100, self.limit - offset),
                        "offset": offset,
                        "sort": "created_at",
                        "order": "desc",
                        "countries": ",".join(self.countries),
                        **(
                            {
                                "open_within_days": max(
                                    1, math.ceil((now() - utc(since)).total_seconds() / 86400)
                                )
                            }
                            if since
                            else {}
                        ),
                    },
                )
                rows = payload["data"]
                if payload.get("meta", {}).get("ignored_params"):
                    raise ValueError("Provider ignored configured filters; refusing misleading broad results")
                if not isinstance(rows, list):
                    raise ValueError("Unexpected freehire response shape")
                for row in rows:
                    try:
                        batch.jobs.append(self.parse(row))
                    except (ValueError, TypeError, KeyError):
                        batch.rejected += 1
                if len(rows) < min(100, self.limit - offset):
                    break
        return batch

    def parse(self, row):
        company = row.get("company") or row.get("company_name") or "Unknown"
        if isinstance(company, dict):
            company = company.get("name", "Unknown")
        url = row.get("apply_url") or row.get("url") or row.get("source_url")
        return CanonicalJob(
            source=self.name,
            external_id=str(row["public_slug"]),
            company=company,
            title=row["title"],
            description=row.get("description") or "",
            location=row.get("location") or "Unknown",
            country_codes=row.get("countries") or [],
            work_mode="on-site"
            if row.get("work_mode") == "onsite"
            else row.get("work_mode")
            if row.get("work_mode") in {"remote", "hybrid", "on-site"}
            else "unknown",
            posted_at=date(row.get("posted_at")),
            salary_min=row.get("salary_min"),
            salary_max=row.get("salary_max"),
            salary_currency=row.get("salary_currency"),
            salary_interval=row.get("salary_period"),
            employment_type=row.get("employment_type"),
            seniority=row.get("seniority") or "unknown",
            source_url=row.get("source_url") or url,
            apply_url=url,
            provider=row.get("ats") or row.get("source"),
            raw=row,
        )


class JobSpy:
    def __init__(self, query, location="USA", limit=50, lookback=168):
        self.name = f"jobspy:{query}:{location}"
        self.query, self.location, self.limit, self.lookback = query, location, limit, lookback

    def fetch(self, since=None):
        # A subprocess provides a real timeout even if upstream requests hang.
        config = {"query": self.query, "location": self.location, "limit": self.limit, "hours": self.lookback}
        result = subprocess.run(
            [sys.executable, "-m", "backend.jobspy_worker"],
            input=json.dumps(config),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode:
            raise RuntimeError(
                "JobSpy unavailable or provider failed; install .[aggregator] and check provider access"
            )
        batch = Batch()
        for row in json.loads(result.stdout):
            try:
                batch.jobs.append(
                    CanonicalJob(
                        source=self.name,
                        external_id=str(row.get("id") or row["job_url"]),
                        company=row.get("company") or "Unknown",
                        title=row["title"],
                        description=row.get("description") or "",
                        location=row.get("location") or "Unknown",
                        work_mode="remote" if row.get("is_remote") else "unknown",
                        posted_at=date(row.get("date_posted")),
                        salary_min=row.get("min_amount"),
                        salary_max=row.get("max_amount"),
                        salary_currency=row.get("currency"),
                        salary_interval=row.get("interval"),
                        employment_type=row.get("job_type"),
                        source_url=row["job_url"],
                        apply_url=row.get("job_url_direct") or row["job_url"],
                        raw=row,
                    )
                )
            except (ValueError, TypeError, KeyError):
                batch.rejected += 1
        return batch


class Demo:
    name = "demo:synthetic"

    def fetch(self, since=None):
        examples = [
            (
                "Northstar Labs",
                "Applied AI Engineer",
                "New York, NY, US",
                "hybrid",
                "Build production agentic workflows, RAG and hybrid retrieval. Deploy backend tool calling with Bedrock, Lambda, PostgreSQL and OpenSearch. Monitor agent evaluation and observability.\nRequired: Python, AWS, RAG, automated testing.\nPreferred: Go language.",
            ),
            (
                "Vector Works",
                "Senior ML Infrastructure Engineer",
                "US Remote",
                "remote",
                "Responsibilities\nBuild distributed multi-GPU training with Ray, PyTorch DDP and Kubernetes. Optimize inference latency with vLLM and TensorRT. Deploy production monitoring.\nRequirements\nPython, Ray, PyTorch, Kubernetes, vLLM. 7+ years of experience.\nPreferred\nDeepSpeed and MLflow.",
            ),
            (
                "Atlas Research",
                "Research Engineer, Multimodal",
                "San Francisco, CA, US",
                "on-site",
                "Responsibilities\nDevelop multimodal training and evaluation pipelines using Qwen, PyTorch, LoRA and Hugging Face. Run distributed training experiments.\nRequired: Python, PyTorch, LoRA.\nPreferred: PhD and publications.",
            ),
            (
                "Harbor AI",
                "LLM Engineer",
                "Boston, MA, US",
                "hybrid",
                "Build RAG retrieval pipelines and production agents with tool calling, OpenSearch and FastAPI. Evaluate agents and monitor production reliability.\nRequired: Python, RAG, FastAPI.\nMust be authorized to work in the United States. Sponsorship is not available.",
            ),
            (
                "Cedar Systems",
                "Inference Engineer",
                "Seattle, WA, US",
                "on-site",
                "Optimize inference latency and throughput using vLLM, ONNX Runtime and TensorRT. Build production services with Docker, Kubernetes and monitoring.\nRequired: Python, vLLM, TensorRT.\nPreferred: CUDA and C++.",
            ),
            (
                "Bright Metrics",
                "Data Scientist",
                "Jersey City, NJ, US",
                "hybrid",
                "Build dashboards and statistical analysis for business intelligence. Own A/B testing and experimentation.\nRequired: SQL, Python, statistics, Spark.\nPreferred: Scala.",
            ),
            (
                "Orchid Robotics",
                "Staff Research Scientist",
                "London, UK",
                "on-site",
                "Lead a research agenda in novel algorithms and publish theoretical results. Manage a team with direct reports and hiring responsibilities.\nRequired: PhD, C++, CUDA and 10+ years of experience.",
            ),
            (
                "Pine Software",
                "Account Executive",
                "New York, NY, US",
                "on-site",
                "Own sales quota, prospect customer accounts and close enterprise contracts. Manage pipeline and commercial negotiations.\nRequired: enterprise sales experience and customer relationship management.",
            ),
        ]
        jobs = []
        for i, (company, title, location, mode, desc) in enumerate(examples):
            jobs.append(
                CanonicalJob(
                    external_id=f"synthetic-{i}",
                    source=self.name,
                    company=company,
                    title=title,
                    description=desc,
                    location=location,
                    work_mode=mode,
                    salary_min=140000 + i * 5000,
                    salary_max=190000 + i * 5000,
                    salary_currency="USD",
                    salary_interval="yearly",
                    posted_at=now() - timedelta(days=i),
                    source_url=f"https://example.com/demo/jobs/{i}",
                    apply_url=f"https://example.com/demo/jobs/{i}",
                    is_demo=True,
                    raw={"synthetic": True, "fixture": i},
                )
            )
        return Batch(jobs)


def configured_sources(prefs):
    sources = []
    for provider in ["greenhouse", "lever", "ashby"]:
        sources.extend(
            ATS(provider, board, prefs.max_jobs_per_source) for board in getattr(prefs, f"{provider}_boards")
        )
    for query in prefs.search_terms:
        if prefs.enable_freehire:
            sources.append(Freehire(query, prefs.max_jobs_per_source, countries=prefs.countries))
        if prefs.enable_jobspy:
            sources.append(JobSpy(query, limit=prefs.max_jobs_per_source, lookback=prefs.lookback_hours))
    return sources
