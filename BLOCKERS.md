# External deployment authorization

The implementation can run locally without external credentials. No Render (or alternative
hosting provider) authorization was present in the environment, so a hosted deployment has
not been created or verified.

Minimum action: sign into Render, authorize this GitHub repository and approve the plans in
the checked-in `render.yaml` Blueprint. Alternatively, provide a Render API token through a
secure environment variable, the workspace/owner id, and explicit approval for the selected
paid resources. Then follow `docs/deployment.md` and verify the hosted URL and persistence.

Do not share credentials in committed files. Unknown application screening answers are normal
review items, not blockers to running the application.
