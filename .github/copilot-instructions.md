# Copilot Instructions

The full project specification lives in `docs/SPEC.md` — always consult it for architecture, data model, component design, and tech stack details. These instructions cover **operational guidance** that is not in the spec.

## Development Tooling

- **Package & project management**: Use `uv` for all dependency management, virtual environments, and running scripts (e.g., `uv run`, `uv add`, `uv sync`). Note: `agent-framework-core` is a prerelease package — always use `--prerelease=allow` with `uv sync`.
- **Type checking**: Use `ty` for static type analysis (`uv run ty check src/`)
- **Linting & formatting**: Use `ruff` for linting and code formatting (`uv run ruff check src/ tests/` and `uv run ruff format src/ tests/`)
- **Validation before committing**: Always run `ruff check`, `ruff format --check`, `ty check`, and `pytest` before committing changes. All four must pass cleanly.
- **Dependencies**: Only use well-known, widely-adopted packages. When in doubt, ask before adding a dependency. Always use the latest stable version available on PyPI when adding or updating packages — check https://pypi.org/pypi/{package}/json for current versions.
- **Bicep**: Always use the latest available API versions for all Azure resource definitions. Check the Azure Resource Manager template reference for current API versions before creating or updating Bicep modules.
- **Source control**: Commit at the end of major changes using imperative mood subject lines (e.g., "Add …", "Update …", "Remove …") with an optional prose paragraph body describing the why or key details
- **Documentation**: Always review `README.md` at the end of major changes and keep it up-to-date with the current state of the project
- **Local Cosmos DB**: The emulator uses `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview` (ARM-compatible). Ports: 8081 (gateway), 1234 (data explorer). Runs via `docker compose up -d`.

## Key Conventions

- The edition `content` dict follows a structured schema — see `prompts/draft.md` for the full specification.
