# agent-forge

agent-forge is a modular multi-agent orchestration platform with a SvelteKit frontend and Python backend.

## Current status

- Phase A implemented: foundation skeleton, run lifecycle, and trace timeline.
- Phase B baseline implemented: provider adapter layer for Groq/OpenRouter/LM Studio and single-agent execution path.
- Phase C baseline implemented: planner-generated task graph and task timeline endpoint.
- Phase D baseline implemented: specialist assignment and critic review loop with one revision pass.
- Phase E baseline implemented: read-only tool runtime with policy checks and tool catalog endpoint.
- Phase F baseline implemented: human-in-the-loop approval queue and approve/reject decision flow.
- Phase G baseline implemented: opt-in persistent memory retrieval/store across runs.

## Stack

- Frontend: SvelteKit + TypeScript + Tailwind CSS
- Backend: FastAPI + SQLAlchemy
- Orchestration path: LangGraph-ready architecture (custom domain layer first)
- Providers: Groq, OpenRouter, LM Studio
- Infra: Docker Compose with Postgres, Redis, MinIO

## Phase A includes

- Goal intake endpoint: `POST /api/v0/goals`
- Run lookup endpoint: `GET /api/v0/runs/{run_id}`
- Timeline endpoint: `GET /api/v0/runs/{run_id}/timeline`
- Run state transitions: `queued -> running -> completed|failed`
- Timeline event model with audit-friendly event types
- Svelte dashboard page to create run and view timeline

## Phase B includes

- Provider registry with adapters:
  - `groq` (`https://api.groq.com/openai/v1`)
  - `openrouter` (`https://openrouter.ai/api/v1`)
  - `lmstudio` (local OpenAI-compatible endpoint)
- Default provider routing via `DEFAULT_MODEL_PROVIDER`
- Single-agent executor that calls selected provider and logs preview in timeline
- `MOCK_MODE=true` in Docker by default for safe startup without API keys

## Phase C includes

- Task graph data model: `task_nodes`
- Planner that creates baseline DAG-like steps per run goal
- Task node statuses and dependency metadata
- New endpoint: `GET /api/v0/runs/{run_id}/tasks`
- UI task graph section to display ordered task nodes

## Phase D includes

- Specialist routing by task kind (`planner`, `researcher`, `analyst`, `writer`, `operator`)
- Orchestrator loop that executes task nodes in order with dependency checks
- Critic review event for each node (`critic.reviewed`) and one revision pass (`task.revised`) when needed
- Additional timeline events: `task.assigned`, `task.blocked`, `run.output`

## Phase E includes

- Read-only tool runtime with initial tools:
  - `search_web`
  - `fetch_url`
  - `calculator`
- Policy allowlist checks before tool usage
- Timeline events for governance and observability:
  - `policy.checked`
  - `tool.invoked`
- Tool catalog endpoint: `GET /api/v0/tools`

## Phase F includes

- Approval request model and queue for risky goals
- New run status: `waiting_approval`
- Approval inbox endpoint: `GET /api/v0/approvals`
- Decision endpoint: `POST /api/v0/approvals/{approval_id}/decision`
- Run resume path after approval and run fail path after rejection
- Approval polling now runs only while a run is `waiting_approval` (prevents constant API spam)

## Phase G includes

- Opt-in memory toggle on run creation (`memory_enabled`)
- Memory retrieval before execution when memory is enabled (`memory.retrieved` event)
- Memory storage after completion (`memory.stored` event)
- Memory endpoint: `GET /api/v0/memory`
- Dashboard memory panel listing recent memory items

## Repository layout

- `apps/api` - Python FastAPI backend
- `apps/web` - SvelteKit frontend
- `docker-compose.yml` - container orchestration
- `.opencode/plans/1776180722899-silent-forest.md` - implementation plan

## Run instructions (you run these)

1. Start containers:

```bash
docker compose up --build
```

If you were already running containers before the postgres port change, refresh with:

```bash
docker compose down -v
docker compose up --build
```

2. Open app:

- Frontend: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- MinIO console: `http://localhost:9001`

3. Optional local API dev:

```bash
cd apps/api
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Optional local web dev:

```bash
cd apps/web
bun install
bun run dev
```

## API environment variables

- `DATABASE_URL`
- `DEFAULT_MODEL_PROVIDER` (`groq` | `openrouter` | `lmstudio`)
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `LMSTUDIO_BASE_URL` (default `http://host.docker.internal:1234/v1`)
- `GROQ_DEFAULT_MODEL`
- `OPENROUTER_DEFAULT_MODEL`
- `LMSTUDIO_DEFAULT_MODEL`
- `MOCK_MODE` (`true`/`false`)

## Frontend dependency versions pinned

- `@sveltejs/kit`: `2.57.1`
- `svelte`: `5.55.4`
- `vite`: `6.3.5`
- `@sveltejs/vite-plugin-svelte`: `5.1.1`
- `tailwindcss`: `4.2.2`
- `typescript`: `6.0.2`

Compatibility note:

- Web container currently runs on Bun image. To avoid Bun/Node-compat issues with Vite 8 (`util.parseEnv`), web runtime is pinned to Vite 6.3.5 stack.
- SvelteKit scaffold now includes required `apps/web/src/app.html` and `jsconfig.json` to prevent startup template/tsconfig warnings.
- `bun run prepare` is executed during web image build to generate `.svelte-kit/tsconfig.json` before dev startup.
- Tailwind v4 uses PostCSS plugin `@tailwindcss/postcss` (not `autoprefixer`/`tailwindcss` plugin pair).
