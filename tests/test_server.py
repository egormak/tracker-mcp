import pytest
from unittest.mock import patch, AsyncMock
import server

@pytest.mark.asyncio
async def test_adjust_running_task_timer():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success", "data": {"task_name": "coding", "target_duration": 30}}
        res = await server.adjust_running_task_timer("coding", 5)
        assert res["status"] == "success"
        mock_req.assert_called_once_with("POST", "/api/v1/timer/run/adjust", json_data={"task_name": "coding", "delta_minutes": 5})

@pytest.mark.asyncio
async def test_get_evening_focus_task():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {
            "status": "success",
            "data": {
                "current_task": {"task_name": "duolingo", "weekly_gap": 60},
                "candidates": [{"task_name": "duolingo"}],
                "sprint_time": 20,
                "rest_pool": 15
            }
        }
        res = await server.get_evening_focus_task(category="learn", sprint_time=20)
        assert res["status"] == "success"
        mock_req.assert_called_once_with("GET", "/api/v1/mode/evening-focus", params={"category": "learn", "time": 20})

@pytest.mark.asyncio
async def test_skip_evening_focus_task():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success"}
        res = await server.skip_evening_focus_task("duolingo")
        assert res["status"] == "success"
        mock_req.assert_called_once_with("POST", "/api/v1/mode/evening-focus/skip", json_data={"task_name": "duolingo"}, params={})

@pytest.mark.asyncio
async def test_get_weekly_stats():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success", "days": []}
        res = await server.get_weekly_stats()
        assert res["status"] == "success"
        mock_req.assert_called_once_with("GET", "/api/v1/stats/weekly")

@pytest.mark.asyncio
async def test_rotate_plan_percent():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "accept"}
        res = await server.rotate_plan_percent()
        assert res["status"] == "accept"
        mock_req.assert_called_once_with("POST", "/api/v1/task/plan/rotate")

@pytest.mark.asyncio
async def test_set_schedule_task_time():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success", "data": {"id": "sched-1"}}
        res = await server.set_schedule_task_time("work", 60, day="today")
        assert res["status"] == "success"
        mock_req.assert_called_once_with(
            "PATCH",
            "/api/v1/schedule/active/task-time",
            json_data={"task_name": "work", "minutes": 60, "day": "today"},
        )

@pytest.mark.asyncio
async def test_set_schedule_task_time_default_day():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success", "data": {"id": "sched-1"}}
        res = await server.set_schedule_task_time("work", 60)
        assert res["status"] == "success"
        mock_req.assert_called_once_with(
            "PATCH",
            "/api/v1/schedule/active/task-time",
            json_data={"task_name": "work", "minutes": 60, "day": "today"},
        )

@pytest.mark.asyncio
async def test_set_schedule_task_time_custom_day():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success", "data": {"id": "sched-1"}}
        res = await server.set_schedule_task_time("video", 30, day="monday")
        assert res["status"] == "success"
        mock_req.assert_called_once_with(
            "PATCH",
            "/api/v1/schedule/active/task-time",
            json_data={"task_name": "video", "minutes": 30, "day": "monday"},
        )

@pytest.mark.asyncio
async def test_set_schedule_task_time_every_day_normalizes_to_all():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success", "data": {"id": "sched-1"}}
        res = await server.set_schedule_task_time("work", 60, day="every day")
        assert res["status"] == "success"
        mock_req.assert_called_once_with(
            "PATCH",
            "/api/v1/schedule/active/task-time",
            json_data={"task_name": "work", "minutes": 60, "day": "all"},
        )

@pytest.mark.asyncio
async def test_set_schedule_task_time_invalid_day():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        res = await server.set_schedule_task_time("work", 60, day="invalid-day")
        assert "error" in res
        assert "Invalid day 'invalid-day'" in res["error"]
        mock_req.assert_not_called()

@pytest.mark.asyncio
async def test_adjust_schedule_task_time():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success", "data": {"id": "sched-1"}}
        res = await server.adjust_schedule_task_time("work", 15, day="today")
        assert res["status"] == "success"
        mock_req.assert_called_once_with(
            "PATCH",
            "/api/v1/schedule/active/task-time",
            json_data={"task_name": "work", "delta_minutes": 15, "day": "today"},
        )

@pytest.mark.asyncio
async def test_adjust_schedule_task_time_default_day():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success", "data": {"id": "sched-1"}}
        res = await server.adjust_schedule_task_time("work", 15)
        assert res["status"] == "success"
        mock_req.assert_called_once_with(
            "PATCH",
            "/api/v1/schedule/active/task-time",
            json_data={"task_name": "work", "delta_minutes": 15, "day": "today"},
        )

