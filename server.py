import os
import sys
import logging
import httpx
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from typing import Optional, Any

# Configure structured logging to stderr (to avoid breaking MCP stdio)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("tracker-mcp-server")

API_BASE = os.getenv("TRACKER_API_URL", "http://localhost:3000").rstrip("/")

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

async def _make_request(method: str, endpoint: str, json_data: dict = None, params: dict = None) -> Any:
    """Helper method to make async HTTP requests to the tracker server."""
    url = f"{API_BASE}{endpoint}"
    headers = {}
    api_key = os.getenv("TRACKER_API_KEY") or os.getenv("TRACKER_BOT_TOKEN")
    if api_key:
        headers["X-Bot-Token"] = api_key
        
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "GET":
                response = await client.get(url, params=params, headers=headers)
            elif method == "POST":
                response = await client.post(url, json=json_data, headers=headers)
            elif method == "PUT":
                response = await client.put(url, json=json_data, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            
            # For 200 OK without content (like sometimes with fiber if it just returns 200)
            if not response.text:
                return {"status": "success"}
                
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e.response.text}")
        return {"error": f"HTTP {e.response.status_code}", "details": e.response.text}
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return {"error": "Internal Error", "details": str(e)}

def _today_name() -> str:
    """Return today's lowercase weekday name."""
    return DAYS[datetime.now().weekday()]

def _normalize_day(day: Optional[str]) -> str:
    """Normalize common day aliases used by natural-language MCP calls."""
    if not day:
        return "today"

    normalized = day.strip().lower().replace("-", " ").replace("_", " ")
    aliases = {
        "tod": "today",
        "today": "today",
        "all": "all",
        "every day": "all",
        "everyday": "all",
        "daily": "all",
        "week": "all",
        "weekly": "all",
    }
    normalized = aliases.get(normalized, normalized)

    if normalized == "today":
        return _today_name()
    if normalized in DAYS or normalized == "all":
        return normalized
    raise ValueError(f"Invalid day '{day}'. Use today, all, or one of: {', '.join(DAYS)}")

def _schedule_request_from_active(schedule: dict) -> dict:
    """Build the update payload expected by PUT /api/v1/schedule/:id."""
    return {day: schedule[day] for day in DAYS}

def _available_tasks(day_schedule: dict) -> list[str]:
    return [task.get("name", "") for task in day_schedule.get("tasks", [])]

async def _get_active_schedule_data() -> tuple[Optional[dict], Optional[dict]]:
    response = await _make_request("GET", "/api/v1/schedule/active")
    if isinstance(response, dict) and response.get("error"):
        return None, response

    schedule = response.get("data") if isinstance(response, dict) else None
    if not isinstance(schedule, dict):
        return None, {"error": "Invalid Response", "details": response}
    if not schedule.get("id"):
        return None, {"error": "Invalid Response", "details": "Active schedule has no id"}

    return schedule, None

def _update_task_time(schedule: dict, day: str, task_name: str, new_minutes: int) -> Optional[dict]:
    day_schedule = schedule.get(day)
    if not isinstance(day_schedule, dict):
        return None

    target = task_name.strip().lower()
    for task in day_schedule.get("tasks", []):
        if task.get("name", "").strip().lower() == target:
            old_minutes = task.get("time", 0)
            task["time"] = new_minutes
            return {
                "day": day,
                "task_name": task.get("name", task_name),
                "old_minutes": old_minutes,
                "new_minutes": new_minutes,
            }
    return None

async def _save_active_schedule(schedule: dict) -> Any:
    schedule_id = schedule["id"]
    payload = _schedule_request_from_active(schedule)
    return await _make_request("PUT", f"/api/v1/schedule/{schedule_id}", json_data=payload)

@mcp.tool()
async def get_today_stats() -> Any:
    """Get today's tasks completion statistics and time spent."""
    return await _make_request("GET", "/api/v1/stats/done/today")

@mcp.tool()
async def get_today_schedule() -> Any:
    """Get today's actual schedule including both rollover and active tasks."""
    return await _make_request("GET", "/api/v1/schedule/active/today")

@mcp.tool()
async def get_active_weekly_schedule() -> Any:
    """Get the full active weekly schedule that can be edited."""
    return await _make_request("GET", "/api/v1/schedule/active")

