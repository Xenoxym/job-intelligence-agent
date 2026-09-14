# Job Intelligence V1

Authoritative initial specification: user-provided “Codex V1 Autonomous Build Task.md”.
Mission: identify worthwhile newly available US AI/ML opportunities, explain fit, prepare
applications, track outcomes and adapt rankings. Primary candidate: Chengqian Luo.

Workflow: discovery → ingestion → normalization → deduplication → deterministic JD analysis
→ candidate-aware ranking → shortlist → preparation → review-gated browser assistance
→ application tracking → outcome feedback → reranking.

One FastAPI service serves a React SPA and API; PostgreSQL persists jobs, source snapshots,
candidate/preferences, scores, preparation, status history and feedback. Alembic owns schema.
Three source classes: optional JobSpy aggregator, public Greenhouse/Lever/Ashby ATS boards,
and freehire discovery. Sources use a canonical Pydantic model and independent transactions.
Demo jobs are explicitly synthetic. No LLM key required. No automatic external submission.

Dashboard: new jobs, ranked shortlist, filters, details, score components, strengths/gaps,
save/dismiss, preparation, applied/outcome updates, pipeline and editable preferences/profile.
Resume categories: Agentic AI, ML infrastructure, Data Science. All preparation uses only
profile facts, never inferred tenure or legal answers. Seniority is assessed as a gap.

Local target: copy .env.example to .env; docker compose up --build; http://localhost:8000.
Hosted target: same Docker service on Render with managed PostgreSQL and API authentication.
No paid services or cloud resources created without authorization. See deployment docs.

Non-goals: mass auto-application, PDF resume perfection, sophisticated learning-to-rank,
enterprise observability, distributed orchestration. Feedback is a bounded, interpretable prior.
