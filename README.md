# agent-forge

A web-based workspace where you type a goal and a team of AI roles works through it step by step.

## What it does

- You describe a task or ask a question
- The system breaks it into steps, runs them in order, and shows you exactly what happened
- It can search the web, fetch pages, and do math when needed
- Every action is logged so you can trace how the answer was built

## Stack

- Frontend: SvelteKit + TypeScript + Tailwind CSS
- Backend: FastAPI + SQLAlchemy + Postgres
- Providers: Groq, OpenRouter, LM Studio
- Infra: Docker Compose

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

- `GROQ_API_KEY` (or OpenRouter / LM Studio config)
- `MOCK_MODE=false` when you want live provider calls
