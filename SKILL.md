---
name: checkmate
description: "Iterative task completion with a judge loop. Converts a vague task into machine-checkable criteria, runs a worker to produce output, then loops through a judge until PASS or max iterations. Use when: (1) a task needs quality guarantees, not just a best-effort attempt; (2) output must meet specific criteria before delivery; (3) you want to iterate autonomously until something is truly done. Triggers on 'checkmate: TASK', 'until it passes', 'keep iterating until', 'quality loop', 'judge and retry'."
---

# Checkmate

Checkmate runs an intake → work → judge → repeat loop. Nothing leaves until it passes.

## How It Works

```
Task → Intake (criteria.md) → Worker → Judge → PASS? → Done
                                  ↑________________________| FAIL + gaps
```

1. **Intake** — converts the user's vague task into a `criteria.md` of machine-checkable acceptance criteria
2. **Worker** — completes the task (inline or as a sub-agent)
3. **Judge** — reads `criteria.md` + output, returns structured `PASS` or `FAIL` with specific gaps
4. **Loop** — if FAIL, worker retries with judge feedback; if PASS, deliver to user

## Invocation

```
checkmate: <task description>
```

Or naturally: "keep iterating until it's right", "run it through a judge", "don't stop until it passes"

## Workflow

### Step 1: Run Intake
Load `prompts/intake.md`. Fill in the task. Output → `checkmate/criteria.md`.

### Step 2: Run Worker
Complete the task. Save output → `checkmate/output.md` (or appropriate file).

### Step 3: Run Judge
Load `prompts/judge.md`. Provide `criteria.md` + output. Returns structured verdict.

### Step 4: Loop or Deliver
- **PASS** → deliver output to user, clean up workspace
- **FAIL** → extract gaps from judge verdict, pass to worker as feedback, increment iteration counter

### Limits
- Default max iterations: **5**
- If still failing at max: surface the best attempt + final judge report to the user
- Always show iteration count to user: `[checkmate: iteration 2/5]`

## Workspace

Use a temporary working directory: `memory/checkmate-<timestamp>/`

Files:
- `criteria.md` — acceptance criteria (written by intake)
- `output.md` — current best output (overwritten each iteration)  
- `verdict.md` — last judge report

Clean up after PASS delivery unless user asks to keep.

## Prompts

- **Intake**: `prompts/intake.md` — converts task → criteria.md
- **Judge**: `prompts/judge.md` — evaluates output against criteria, returns PASS/FAIL
- **Orchestrator**: `prompts/orchestrator.md` — loop controller pattern reference
