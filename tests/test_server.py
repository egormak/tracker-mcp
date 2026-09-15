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
