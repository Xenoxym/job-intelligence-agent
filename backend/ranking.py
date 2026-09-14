import re
from datetime import timedelta
from typing import Protocol

from backend.db import now
from backend.normalization import utc

SKILLS = {
    "Python": ["python"],
    "SQL": ["sql"],
    "AWS": ["aws", "amazon web services"],
    "Amazon Bedrock": ["bedrock"],
    "RAG": ["rag", "retrieval augmented", "retrieval-augmented"],
    "OpenSearch": ["opensearch"],
    "hybrid retrieval": ["hybrid retrieval", "hybrid search"],
    "tool calling": ["tool calling", "tool execution", "function calling"],
    "Lambda": ["lambda"],
    "API Gateway": ["api gateway"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Twilio": ["twilio"],
    "SendGrid": ["sendgrid"],
    "automated testing": ["automated testing", "pytest"],
    "GitHub Actions": ["github actions"],
    "CloudWatch": ["cloudwatch"],
    "agent evaluation": ["agent evaluation", "tool-trajectory", "tool trajectories"],
    "observability": ["observability", "monitoring"],
    "PyTorch": ["pytorch"],
    "Hugging Face": ["hugging face", "transformers"],
    "PEFT": ["peft"],
    "LoRA": ["lora"],
    "QLoRA": ["qlora"],
    "Qwen": ["qwen"],
    "Ray": ["ray"],
    "DDP": ["ddp"],
    "DeepSpeed": ["deepspeed", "zero-3"],
    "MLflow": ["mlflow"],
    "MinIO": ["minio"],
    "vLLM": ["vllm"],
    "ONNX Runtime": ["onnx"],
    "TensorRT": ["tensorrt"],
    "FastAPI": ["fastapi"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Prometheus": ["prometheus"],
    "Grafana": ["grafana"],
    "C++": ["c++"],
    "Java": ["java"],
    "Go": ["golang", "go language"],
    "CUDA": ["cuda"],
    "TensorFlow": ["tensorflow"],
    "Spark": ["spark"],
    "Scala": ["scala"],
    "statistics": ["statistics", "statistical"],
    "A/B testing": ["a/b testing", "experimentation"],
}
CLUSTERS = {
    "agentic_ai": ["agentic", "agents", "tool calling", "tool execution", "bedrock"],
    "retrieval": ["retrieval", "rag", "opensearch"],
    "production": ["production", "deploy", "monitoring", "observability", "backend", "testing"],
    "training": ["fine-tun", "finetun", "training", "multimodal", "pytorch", "lora"],
    "distributed": ["distributed", "multi-gpu", "ray", "ddp", "deepspeed"],
    "inference": ["inference", "latency", "throughput", "vllm", "tensorrt"],
    "research": ["novel algorithms", "publish", "publications", "theoretical", "research agenda"],
    "management": ["manage a team", "direct reports", "hiring", "people management"],
    "analytics": ["dashboards", "business intelligence", "a/b testing", "statistical analysis"],
}


def contains(text, term):
    return bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I))


def extract_skills(text):
    return sorted(name for name, aliases in SKILLS.items() if any(contains(text, a) for a in aliases))


def role_family(title):
    t = title.lower()
    if any(x in t for x in ["agent", "llm", "applied ai"]):
        return "agentic_ai"
    if any(
        x in t
        for x in [
            "inference",
            "ml systems",
            "ml infrastructure",
            "ai infrastructure",
            "ml platform",
            "machine learning infrastructure",
        ]
    ):
        return "ml_infrastructure"
    if "research" in t:
        return "research"
    if any(x in t for x in ["machine learning", "ml engineer", "ai engineer"]):
        return "ml_engineering"
    if "software" in t and any(contains(t, x) for x in ["ai", "ml"]):
        return "ai_software"
    if "data scien" in t:
        return "data_science"
    return "other"


class Analyzer(Protocol):
    def analyze(self, data: dict) -> dict: ...


