"""Stage 2: Jev grades answers against gold, and predicts per-arm success for routing.

Grading uses the gold answer, so it measures correctness. Prediction sees only the
question, which makes Jev a zero-shot router to compare against the learned bandit.
"""

import csv
import logging
import random

from app import jev
from app.eval.collect import latest_results
from app.eval.data import (
    ARMS,
    GRADES_PATH,
    HANDCHECK_PATH,
    JEV_PREDICTIONS_PATH,
    append_jsonl,
    load_sample,
    read_jsonl,
)

logger = logging.getLogger(__name__)

RESPONSE_TAIL_CHARS = 1500
HANDCHECK_SIZE = 30

GRADE_QUESTION = jev.noul(
    "Does the response's final answer match the gold answer to the question?",
    true="The response commits to the same fact as the gold answer. Wording, formatting "
    "and units may differ.",
    false="The response gives a different answer, no answer, or hedges between answers.",
)


async def grade() -> None:
    questions = {q.qid: q for q in load_sample()}
    graded = {(g["qid"], g["arm"]) for g in read_jsonl(GRADES_PATH)}
    for (qid, arm), row in latest_results().items():
        if (qid, arm) in graded:
            continue
        if row["error"] or not row["answer"].strip():
            p_correct = 0.0
        else:
            state = {
                "question": questions[qid].question,
                "gold_answer": questions[qid].answer,
                "response": row["answer"][-RESPONSE_TAIL_CHARS:],
            }
            answers = await jev.ask(state, {"correct": GRADE_QUESTION})
            p_correct = float(answers["correct"]["noul"])
        append_jsonl(GRADES_PATH, {"qid": qid, "arm": arm, "p_correct": p_correct})
        logger.info(f"q{qid} {arm}: p_correct={p_correct:.2f}")


def load_grades() -> dict[tuple[int, str], bool]:
    return {(g["qid"], g["arm"]): g["p_correct"] >= 0.5 for g in read_jsonl(GRADES_PATH)}


async def predict() -> None:
    done = {p["qid"] for p in read_jsonl(JEV_PREDICTIONS_PATH)}
    questions = {
        arm.name: jev.noul(
            f"Will this strategy answer the question correctly? Strategy: {arm.description}.",
            true="The strategy is likely to find and state the correct answer.",
            false="The strategy is likely to miss facts or reason wrongly.",
        )
        for arm in ARMS
    }
    for question in load_sample():
        if question.qid in done:
            continue
        answers = await jev.ask(question.question, questions)
        probs = {name: float(a["noul"]) for name, a in answers.items()}
        append_jsonl(JEV_PREDICTIONS_PATH, {"qid": question.qid, "p_success": probs})
        logger.info(f"q{question.qid}: {probs}")


def write_handcheck() -> None:
    """Sample graded rows for a human to label; agreement is computed in the report."""
    questions = {q.qid: q for q in load_sample()}
    results = latest_results()
    grades = read_jsonl(GRADES_PATH)
    picked = random.Random(0).sample(grades, min(HANDCHECK_SIZE, len(grades)))
    with HANDCHECK_PATH.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["qid", "arm", "question", "gold", "response_tail", "jev_p", "human"])
        for g in picked:
            q = questions[g["qid"]]
            tail = results[(g["qid"], g["arm"])]["answer"][-400:]
            writer.writerow([g["qid"], g["arm"], q.question, q.answer, tail, g["p_correct"], ""])