@mcp.tool()
async def apply_schedule_today() -> Any:
    """Apply the active schedule for today, creating daily task definitions in tracker-server."""
    return await _make_request("POST", "/api/v1/schedule/apply")

@mcp.tool()
async def set_schedule_task_time(task_name: str, minutes: int, day: str = "today") -> dict:
    """Set an existing task's scheduled minutes for today, a weekday, or all days.

    Args:
        task_name: Existing schedule task name, matched case-insensitively (for example, "work" or "video").
        minutes: New scheduled duration in minutes. Must be zero or greater.
        day: "today", a weekday name such as "monday", or "all"/"every day" for every weekday.
    """
    if minutes < 0:
        return {"error": "Minutes must be zero or greater"}

    try:
        normalized_day = _normalize_day(day)
    except ValueError as e:
        return {"error": "Invalid Day", "details": str(e)}

    schedule, error = await _get_active_schedule_data()
    if error:
        return error

    days_to_update = DAYS if normalized_day == "all" else [normalized_day]
    changes = []
    missing = {}

    for update_day in days_to_update:
        change = _update_task_time(schedule, update_day, task_name, minutes)
        if change:
            changes.append(change)
        else:
            missing[update_day] = _available_tasks(schedule.get(update_day, {}))

    if not changes:
        return {
            "error": "Task Not Found",
            "task_name": task_name,
            "searched_days": days_to_update,
            "available_tasks": missing,
        }

    update_response = await _save_active_schedule(schedule)
    if isinstance(update_response, dict) and update_response.get("error"):
        return update_response

    return {
        "status": "success",
        "schedule_id": schedule["id"],
        "changes": changes,
        "missing_days": missing,
        "tracker_response": update_response,
    }

@mcp.tool()
async def adjust_schedule_task_time(task_name: str, minutes_delta: int, day: str = "all") -> dict:
    """Increase or decrease an existing task's scheduled minutes.

    Args:
        task_name: Existing schedule task name, matched case-insensitively.
        minutes_delta: Minutes to add or subtract, for example 10 or -15.
        day: "today", a weekday name such as "monday", or "all"/"every day" for every weekday.
    """
    try:
        normalized_day = _normalize_day(day)
    except ValueError as e:
        return {"error": "Invalid Day", "details": str(e)}

    schedule, error = await _get_active_schedule_data()
    if error:
        return error

    days_to_update = DAYS if normalized_day == "all" else [normalized_day]
    changes = []
    missing = {}

    for update_day in days_to_update:
        day_schedule = schedule.get(update_day, {})
        target = task_name.strip().lower()
        matched = False

        for task in day_schedule.get("tasks", []):
            if task.get("name", "").strip().lower() == target:
                old_minutes = task.get("time", 0)
                new_minutes = old_minutes + minutes_delta
                if new_minutes < 0:
                    return {
                        "error": "Invalid Minutes",
                        "details": f"{task.get('name', task_name)} on {update_day} would become negative ({new_minutes})",
                    }
                task["time"] = new_minutes
                changes.append({
                    "day": update_day,
                    "task_name": task.get("name", task_name),
                    "old_minutes": old_minutes,
                    "new_minutes": new_minutes,
                })
                matched = True
                break

        if not matched:
            missing[update_day] = _available_tasks(day_schedule)

    if not changes:
        return {
            "error": "Task Not Found",
            "task_name": task_name,
            "searched_days": days_to_update,
            "available_tasks": missing,
        }

    update_response = await _save_active_schedule(schedule)
    if isinstance(update_response, dict) and update_response.get("error"):
        return update_response

    return {
        "status": "success",
        "schedule_id": schedule["id"],
        "changes": changes,
        "missing_days": missing,
        "tracker_response": update_response,
    }

@mcp.tool()
async def get_rollover_tasks(day: Optional[str] = None) -> Any:
    """Get incomplete tasks from previous days that carry over. Optional day argument (e.g., 'monday')."""
    params = {"day": day} if day else None
    return await _make_request("GET", "/api/v1/schedule/active/rollover", params=params)

@mcp.tool()
async def get_task_plan(task_name: Optional[str] = None) -> Any:
    """Get the next recommended task based on assigned percentages and schedule priority."""
    params = {"task_name": task_name} if task_name else None
    return await _make_request("GET", "/api/v1/task/plan/percent/schedule", params=params)

