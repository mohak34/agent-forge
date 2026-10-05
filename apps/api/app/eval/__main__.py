"""Eval CLI. Run from apps/api:

uv run python -m app.eval sample      # download FRAMES, write the fixed 100-question sample
uv run python -m app.eval collect     # run all arms (Groq); resumable, cached
uv run python -m app.eval grade       # Jev grades answers against gold
uv run python -m app.eval predict     # Jev predicts per-arm success (router baseline)
uv run python -m app.eval handcheck   # write eval/handcheck.csv for human labels
uv run python -m app.eval report      # train bandits, write eval/report.md
"""

import argparse
import asyncio
import logging

from app import cache
from app.eval import collect, judge, report
from app.eval.data import CACHE_PATH, build_sample


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.eval")
    parser.add_argument(
        "stage", choices=["sample", "collect", "grade", "predict", "handcheck", "report"]
    )
    parser.add_argument("--limit", type=int, help="collect: only the first N questions")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cache.enable(CACHE_PATH)

    match args.stage:
        case "sample":
            print(f"{len(build_sample())} questions written")
        case "collect":
            asyncio.run(collect.collect(args.limit))
        case "grade":
            asyncio.run(judge.grade())
        case "predict":
            asyncio.run(judge.predict())
        case "handcheck":
            judge.write_handcheck()
        case "report":
            report.report()


if __name__ == "__main__":
    main()
