"""FRAMES sample, arms, and the JSONL files every eval stage reads and writes.

All files live in apps/api/eval/. Everything except cache.sqlite is committed so the
README numbers can be checked and re-derived without spending anything.
"""

import csv
import io
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
SAMPLE_PATH = EVAL_DIR / "data" / "frames_sample.jsonl"
RESULTS_PATH = EVAL_DIR / "results.jsonl"
GRADES_PATH = EVAL_DIR / "grades.jsonl"
JEV_PREDICTIONS_PATH = EVAL_DIR / "jev_predictions.jsonl"
HANDCHECK_PATH = EVAL_DIR / "handcheck.csv"
CACHE_PATH = EVAL_DIR / "cache.sqlite"

FRAMES_URL = "https://huggingface.co/datasets/google/frames-benchmark/resolve/main/test.tsv"
SAMPLE_SIZE = 100
TRAIN_SIZE = 50
SEED = 7


@dataclass(frozen=True)
class Question:
    qid: int
    question: str
    answer: str
    split: str  # "train" or "test"


# One way of answering a question. The bandit picks one arm per question.
@dataclass(frozen=True)
class Arm:
    name: str
    mode: str  # "direct" or "orchestrated"
    provider: str
    model: str
    description: str


ARMS = [
    Arm(
        "direct-20b",
        "direct",
        "groq",
        "openai/gpt-oss-20b",
        "Small model, single agent with web search",
    ),
    Arm(
        "direct-muse",
        "direct",
        "zen",
        "muse-spark-1.3-contributor-free",
        "Large frontier model, single agent with web search",
    ),
    Arm(
        "orch-20b",
        "orchestrated",
        "groq",
        "openai/gpt-oss-20b",
        "Small model, planned multi-step team of specialist agents",
    ),
    Arm(
        "orch-muse",
        "orchestrated",
        "zen",
        "muse-spark-1.3-contributor-free",
        "Large frontier model, planned multi-step team of specialist agents",
    ),
]
ARM_NAMES = [arm.name for arm in ARMS]


def build_sample() -> list[Question]:
    response = httpx.get(FRAMES_URL, follow_redirects=True, timeout=60)
    response.raise_for_status()
    csv.field_size_limit(10**8)
    rows = list(csv.DictReader(io.StringIO(response.text), delimiter="\t"))

    picked = random.Random(SEED).sample(rows, SAMPLE_SIZE)
    questions = [
        Question(
            qid=int(row[""]),
            question=row["Prompt"].strip(),
            answer=row["Answer"].strip(),
            split="train" if index < TRAIN_SIZE else "test",
        )
        for index, row in enumerate(picked)
    ]
    write_jsonl(SAMPLE_PATH, [asdict(q) for q in questions])
    return questions


def load_sample() -> list[Question]:
    if not SAMPLE_PATH.exists():
        return build_sample()
    return [Question(**row) for row in read_jsonl(SAMPLE_PATH)]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")