@mcp.tool()
async def add_task_record(task_name: str, minutes: int, source_day: Optional[str] = None, manage_by_service: Optional[bool] = None) -> dict:
    """Record completion time for a specific task.
    
    Args:
        task_name: The exact name of the task
        minutes: Total number of minutes spent (must be > 0)
        source_day: Optional day name (e.g. "monday", "tuesday") to log the task under.
        manage_by_service: Optional flag to distribute time to past unfilled schedules.
    """
    if minutes <= 0:
        return {"error": "Minutes must be strictly positive"}
    
    payload = {
        "task_name": task_name,
        "time_done": minutes
    }
    if source_day:
        payload["source_day"] = source_day
    if manage_by_service is not None:
        payload["manage_by_service"] = manage_by_service
        
    return await _make_request("POST", "/api/v1/taskrecord", json_data=payload)

@mcp.tool()
async def get_rest() -> Any:
    """Get the amount of available rest time."""
    return await _make_request("GET", "/api/v1/rest/get")

@mcp.tool()
async def add_rest(minutes: int) -> dict:
    """Add accumulated rest time to the account.
    
    Args:
        minutes: Total minutes to add to the rest pool.
    """
    payload = {"minutes": minutes}
    return await _make_request("POST", "/api/v1/rest/add", json_data=payload)

@mcp.tool()
async def spend_rest(minutes: int) -> dict:
    """Spend rest time from the account.
    
    Args:
        minutes: Total minutes of rest to consume.
    """
    payload = {"minutes": minutes}
    return await _make_request("POST", "/api/v1/rest/spend", json_data=payload)

@mcp.tool()
async def get_timer() -> Any:
    """Get the currently active system timer."""
    return await _make_request("GET", "/api/v1/timer/get")

@mcp.tool()
async def set_timer(count: int, source_day: Optional[str] = None, current_task: Optional[str] = None) -> dict:
    """Set the system countdown timer.
    
    Args:
        count: Number of seconds for the timer.
        source_day: The origin day for rollover tasks (e.g., 'monday').
        current_task: The name of the task the timer is for.
    """
    payload = {"count": count}
    if source_day:
        payload["source_day"] = source_day
    if current_task:
        payload["current_task"] = current_task
        
    return await _make_request("POST", "/api/v1/timer/set", json_data=payload)

@mcp.tool()
async def start_task_timer(task_name: str, role: str = "", target_duration: int = 0, source_day: Optional[str] = None) -> dict:
    """Start a running task timer.
    
    Args:
        task_name: The name of the task to start.
        role: The role/group for the task (e.g. "work", "learn", "rest"). If empty, server defaults to existing role or "work".
        target_duration: Target duration in minutes (optional).
        source_day: The origin day for rollover tasks (e.g. 'monday') (optional).
    """
    payload = {
        "task_name": task_name,
        "role": role,
        "target_duration": target_duration,
        "source_day": source_day or ""
    }
    return await _make_request("POST", "/api/v1/timer/run/start", json_data=payload)

@mcp.tool()
async def stop_task_timer(task_name: Optional[str] = None) -> dict:
    """Stop a running task timer.
    
    Args:
        task_name: The name of the task to stop (optional). If empty, stops the active/first running task.
    """
    payload = {}
    if task_name:
        payload["task_name"] = task_name
    return await _make_request("POST", "/api/v1/timer/run/stop", json_data=payload)

@mcp.tool()
async def pause_task_timer(task_name: Optional[str] = None) -> dict:
    """Pause a running task timer.
    
    Args:
        task_name: The name of the task to pause (optional). If empty, pauses the active running task.
    """
    payload = {}
    if task_name:
        payload["task_name"] = task_name
    return await _make_request("POST", "/api/v1/timer/run/pause", json_data=payload)

@mcp.tool()
async def resume_task_timer(task_name: Optional[str] = None) -> dict:
    """Resume a paused task timer.
    
    Args:
        task_name: The name of the task to resume (optional). If empty, resumes the first paused task.
    """
    payload = {}
    if task_name:
        payload["task_name"] = task_name
    return await _make_request("POST", "/api/v1/timer/run/resume", json_data=payload)

