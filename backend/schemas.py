from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CanonicalJob(StrictModel):
    external_id: str = Field(min_length=1, max_length=500)
    source: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=300)
    company_id: str | None = None
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=200000)
    location: str = "Unknown"
    country_codes: list[str] = Field(default_factory=list)
    work_mode: Literal["remote", "hybrid", "on-site", "unknown"] = "unknown"
    employment_type: str | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_currency: str | None = None
    salary_interval: str | None = None
    seniority: str = "unknown"
    posted_at: datetime | None = None
    source_url: HttpUrl
    apply_url: HttpUrl
    provider: str | None = None
    raw: dict = Field(default_factory=dict)
    is_demo: bool = False


class Evidence(StrictModel):
    category: str
    statement: str
    skills: list[str]


class Profile(StrictModel):
    name: str = Field(min_length=1)
    education: list[str]
    skills: list[str]
    evidence: list[Evidence]
    email: str | None = None
    phone: str | None = None
    years_experience: float | None = Field(default=None, ge=0)
    work_authorization: str | None = None
    sponsorship: str | None = None
    citizenship: str | None = None
    clearance: str | None = None
    demographics: str | None = None
    relocation: str | None = None
    salary_requirement: str | None = None
    resume_variants: list[str] = ["Agentic AI / AI Engineer", "ML / ML Infrastructure", "Data Science"]


class Preferences(StrictModel):
    countries: list[str] = ["us"]
    search_terms: list[str] = Field(default=["AI Engineer", "Machine Learning Engineer"], max_length=10)
    locations: list[str] = ["New York", "Jersey City", "US Remote", "San Francisco", "Seattle", "Boston"]
    preferred_companies: list[str] = []
    target_families: list[str] = [
        "agentic_ai",
        "ml_infrastructure",
        "ml_engineering",
        "research",
        "ai_software",
    ]
    greenhouse_boards: list[str] = ["anthropic"]
    lever_boards: list[str] = []
    ashby_boards: list[str] = ["OpenAI"]
    enable_jobspy: bool = False
    enable_freehire: bool = True
    lookback_hours: int = Field(default=168, ge=1, le=2160)
    max_jobs_per_source: int = Field(default=50, ge=1, le=200)
    application_mode: Literal["review"] = "review"

    @field_validator("greenhouse_boards", "lever_boards", "ashby_boards")
    @classmethod
    def validate_boards(cls, values):
        import re

        if len(values) > 20 or any(not re.fullmatch(r"[\w-]{1,100}", v) for v in values):
            raise ValueError("Use up to 20 board slugs containing letters, numbers, underscores or hyphens")
        return values


class Status(StrEnum):
    new = "new"
    reviewed = "reviewed"
    saved = "saved"
    dismissed = "dismissed"
    preparing = "preparing"
    ready_to_apply = "ready_to_apply"
    applied = "applied"
    oa = "oa"
    recruiter = "recruiter"
    interview = "interview"
    rejected = "rejected"
    offer = "offer"


class StatusUpdate(StrictModel):
    status: Status
    note: str = Field(default="", max_length=10000)


class IngestRequest(StrictModel):
    demo: bool = False