class RuleAnalyzer:
    def analyze(self, data):
        desc = data["description"]
        lines = [x.strip(" •-\t") for x in re.split(r"\n|(?<=[.;])\s+", desc) if x.strip()]
        required, preferred, responsibilities = [], [], []
        section = "responsibilities"
        for line in lines:
            low = line.lower()
            if any(x in low for x in ["preferred", "nice to have", "bonus", "ideally"]):
                target = preferred
                if len(line) < 80:
                    section = "preferred"
            elif any(
                x in low
                for x in ["required", "must have", "minimum qualifications", "requirements", "you bring"]
            ):
                target = required
                if len(line) < 80:
                    section = "required"
            elif any(x in low for x in ["responsibilities", "what you'll do", "what you will do"]):
                section = "responsibilities"
                target = responsibilities
            else:
                target = {"required": required, "preferred": preferred, "responsibilities": responsibilities}[
                    section
                ]
            target.append(line)
        seniority = next(
            (
                x
                for x in ["principal", "staff", "senior", "lead", "junior", "intern"]
                if contains(data["title"], x)
            ),
            data.get("seniority", "unknown"),
        )
        year_lines = [
            x
            for x in required + responsibilities
            if re.search(r"\b\d+\s*\+?\s*(?:[-–]\s*\d+\s*)?years?", x, re.I)
        ]
        years = [
            int(x)
            for line in year_lines
            for x in re.findall(r"\b(\d+)\s*\+?\s*(?:[-–]\s*\d+\s*)?years?", line, re.I)
        ]
        legal = [
            x for x in lines if re.search(r"sponsor|visa|authoriz|citizen|clearance|export control", x, re.I)
        ]
        responsibility_text = " ".join(responsibilities).lower()
        clusters = [
            name for name, terms in CLUSTERS.items() if any(term in responsibility_text for term in terms)
        ]
        return {
            "version": "rules-v1",
            "role_family": role_family(data["title"]),
            "skills": extract_skills(desc),
            "required_skills": extract_skills(" ".join(required)),
            "preferred_skills": extract_skills(" ".join(preferred)),
            "required_qualifications": required,
            "preferred_qualifications": preferred,
            "responsibilities": responsibilities,
            "responsibility_clusters": clusters,
            "seniority": seniority,
            "years_required": max(years) if years else None,
            "seniority_evidence": year_lines,
            "education_requirements": [
                x for x in lines if re.search(r"degree|bachelor|master|ph\.?d", x, re.I)
            ],
            "authorization_language": legal,
            "major_disqualifiers": legal,
            "infrastructure_expectations": [
                x
                for x in responsibilities
                if re.search(r"infrastructure|deploy|distributed|kubernetes", x, re.I)
            ],
            "research_expectations": [
                x for x in responsibilities if re.search(r"research|publish|novel", x, re.I)
            ],
            "production_expectations": [
                x for x in responsibilities if re.search(r"production|monitor|reliab", x, re.I)
            ],
            "domain": next(
                (
                    x
                    for x in ["healthcare", "finance", "robotics", "autonomous", "security"]
                    if contains(desc, x)
                ),
                "unspecified",
            ),
        }


OUTCOME_VALUE = {"applied": 0, "oa": 0.3, "recruiter": 0.5, "interview": 0.8, "offer": 1, "rejected": -0.3}


def feedback_adjustment(data, analysis, observations):
    changes = []
    for feature, value in {"role_family": analysis["role_family"], "work_mode": data["work_mode"]}.items():
        matching = [
            o
            for o in observations
            if o["features"].get(feature) == value and o["features"].get("is_demo", False) == data["is_demo"]
        ]
        if matching:
            delta = 6 * sum(OUTCOME_VALUE[o["outcome"]] for o in matching) / (len(matching) + 3)
            changes.append(
                {
                    "feature": feature,
                    "value": value,
                    "observations": len(matching),
                    "delta": round(delta, 2),
                    "outcomes": [o["outcome"] for o in matching],
                }
            )
    return round(max(-10, min(10, sum(x["delta"] for x in changes))), 2), changes


