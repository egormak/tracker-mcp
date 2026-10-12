# Repository Guidelines

## Project Structure & Module Organization

This repository contains a small Python MCP server that bridges MCP clients to a local `tracker-server`.

- `server.py`: FastMCP server entrypoint, tool definitions, and HTTP helper logic.
- `requirements.txt`: runtime Python dependencies.
- `Dockerfile`: container image definition for stdio-based MCP usage.
- `.github/workflows/docker-publish.yml`: runs `pytest`, then builds the Docker image; it is pushed to GHCR only on `main` or `master` (PRs build without pushing).
- `README.md`: end-user setup instructions for Docker and local execution.
- `tests/test_server.py`: pytest suite; `pytest.ini` puts the repo root on `sys.path`.
- `requirements-dev.txt`: runtime deps plus `pytest` and `pytest-asyncio`.

## Build, Test, and Development Commands

Set up a local environment:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

Run the MCP server locally:

```bash
TRACKER_API_URL=http://localhost:3000 python server.py
```

The process communicates over stdio and waits for MCP JSON-RPC input. Ensure `tracker-server` is running before manual checks.

Build the Docker image locally:

```bash
docker build -t tracker-mcp .
```

Run the container:

```bash
docker run -i --rm -e TRACKER_API_URL=http://host.docker.internal:3000 tracker-mcp
```

## Coding Style & Naming Conventions

Use Python 3.11+ and follow PEP 8 with 4-space indentation. Keep MCP tool functions asynchronous and named with clear snake_case verbs, such as `get_today_schedule` or `add_task_record`. Keep request routing centralized through `_make_request` so timeout, error handling, and JSON parsing stay consistent.

- **MCP Stdio Safety**: FastMCP communicates over stdio using `sys.stdout`. Never call `print()` or write to stdout (outside CLI `--help`). All application logging must be routed to `sys.stderr` via `logger`.
- **Validation**: Reject invalid inputs client-side (non-positive minutes, invalid day names, malformed task dicts) and return `{"error": ...}` dicts without raising unhandled exceptions or making failed API requests.
- **Units**: Rest endpoints send `rest_time` in minutes (the server converts to raw units `minutes * 100`); `get_rest` returns raw `rest_time` plus a calculated `rest_minutes`. The legacy countdown timer is an interval list in minutes: `set_timer(count)` resets it to `[1..count]`, `get_timer` returns the first remaining interval.
- **API Contract**: Match request/response schemas with `../tracker-server/openapi.yml` and the Go route handlers under `../tracker-server/internal/api/handler/`.

Prefer explicit type hints for public helpers and MCP tool parameters. Keep comments short and limited to non-obvious behavior.

## Testing Guidelines

Tests use `pytest` + `pytest-asyncio` and never need a live tracker API: tool tests patch `server._make_request` with `AsyncMock`, and `_make_request` itself is tested with `httpx.MockTransport`. Name test files `test_*.py` and test functions `test_*`.

```bash
pytest
pytest tests/test_server.py::test_add_rest_sends_rest_time
```

Before submitting changes, at minimum run the server locally and verify changed tools against a running `tracker-server`.

## Commit & Pull Request Guidelines

Commits follow Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`), for example `fix: send rest_time in rest tools`.

Pull requests should include a short summary, reason for the change, test results, and configuration impact. For MCP behavior changes, list affected tool names and tracker API endpoints.

## Security & Configuration Tips

Do not commit local secrets, `.env` files, or virtual environments. Configure the backend URL with `TRACKER_API_URL` and, if the backend requires it, `TRACKER_API_KEY` (or `TRACKER_BOT_TOKEN`), sent as `X-Bot-Token`; use `http://localhost:3000` for local Python runs and `http://host.docker.internal:3000` for Docker Desktop.
