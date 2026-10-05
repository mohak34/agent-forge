"""Stage 3: train routers on the train split, score every policy on the test split.

Writes eval/report.md (tables for the README) and eval/report.json (data for the plot).
Bandit numbers are averaged over SEEDS shuffles of the training order.
"""

import csv
import json
from statistics import mean

import numpy as np

from app.eval import bandit
from app.eval.collect import latest_results
from app.eval.data import (
    ARM_NAMES,
    EVAL_DIR,
    HANDCHECK_PATH,
    JEV_PREDICTIONS_PATH,
    load_sample,
    read_jsonl,
)
from app.eval.judge import load_grades

LAMBDAS = [0.0, 20.0, 50.0, 100.0, 200.0]
ALPHA = 1.0
EPOCHS = 3
SEEDS = 20

Policy = dict[str, float | str]


def build_rounds() -> tuple[list[bandit.Round], list[bandit.Round]]:
    """Questions where every arm was run and graded, split into (train, test)."""
    results = latest_results()
    grades = load_grades()
    train: list[bandit.Round] = []
    test: list[bandit.Round] = []
    for q in load_sample():
        keys = [(q.qid, arm) for arm in ARM_NAMES]
        if not all(k in grades and k in results for k in keys):
            continue
        r = bandit.Round(
            qid=q.qid,
            x=bandit.features(q.question),
            correct=tuple(grades[k] for k in keys),
            cost=tuple(results[k]["cost_usd"] for k in keys),
        )
        (train if q.split == "train" else test).append(r)
    return train, test


def policy_row(name: str, accuracy: float, cost: float, lam: float) -> Policy:
    return {"policy": name, "accuracy": accuracy, "cost": cost, "reward": accuracy - lam * cost}


def bandit_row(name: str, train, test, lam: float, contextual: bool) -> Policy:
    scores = []
    for seed in range(SEEDS):
        policy = bandit.train(train, lam, ALPHA, seed, EPOCHS, contextual)
        scores.append(bandit.evaluate(bandit.greedy_choices(policy, test, contextual, seed), test))
    return policy_row(name, mean(s[0] for s in scores), mean(s[1] for s in scores), lam)


def jev_row(train, test, lam: float) -> Policy | None:
    predictions = {p["qid"]: p["p_success"] for p in read_jsonl(JEV_PREDICTIONS_PATH)}
    if not all(r.qid in predictions for r in test):
        return None
    arm_cost = [mean(r.cost[a] for r in train) for a in range(len(ARM_NAMES))]
    choices = [
        int(np.argmax([predictions[r.qid][n] - lam * arm_cost[a] for a, n in enumerate(ARM_NAMES)]))
        for r in test
    ]
    return policy_row("jev-router", *bandit.evaluate(choices, test), lam)


def policies_for(lam: float, train, test) -> list[Policy]:
    rows = [
        policy_row(f"always {name}", *bandit.evaluate([a] * len(test), test), lam)
        for a, name in enumerate(ARM_NAMES)
    ]
    n = len(ARM_NAMES)
    rows.append(
        policy_row(
            "random",
            mean(mean(r.correct) for r in test),
            mean(mean(r.cost) for r in test),
            lam,
        )
    )
    oracle = [max(range(n), key=lambda a, r=r: r.reward(a, lam)) for r in test]
    rows.append(policy_row("oracle (hindsight)", *bandit.evaluate(oracle, test), lam))
    if (jev := jev_row(train, test, lam)) is not None:
        rows.append(jev)
    rows.append(bandit_row("ucb (no features)", train, test, lam, contextual=False))
    rows.append(bandit_row("linucb", train, test, lam, contextual=True))
    return rows


def arm_summary() -> list[str]:
    results = latest_results()
    grades = load_grades()
    lines = [
        "| arm | accuracy | mean cost | mean latency | mean LLM calls |",
        "|---|---|---|---|---|",
    ]
    for arm in ARM_NAMES:
        rows = [r for (_, a), r in results.items() if a == arm and (r["qid"], a) in grades]
        if not rows:
            continue
        acc = mean(grades[(r["qid"], arm)] for r in rows)
        lines.append(
            f"| {arm} | {acc:.0%} | ${mean(r['cost_usd'] for r in rows):.5f} "
            f"| {mean(r['latency_s'] for r in rows):.1f}s | {mean(r['calls'] for r in rows):.1f} |"
        )
    return lines


def judge_agreement() -> str:
    if not HANDCHECK_PATH.exists():
        return "Hand-check not done yet."
    with HANDCHECK_PATH.open() as f:
        rows = [r for r in csv.DictReader(f) if r["human"].strip() in {"0", "1"}]
    if not rows:
        return "Hand-check not done yet."
    agree = sum((float(r["jev_p"]) >= 0.5) == (r["human"].strip() == "1") for r in rows)
    return f"Jev's grade agreed with a human label on {agree}/{len(rows)} hand-checked answers."


def report() -> None:
    train, test = build_rounds()
    if not train or not test:
        raise SystemExit("No fully graded questions yet. Run collect and grade first.")

    sections = {lam: policies_for(lam, train, test) for lam in LAMBDAS}
    lines = [
        (
            f"Questions: {len(train)} train, {len(test)} test (FRAMES). "
            f"Bandits: alpha={ALPHA}, {EPOCHS} passes, mean of {SEEDS} seeds."
        ),
        "",
        "## Arms (all questions)",
        "",
        *arm_summary(),
        "",
        judge_agreement(),
    ]
    for lam, rows in sections.items():
        worth = "accuracy only" if lam == 0 else f"one correct answer is worth ${1 / lam:.3f}"
        lines += [
            "",
            f"## lambda = {lam:g} ({worth})",
            "",
            "| policy | accuracy | mean cost | reward |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| {r['policy']} | {r['accuracy']:.0%} | ${r['cost']:.5f} | {r['reward']:.3f} |"
            for r in rows
        ]

    (EVAL_DIR / "report.md").write_text("\n".join(lines) + "\n")
    (EVAL_DIR / "report.json").write_text(json.dumps({str(k): v for k, v in sections.items()}))
    print("\n".join(lines))