def rank(data, analysis, profile, prefs, discovered_at, observations=()):
    candidate = {s.lower() for s in profile.skills}
    required = analysis["required_skills"]
    relevant_skills = required or [s for s in analysis["skills"] if s not in analysis["preferred_skills"]]
    matched = [s for s in relevant_skills if s.lower() in candidate]
    missing = [s for s in relevant_skills if s.lower() not in candidate]
    technical = 100 * len(matched) / len(relevant_skills) if relevant_skills else 50
    clusters = analysis["responsibility_clusters"]
    evidence = [e for e in profile.evidence if e.category in clusters]
    supported = {e.category for e in evidence}
    responsibility = 100 * len(supported) / len(clusters) if clusters else 40
    evidence_skills = {s.lower() for e in profile.evidence for s in e.skills}
    evidence_strength = (
        100 * sum(s.lower() in evidence_skills for s in relevant_skills) / len(relevant_skills)
        if relevant_skills
        else 40
    )
    senior = analysis["seniority"] in {"senior", "staff", "principal", "lead"}
    years = analysis["years_required"]
    tenure_gap = years is not None and (profile.years_experience is None or profile.years_experience < years)
    seniority_gap = 60 if tenure_gap else 35 if senior else 0
    strengths = [e.statement for e in evidence]
    gaps = [f"No verified evidence for required skill: {s}" for s in missing]
    gaps += [f"Responsibility evidence missing: {c}" for c in clusters if c not in supported]
    if tenure_gap:
        gaps.append(
            f"JD asks for {years}+ years; candidate tenure is {profile.years_experience if profile.years_experience is not None else 'unknown'}. This is a gap, not an automatic rejection."
        )
    if senior:
        gaps.append(
            f"{analysis['seniority'].title()} scope needs review; assess ownership and leadership against evidence."
        )
    location = data["location"].lower()
    us = "us" in [x.lower() for x in data.get("country_codes", [])] or bool(
        re.search(
            r"united states|\busa?\b|new york|jersey|san francisco|bay area|seattle|boston|\b(ny|nj|ca|wa|ma|tx|il|co|fl|va|dc)\b",
            location,
        )
    )
    preferred_loc = any(x.lower() in location for x in prefs.locations if x.lower() != "us remote")
    if "remote" == data["work_mode"] and us and "US Remote" in prefs.locations:
        preferred_loc = True
    location_fit = 100 if preferred_loc else 70 if us else 30
    if not us and not preferred_loc:
        gaps.append(
            "US eligibility/location unclear or outside preferred geography; verify original listing."
        )
    age = max(
        0,
        (now() - (utc(data.get("posted_at")) or utc(discovered_at))).total_seconds()
        / timedelta(days=1).total_seconds(),
    )
    freshness = max(0, 100 - age * 3)
    if not data.get("posted_at"):
        gaps.append("Posted date unknown; freshness uses first discovery time.")
    if len(data["description"]) < 100:
        gaps.append("Insufficient job description; open the original posting before deciding.")
    if analysis["authorization_language"]:
        gaps.append("Explicit eligibility language requires review; no legal eligibility inferred.")
    family = analysis["role_family"]
    components = {
        "technical_fit": (technical, "Required skill coverage; preferred-only skills excluded"),
        "experience_fit": (
            responsibility * 0.8 + 20 * (not tenure_gap),
            "Demonstrated work with a limited tenure uncertainty penalty",
        ),
        "evidence_strength": (evidence_strength, "Skills linked to concrete profile evidence"),
        "responsibility_fit": (responsibility, "Responsibility groups supported by candidate evidence"),
        "seniority_gap": (
            seniority_gap,
            "Higher means more scope/tenure uncertainty; never a rejection rule",
        ),
        "skills_gap": (100 - technical, "Higher means more required skill gaps"),
        "role_family_fit": (
            100 if family in prefs.target_families else 20,
            f"Normalized role family: {family}",
        ),
        "company_relevance": (
            100 if data["company"].lower() in [x.lower() for x in prefs.preferred_companies] else 50,
            "Explicit company preference or neutral prior",
        ),
        "location_fit": (location_fit, "Configured geography; remote alone does not imply US eligibility"),
        "freshness": (freshness, f"{age:.1f} days since posting or first discovery"),
        "application_effort": (
            50 if analysis["authorization_language"] else 20,
            "Estimated review friction; higher means more effort",
        ),
    }
    weights = {
        "technical_fit": 0.19,
        "experience_fit": 0.13,
        "evidence_strength": 0.14,
        "responsibility_fit": 0.20,
        "role_family_fit": 0.14,
        "company_relevance": 0.04,
        "location_fit": 0.10,
        "freshness": 0.06,
    }
    base = sum(components[k][0] * w for k, w in weights.items())
    delta, changes = feedback_adjustment(data, analysis, observations)
    score = round(max(0, min(100, base + delta)), 1)
    decision = (
        "APPLY" if score >= 72 else "REVIEW" if score >= 52 else "LOW PRIORITY" if score >= 32 else "SKIP"
    )
    if decision == "APPLY" and (
        analysis["authorization_language"] or len(data["description"]) < 100 or (not us and not preferred_loc)
    ):
        decision = "REVIEW"
    return {
        "version": "rules-v1",
        "score": score,
        "base_score": round(base, 1),
        "decision": decision,
        "components": {
            k: {"score": round(v[0], 1), "explanation": v[1], "weight": weights.get(k, 0)}
            for k, v in components.items()
        },
        "strengths": strengths or ["No responsibility-level evidence identified; manual review needed."],
        "gaps": gaps,
        "matched_skills": matched,
        "missing_skills": missing,
        "reasons": [
            f"{family.replace('_', ' ')} role; {len(supported)}/{len(clusters)} responsibility groups supported.",
            f"{len(matched)}/{len(relevant_skills)} required or core skills supported.",
        ]
        + (["Eligibility or listing completeness needs review."] if decision == "REVIEW" else []),
        "feedback_adjustment": delta,
        "feedback_explanation": changes,
        "ranked_at": now().isoformat(),
    }
