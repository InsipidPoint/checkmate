# Acceptance Criteria: Checkmate Skill Publication-Ready

## Must Pass (blocking)

- [ ] `README.md` exists at `/root/clawd/skills/checkmate/README.md` and contains all of the following section headings (exact match not required, but content must cover): What It Is, How It Works, Installation, Usage, Loop Mechanics, Workspace Layout, and Resuming Interrupted Runs
- [ ] `README.md` contains an architecture diagram — either ASCII art or an embedded image — illustrating the intake → worker → judge loop flow
- [ ] `run.py` contains explicit error handling for all three of: (1) worker session failure or non-response, (2) judge timeout or session failure, (3) malformed judge output that does not contain a clear PASS or FAIL signal — each verifiable by grep or code inspection
- [ ] `SKILL.md`, `README.md`, `run.py`, and all prompt files use identical names for every configurable parameter (e.g. `MAX_ITERATIONS`, workspace path, model names) — no contradictions or aliases across files
- [ ] All prompt files referenced by name in `run.py` exist on disk under `scripts/` or `prompts/`
- [ ] A `clawhub.yaml` (or equivalent manifest) exists at the skill root containing at minimum: `name`, `version`, and `description` fields
- [ ] No file under `/root/clawd/skills/checkmate/` contains any of the strings: `TODO`, `placeholder`, `TBD`, `coming soon`, `FIXME`, or `XXX`
- [ ] `README.md` installation section includes the exact command `clawhub install checkmate` and any prerequisites (OpenClaw version, Python version, dependencies)
- [ ] `README.md` usage section includes at least one concrete invocation example showing how to trigger checkmate from a user message or agent prompt, with expected output described
- [ ] `SKILL.md` trigger phrases/conditions match the actual behaviour described in `README.md` and `run.py` — no orphaned triggers or undocumented invocation paths

## Should Pass (non-blocking)

- [ ] `run.py` includes a `--dry-run` flag or equivalent mode for testing without executing agent sessions
- [ ] `README.md` includes a troubleshooting or FAQ section covering common failure modes (e.g. judge never returns PASS, workspace conflicts)
- [ ] Workspace directory layout described in `README.md` matches the actual directories created by `scripts/workspace.sh`
- [ ] `prompts/orchestrator.md` is consistent with the actual loop logic in `run.py` (no stale architecture references)

## Context

The checkmate skill implements a deterministic quality loop: an intake phase converts a vague task into machine-checkable criteria, then a worker→judge cycle runs until the output passes or max iterations is reached. Publication-ready means a developer landing on GitHub or ClawhHub can understand the system, install it, and invoke it correctly without reading source code. "Great" looks like: a README that serves as a standalone manual, prompts and code that are fully self-consistent, and zero rough edges that would confuse a first-time user or reviewer.
