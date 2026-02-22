#!/usr/bin/env python3
"""
checkmate/scripts/run.py

Deterministic Python orchestrator for the checkmate skill.
Real while loop. LLM called as a subprocess via `openclaw agent`.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent


# ── Utilities ─────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[checkmate {ts}] {msg}", flush=True)


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_state(workspace: Path) -> dict:
    p = workspace / "state.json"
    return json.loads(p.read_text()) if p.exists() else {"iteration": 0, "status": "running"}


def save_state(workspace: Path, state: dict):
    write_file(workspace / "state.json", json.dumps(state, indent=2))


# ── LLM interface ─────────────────────────────────────────────────────────────

def call_agent(prompt: str, session_id: str, timeout_s: int = 3600) -> str:
    """
    Spawn an agent session via the OpenClaw gateway (openclaw agent CLI).
    Each session gets the full agent runtime: all tools, all skills, OAuth auth.
    No direct Anthropic API calls — routes through the gateway like any sub-agent.
    """
    cmd = [
        "openclaw", "agent",
        "--session-id", session_id,
        "--message", prompt,
        "--timeout", str(timeout_s),
        "--json",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 30)
        if result.returncode != 0:
            raise RuntimeError(f"openclaw agent exited {result.returncode}: {result.stderr[:200]}")
        data = json.loads(result.stdout)
        return data["result"]["payloads"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected response shape: {result.stdout[:200]}") from e


def notify(session_key: str, message: str, channel: str):
    """Deliver a message to the user via the main session."""
    if not session_key:
        log("No session key — result written to workspace/final-output.md")
        return
    cmd = [
        "openclaw", "agent",
        "--session-id", session_key,
        "--message", message,
        "--deliver",
        "--channel", channel,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        log(f"Delivered message to session {session_key}")
    except Exception as e:
        log(f"Notification failed ({e})")


def request_clarification(workspace: Path, session_key: str, questions: str, channel: str) -> str:
    """
    Pause the run, ask the user clarifying questions, wait for response (up to 30 min).
    Returns the clarification text, or empty string if timed out.
    """
    clarification_path = workspace / "pending-clarification.md"
    response_path      = workspace / "clarification-response.md"

    write_file(clarification_path, questions)

    msg = (
        f"[checkmate: clarification needed]\n\n"
        f"{questions}\n\n"
        f"---\n"
        f"Please answer the above. I'll incorporate your answers and continue.\n"
        f"Workspace: {workspace}"
    )
    notify(session_key, msg, channel)
    log("paused — waiting for clarification (up to 30 min)...")

    for _ in range(60):  # 60 × 30s = 30 min
        if response_path.exists():
            response = response_path.read_text().strip()
            log(f"clarification received ({len(response)} chars) — resuming")
            clarification_path.unlink(missing_ok=True)
            # Append clarification to task.md so future intake sessions see it
            with open(workspace / "task.md", "a") as f:
                f.write(f"\n\n## User Clarification\n\n{response}\n")
            return response
        time.sleep(30)

    log("clarification timeout — proceeding with existing task description")
    return ""


# ── Stages ────────────────────────────────────────────────────────────────────

def run_intake_draft(task: str, feedback: str, iteration: int) -> str:
    """Generate a criteria draft, optionally with refinement feedback."""
    template = read_file(SKILL_DIR / "prompts" / "intake.md")
    prompt = f"{template}\n\n---\n\n## Task\n\n{task}"
    if feedback.strip():
        prompt += f"\n\n## Refinement Feedback (fix these issues)\n\n{feedback}"
    return call_agent(prompt, f"checkmate-intake-draft-{iteration}-{int(time.time())}", timeout_s=120)


def run_criteria_judge(task: str, criteria: str, iteration: int) -> tuple[str, bool]:
    """Judge whether the criteria themselves are good enough."""
    template = read_file(SKILL_DIR / "prompts" / "criteria-judge.md")
    prompt = (
        f"{template}\n\n---\n\n"
        f"## Original Task\n\n{task}\n\n"
        f"## Proposed Criteria (intake iteration {iteration})\n\n{criteria}"
    )
    reply = call_agent(prompt, f"checkmate-criteria-judge-{iteration}-{int(time.time())}", timeout_s=120)
    approved = bool(re.search(r"\*\*Result:\*\*\s*APPROVED", reply, re.IGNORECASE))
    return reply, approved


def extract_criteria_feedback(verdict: str) -> str:
    """Extract suggested fixes from a criteria judge verdict."""
    m = re.search(r"## Suggested Fixes\n(.*?)(?=\n## |\Z)", verdict, re.DOTALL)
    return m.group(1).strip() if m else ""


def run_intake(workspace: Path, task: str, max_intake_iter: int = 5,
               session_key: str = "", channel: str = "telegram") -> str:
    criteria_path = workspace / "criteria.md"
    if criteria_path.exists():
        log("intake: criteria.md already exists, skipping")
        return criteria_path.read_text()

    feedback = ""
    criteria = ""

    for i in range(1, max_intake_iter + 1):
        # Re-read task each iteration (may have been updated with clarification)
        task = read_file(workspace / "task.md") or task

        log(f"intake: iteration {i}/{max_intake_iter} — drafting criteria...")
        criteria = run_intake_draft(task, feedback, i)

        intake_dir = workspace / f"intake-{i:02d}"
        intake_dir.mkdir(parents=True, exist_ok=True)
        write_file(intake_dir / "criteria-draft.md", criteria)

        # Check if intake is asking for user clarification
        if "[NEEDS_CLARIFICATION]" in criteria:
            log(f"intake: needs user clarification (iter {i})")
            questions = criteria.split("[NEEDS_CLARIFICATION]", 1)[1].strip()
            clarification = request_clarification(workspace, session_key, questions, channel)
            if clarification:
                feedback = f"User clarification provided:\n{clarification}"
            continue

        log(f"intake: judging criteria quality (iter {i})...")
        verdict, approved = run_criteria_judge(task, criteria, i)
        write_file(intake_dir / "criteria-verdict.md", verdict)

        if approved:
            log(f"intake: criteria APPROVED on iteration {i}")
            break

        feedback = extract_criteria_feedback(verdict)
        log(f"intake: criteria NEEDS_WORK — refining (iter {i})")

    write_file(criteria_path, criteria)
    log(f"intake: locked criteria.md ({len(criteria)} chars)")
    return criteria


def run_worker(workspace: Path, task: str, criteria: str, feedback: str,
               iteration: int, max_iter: int, worker_timeout: int = 3600) -> str:
    iter_dir = workspace / f"iter-{iteration:02d}"
    iter_dir.mkdir(parents=True, exist_ok=True)
    output_path = iter_dir / "output.md"

    if output_path.exists():
        log(f"iter {iteration}: output.md already exists, skipping worker (resume)")
        return output_path.read_text()

    template = read_file(SKILL_DIR / "prompts" / "worker.md")
    prompt = (
        template
        .replace("{{TASK}}", task)
        .replace("{{CRITERIA}}", criteria)
        .replace("{{FEEDBACK}}", feedback.strip() or "(none — this is the first attempt)")
        .replace("{{ITERATION}}", str(iteration))
        .replace("{{MAX_ITER}}", str(max_iter))
        .replace("{{OUTPUT_PATH}}", str(output_path))
    )

    log(f"iter {iteration}/{max_iter}: calling worker (timeout={worker_timeout}s)...")
    reply = call_agent(prompt, f"checkmate-worker-{iteration}-{int(time.time())}", timeout_s=worker_timeout)
    write_file(output_path, reply)
    log(f"iter {iteration}: worker done ({len(reply)} chars)")
    return reply


def run_judge(workspace: Path, criteria: str, output: str,
              iteration: int, max_iter: int, judge_timeout: int = 300) -> tuple[str, bool]:
    iter_dir = workspace / f"iter-{iteration:02d}"
    verdict_path = iter_dir / "verdict.md"

    template = read_file(SKILL_DIR / "prompts" / "judge.md")
    prompt = (
        f"{template}\n\n---\n\n"
        f"## Criteria\n\n{criteria}\n\n"
        f"## Worker Output\n\n{output}\n\n"
        f"## Context\n\nThis is iteration {iteration} of {max_iter}."
    )

    log(f"iter {iteration}: running judge (timeout={judge_timeout}s)...")
    reply = call_agent(prompt, f"checkmate-judge-{iteration}-{int(time.time())}", timeout_s=judge_timeout)
    write_file(verdict_path, reply)

    is_pass = bool(re.search(r"\*\*Result:\*\*\s*PASS", reply, re.IGNORECASE))
    score_m = re.search(r"\*\*Score:\*\*\s*(\d+)/(\d+)", reply)
    score = f"{score_m.group(1)}/{score_m.group(2)}" if score_m else "?/?"
    log(f"iter {iteration}: judge → {'PASS ✅' if is_pass else f'FAIL ❌ ({score} criteria passing)'}")
    return reply, is_pass


def extract_gaps(verdict: str) -> str:
    m = re.search(r"## Gap Summary\n(.*?)(?=\n## |\Z)", verdict, re.DOTALL)
    return m.group(1).strip() if m else ""


def find_best_iteration(workspace: Path) -> tuple[int, str]:
    best_iter, best_score, best_output = 1, -1, ""
    for iter_dir in sorted(workspace.glob("iter-*")):
        m = re.search(r"\*\*Score:\*\*\s*(\d+)/\d+",
                      read_file(iter_dir / "verdict.md"))
        if m and int(m.group(1)) > best_score:
            best_score = int(m.group(1))
            best_iter = int(iter_dir.name.split("-")[1])
            best_output = read_file(iter_dir / "output.md")
    return best_iter, best_output


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Checkmate — deterministic LLM iteration loop")
    parser.add_argument("--workspace", required=True, help="Workspace directory path")
    parser.add_argument("--task",        default="",       help="Task text (or read from workspace/task.md)")
    parser.add_argument("--max-iter",    type=int, default=10)
    parser.add_argument("--session-key",    default="",       help="Main session key for result delivery")
    parser.add_argument("--channel",        default="telegram")
    parser.add_argument("--worker-timeout",   type=int, default=3600, help="Seconds per worker turn (default: 3600)")
    parser.add_argument("--judge-timeout",    type=int, default=300,  help="Seconds per judge turn (default: 300)")
    parser.add_argument("--max-intake-iter",  type=int, default=5,    help="Max intake refinement iterations (default: 5)")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    task = args.task or read_file(workspace / "task.md")
    if not task:
        print("Error: --task is required (or write task to workspace/task.md)", file=sys.stderr)
        sys.exit(1)
    write_file(workspace / "task.md", task)

    state = load_state(workspace)
    if state.get("status") in ("pass", "fail"):
        log(f"workspace already completed with status={state['status']} — exiting")
        return

    start_iter  = state.get("iteration", 0) + 1
    max_iter    = args.max_iter
    session_key = args.session_key

    log(f"starting — iterations {start_iter}–{max_iter}, workspace={workspace}")

    # ── Intake ────────────────────────────────────────────────────────────────
    criteria = run_intake(workspace, task, max_intake_iter=args.max_intake_iter,
                          session_key=session_key, channel=args.channel)

    # ── Loop ──────────────────────────────────────────────────────────────────
    feedback = read_file(workspace / "feedback.md")

    for iteration in range(start_iter, max_iter + 1):
        log(f"────── Iteration {iteration}/{max_iter} ──────")
        save_state(workspace, {"iteration": iteration, "status": "running"})

        # Worker
        output = run_worker(workspace, task, criteria, feedback, iteration, max_iter,
                            worker_timeout=args.worker_timeout)

        if "[BLOCKED]" in output:
            log(f"worker BLOCKED — skipping judge this iteration")
            gaps = f"Worker was blocked:\n{output}"
        else:
            # Judge
            verdict, is_pass = run_judge(workspace, criteria, output, iteration, max_iter,
                                         judge_timeout=args.judge_timeout)

            if is_pass:
                write_file(workspace / "final-output.md", output)
                save_state(workspace, {"iteration": iteration, "status": "pass"})
                log(f"✅ PASSED on iteration {iteration}/{max_iter}")
                notify(
                    args.session_key,
                    f"✅ checkmate: PASSED on iteration {iteration}/{max_iter}\n\n{output}",
                    args.channel,
                )
                return

            gaps = extract_gaps(verdict)

        # Accumulate feedback for next worker
        if gaps:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            entry = f"\n## Iteration {iteration} gaps ({ts})\n{gaps}\n"
            with open(workspace / "feedback.md", "a") as f:
                f.write(entry)
            feedback += entry

    # ── Max iterations reached ────────────────────────────────────────────────
    best_iter, best_output = find_best_iteration(workspace)
    write_file(workspace / "final-output.md", best_output)
    save_state(workspace, {"iteration": max_iter, "status": "fail"})

    best_verdict = read_file(workspace / f"iter-{best_iter:02d}" / "verdict.md")
    log(f"⚠️ max iterations reached — best attempt was iter {best_iter}")
    notify(
        args.session_key,
        (
            f"⚠️ checkmate: max iterations ({max_iter}) reached without full PASS\n\n"
            f"Best attempt: iteration {best_iter}\n\n{best_output}\n\n"
            f"---\nFinal judge report:\n{best_verdict}"
        ),
        args.channel,
    )


if __name__ == "__main__":
    main()
