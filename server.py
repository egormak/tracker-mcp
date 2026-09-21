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
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
WEEKENDS = ["saturday", "sunday"]
DEFAULT_BACKGROUND_TASKS = ["video", "games", "movies", "telegram"]

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
            elif method == "PATCH":
                response = await client.patch(url, json=json_data, headers=headers)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers)
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

def _normalize_day(day: Optional[str]) -> Optional[str]:
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

    if normalized in DAYS or normalized in ("today", "all"):
        return normalized
    return None

def _resolve_target_days(scope: Optional[str]) -> list[str]:
    """Resolve target scope to a list of weekday names."""
    if not scope:
        return DAYS

    normalized = scope.strip().lower().replace("-", " ").replace("_", " ")
    if normalized in ("all", "week", "weekly", "every day", "everyday", "daily"):
        return DAYS
    if normalized in ("weekdays", "weekday", "workdays", "workday", "working days"):
        return WEEKDAYS
    if normalized in ("weekends", "weekend"):
        return WEEKENDS
    if normalized in ("today", "tod"):
        return [_today_name()]
    if normalized in DAYS:
        return [normalized]
    return []

def _schedule_request_from_active(schedule: dict) -> dict:
    """Build the update payload expected by PUT /api/v1/schedule/:id."""
    return {day: schedule[day] for day in DAYS}

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
        day: Target day: 'today', 'all', or a weekday name (e.g. 'monday'). Defaults to 'today'.
    """
    normalized_day = _normalize_day(day)
    if not normalized_day:
        return {"error": f"Invalid day '{day}'. Supported: today, all, or weekday name (e.g. monday)"}

    payload = {"task_name": task_name, "minutes": minutes, "day": normalized_day}
    return await _make_request("PATCH", "/api/v1/schedule/active/task-time", json_data=payload)

@mcp.tool()
async def adjust_schedule_task_time(task_name: str, delta_minutes: int, day: str = "today") -> dict:
    """Increase or decrease an existing task's scheduled minutes.

    Args:
        task_name: Existing schedule task name, matched case-insensitively.
        delta_minutes: Minutes to add or subtract, for example 10 or -15.
        day: Target day: 'today', 'all', or a weekday name (e.g. 'monday'). Defaults to 'today'.
    """
    normalized_day = _normalize_day(day)
    if not normalized_day:
        return {"error": f"Invalid day '{day}'. Supported: today, all, or weekday name (e.g. monday)"}

    payload = {"task_name": task_name, "delta_minutes": delta_minutes, "day": normalized_day}
    return await _make_request("PATCH", "/api/v1/schedule/active/task-time", json_data=payload)

@mcp.tool()
async def suggest_daily_schedule(
    target_scope: str = "week",
    background_tasks: Optional[list[str]] = None,
    background_minutes: int = 30,
    work_minutes: int = 270,
    english_minutes: int = 20,
    home_task_weekend_minutes: int = 60,
    apply: bool = False,
) -> dict:
    """Analyze and balance weekly or daily schedule according to workflow heuristics.

    Evaluates the active schedule against user routine rules:
    - Weekdays (Mon-Fri): Work (default 270m), English (default 20m), Background smoothing slots (default 30m each for video, games, movies, telegram), and Home task (0m, shifted to weekend).
    - Weekends (Sat-Sun): Work (0m, day off), Home task focus (default 60m), Background activities (30m min).
    - Rollover deficit inspection: Surfaces carryover deficits from previous days.

    Args:
        target_scope: Scope of days to balance: 'week' (or 'all'), 'weekdays', 'weekends', 'today', or a specific day (e.g. 'monday'). Defaults to 'week'.
        background_tasks: Optional list of background task names to smooth. Defaults to ['video', 'games', 'movies', 'telegram'].
        background_minutes: Target minutes for weekday background tasks (default 30).
        work_minutes: Target minutes for weekday work (default 270).
        english_minutes: Target minutes for english practice (default 20).
        home_task_weekend_minutes: Target minutes for weekend home tasks (default 60).
        apply: If False (default), returns preview of suggestions and diffs. If True, executes atomic updates to the active schedule.
    """
    days_to_analyze = _resolve_target_days(target_scope)
    if not days_to_analyze:
        return {
            "error": "Invalid target_scope",
            "details": f"Unknown target scope '{target_scope}'. Supported: week, all, weekdays, weekends, today, or weekday name."
        }

    bg_tasks = [t.strip().lower() for t in (background_tasks if background_tasks is not None else DEFAULT_BACKGROUND_TASKS)]

    schedule, error = await _get_active_schedule_data()
    if error:
        return error

    rollover_resp = await _make_request("GET", "/api/v1/schedule/active/rollover")
    rollovers_detected = []
    if isinstance(rollover_resp, dict) and rollover_resp.get("status") == "success":
        rdata = rollover_resp.get("data", {})
        if isinstance(rdata, dict):
            rollovers_detected = rdata.get("rollover_tasks", [])

    daily_suggestions = []
    all_changes = []
    total_minutes_before = 0
    total_minutes_after = 0

    for day in days_to_analyze:
        day_schedule = schedule.get(day)
        if not isinstance(day_schedule, dict):
            continue

        tasks = day_schedule.get("tasks", [])
        current_day_total = sum(t.get("time", 0) for t in tasks)
        total_minutes_before += current_day_total

        is_weekday = day in WEEKDAYS
        is_weekend = day in WEEKENDS

        day_changes = []
        new_tasks_time_map = {}

        # Map existing tasks by lowercase name
        task_map = {}
        for t in tasks:
            tname = t.get("name", "").strip().lower()
            task_map[tname] = t
            new_tasks_time_map[tname] = t.get("time", 0)

        # 1. Work heuristic
        if "work" in task_map:
            current_time = task_map["work"].get("time", 0)
            target_time = work_minutes if is_weekday else 0
            if current_time != target_time:
                reason = f"Standard weekday work obligation ({work_minutes}m)" if is_weekday else "Weekend day off for work (0m)"
                change = {
                    "day": day,
                    "task_name": task_map["work"].get("name", "work"),
                    "current_minutes": current_time,
                    "suggested_minutes": target_time,
                    "delta_minutes": target_time - current_time,
                    "reason": reason,
                }
                day_changes.append(change)
                all_changes.append(change)
                new_tasks_time_map["work"] = target_time

        # 2. English heuristic
        if "english" in task_map:
            current_time = task_map["english"].get("time", 0)
            target_time = english_minutes
            if current_time != target_time:
                change = {
                    "day": day,
                    "task_name": task_map["english"].get("name", "english"),
                    "current_minutes": current_time,
                    "suggested_minutes": target_time,
                    "delta_minutes": target_time - current_time,
                    "reason": f"Daily english practice target ({english_minutes}m)",
                }
                day_changes.append(change)
                all_changes.append(change)
                new_tasks_time_map["english"] = target_time

        # 3. Background tasks smoothing heuristic
        for bg in bg_tasks:
            if bg in task_map:
                current_time = task_map[bg].get("time", 0)
                if is_weekday:
                    target_time = background_minutes
                    if current_time != target_time:
                        change = {
                            "day": day,
                            "task_name": task_map[bg].get("name", bg),
                            "current_minutes": current_time,
                            "suggested_minutes": target_time,
                            "delta_minutes": target_time - current_time,
                            "reason": f"Weekday background smoothing slot ({background_minutes}m)",
                        }
                        day_changes.append(change)
                        all_changes.append(change)
                        new_tasks_time_map[bg] = target_time
                elif is_weekend:
                    if current_time < background_minutes:
                        target_time = background_minutes
                        change = {
                            "day": day,
                            "task_name": task_map[bg].get("name", bg),
                            "current_minutes": current_time,
                            "suggested_minutes": target_time,
                            "delta_minutes": target_time - current_time,
                            "reason": f"Weekend background activity minimum ({background_minutes}m)",
                        }
                        day_changes.append(change)
                        all_changes.append(change)
                        new_tasks_time_map[bg] = target_time

        # 4. Home task heuristic
        if "home_task" in task_map:
            current_time = task_map["home_task"].get("time", 0)
            if is_weekday:
                target_time = 0
                if current_time != target_time:
                    change = {
                        "day": day,
                        "task_name": task_map["home_task"].get("name", "home_task"),
                        "current_minutes": current_time,
                        "suggested_minutes": target_time,
                        "delta_minutes": target_time - current_time,
                        "reason": "Weekday home_task shifted to weekend focus (0m)",
                    }
                    day_changes.append(change)
                    all_changes.append(change)
                    new_tasks_time_map["home_task"] = target_time
            elif is_weekend:
                target_time = home_task_weekend_minutes
                if current_time != target_time:
                    change = {
                        "day": day,
                        "task_name": task_map["home_task"].get("name", "home_task"),
                        "current_minutes": current_time,
                        "suggested_minutes": target_time,
                        "delta_minutes": target_time - current_time,
                        "reason": f"Weekend home_task focus block ({home_task_weekend_minutes}m)",
                    }
                    day_changes.append(change)
                    all_changes.append(change)
                    new_tasks_time_map["home_task"] = target_time

        suggested_day_total = sum(new_tasks_time_map.values())
        total_minutes_after += suggested_day_total

        daily_suggestions.append({
            "day": day,
            "total_time_current": current_day_total,
            "total_time_suggested": suggested_day_total,
            "changes_count": len(day_changes),
            "changes": day_changes,
        })

    summary = {
        "days_analyzed": len(days_to_analyze),
        "total_changes_suggested": len(all_changes),
        "total_minutes_before": total_minutes_before,
        "total_minutes_after": total_minutes_after,
        "delta_minutes": total_minutes_after - total_minutes_before,
    }

    if not apply:
        msg = f"Generated {len(all_changes)} schedule adjustment suggestions across {len(days_to_analyze)} days. Run with apply=True to apply them directly to the active schedule." if all_changes else "Schedule is already balanced according to the specified heuristics."
        return {
            "status": "success",
            "applied": False,
            "target_scope": target_scope,
            "summary": summary,
            "rollovers_detected": rollovers_detected,
            "daily_suggestions": daily_suggestions,
            "message": msg
        }

    applied_changes = []
    errors = []

    for change in all_changes:
        day = change["day"]
        task_name = change["task_name"]
        minutes = change["suggested_minutes"]

        patch_res = await set_schedule_task_time(task_name=task_name, minutes=minutes, day=day)
        if isinstance(patch_res, dict) and patch_res.get("error"):
            errors.append({
                "day": day,
                "task_name": task_name,
                "error": patch_res.get("error"),
                "details": patch_res.get("details")
            })
        else:
            applied_changes.append({
                "day": day,
                "task_name": task_name,
                "new_minutes": minutes
            })

    if not all_changes:
        msg = "Schedule is already balanced according to the specified heuristics. No changes needed."
    elif not errors:
        msg = f"Successfully applied {len(applied_changes)} schedule adjustments across {len(days_to_analyze)} days."
    else:
        msg = f"Applied {len(applied_changes)} adjustments with {len(errors)} errors."

    return {
        "status": "success" if not errors else ("partial" if applied_changes else "error"),
        "applied": True,
        "applied_count": len(applied_changes),
        "errors_count": len(errors),
        "errors": errors,
        "target_scope": target_scope,
        "summary": summary,
        "rollovers_detected": rollovers_detected,
        "applied_changes": applied_changes,
        "daily_suggestions": daily_suggestions,
        "message": msg
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

    normalized_day = _normalize_day(day)
    if not normalized_day:
        return {"error": "Invalid Day", "details": f"Invalid day '{day}'. Supported: today, all, or weekday name (e.g. monday)"}

    target_day = _today_name() if normalized_day == "today" else normalized_day
    schedule, error = await _get_active_schedule_data()
    if error:
        return error

    days_to_update = DAYS if target_day == "all" else [target_day]
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

@mcp.tool()
async def adjust_running_task_timer(task_name: str, delta_minutes: int) -> dict:
    """Adjust the target duration of an active running task timer (+/- minutes).

    Args:
        task_name: The name of the task to adjust.
        delta_minutes: Minutes to add or subtract (e.g. 5, 10, -5).
    """
    payload = {"task_name": task_name, "delta_minutes": delta_minutes}
    return await _make_request("POST", "/api/v1/timer/run/adjust", json_data=payload)

@mcp.tool()
async def get_weekly_stats() -> dict:
    """Get the full weekly completion statistics with per-day breakdowns and role totals."""
    return await _make_request("GET", "/api/v1/stats/weekly")

@mcp.tool()
async def get_evening_focus_task(category: Optional[str] = None, sprint_time: Optional[int] = None) -> dict:
    """Get the current recommended focus task candidate for evening catch-up mode.

    Args:
        category: Optional category filter (e.g., 'learn' or 'rest').
        sprint_time: Optional micro-sprint time in minutes (default 20).
    """
    params = {}
    if category:
        params["category"] = category
    if sprint_time:
        params["time"] = sprint_time
    return await _make_request("GET", "/api/v1/mode/evening-focus", params=params)

@mcp.tool()
async def skip_evening_focus_task(task_name: str, category: Optional[str] = None, sprint_time: Optional[int] = None) -> dict:
    """Skip the current evening candidate task and fetch the next candidate.

    Args:
        task_name: The task to snooze/skip for tonight.
        category: Optional category filter.
        sprint_time: Optional micro-sprint time in minutes.
    """
    params = {}
    if category:
        params["category"] = category
    if sprint_time:
        params["time"] = sprint_time
    payload = {"task_name": task_name}
    return await _make_request("POST", "/api/v1/mode/evening-focus/skip", json_data=payload, params=params)

@mcp.tool()
async def rotate_plan_percent() -> dict:
    """Rotate the current active plan percent group to the next configured group."""
    return await _make_request("POST", "/api/v1/task/plan/rotate")

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
