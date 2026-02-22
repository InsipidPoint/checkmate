---
name: checkmate
description: "Iterative task completion with a judge loop. Converts a vague task into machine-checkable criteria, calls an LLM worker to produce output, judges the result, and loops with accumulated feedback until PASS or max iterations. The orchestrator is a real Python script with a deterministic while loop — LLM is used only as worker and judge. Designed for long-running tasks: supports dozens of iterations over hours. Use when: (1) a task needs quality guarantees, not just best-effort; (2) output must meet specific criteria before delivery; (3) you want autonomous iteration until something is truly done. Triggers on 'checkmate: TASK', 'until it passes', 'keep iterating until done', 'quality loop', 'judge and retry'."
---

# Checkmate

A deterministic Python loop (`scripts/run.py`) calls an LLM for worker and judge roles.
Nothing leaves until it passes.

## Architecture

```
scripts/run.py  (deterministic Python while loop — the orchestrator)
  ├─ Intake loop [up to max_intake_iter, default 5]:
  │    ├─ Draft criteria (intake prompt + task + refinement feedback)
  │    ├─ Criteria-judge: are the criteria good enough?
  │    ├─ APPROVED → lock criteria.md, proceed
  │    └─ NEEDS_WORK → extract fixes, refine, next intake iteration
  └─ Main loop [up to max_iter, default 10]:
       ├─ Worker: spawn agent session → iter-N/output.md
       │          (full runtime: exec, web_search, all skills, OAuth auth)
       ├─ Judge:  spawn agent session → iter-N/verdict.md
       ├─ PASS?  → write final-output.md, notify user, exit
       └─ FAIL?  → extract gaps, append to feedback.md, next iteration
```

Each agent session is spawned via:
```bash
openclaw agent --session-id <isolated-id> --message <prompt> --timeout <N> --json
```
Routes through the gateway WebSocket using existing OAuth — no separate API key.
Workers get full agent runtime: exec, web_search, web_fetch, all skills, sessions_spawn.

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
| `--max-intake-iter` | 5 | Intake criteria refinement iterations |
| `--max-iter` | 10 | Main loop iterations (increase to 20 for complex tasks) |
| `--worker-timeout` | 3600s | Per worker session |
| `--judge-timeout` | 300s | Per judge session |
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

## Handling Clarification Requests

If the intake can't produce testable criteria, it sends a `[checkmate: clarification needed]` message to your session.

**When you receive this:**
1. Relay the questions to the user naturally
2. When the user answers, write their response to: `WORKSPACE/clarification-response.md`
3. The script is polling for that file — it will resume automatically

```bash
cat > /path/to/workspace/clarification-response.md << 'EOF'
[user's answers here]
EOF
```

The workspace path is included in the clarification message. The script waits up to 30 minutes before timing out.

## Resume

If the script is interrupted, just re-run it with the same `--workspace`. It reads `state.json` and skips completed steps.

## Prompts

- `prompts/intake.md` — converts task → criteria draft
- `prompts/criteria-judge.md` — evaluates criteria quality (APPROVED / NEEDS_WORK)
- `prompts/worker.md` — worker prompt (variables: TASK, CRITERIA, FEEDBACK, ITERATION, MAX_ITER, OUTPUT_PATH)
- `prompts/judge.md` — evaluates output against criteria (PASS / FAIL)
