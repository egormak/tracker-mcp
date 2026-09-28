# tracker-mcp

FastMCP Python server exposing `tracker-server` REST API capabilities as Model Context Protocol (MCP) tools over stdio for LLM assistants.

## Project Overview

- **Technologies**: Python 3.11+, FastMCP, httpx, pytest, pytest-asyncio.
- **Transport**: stdio (MCP JSON-RPC over stdin/stdout).
- **Role**: Bridges LLM AI assistants (Gemini, Claude, Antigravity) to `tracker-server` REST endpoints, providing tools for task tracking, schedule editing, timer control, rest tracking, and evening focus mode.
- **Ecosystem Context**: Part of the tracker ecosystem (`../tracker-server` Go Fiber backend, `tracker-app` macOS app, `tracker_cli`, `tracker_bot`, `tracker-web`). The definitive API contract is `../tracker-server/openapi.yml` and Go handlers in `../tracker-server/internal/api/handler/`.
- **Key Files**:
  - `server.py`: FastMCP server entrypoint, tool definitions, request routing helper, and normalization logic.
  - `requirements.txt`: Minimal runtime dependencies (`fastmcp`, `httpx`).
  - `requirements-dev.txt`: Runtime dependencies plus test suite packages (`pytest`, `pytest-asyncio`).
  - `pytest.ini`: Configures test paths and sets pythonpath to root.
  - `tests/test_server.py`: Comprehensive test suite using mocked transport and async mocks.
  - `Dockerfile`: Multi-arch container image definition for stdio execution.
  - `.github/workflows/docker-publish.yml`: CI running pytest and publishing Docker images to GHCR.

## Building and Running

### Local Environment Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

### Running Tests
All tests are fully mocked and require no live `tracker-server`:
```bash
pytest                                                      # Run all tests
pytest tests/test_server.py::test_set_schedule_task_time    # Run specific test
pytest -k suggest_daily_schedule                            # Filter tests by expression
```

### Running Locally
```bash
TRACKER_API_URL=http://localhost:3000 python server.py
```
*Note: The process communicates over stdio and will block waiting for MCP JSON-RPC input.*
Use `python server.py --help` to display help and environment variable documentation.

### Running with Docker
```bash
docker build -t tracker-mcp .
docker run -i --rm -e TRACKER_API_URL=http://host.docker.internal:3000 tracker-mcp
```
*Note: Always pass `-i` and do NOT pass `-t`. The container runs interactively over stdio without a TTY.*

## Configuration

- `TRACKER_API_URL`: Backend REST API URL (default: `http://localhost:3000`; Docker image defaults to `http://host.docker.internal:3000`).
- `TRACKER_API_KEY` or `TRACKER_BOT_TOKEN`: Optional auth token, forwarded as the `X-Bot-Token` HTTP header to `tracker-server`.

## Architecture & Implementation Patterns