@pytest.mark.asyncio
async def test_adjust_schedule_task_time_custom_day():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success", "data": {"id": "sched-1"}}
        res = await server.adjust_schedule_task_time("coding", -10, day="all")
        assert res["status"] == "success"
        mock_req.assert_called_once_with(
            "PATCH",
            "/api/v1/schedule/active/task-time",
            json_data={"task_name": "coding", "delta_minutes": -10, "day": "all"},
        )

@pytest.mark.asyncio
async def test_adjust_schedule_task_time_every_day_normalizes_to_all():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "success", "data": {"id": "sched-1"}}
        res = await server.adjust_schedule_task_time("work", 15, day="every day")
        assert res["status"] == "success"
        mock_req.assert_called_once_with(
            "PATCH",
            "/api/v1/schedule/active/task-time",
            json_data={"task_name": "work", "delta_minutes": 15, "day": "all"},
        )

@pytest.mark.asyncio
async def test_adjust_schedule_task_time_invalid_day():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        res = await server.adjust_schedule_task_time("work", 15, day="invalid-day")
        assert "error" in res
        assert "Invalid day 'invalid-day'" in res["error"]
        mock_req.assert_not_called()

def test_resolve_target_days():
    assert server._resolve_target_days("week") == server.DAYS
    assert server._resolve_target_days("all") == server.DAYS
    assert server._resolve_target_days("weekdays") == server.WEEKDAYS
    assert server._resolve_target_days("workdays") == server.WEEKDAYS
    assert server._resolve_target_days("weekends") == server.WEEKENDS
    assert server._resolve_target_days("weekend") == server.WEEKENDS
    assert server._resolve_target_days("today") == [server._today_name()]
    assert server._resolve_target_days("monday") == ["monday"]
    assert server._resolve_target_days("invalid_scope") == []

@pytest.mark.asyncio
async def test_suggest_daily_schedule_invalid_scope():
    res = await server.suggest_daily_schedule(target_scope="invalid-foo")
    assert "error" in res
    assert "Invalid target_scope" in res["error"]

