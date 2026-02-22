# Checkmate

**Iterative task completion with a judge loop.**

Checkmate converts a vague task into machine-checkable criteria, calls an LLM worker to produce output, judges the result, and loops with accumulated feedback until the work passes — or max iterations are reached. The orchestrator is a real Python script with a deterministic `while` loop. LLM is used only as worker and judge. Designed for long-running tasks: supports dozens of iterations over hours.

Use when:
- A task needs quality guarantees, not just best-effort
- Output must meet specific criteria before delivery
- You want autonomous iteration until something is truly done

Triggers: `checkmate: TASK`, `until it passes`, `keep iterating until done`, `quality loop`, `judge and retry`

---

## What It Is

Checkmate is a **deterministic Python orchestration loop** that wraps LLM calls for worker and judge roles. The Python script (`scripts/run.py`) maintains state, persists progress to disk, and drives the loop — it never "forgets" its place. LLM sessions are isolated per-call; no shared history bleeds between iterations.

The intake stage first converts the task into machine-checkable acceptance criteria (with a criteria-quality judge loop of its own). Only when criteria are approved does the main worker→judge loop begin.

Workers get the full OpenClaw agent runtime: `exec`, `web_search`, `web_fetch`, all skills, OAuth auth. They can browse, run code, fetch URLs — anything the main agent can do.

---

## Architecture

```
scripts/run.py  (deterministic Python while loop — the real orchestrator)
  │
  ├─ Intake loop [up to --max-intake-iter, default 5]:
  │    ├─ Draft criteria  (intake prompt + task + refinement feedback)
  │    ├─ ⏸ USER REVIEW (interactive): show draft → wait for approval/feedback
  │    │     approved? → lock criteria.md
  │    │     feedback? → refine, next intake iteration
  │    └─ (batch mode --no-interactive: criteria-judge gates instead of user)
  │
  ├─ ⏸ PRE-START GATE (interactive): show final task + criteria → user confirms "go"
  │         (edit task / cancel supported here)
  │
  └─ Main loop [up to --max-iter, default 10]:
       ├─ Worker: spawn agent session → writes iter-N/output.md
       │          (full runtime: exec, web_search, all skills, OAuth auth)
       ├─ Judge:  spawn agent session → writes iter-N/verdict.md
       ├─ PASS?  → write final-output.md, notify user via --session-key, exit
       └─ FAIL?  → extract gap summary → ⏸ CHECKPOINT (interactive): show score + gaps
                     continue?    → next iteration (with judge gaps)
                     redirect: X  → next iteration (with user direction appended)
                     stop?        → end loop, take best result so far
```

**Interactive mode** (default): user approves criteria, confirms pre-start, and reviews each FAIL checkpoint.
**Batch mode** (`--no-interactive`): fully autonomous; criteria-judge gates intake, no checkpoints.

### User input bridge

When the orchestrator needs user input, it:
1. Writes `workspace/pending-input.json` (kind + workspace path + channel)
2. Sends a notification via `--session-key` and `--channel`
3. Polls `workspace/user-input.md` every 30 seconds (up to `--checkpoint-timeout` minutes)

The main agent acts as the bridge: when `pending-input.json` exists and the user replies, the agent writes their response to `user-input.md`. The orchestrator picks it up automatically and resumes.

Each LLM call is an isolated OpenClaw agent session:

```bash
openclaw agent --session-id checkmate-worker-N-TIMESTAMP \
               --message "PROMPT" \
               --timeout 3600 \
               --json
```

Result is read from `result.payloads[0].text`. Sessions are stateless — no shared history between iterations.

### Prompt roles

| File | Role | Called by |
|------|------|-----------|
| `prompts/intake.md` | Converts task → criteria draft | `run_intake_draft()` |
| `prompts/criteria-judge.md` | Evaluates criteria quality (APPROVED / NEEDS_WORK) — batch mode only | `run_criteria_judge()` |
| `prompts/worker.md` | Performs the actual task | `run_worker()` |
| `prompts/judge.md` | Evaluates output against criteria (PASS / FAIL) | `run_judge()` |

`prompts/orchestrator.md` is architecture reference documentation only — **not called by `run.py`**.

---

## Installation

