# Orchestrator Pattern

Reference for the checkmate loop controller. Not a prompt — a pattern guide.

---

## Loop Structure (pseudocode)

```
workspace = create_workspace("memory/checkmate-{timestamp}/")
criteria  = run_intake(task, workspace)

iteration = 1
max_iter  = 5

while iteration <= max_iter:
    notify_user(f"[checkmate: iteration {iteration}/{max_iter}]")
    
    output  = run_worker(task, criteria, feedback=last_gaps, workspace)
    verdict = run_judge(criteria, output, iteration, max_iter, workspace)
    
    if verdict.result == "PASS":
        deliver(output)
        cleanup(workspace)
        break
    
    last_gaps = verdict.gap_summary
    iteration += 1

else:
    # Max iterations reached
    deliver_best_attempt(output, verdict)
    notify_user("checkmate: max iterations reached. Delivering best attempt + final judge report.")
```

## Orchestrator Responsibilities

1. **Maintain state** — track iteration count, last gaps, workspace path
2. **Notify the user** — always show `[checkmate: iteration N/max]` at the start of each round
3. **Pass feedback** — give the judge's gap summary to the worker as explicit input
4. **Handle failure gracefully** — if max iterations hit, don't silently fail; surface the situation

## Worker Handoff Template

When handing off to the worker on iteration > 1, include:

```
You are the worker in a checkmate loop (iteration {n}/{max}).

TASK: {original task}

ACCEPTANCE CRITERIA: {criteria.md contents}

PREVIOUS ATTEMPT: {output.md contents}

JUDGE FEEDBACK (what to fix):
{verdict.gap_summary}

Produce an improved version that directly addresses the judge's feedback.
Do not address non-blocking observations unless the blocking criteria are all met.
```

## Inline vs Sub-agent

- **Inline (default):** Run intake, worker, judge as sequential reasoning steps in the same context. Use for short tasks (<500 word output).
- **Sub-agent:** Spawn worker and/or judge as sub-agents for long or complex tasks. Pass workspace files via shared filesystem.

## Workspace Cleanup

After successful delivery:
```bash
rm -rf memory/checkmate-{timestamp}/
```

Unless the user says "keep the workspace" or the task was complex enough to warrant keeping artifacts.