@pytest.mark.asyncio
async def test_suggest_daily_schedule_fetch_error():
    with patch("server._make_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"error": "HTTP 500", "details": "Server error"}
        res = await server.suggest_daily_schedule(target_scope="monday")
        assert "error" in res

@pytest.mark.asyncio
async def test_suggest_daily_schedule_preview_weekdays():
    sample_schedule = {
        "id": "sched-123",
        "monday": {
            "day": "monday",
            "tasks": [
                {"name": "work", "role": "work", "time": 60},
                {"name": "english", "role": "learn", "time": 10},
                {"name": "video", "role": "rest", "time": 5},
                {"name": "home_task", "role": "work", "time": 20},
                {"name": "guitar", "role": "rest", "time": 15},  # Custom task, should stay untouched
            ]
        },
        "saturday": {
            "day": "saturday",
            "tasks": [
                {"name": "work", "role": "work", "time": 120},
                {"name": "home_task", "role": "work", "time": 15},
                {"name": "games", "role": "rest", "time": 10},
            ]
        }
    }

    async def mock_make_req(method, endpoint, json_data=None, params=None):
        if endpoint == "/api/v1/schedule/active":
            return {"status": "success", "data": sample_schedule}
        if endpoint == "/api/v1/schedule/active/rollover":
            return {"status": "success", "data": {"rollover_tasks": [{"task_name": "work", "remaining_time": 30}]}}
        return {"status": "success"}

    with patch("server._make_request", side_effect=mock_make_req) as mock_req:
        res = await server.suggest_daily_schedule(target_scope="monday", apply=False)
        assert res["status"] == "success"
        assert res["applied"] is False
        assert res["summary"]["days_analyzed"] == 1
        assert res["summary"]["total_changes_suggested"] == 4

        # Changes for Monday:
        mon_changes = {c["task_name"]: c for c in res["daily_suggestions"][0]["changes"]}
        assert mon_changes["work"]["suggested_minutes"] == 270
        assert mon_changes["work"]["delta_minutes"] == 210
        assert mon_changes["english"]["suggested_minutes"] == 20
        assert mon_changes["english"]["delta_minutes"] == 10
        assert mon_changes["video"]["suggested_minutes"] == 30
        assert mon_changes["video"]["delta_minutes"] == 25
        assert mon_changes["home_task"]["suggested_minutes"] == 0
        assert mon_changes["home_task"]["delta_minutes"] == -20

        # Guitar is not in changes
        assert "guitar" not in mon_changes

        # Rollovers surfaced
        assert len(res["rollovers_detected"]) == 1
        assert res["rollovers_detected"][0]["task_name"] == "work"

@pytest.mark.asyncio
async def test_suggest_daily_schedule_preview_weekends():
    sample_schedule = {
        "id": "sched-123",
        "saturday": {
            "day": "saturday",
            "tasks": [
                {"name": "work", "role": "work", "time": 120},
                {"name": "home_task", "role": "work", "time": 15},
                {"name": "games", "role": "rest", "time": 10},
                {"name": "movies", "role": "rest", "time": 60},  # Weekend leisure >= 30, keep as is
            ]
        }
    }

    async def mock_make_req(method, endpoint, json_data=None, params=None):
        if endpoint == "/api/v1/schedule/active":
            return {"status": "success", "data": sample_schedule}
        if endpoint == "/api/v1/schedule/active/rollover":
            return {"status": "success", "data": {"rollover_tasks": []}}
        return {"status": "success"}

    with patch("server._make_request", side_effect=mock_make_req):
        res = await server.suggest_daily_schedule(target_scope="saturday", apply=False)
        assert res["status"] == "success"
        sat_changes = {c["task_name"]: c for c in res["daily_suggestions"][0]["changes"]}
        assert sat_changes["work"]["suggested_minutes"] == 0
        assert sat_changes["work"]["delta_minutes"] == -120
        assert sat_changes["home_task"]["suggested_minutes"] == 60
        assert sat_changes["home_task"]["delta_minutes"] == 45
        assert sat_changes["games"]["suggested_minutes"] == 30
        assert sat_changes["games"]["delta_minutes"] == 20
        assert "movies" not in sat_changes  # 60 >= 30, not changed

@pytest.mark.asyncio
async def test_suggest_daily_schedule_apply_mode():
    sample_schedule = {
        "id": "sched-123",
        "monday": {
            "day": "monday",
            "tasks": [
                {"name": "work", "role": "work", "time": 200},
                {"name": "video", "role": "rest", "time": 10},
            ]
        }
    }

    patch_calls = []

    async def mock_make_req(method, endpoint, json_data=None, params=None):
        if endpoint == "/api/v1/schedule/active":
            return {"status": "success", "data": sample_schedule}
        if endpoint == "/api/v1/schedule/active/rollover":
            return {"status": "success", "data": {"rollover_tasks": []}}
        if method == "PATCH" and endpoint == "/api/v1/schedule/active/task-time":
            patch_calls.append(json_data)
            return {"status": "success", "data": {"id": "sched-123"}}
        return {"status": "success"}

    with patch("server._make_request", side_effect=mock_make_req):
        res = await server.suggest_daily_schedule(target_scope="monday", apply=True)
        assert res["status"] == "success"
        assert res["applied"] is True
        assert res["applied_count"] == 2
        assert len(res["errors"]) == 0

        # Verify PATCH calls made
        assert {"task_name": "work", "minutes": 270, "day": "monday"} in patch_calls
        assert {"task_name": "video", "minutes": 30, "day": "monday"} in patch_calls

@pytest.mark.asyncio
async def test_suggest_daily_schedule_already_balanced():
    sample_schedule = {
        "id": "sched-123",
        "monday": {
            "day": "monday",
            "tasks": [
                {"name": "work", "role": "work", "time": 270},
                {"name": "english", "role": "learn", "time": 20},
                {"name": "video", "role": "rest", "time": 30},
                {"name": "games", "role": "rest", "time": 30},
                {"name": "movies", "role": "rest", "time": 30},
                {"name": "telegram", "role": "rest", "time": 30},
                {"name": "home_task", "role": "work", "time": 0},
            ]
        }
    }

    async def mock_make_req(method, endpoint, json_data=None, params=None):
        if endpoint == "/api/v1/schedule/active":
            return {"status": "success", "data": sample_schedule}
        if endpoint == "/api/v1/schedule/active/rollover":
            return {"status": "success", "data": {"rollover_tasks": []}}
        return {"status": "success"}

    with patch("server._make_request", side_effect=mock_make_req):
        res = await server.suggest_daily_schedule(target_scope="monday", apply=False)
        assert res["status"] == "success"
        assert res["summary"]["total_changes_suggested"] == 0
        assert "already balanced" in res["message"]

@pytest.mark.asyncio
async def test_suggest_daily_schedule_scope_weekdays_filters_days():
    days_data = {
        day: {
            "day": day,
            "tasks": [{"name": "work", "role": "work", "time": 100}]
        }
        for day in server.DAYS
    }
    sample_schedule = {"id": "sched-all", **days_data}

    async def mock_make_req(method, endpoint, json_data=None, params=None):
        if endpoint == "/api/v1/schedule/active":
            return {"status": "success", "data": sample_schedule}
        if endpoint == "/api/v1/schedule/active/rollover":
            return {"status": "success", "data": {"rollover_tasks": []}}
        return {"status": "success"}

    with patch("server._make_request", side_effect=mock_make_req):
        res = await server.suggest_daily_schedule(target_scope="weekdays", apply=False)
        assert res["status"] == "success"
        assert res["summary"]["days_analyzed"] == 5
        analyzed_days = [d["day"] for d in res["daily_suggestions"]]
        assert analyzed_days == server.WEEKDAYS
        assert "saturday" not in analyzed_days
        assert "sunday" not in analyzed_days


