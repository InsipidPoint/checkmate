# Acceptance Criteria: Checkmate Skill — Publication Ready

## Must Pass (blocking)

- [ ] `skills/checkmate/README.md` exists and contains all five required sections: (1) what it is / elevator pitch, (2) installation command `clawhub install checkmate`, (3) concrete `run.py` usage example showing `--workspace`, `--task`, `--max-iter`, `--session-key`, and `--channel` flags, (4) workspace layout directory tree, (5) resume instructions explaining how to re-run with the same `--workspace`. Each section is verifiable by locating it in the file.

- [ ] No placeholder text exists in any file under `skills/checkmate/` — no occurrences of "TODO", "FIXME", "PLACEHOLDER", "TBD", "coming soon", or unfilled `{variable}` patterns (single-brace tokens). Exception: intentional `{{VARIABLE}}` double-brace template tokens in `prompts/` files are allowed.

- [ ] `run.py`'s `call_agent()` function explicitly catches `json.JSONDecodeError` (malformed JSON response from `openclaw agent`) and raises a descriptive `RuntimeError` instead of crashing with an unhandled exception.

- [ ] `run.py`'s `call_agent()` function explicitly catches `subprocess.TimeoutExpired` and handles it (raises `RuntimeError` or returns a `[BLOCKED]` signal) — no unhandled `TimeoutExpired` propagates to the caller.

- [ ] Malformed judge output (a judge reply that contains neither `**Result:** PASS` nor `**Result:** FAIL`) is explicitly detected and logged as a warning in `run_judge()`, not silently treated as FAIL with no indication.

- [ ] A file named exactly `clawhub.yaml` or `skill.json` exists at the root of `skills/checkmate/` and contains all three fields — `name`, `version`, and `description` — as top-level keys. Verifiable by `grep -E "^name:|^version:|^description:"` (YAML) or `jq .name,.version,.description` (JSON).

- [ ] All parameter flag names are consistent across `SKILL.md`, `README.md`, and `run.py` — specifically: `--max-iter`, `--max-intake-iter`, `--worker-timeout`, `--judge-timeout`, `--session-key`, `--channel`. No document uses a different name or spelling for the same flag. Verifiable by grepping each flag name across all three files.

- [ ] The template variable names in `prompts/worker.md` exactly match the `.replace()` calls in `run_worker()` in `run.py` — `{{TASK}}`, `{{CRITERIA}}`, `{{FEEDBACK}}`, `{{ITERATION}}`, `{{MAX_ITER}}`, `{{OUTPUT_PATH}}` — no missing variables, no extra unsubstituted `{{...}}` tokens remaining after substitution in a real run.

- [ ] The judge output format documented in `prompts/judge.md` (specifically `**Result:** PASS|FAIL` and `**Score:** X/Y`) matches the regex patterns used in `run_judge()` in `run.py`. No format drift — if the prompt says one thing and the regex expects another, this fails.

- [ ] **10a.** Every trigger phrase listed in SKILL.md's trigger/usage section also appears, verbatim or paraphrased, in README.md's usage section — no trigger in SKILL.md is absent from README. Verifiable by listing SKILL.md triggers and confirming each is findable in README.

  **10b.** Every invocation of `run.py` shown in SKILL.md uses only flag names that exist in `run.py`'s `argparse` definition — no SKILL.md example references a flag not found in an `add_argument(...)` call. Verifiable by grepping `add_argument` in `run.py` and checking each flag in SKILL.md examples against that list.

## Should Pass (non-blocking)

- [ ] `README.md` includes an architecture diagram (ASCII, mermaid, or equivalent) showing the intake loop and main worker→judge loop, making the flow visually scannable without reading prose.

- [ ] `README.md` includes a short sample of what a successful run looks like — either sample terminal output, log lines, or a description of the iteration flow with example pass/fail verdicts.

- [ ] `README.md` includes a troubleshooting section covering at least: what to do when the script is interrupted, how to increase `--max-iter` for complex tasks, and what `[BLOCKED]` output means.

- [ ] `run.py` has inline comments at the top of `main()` and at each major stage (intake loop, worker call, judge call, feedback accumulation) explaining the high-level structure for new contributors.

- [ ] The `prompts/orchestrator.md` file is either updated to reflect current `run.py` behaviour (intake loop, `--json` flag, response extraction path) or clearly marked as an architecture reference doc rather than a live prompt.

## Context

The checkmate skill's key differentiator is its deterministic Python loop and resumability — LLMs are only ever workers and judges, not orchestrators. Publication-ready means a developer discovering it on GitHub or ClawhHub can understand the architecture, install it, invoke it, and recover from a failure without reading source code. The blocking criteria above ensure internal consistency (prompts match code, docs match flags, templates match substitution calls) and robustness (error paths are handled explicitly). "Great" means someone clones the repo, runs the example command, and sees it work end-to-end — or knows exactly what to do when something goes wrong.
