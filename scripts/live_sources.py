"""Read-only adapter contract smoke; opt-in network test, never submits applications."""

import json

from backend.sources import ATS, Freehire

for source in [
    ATS("greenhouse", "anthropic", limit=3),
    ATS("ashby", "OpenAI", limit=3),
    ATS("lever", "weride", limit=3),
    Freehire("AI Engineer", limit=3),
]:
    try:
        result = source.fetch()
        print(
            json.dumps(
                {
                    "source": source.name,
                    "jobs": len(result.jobs),
                    "rejected": result.rejected,
                    "titles": [j.title for j in result.jobs],
                }
            )
        )
    except Exception as e:
        print(json.dumps({"source": source.name, "error": type(e).__name__}))
