"""Stage 1: run every arm on every sampled question and append outcomes to results.jsonl.

Resumable: rows that already succeeded are skipped, failed rows are retried. Questions
are the outer loop so a partial run still covers all arms evenly.
"""

import logging
import time

from app.agent import run_direct, run_orchestrated
from app.eval.data import ARMS, RESULTS_PATH, Arm, Question, append_jsonl, load_sample, read_jsonl
from app.providers.base import Usage
from app.router import cost_usd

logger = logging.getLogger(__name__)

ANSWER_FORMAT = "\n\nEnd your reply with one line in the form: Final answer: <answer>"


async def run_arm(arm: Arm, question: Question) -> dict:
    usage = Usage()
    goal = question.question + ANSWER_FORMAT
    runner = run_direct if arm.mode == "direct" else run_orchestrated
    started = time.monotonic()
    error = ""
    try:
        answer = await runner(goal, arm.model, usage, provider=arm.provider)
    except Exception as exc:  # noqa: BLE001 - any failure is recorded and retried next run
        answer, error = "", f"{type(exc).__name__}: {exc}"
    return {
        "qid": question.qid,
        "arm": arm.name,
        "answer": answer,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "calls": usage.calls,
        "cost_usd": cost_usd(arm.model, usage),
        "latency_s": round(time.monotonic() - started, 2),
        "error": error,
    }


async def collect(limit: int | None = None) -> None:
    done = {(r["qid"], r["arm"]) for r in read_jsonl(RESULTS_PATH) if not r["error"]}
    questions = load_sample()[:limit]
    for index, question in enumerate(questions, start=1):
        for arm in ARMS:
            if (question.qid, arm.name) in done:
                continue
            row = await run_arm(arm, question)
            append_jsonl(RESULTS_PATH, row)
            status = row["error"][:80] or f"${row['cost_usd']:.5f} {row['latency_s']}s"
            logger.info(f"[{index}/{len(questions)}] q{question.qid} {arm.name}: {status}")


def latest_results() -> dict[tuple[int, str], dict]:
    """Last row per (qid, arm); later successful retries replace earlier failures."""
    rows: dict[tuple[int, str], dict] = {}
    for row in read_jsonl(RESULTS_PATH):
        key = (row["qid"], row["arm"])
        if key not in rows or not row["error"]:
            rows[key] = row
    return rows
