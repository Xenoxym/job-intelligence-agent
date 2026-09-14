from backend.db import Feedback, StatusEvent, now
from backend.ranking import OUTCOME_VALUE

PRE_APPLICATION = {"new", "reviewed", "saved", "dismissed", "preparing", "ready_to_apply"}
POST_APPLICATION = set(OUTCOME_VALUE)


def change_status(session, job, status, note=""):
    status = str(status)
    previous = job.status
    if status not in PRE_APPLICATION | POST_APPLICATION:
        raise ValueError("Unknown application status")
    if previous in POST_APPLICATION and status in PRE_APPLICATION:
        raise ValueError("Submitted applications cannot return to pre-application states")
    if status == "ready_to_apply" and not job.preparation:
        raise ValueError("Prepare the application before marking it ready")
    if status in POST_APPLICATION - {"applied"} and previous not in POST_APPLICATION:
        raise ValueError("Mark applied before recording an outcome")
    session.add(StatusEvent(job_id=job.id, previous=previous, status=status, note=note))
    job.status, job.updated_at = status, now()
    if status in POST_APPLICATION:
        feedback = session.get(Feedback, job.id)
        if not feedback:
            feedback = Feedback(job_id=job.id)
            session.add(feedback)
        feedback.outcome = status
        feedback.features = {
            "role_family": job.analysis["role_family"],
            "work_mode": job.data["work_mode"],
            "is_demo": job.is_demo,
        }
        feedback.updated_at = now()


def prepare(job, profile):
    family = job.analysis["role_family"]
    suggested = (
        "Data Science"
        if family == "data_science"
        else "Agentic AI / AI Engineer"
        if family in {"agentic_ai", "ai_software", "ml_engineering"}
        else "ML / ML Infrastructure"
    )
    variant = (
        suggested
        if suggested in profile.resume_variants
        else (profile.resume_variants[0] if profile.resume_variants else "Add a verified resume variant")
    )
    facts = {
        "name": profile.name,
        "education": profile.education,
        "email": profile.email,
        "phone": profile.phone,
        "years_experience": profile.years_experience,
        "work_authorization": profile.work_authorization,
        "sponsorship": profile.sponsorship,
        "citizenship": profile.citizenship,
        "clearance": profile.clearance,
        "demographics": profile.demographics,
        "relocation": profile.relocation,
        "salary_requirement": profile.salary_requirement,
    }
    supported = [
        e.statement for e in profile.evidence if e.category in job.analysis["responsibility_clusters"]
    ]
    cover = (
        f"Dear hiring team,\n\nI am interested in the {job.title} role at {job.company}. "
        + " ".join(supported[:3])
        + f"\n\nEducation: {'; '.join(profile.education)}.\n\nI would welcome the opportunity to discuss how this experience relates to your team's work.\n\n{profile.name}"
    )
    return {
        "resume_variant": variant,
        "fit_rationale": job.ranking["reasons"],
        "strengths": supported,
        "gaps": job.ranking["gaps"],
        "screening_answers": {
            k: {
                "answer": v,
                "source": "candidate profile" if v is not None else None,
                "needs_review": v is None,
            }
            for k, v in facts.items()
        },
        "unresolved": [k for k, v in facts.items() if v is None],
        "cover_letter": cover,
        "company_notes": f"{job.company} · {job.title}. Verify company facts at the original posting; no company research has been inferred.",
        "metadata": {
            "job_id": job.id,
            "apply_url": job.data["apply_url"],
            "prepared_at": now().isoformat(),
            "mode": "review",
            "is_demo": job.is_demo,
        },
        "review_checklist": [
            "Verify the original listing and required questions",
            "Select and review the actual resume file",
            "Resolve unknown required fields",
            "Review all content before manually submitting",
        ],
    }