@mcp.tool()
async def get_running_task_status(task_name: Optional[str] = None) -> dict:
    """Get the status of running/paused task timers.
    
    Args:
        task_name: The name of the task to check (optional). If empty, gets the active running task's status.
    """
    params = {}
    if task_name:
        params["task_name"] = task_name
    return await _make_request("GET", "/api/v1/timer/run/status", params=params)

@mcp.tool()
async def list_running_tasks() -> dict:
    """List all currently active and paused running tasks."""
    return await _make_request("GET", "/api/v1/timer/run/list")

@mcp.tool()
async def add_schedule_tasks(tasks: list[dict], day: str = "today") -> dict:
    """Add a list of tasks with specified times to the active weekly schedule.

    If a task already exists on a day, its time, role, and priority will be updated.
    Otherwise, the new task will be added. The total time for modified days will
    be automatically recalculated as the sum of all tasks' times.

    Args:
        tasks: A list of dicts, where each dict has:
               - "name": str (task name, e.g. "math")
               - "time": int (allocated time in minutes, e.g. 60)
               - "role": str ("work", "learn", "rest")
               - "priority": int (optional, default 1)
               - "percents": list[int] (optional, e.g. [100])
        day: "today", a weekday name like "monday", or "all" to add to all weekdays.
    """
    # Validation
    for i, t in enumerate(tasks):
        if not isinstance(t, dict):
            return {"error": f"Task at index {i} must be a dictionary"}
        if "name" not in t or not t["name"]:
            return {"error": f"Task at index {i} is missing 'name'"}
        if "time" not in t or not isinstance(t["time"], int) or t["time"] < 0:
            return {"error": f"Task at index {i} must have non-negative 'time'"}
        if "role" not in t or t["role"] not in ["work", "learn", "rest"]:
            return {"error": f"Task at index {i} must have 'role' of 'work', 'learn', or 'rest'"}

    try:
        normalized_day = _normalize_day(day)
    except ValueError as e:
        return {"error": "Invalid Day", "details": str(e)}

    schedule, error = await _get_active_schedule_data()
    if error:
        return error

    days_to_update = DAYS if normalized_day == "all" else [normalized_day]
    updated_days = []

    for update_day in days_to_update:
        day_schedule = schedule.get(update_day)
        if not isinstance(day_schedule, dict):
            day_schedule = {
                "day": update_day,
                "total_time": 0,
                "tasks": [],
                "plan_group": ["plan", "work", "learn", "rest"]
            }
            schedule[update_day] = day_schedule

        existing_tasks = day_schedule.setdefault("tasks", [])
        
        for task_def in tasks:
            name = task_def["name"].strip()
            role = task_def["role"]
            time_val = task_def["time"]
            priority = task_def.get("priority", 1)
            percents = task_def.get("percents")

            # Check if task already exists (case-insensitive name match)
            target = name.lower()
            matched = False
            for task in existing_tasks:
                if task.get("name", "").strip().lower() == target:
                    task["time"] = time_val
                    task["role"] = role
                    task["priority"] = priority
                    if percents is not None:
                        task["percents"] = percents
                    matched = True
                    break

            if not matched:
                new_task = {
                    "name": name,
                    "role": role,
                    "time": time_val,
                    "priority": priority
                }
                if percents is not None:
                    new_task["percents"] = percents
                existing_tasks.append(new_task)

        # Recalculate total_time
        day_schedule["total_time"] = sum(t.get("time", 0) for t in existing_tasks)
        updated_days.append(update_day)

    update_response = await _save_active_schedule(schedule)
    if isinstance(update_response, dict) and update_response.get("error"):
        return update_response

    return {
        "status": "success",
        "schedule_id": schedule["id"],
        "updated_days": updated_days,
        "tracker_response": update_response
    }

if __name__ == "__main__":
    import sys
    if "--help" in sys.argv:
        print("Tracker MCP Server")
        print("This server provides tools to interact with the Tracker API.")
        print("It uses the MCP (Model Context Protocol) over stdio.")
        print("\nEnvironment Variables:")
        print("  TRACKER_API_URL: URL of the tracker-server (default: http://localhost:3000)")
        sys.exit(0)
    
    # Ensure MCP Server always runs in stdio mode by default if executed directly
    mcp.run(transport="stdio")