Install via the [ClawhHub CLI](https://clawhub.ai):

```bash
clawhub install checkmate
```

This adds the skill to your OpenClaw workspace. Requires OpenClaw to be running.

Manual install (clone into your skills directory):

```bash
cd /root/clawd/skills
git clone https://github.com/InsipidPoint/checkmate checkmate
```

---

## Quick Start

### 1. Get your session key

```python
session_status()  # note the sessionKey field
```

Or from the CLI:

```bash
openclaw sessions list --limit 1
```

### 2. Create a workspace

```bash
WORKSPACE=$(bash /root/clawd/skills/checkmate/scripts/workspace.sh /root/clawd/memory "Your task description")
echo "Workspace: $WORKSPACE"
```

### 3. Run the orchestrator

```bash
python3 /root/clawd/skills/checkmate/scripts/run.py \
  --workspace "$WORKSPACE" \
  --task "Your task description" \
  --max-iter 10 \
  --session-key YOUR_SESSION_KEY \
  --channel telegram
```

Run in background for long tasks:

```bash
nohup python3 /root/clawd/skills/checkmate/scripts/run.py \
  --workspace "$WORKSPACE" \
  --task "Your task description" \
  --max-iter 20 \
  --session-key YOUR_SESSION_KEY \
  --channel telegram \
  > "$WORKSPACE/run.log" 2>&1 &

echo "Running as PID $! — tail $WORKSPACE/run.log"
```

### 4. Find your output

On PASS or after max iterations, the best output is written to:

```
$WORKSPACE/final-output.md
```

You will also receive a Telegram notification (if `--session-key` and `--channel` are set).

---

## Invocation Examples

**Basic usage:**
```bash
python3 scripts/run.py \
  --workspace /root/clawd/memory/checkmate-20260222-120000 \
  --task "Write a README for the checkmate skill"
```

**Long-running research task (20 iterations, 2h worker timeout):**
```bash
python3 scripts/run.py \
  --workspace /root/clawd/memory/checkmate-20260222-120000 \
  --task "Deep analysis of NVDA vs AMD for 2026 AI infrastructure spend" \
  --max-iter 20 \
  --worker-timeout 7200 \
  --session-key main-session-key \
  --channel telegram
```

**Resume an interrupted run:**
```bash
# Just re-run with the same --workspace — it picks up from state.json
python3 scripts/run.py \
  --workspace /root/clawd/memory/checkmate-20260222-120000 \
  --task "same task text"
```

**Triggered from the main agent (via checkmate skill):**
When the user says `checkmate: <task>` or `until it passes`, the main agent:
1. Calls `session_status` to get its session key
2. Creates a workspace via `workspace.sh`
3. Spawns `run.py` via `exec` with `background=true`
4. Tells the user it's running and will notify on Telegram when done

---

## Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--workspace` | *(required)* | Workspace directory path |
| `--task` | `""` | Task text (or write to `workspace/task.md` before running) |
| `--max-intake-iter` | `5` | Max intake criteria refinement iterations |
| `--max-iter` | `10` | Max main loop iterations (increase to 20 for complex tasks) |
| `--worker-timeout` | `3600` | Seconds per worker agent call |
| `--judge-timeout` | `300` | Seconds per judge agent call |
| `--session-key` | `""` | Main session key; used to deliver result notification |
| `--channel` | `telegram` | Delivery channel for result (`telegram`, `whatsapp`, etc.) |
| `--no-interactive` | off | Disable user checkpoints; fully autonomous batch mode |
| `--checkpoint-timeout` | `60` | Minutes to wait for user reply at each interactive checkpoint |

---

## Workspace Layout

```
/root/clawd/memory/checkmate-YYYYMMDD-HHMMSS/
├── task.md                  # Original task description
├── criteria.md              # Locked acceptance criteria (written by intake)
├── feedback.md              # Accumulated judge gap summaries
├── state.json               # {iteration, status} — used for resume
├── run.log                  # Orchestrator stdout (if redirected)
│
├── intake-01/               # Intake iterations (one per refinement round)
│   ├── criteria-draft.md    # Draft criteria from intake agent
│   └── criteria-verdict.md  # Criteria-judge verdict
│
├── iter-01/                 # Main loop iterations
│   ├── output.md            # Worker output
│   └── verdict.md           # Judge verdict (PASS/FAIL + score + gap summary)
│
├── iter-02/ ...             # Additional iterations if needed
│
└── final-output.md          # Best output — written on PASS or max iterations
```

`state.json` values:
- `status: "running"` — iteration in progress
- `status: "pass"` — task passed, `final-output.md` contains the result
- `status: "fail"` — max iterations reached, best attempt saved to `final-output.md`

---

## Resume Support

Checkmate is designed to survive interruptions. If `run.py` is killed (crash, timeout, manual stop), re-run it with the **same `--workspace` path**:

```bash
python3 scripts/run.py \
  --workspace /root/clawd/memory/checkmate-20260222-120000 \
  --task "original task"
```

The script reads `state.json` to find where it left off:
- **Intake:** If `criteria.md` already exists, intake is skipped entirely
- **Worker:** If `iter-N/output.md` already exists, the worker call is skipped (uses cached output)
- **Judge:** Always re-runs (verdict may differ on retry — this is intentional)
- **Already completed:** If `state.status` is `"pass"` or `"fail"`, the script exits immediately

This means you can safely re-run after a network blip, rate-limit crash, or system restart.

### Interactive checkpoints

In interactive mode (default), the orchestrator pauses at three gates: criteria review, pre-start confirmation, and each FAIL iteration. When paused, it writes `workspace/pending-input.json` and sends you a notification via `--channel`.

The main agent acts as a bridge: when you reply to the notification, it writes your response to `workspace/user-input.md`. The orchestrator detects the file within 30 seconds and resumes.

**Accepted replies at each gate:**

| Gate | Approve / continue | Redirect | Cancel |
|------|--------------------|----------|--------|
| Criteria review | `ok`, `approve`, `lgtm` | any feedback text | — |
| Pre-start | `go`, `start`, `ok` | `edit task: NEW TASK` | `cancel` |
| Iteration checkpoint | `continue`, (empty) | `redirect: DIRECTION` | `stop` |

To inject a response manually (e.g., after a notification was missed):

```bash
echo "continue" > /root/clawd/memory/checkmate-TIMESTAMP/user-input.md
```

The orchestrator polls every 30 seconds and resumes automatically.
