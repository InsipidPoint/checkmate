---
name: checkmate
description: "Focus your agent on a long-running task and keep iterating until your satisfaction criteria are met — not just a best-effort attempt. Use when you want to lock your agent into a quality loop: it converts your goal into machine-checkable criteria, spins up a worker, judges the output, feeds back gaps, and repeats until PASS or you call it done. Good for tasks where correctness matters: code that must pass tests, docs that must hit a standard, research that must be thorough, anything where 'good enough on first try' isn't acceptable. Triggers on 'checkmate: TASK', 'keep going until it passes', 'don't stop until done', 'quality loop', 'iterate until satisfied', 'judge and retry'."
---

# Checkmate

A deterministic Python loop (`scripts/run.py`) calls an LLM for worker and judge roles.
Nothing leaves until it passes — and you stay in control at every checkpoint.

## Architecture

```
scripts/run.py  (deterministic Python while loop — the orchestrator)
  ├─ Intake loop [up to max_intake_iter, default 5]:
  │    ├─ Draft criteria (intake prompt + task + refinement feedback)
  │    ├─ ⏸ USER REVIEW: show draft → wait for approval or feedback
  │    │     approved? → lock criteria.md
  │    │     feedback? → refine, next intake iteration
  │    └─ (non-interactive: criteria-judge gates instead of user)
  │
  ├─ ⏸ PRE-START GATE: show final task + criteria → user confirms "go"
  │         (edit task / cancel supported here)
  │
  └─ Main loop [up to max_iter, default 10]:
       ├─ Worker: spawn agent session → iter-N/output.md
       │          (full runtime: exec, web_search, all skills, OAuth auth)
       ├─ Judge:  spawn agent session → iter-N/verdict.md
       ├─ PASS?  → write final-output.md, notify user, exit
       └─ FAIL?  → extract gaps → ⏸ CHECKPOINT: show score + gaps to user
                     continue?  → next iteration (with judge gaps)
                     redirect:X → next iteration (with user direction appended)
                     stop?      → end loop, take best result so far
```

**Interactive mode** (default): user approves criteria, confirms pre-start, and reviews each FAIL checkpoint.
**Batch mode** (`--no-interactive`): fully autonomous; criteria-judge gates intake, no checkpoints.

### User Input Bridge

When the orchestrator needs user input, it:
1. Writes `workspace/pending-input.json` (kind + workspace path)
2. Sends a notification via `--recipient` and `--channel`
3. Polls `workspace/user-input.md` every 5s (up to `--checkpoint-timeout` minutes)

The main agent acts as the bridge: when `pending-input.json` exists and the user replies, the agent writes their response to `user-input.md`. The orchestrator picks it up automatically.

Each agent session is spawned via:
```bash
openclaw agent --session-id <isolated-id> --message <prompt> --timeout <N> --json
```
Routes through the gateway WebSocket using existing OAuth — no separate API key.
Workers get full agent runtime: exec, web_search, web_fetch, all skills, sessions_spawn.

## Your Job (main agent)

When checkmate is triggered:

1. **Get recipient ID**: your channel-specific identifier (e.g. your channel's user ID, phone number in E.164)
2. **Create workspace**:
   ```bash
   bash <skill-path>/scripts/workspace.sh /tmp "TASK"
   ```
   Prints the workspace path. Write the full task to `workspace/task.md` if needed.

3. **Run the orchestrator** (background exec):
   ```bash
   python3 <skill-path>/scripts/run.py \
     --workspace /tmp/checkmate-TIMESTAMP \
     --task "FULL TASK DESCRIPTION" \
     --max-iter 10 \
     --recipient RECIPIENT \
     --channel <your-channel>
   ```
   Use `exec` with `background=true`. This runs for as long as needed.
   Add `--no-interactive` for fully autonomous runs (no user checkpoints).

4. **Tell the user** checkmate is running, what it's working on, and that they'll receive criteria drafts and checkpoint messages via your configured channel to review and approve.

5. **Bridge user replies**: When user responds to a checkpoint message, check for `pending-input.json` and write their response to `workspace/user-input.md`.

## Bridging User Input

**When a checkpoint message arrives** (the orchestrator sent the user a criteria/approval/checkpoint request), bridge their reply:

```bash
# Find active pending input
cat <workspace-parent>/checkmate-*/pending-input.json 2>/dev/null

# Route user's reply
echo "USER REPLY HERE" > /path/to/workspace/user-input.md
```

The orchestrator polls for this file every 30 seconds. Once written, it resumes automatically and deletes the file.

**Accepted replies at each gate:**

| Gate | Continue | Redirect | Cancel |
|------|----------|----------|--------|
| Criteria review | "ok", "approve", "lgtm" | any feedback text | — |
| Pre-start | "go", "start", "ok" | "edit task: NEW TASK" | "cancel" |
| Iteration checkpoint | "continue", (empty) | "redirect: DIRECTION" | "stop" |

## Parameters

| Flag | Default | Notes |
|------|---------|-------|
| `--max-intake-iter` | 5 | Intake criteria refinement iterations |
| `--max-iter` | 10 | Main loop iterations (increase to 20 for complex tasks) |
| `--worker-timeout` | 3600s | Per worker session |
| `--judge-timeout` | 300s | Per judge session |
| `--recipient` | — | Channel recipient ID (e.g. your channel's user ID, phone number in E.164); used to deliver checkpoints and result |
| `--channel` | — | Delivery channel for notifications (e.g. `telegram`, `whatsapp`, `signal`) |
| `--no-interactive` | off | Disable user checkpoints (batch mode) |
| `--checkpoint-timeout` | 60 | Minutes to wait for user reply at each checkpoint |

## Workspace layout

```
memory/checkmate-YYYYMMDD-HHMMSS/
├── task.md               # task description (user may edit pre-start)
├── criteria.md           # locked after intake
├── feedback.md           # accumulated judge gaps + user direction
├── state.json            # {iteration, status} — resume support
├── pending-input.json    # written when waiting for user; deleted after response
├── user-input.md         # agent writes user's reply here; read + deleted by orchestrator
├── intake-01/
│   ├── criteria-draft.md
│   ├── criteria-verdict.md  (non-interactive only)
│   └── user-feedback.md     (interactive: user's review comments)
├── iter-01/
│   ├── output.md         # worker output
│   └── verdict.md        # judge verdict
└── final-output.md       # written on completion
```

## Resume

If the script is interrupted, just re-run it with the same `--workspace`. It reads `state.json` and skips completed steps. Locked `criteria.md` is reused; completed `iter-N/output.md` files are not re-run.

## Prompts

Active prompts called by `run.py`:

- `prompts/intake.md` — converts task → criteria draft
- `prompts/criteria-judge.md` — evaluates criteria quality (APPROVED / NEEDS_WORK) — used in non-interactive mode
- `prompts/worker.md` — worker prompt (variables: TASK, CRITERIA, FEEDBACK, ITERATION, MAX_ITER, OUTPUT_PATH)
- `prompts/judge.md` — evaluates output against criteria (PASS / FAIL)

Reference only (not called by `run.py`):

- `prompts/orchestrator.md` — architecture documentation explaining the design rationale
