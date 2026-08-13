# tracker-mcp

FastMCP Python server exposing `tracker-server` REST API capabilities as Model Context Protocol (MCP) tools over stdio for LLM assistants.

## Project Overview

- **Technologies**: Python 3.10+, FastMCP, httpx.
- **Transport**: stdio.
- **Role**: Bridges LLM AI assistants (like Claude, Gemini, Antigravity) to `tracker-server` REST endpoints, providing tools for task tracking, schedule editing, timer control, rest tracking, and evening focus mode.
- **Architecture**:
  - `server.py`: Entrypoint defining FastMCP server, async tools, and `_make_request()` helper.
  - `requirements.txt`: Python dependencies (`fastmcp`, `httpx`).
  - `Dockerfile`: Container image definition for stdio execution.

## Building and Running

### Local Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running Locally
```bash
TRACKER_API_URL=http://localhost:3000 python server.py
```

### Docker
```bash
docker build -t tracker-mcp .
docker run -i --rm -e TRACKER_API_URL=http://host.docker.internal:3000 tracker-mcp
```

## Available MCP Tools

- `get_today_schedule`: Fetch active schedule for today.
- `set_schedule_task_time`: Update target time for a specific task in schedule.
- `add_schedule_tasks`: Batch add/update tasks in schedule.
- `apply_schedule_today`: Reset/apply active schedule to today's task plan.
- `get_evening_focus_task`: Fetch ranked candidate task for Evening Catch-Up Mode.
- `skip_evening_focus_task`: Skip current evening candidate task and move to next.
- `add_task_record`: Record completed task minutes.
- `get_tasks_list`: Fetch list of available tasks.
- `start_running_task` / `stop_running_task` / `pause_running_task` / `resume_running_task` / `get_running_task_status`: Control server-authoritative timer.
- `spend_rest` / `get_rest_info`: Manage rest time.

## Development Conventions

- **Async Tools**: All FastMCP tool functions are `async def`.
- **Centralized Routing**: Pass all backend HTTP calls through `_make_request()` to ensure uniform error handling and JSON parsing.
- **URL Configuration**: Base API URL is specified via `TRACKER_API_URL` environment variable (default: `http://localhost:3000`).
