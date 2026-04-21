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

## Dev mode (optional)

```bash
cd apps/api && uv sync && uv run uvicorn app.main:app --reload
cd apps/web && bun install && bun run dev
```

## Environment

Copy `apps/api/.env.example` to `apps/api/.env` and set at least:

- `GROQ_API_KEY`
- `MOCK_MODE=false` when you want live provider calls

## Tool runtime note

- `search_web` and `fetch_url` use live web retrieval with read-only safeguards.
- Safety controls include URL scheme checks, local/private host blocking, fetch timeouts, and response byte limits.