- **Stdio Transport Safety**: MCP uses `sys.stdout` exclusively for JSON-RPC messages. Never call `print()` in server code (outside CLI `--help`). All logging must be sent to `sys.stderr` via `logging.basicConfig(level=logging.INFO, stream=sys.stderr)` and `logger`.
- **Centralized Routing (`_make_request`)**:
  - Single helper for all outbound HTTP requests (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`).
  - Forwards `json_data` body and `params` query string for any HTTP method.
  - Exception-safe: Never raises unhandled exceptions to MCP callers. Converts HTTP error codes to `{"error": f"HTTP {status_code}", "details": ...}` and network/system errors to `{"error": "Internal Error", "details": ...}`.
  - Handles empty 200 OK responses as `{"status": "success"}` and raw text as `{"status": "success", "details": text}`.
  - Callers check errors via `isinstance(res, dict) and res.get("error")`.
- **Client-Side Validation**:
  - Validates positive integers for task minutes, rest minutes, and timer durations before sending requests.
  - Validates task payload dictionaries in batch updates (`add_schedule_tasks`) and rejects invalid shapes (e.g., boolean `time`).
  - Returns `{"error": ...}` dicts directly without dispatching invalid HTTP calls.
- **Day & Scope Normalization**:
  - `_normalize_day(day)`: Normalizes weekday names and aliases (`"today"`, `"all"`, `"every day"`, `"weekly"`, etc.).
  - `_resolve_target_days(scope)`: Expands targets to appropriate day lists (`"week"` -> 7 days, `"weekdays"` -> 5 days, `"weekends"` -> 2 days, `"today"` -> current weekday).
- **Time Units Conventions**:
  - Rest pool: `tracker-server` represents raw rest time in units (`minutes * 100`). MCP rest tools (`add_rest`, `spend_rest`) accept `minutes`. `get_rest` returns server's `rest_time` plus a calculated `rest_minutes = rest_time / 100`. Pool is capped at 60 minutes.
  - Legacy countdown timer: `get_timer`/`set_timer` deal with default timer duration in minutes (`time_duration`), separate from `timer/run/*` running-task timers.
- **Composite Tools**:
  - `add_schedule_tasks`: Performs client-side read-modify-write on active weekly schedule (`GET /api/v1/schedule/active` -> update in memory with case-insensitive matching & recalculate `total_time` -> `PUT /api/v1/schedule/{id}`).
  - `suggest_daily_schedule`: Encodes routine heuristics (weekday work 270m, english 20m, background task smoothing 30m, weekend home task 60m focus, rollover deficit detection). Previews by default; atomically updates schedule via `set_schedule_task_time` when `apply=True`.

## Available MCP Tools

### Schedule & Planning
- `get_today_schedule`: Fetch today's actual schedule including active and rollover tasks (`GET /api/v1/schedule/active/today`).
- `get_active_weekly_schedule`: Fetch full editable weekly schedule model (`GET /api/v1/schedule/active`).
- `apply_schedule_today`: Reset/apply active schedule to today's daily task definitions in `tracker-server` (`POST /api/v1/schedule/apply`).
- `set_schedule_task_time`: Set existing task's scheduled minutes for today, a weekday, or all days (`PATCH /api/v1/schedule/active/task-time`).
- `adjust_schedule_task_time`: Relative increase/decrease (`delta_minutes`) for task in active schedule (`PATCH /api/v1/schedule/active/task-time`).
- `add_schedule_tasks`: Batch add or update tasks in active weekly schedule (`PUT /api/v1/schedule/{id}`).
- `suggest_daily_schedule`: Analyze and balance weekly or daily schedule against routine heuristics (supports preview and `apply=True`).
- `get_rollover_tasks`: Fetch incomplete tasks carrying over from previous days (`GET /api/v1/schedule/active/rollover`).
- `get_task_plan`: Fetch next recommended task based on assigned percentages and schedule priority (`GET /api/v1/task/plan/percent/schedule`).
- `rotate_plan_percent`: Rotate active plan percent group to the next configured group (`POST /api/v1/task/plan/rotate`).

### Task Records & Statistics
- `add_task_record`: Record completed task minutes with optional `source_day` and `manage_by_service` (`POST /api/v1/taskrecord`).
- `get_today_stats`: Fetch today's task completion statistics and time spent (`GET /api/v1/stats/done/today`).
- `get_weekly_stats`: Fetch weekly completion statistics with per-day breakdowns and role totals (`GET /api/v1/stats/weekly`).

### Running Task Timers (Server-Authoritative)
- `start_task_timer`: Start timer for a task with optional role, target duration, and source day (`POST /api/v1/timer/run/start`).
- `stop_task_timer`: Stop running task timer (`POST /api/v1/timer/run/stop`).
- `pause_task_timer`: Pause active task timer (`POST /api/v1/timer/run/pause`).
- `resume_task_timer`: Resume paused task timer (`POST /api/v1/timer/run/resume`).
- `adjust_running_task_timer`: Adjust target duration of active running timer (+/- minutes) (`POST /api/v1/timer/run/adjust`).
- `get_running_task_status`: Get status of running or paused task timers (`GET /api/v1/timer/run/status`).
- `list_running_tasks`: List all active and paused running tasks (`GET /api/v1/timer/run/list`).

### Rest Pool Management
- `get_rest`: Retrieve available rest pool balance (`rest_time` in units and `rest_minutes`) (`GET /api/v1/rest/get`).
- `add_rest`: Add accumulated rest minutes to pool (capped at 60m) (`POST /api/v1/rest/add`).
- `spend_rest`: Spend rest minutes from pool (`POST /api/v1/rest/spend`).

### Default Countdown Timer
- `get_timer`: Get default countdown timer duration in minutes (`GET /api/v1/timer/get`).
- `set_timer`: Set default countdown timer duration in minutes (`POST /api/v1/timer/set`).

### Evening Focus Mode
- `get_evening_focus_task`: Fetch ranked candidate task for evening catch-up mode (`GET /api/v1/mode/evening-focus`).
- `skip_evening_focus_task`: Skip current evening candidate and fetch next candidate (`POST /api/v1/mode/evening-focus/skip`).

## Development & Testing Guidelines

- **Mocking Outbound Requests**: Never connect to live servers in automated tests. Patch `server._make_request` with `AsyncMock` to verify exact parameters (`method`, `endpoint`, `json_data`, `params`).
- **Testing HTTP Client**: Use `httpx.MockTransport` when testing `_make_request` error conditions and text/JSON parsing.
- **Tool Docstrings**: Keep docstrings and `Args:` clear and accurate — MCP clients display these directly to LLMs as tool descriptions.
- **Conventional Commits**: Use conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).
