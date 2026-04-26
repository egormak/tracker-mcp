# Repository Guidelines

## Project Structure & Module Organization

This repository contains a small Python MCP server that bridges MCP clients to a local `tracker-server`.

- `server.py`: FastMCP server entrypoint, tool definitions, and HTTP helper logic.
- `requirements.txt`: runtime Python dependencies.
- `Dockerfile`: container image definition for stdio-based MCP usage.
- `.github/workflows/docker-publish.yml`: builds and pushes the Docker image to GHCR on `main` or `master`.
- `README.md`: end-user setup instructions for Docker and local execution.

There is no `tests/` directory yet. If tests are added, keep them under `tests/`, for example `tests/test_server.py`.

## Build, Test, and Development Commands

Set up a local environment:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
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

Prefer explicit type hints for public helpers and MCP tool parameters. Keep comments short and limited to non-obvious behavior.

## Testing Guidelines

No automated test framework is configured yet. For new tests, use `pytest` and mock outbound `httpx.AsyncClient` calls instead of requiring a live tracker API. Name test files `test_*.py` and test functions `test_*`.

Recommended command once tests exist:

```bash
pytest
```

Before submitting changes, at minimum run the server locally and verify changed tools against a running `tracker-server`.

## Commit & Pull Request Guidelines

This directory does not include Git history, so no repository-specific commit convention is visible. Use concise, imperative commit messages, for example `Add timer validation`.

Pull requests should include a short summary, reason for the change, test results, and configuration impact. For MCP behavior changes, list affected tool names and tracker API endpoints.

## Security & Configuration Tips

Do not commit local secrets, `.env` files, or virtual environments. Configure the backend URL with `TRACKER_API_URL`; use `http://localhost:3000` for local Python runs and `http://host.docker.internal:3000` for Docker Desktop.
