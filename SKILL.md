---
name: checkmate
description: "Iterative task completion with a judge loop. Converts a vague task into machine-checkable criteria, calls an LLM worker to produce output, judges the result, and loops with accumulated feedback until PASS or max iterations. The orchestrator is a real Python script with a deterministic while loop — LLM is used only as worker and judge. Designed for long-running tasks: supports dozens of iterations over hours. Use when: (1) a task needs quality guarantees, not just best-effort; (2) output must meet specific criteria before delivery; (3) you want autonomous iteration until something is truly done. Triggers on 'checkmate: TASK', 'until it passes', 'keep iterating until done', 'quality loop', 'judge and retry'."
---

# Checkmate

A deterministic Python loop (`scripts/run.py`) calls an LLM for worker and judge roles.
Nothing leaves until it passes.

## Architecture

```
scripts/run.py (real while loop)
  ├─ Intake:  call_llm(intake prompt + task)     → criteria.md    [once]
  └─ Loop [up to max_iter]:
       ├─ Worker: call_llm(worker prompt + criteria + feedback) → iter-N/output.md
       ├─ Judge:  call_llm(judge prompt + criteria + output)   → iter-N/verdict.md
       ├─ PASS?  → write final-output.md, notify user, exit
       └─ FAIL?  → extract gaps, append to feedback.md, next iteration
```

Each `call_llm` runs `openclaw agent --session-id <isolated-id> --message <prompt> --json`.

## Your Job (main agent)

When checkmate is triggered:

1. **Get session key**: call `session_status` — note the sessionKey
2. **Create workspace**:
   ```bash
   bash /root/clawd/skills/checkmate/scripts/workspace.sh /root/clawd/memory "TASK"
   ```
   Prints the workspace path. Write the full task to `workspace/task.md` if needed.

3. **Run the orchestrator** (background exec):
   ```bash
   python3 /root/clawd/skills/checkmate/scripts/run.py \
     --workspace /root/clawd/memory/checkmate-TIMESTAMP \
     --task "FULL TASK DESCRIPTION" \
     --max-iter 20 \
     --session-key SESSION_KEY \
     --channel telegram
   ```
   Use `exec` with `background=true`. This runs for as long as needed.

4. **Tell the user** checkmate is running, what it's working on, and that you'll notify them on Telegram when done.

## Parameters

| Flag | Default | Notes |
|------|---------|-------|
| `--max-iter` | 20 | Increase for complex tasks |
| `--session-key` | — | Your session key; used to deliver result |
| `--channel` | telegram | Delivery channel for result |

## Workspace layout

```
memory/checkmate-YYYYMMDD-HHMMSS/
├── task.md           # original task
├── criteria.md       # from intake
├── feedback.md       # accumulated judge gaps
├── state.json        # {iteration, status} — resume support
├── iter-01/
│   ├── output.md     # worker output
│   └── verdict.md    # judge verdict
└── final-output.md   # written on completion
```

## Resume

If the script is interrupted, just re-run it with the same `--workspace`. It reads `state.json` and skips completed steps.

## Prompts

- `prompts/intake.md` — intake prompt template
- `prompts/worker.md` — worker prompt template (variables: TASK, CRITERIA, FEEDBACK, ITERATION, MAX_ITER, OUTPUT_PATH)
- `prompts/judge.md` — judge prompt template
