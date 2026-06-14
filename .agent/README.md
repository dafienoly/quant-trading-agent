# Agent Pipeline Runtime State

This directory stores machine-readable state, gate outputs, and handoff prompts
for the Issue-driven Agent pipeline.

Generated files include:

- `state.json`
- `current_task.yaml`
- `handoff/*.md`
- `gates/*.json`

Do not use private chat history as the pipeline source of truth. If a pipeline
stage matters, persist it here or under `docs/` / `feedback/bugs/`.
