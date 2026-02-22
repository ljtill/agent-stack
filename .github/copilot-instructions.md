# Copilot Instructions

The full project specification lives in `docs/SPECIFICATION.md` — always consult it for architecture, data model, component design, and tech stack details. For visual diagrams, see `docs/ARCHITECTURE.md`. These instructions cover **operational guidance** that is not in the spec.

## Build, Test & Lint

```bash
# Install dependencies (prerelease flag required for agent-framework-core)
uv sync --all-groups --prerelease=allow

# Run all tests
uv run pytest tests/ -v

# Run a single test file or test function
uv run pytest tests/agents/test_fetch.py -v
uv run pytest tests/agents/test_fetch.py::test_fetch_agent_returns_content -v

# Lint and format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type checking
uv run ty check src/

# Run the app locally (requires docker compose up -d first)
uv run uvicorn agent_stack.app:create_app --factory --reload --reload-dir src
```

Always run `ruff check`, `ruff format --check`, `ty check`, and `pytest` before committing. All four must pass cleanly.

Tests use `pytest-asyncio` with `asyncio_mode = "auto"` and support markers `@pytest.mark.unit` and `@pytest.mark.integration`. Coverage must stay at or above 80% (`fail_under = 80` in `pyproject.toml`).

## Architecture

This is an event-driven editorial pipeline for a newsletter. The system has three surfaces: a FastAPI + HTMX dashboard (private), a multi-agent LLM pipeline, and a statically generated public newsletter site.

**Event flow**: Editor submits link → Cosmos DB → change feed processor → pipeline orchestrator → sub-agents (Fetch → Review → Draft) → Cosmos DB updates → SSE to dashboard. Feedback and publish follow similar event-driven paths. No external message broker — Cosmos DB's change feed is the sole event source.

**Agent architecture**: Five specialized agents (Fetch, Review, Draft, Edit, Publish) are coordinated by a `PipelineOrchestrator` agent. Each agent wraps a Microsoft Agent Framework `Agent` instance, exposes `@tool`-decorated methods as LLM-callable functions, and is registered on the orchestrator via `.as_tool()`. Middleware (token tracking, tool logging) stacks on each agent.

**App wiring**: `app.py` uses a lifespan context manager to initialize Cosmos client → repositories → agents → orchestrator → change feed processor, stashing everything in `app.state`. Routes access dependencies via `request.app.state`.

**Local emulators**: `docker compose up -d` starts both the Cosmos DB emulator (ports 8081/1234) and Azurite storage emulator (ports 10000–10002).

## Key Conventions

- **Package management**: Use `uv` for everything — `uv run`, `uv add`, `uv sync`. The `agent-framework-core` package requires `--prerelease=allow`.
- **Database layer**: `BaseRepository[T]` provides generic CRUD with automatic soft-delete filtering (`deleted_at` timestamp). Each entity (Link, Edition, Feedback, AgentRun) has its own repository subclass. All models extend `DocumentBase` (Pydantic) which generates `id`, `created_at`, `updated_at`, and `deleted_at` fields.
- **Agent prompts**: Stored as Markdown in `prompts/` (one per agent stage), loaded at runtime. The edition `content` dict follows a structured schema — see `prompts/draft.md` for the full specification.
- **Config**: Frozen dataclasses in `config.py`, composed into a `Settings` aggregate. Values come from environment variables (`.env` locally, Azure App Configuration in production).
- **Frontend**: Jinja2 templates + HTMX for the dashboard. Partials in `templates/partials/` return HTML fragments for in-place updates. SSE via `sse-starlette` for real-time events.
- **Test patterns**: `AsyncMock` fixtures for repositories, callable factory fixtures (`make_link()`, `make_edition()`, etc.) with sensible defaults in `tests/conftest.py`, `pytest-asyncio` with `asyncio_mode = "auto"`.
- **Ruff config**: `select = ["ALL"]` — all rules enabled with minimal exceptions. Tests are exempted from `S101` (assert). See `pyproject.toml` for details.
- **Bicep**: Use the latest available API versions for all Azure resource definitions. Infrastructure modules live in `infra/`.
- **Source control**: Imperative mood commit subjects (e.g., "Add …", "Update …"). Always review `README.md` at the end of major changes.
- **Dependencies**: Only add well-known, widely-adopted packages. Use the latest stable version from PyPI.
