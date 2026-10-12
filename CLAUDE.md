# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`tracker-mcp` is a Python FastMCP server that exposes `tracker-server`'s REST API as MCP tools over **stdio**. It is one client in the tracker meta-repo (see `../CLAUDE.md` for cross-component conventions); `../tracker-server/openapi.yml` is the API contract every tool here must follow.

## Commands

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt        # runtime deps + pytest, pytest-asyncio

pytest                                     # all tests (fully mocked, no live server needed; pytest.ini sets pythonpath)
pytest tests/test_server.py::test_set_schedule_task_time   # single test
pytest -k suggest_daily_schedule           # by name pattern

TRACKER_API_URL=http://localhost:3000 python server.py   # blocks waiting for MCP JSON-RPC on stdin — expected
python server.py --help

docker build -t tracker-mcp .
docker run -i --rm -e TRACKER_API_URL=http://host.docker.internal:3000 tracker-mcp   # -i required, no -t
```

There is no linter/formatter config. CI (`.github/workflows/docker-publish.yml`) runs `pytest`, then builds a multi-arch image; on push to `main`/`master` it pushes to `ghcr.io/<owner>/tracker-mcp` (tags `latest`, date, short sha), on PRs it only builds.

## Configuration

- `TRACKER_API_URL` — backend base URL (default `http://localhost:3000`; the Docker image defaults to `http://host.docker.internal:3000`).
- `TRACKER_API_KEY` or `TRACKER_BOT_TOKEN` — if set, sent as the `X-Bot-Token` header (checked by `tracker-server`'s `internal/api/middleware/telegram.go`).

## Architecture

Everything lives in `server.py`; tests in `tests/test_server.py`.

- **`_make_request(method, endpoint, json_data, params)`** is the single HTTP path for all tools; it forwards both body and query params for every method. It never raises: HTTP errors become `{"error": "HTTP <code>", "details": ...}`, other exceptions `{"error": "Internal Error", ...}`, an empty body becomes `{"status": "success"}`, a non-JSON 2xx body `{"error": "Invalid Response", "details": <text>}` (every API endpoint returns JSON, so it means the URL points at something else), and an unsupported method `{"error": "Unsupported Method", ...}`. Callers (and composite tools) detect failure by checking `isinstance(res, dict) and res.get("error")`.
- **Logging must go to stderr** — stdout is the MCP stdio transport, so any `print` outside `--help` corrupts the protocol.
- **Most tools are thin 1:1 wrappers** over one endpoint. The few with real logic:
  - `set_schedule_task_time` / `adjust_schedule_task_time` → server-side `PATCH /api/v1/schedule/active/task-time`; day strings go through `_normalize_day` (aliases like `"every day"`/`"weekly"` → `"all"`).
  - `add_schedule_tasks` does a **client-side read-modify-write**: `GET /api/v1/schedule/active`, mutate the day(s) in memory (case-insensitive name match, recompute `total_time`), then `PUT /api/v1/schedule/{id}` with only the seven weekday keys (`_schedule_request_from_active`).
  - `suggest_daily_schedule` encodes the user's personal routine heuristics (work/english/background tasks/`home_task`, weekday vs weekend targets). It previews by default; with `apply=True` it calls `set_schedule_task_time` once per change and reports `success`/`partial`/`error`. Scope strings resolve via `_resolve_target_days`.
- **Units:** rest tools send `rest_time` in minutes (server converts); `get_rest` returns the server's raw units (`minutes * 100`) plus a derived `rest_minutes`. The legacy `get_timer`/`set_timer` pair works on the server's escalating interval list: `set_timer(count)` resets it to `[1..count]` minutes and `get_timer` returns the first remaining interval (so not the value just set); it is unrelated to the `timer/run/*` running-task timers.
- Validation that the server would otherwise reject (positive minutes, `source_day` must be a weekday name, schedule task shape) is done client-side and returns an `{"error": ...}` dict without calling the API.
- MCP tool docstrings and `Args:` sections are what the LLM client sees as the tool description — keep them accurate when changing behavior.

## Testing pattern

Tests patch `server._make_request` with `AsyncMock` and assert the exact `(method, endpoint, json_data=..., params=...)` call, so changing a tool's request shape means updating the matching `assert_called_once_with`. Composite tools (`suggest_daily_schedule`) use `side_effect` to return different responses per call. `_make_request` itself is tested by patching `server.httpx.AsyncClient` to inject an `httpx.MockTransport`.

When adding or changing a tool, verify the request shape against the Go handler in `../tracker-server/internal/api/handler/` as well as `openapi.yml` — the spec lags the handlers in places (e.g. `manage_by_service` on `/taskrecord`, `time_duration` on `/timer/set` exist only in the Go structs).
