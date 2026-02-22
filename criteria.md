# Acceptance Criteria: Checkmate Skill — Publication-Ready

## Must Pass (blocking)

- [ ] `README.md` exists at the repo root (`/root/clawd/skills/checkmate/README.md`) and is tracked by git
- [ ] `README.md` contains all of these sections (by heading): What It Is, Architecture, Installation (via clawhub CLI `clawhub install checkmate` or equivalent), Invocation Examples (at least 2), Parameters table (covering `--max-iter`, `--worker-timeout`, `--judge-timeout`, `--max-intake-iter`, `--session-key`, `--channel`), Workspace Layout, Resume Support
- [ ] `scripts/run.py` catches `subprocess.TimeoutExpired` in `call_agent` (or in `run_worker`/`run_judge`) and handles it gracefully — logs the timeout and either raises a recoverable error or marks the iteration as blocked, without crashing the whole loop
- [ ] `scripts/run.py` handles malformed judge output (no `**Result:** PASS/FAIL` match) explicitly — logs a warning and treats the iteration as FAIL rather than silently doing so with no trace
- [ ] `scripts/run.py` handles intake exhausting `max_intake_iter` without APPROVED — logs a warning that criteria were not approved, and writes the best-available criteria draft to `criteria.md` rather than silently proceeding
- [ ] `prompts/judge.md` does not instruct the judge to "write" output to `iter-{N}/verdict.md` as a file (the LLM cannot write files — run.py captures the reply and writes it); the prompt accurately describes the LLM's job as returning a structured text response
- [ ] `prompts/worker.md`: the `{{FEEDBACK}}` placeholder note `*(Empty means this is the first attempt — no prior feedback.)*` appears only when feedback is empty, OR it is removed from the static template so it cannot appear misleadingly when feedback is actually present
- [ ] `SKILL.md` mentions all 5 prompt files (`intake.md`, `criteria-judge.md`, `worker.md`, `judge.md`, `orchestrator.md`) or accurately documents that `orchestrator.md` is a reference document (not an LLM-called prompt), with no stale references to removed features or old parameter names
- [ ] No file in the repo contains a TODO, FIXME, TBD, or `{placeholder}` pattern that represents incomplete work (as opposed to example/template text in prompts)
- [ ] All variable names used in `prompts/worker.md` (`{{TASK}}`, `{{CRITERIA}}`, `{{FEEDBACK}}`, `{{ITERATION}}`, `{{MAX_ITER}}`, `{{OUTPUT_PATH}}`) exactly match the `.replace(...)` calls in `run_worker()` in `scripts/run.py` — no missing substitutions, no extra variables left unrendered

## Should Pass (non-blocking)

- [ ] `README.md` includes a "How It Works" diagram or ASCII flowchart matching the actual intake→loop→judge architecture
- [ ] `README.md` documents the clarification channel: when intake emits `[NEEDS_CLARIFICATION]`, what happens, and how to write `clarification-response.md`
- [ ] `scripts/run.py` logs a clear warning when malformed judge output is detected (e.g., `"judge output unparseable — treating as FAIL"`) rather than silently defaulting
- [ ] ClawhHub listing at `clawhub.ai/skills/checkmate` matches the `description` field in `SKILL.md` (consistent tagline/trigger phrases)

## Context

The goal is a skill that a stranger can discover on ClawhHub or GitHub, understand in under 5 minutes, install with one command, and run without reading the source. Internally, all prompts and run.py must be a coherent, self-consistent system — no prompt should describe behaviour that differs from what run.py actually does. Error handling must be explicit, not silent — failures should be logged and recoverable, not invisible.
