# agent-forge

Structured research with agent teams. Ask a question, watch the plan execute, get a traced answer.

## What it does

- Ask a question or describe a task
- The system plans steps, runs them in order, and shows the full trace
- Searches the web and fetches sources when needed
- Every action is logged so you can see how the answer was built

## Run locally

```bash
docker compose up --build
```

- App: http://localhost:5173
- API docs: http://localhost:8000/docs

## Learned router

Each question can be answered four ways: a single agent or a planned team of agents, on `gpt-oss-20b` (Groq) or Muse Spark 1.3 (OpenCode Zen). A LinUCB contextual bandit learns which one to use from cheap features of the question. Its reward is correctness minus a cost penalty. It is compared against fixed strategies, plain UCB, a hindsight oracle, and [Jev](https://typesafe.ai) used as a zero-shot router.

Benchmark: 100 questions from [FRAMES](https://huggingface.co/datasets/google/frames-benchmark) (Apache 2.0), fixed seed, 50 train and 50 test. Jev grades each answer against the gold answer, and 30 of those grades are checked by hand.

Costs use each model's paid list price, even though the runs used free tiers.

Run from `apps/api` with `GROQ_API_KEY` and `OPENCODE_API_KEY` in `.env` (Jev runs on Zen; `TYPESAFE_API_KEY` works instead):

```bash
uv run python -m app.eval collect     # run all arms; resumable, every call cached
uv run python -m app.eval grade       # Jev grades against gold
uv run python -m app.eval predict     # Jev router baseline
uv run python -m app.eval handcheck   # 30 grades for human labels
uv run python -m app.eval report      # writes eval/report.md
```

Results: pending the first full run.
