---
name: checkmate
description: "Iterative task completion with a judge loop. Converts a vague task into machine-checkable criteria, spawns a worker sub-agent to produce output, judges the result, and respawns with feedback until PASS or max iterations. Designed for long-running tasks: supports dozens of iterations over hours. Use when: (1) a task needs quality guarantees, not just a best-effort attempt; (2) output must meet specific criteria before delivery; (3) you want autonomous iteration until something is truly done. Triggers on 'checkmate: TASK', 'until it passes', 'keep iterating until done', 'quality loop', 'judge and retry'."
---

# Checkmate

Spawn an orchestrator sub-agent that runs intake → worker → judge in a loop until PASS.

## Flow

```
You (main agent)
  └─ spawn: Orchestrator sub-agent (long-running)
        ├─ Intake (inline) → criteria.md
        └─ Loop [up to max_iter]:
              ├─ spawn: Worker sub-agent → output.md
              ├─ Judge (inline) → verdict.md
              ├─ PASS → notify you → done
              └─ FAIL → update feedback.md → next iteration
```

## Your Job (main agent)

When checkmate is triggered:

1. **Create workspace**: `memory/checkmate-<timestamp>/` (use `scripts/workspace.sh`)
2. **Write `task.md`** to workspace: the full task description + any context
3. **Spawn orchestrator sub-agent** using `prompts/orchestrator.md` as the task template
   - Fill in: `WORKSPACE`, `TASK`, `MAX_ITER`, `SKILL_DIR`, your `SESSION_KEY`
   - Use model: `anthropic/claude-sonnet-4-6`
   - Set `runTimeoutSeconds`: estimate generously — default to **14400** (4 hours)
   - Set `mode: "run"`
4. **Tell the user** checkmate is running, what it's working on, and that you'll notify them when done

## Orchestrator task template variables

| Variable | Value |
|---|---|
| `WORKSPACE` | Absolute path to `memory/checkmate-<timestamp>/` |
| `TASK` | Full task description |
| `MAX_ITER` | Default **20**; increase for complex tasks |
| `SKILL_DIR` | Absolute path to this skill directory |
| `SESSION_KEY` | Your current session key (from session_status) |

## Passing the orchestrator task

Read `prompts/orchestrator.md`, substitute the variables above, and use that as the `task` argument to `sessions_spawn`.

## On completion

The orchestrator will call `sessions_send` to your session with the final output or failure report. Deliver it to the user.

## Defaults

- Max iterations: **20** (override if user specifies)
- Worker timeout per iteration: **3600s** (1 hour)
- Judge: runs inline inside orchestrator (no sub-agent needed)
- Intake: runs inline inside orchestrator
