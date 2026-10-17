"""Scheduling wall-time policy tested without a database."""

import os
import subprocess
import sys
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from careflow.scheduling import ScheduleWindow, intervals, local_instant, validate_range


def test_karachi_weekday_midnight_and_effective_dates_roundtrip() -> None:
    window = ScheduleWindow(
        weekday=5,
        local_start=time(0),
        local_end=time(1),
        effective_from=date(2026, 10, 17),
        effective_to=date(2026, 10, 17),
    )
    assert intervals(window, now=datetime(2026, 10, 16, 19, 15, tzinfo=UTC)) == [
        (
            datetime(2026, 10, 16, 19, 30, tzinfo=UTC),
            datetime(2026, 10, 16, 20, tzinfo=UTC),
        )
    ]


@pytest.mark.parametrize(
    "start,end",
    [
        (datetime(2026, 10, 17), datetime(2026, 10, 18, tzinfo=UTC)),
        (datetime(2026, 10, 17, tzinfo=UTC), datetime(2026, 10, 17, tzinfo=UTC)),
        (datetime(2026, 10, 16, 18, tzinfo=UTC), datetime(2026, 10, 17, tzinfo=UTC)),
        (datetime(2026, 10, 17, tzinfo=UTC), datetime(2026, 11, 15, 19, 1, tzinfo=UTC)),
    ],
)
def test_invalid_query_ranges_are_rejected(start: datetime, end: datetime) -> None:
    with pytest.raises(ValueError):
        validate_range(start, end, now=datetime(2026, 10, 17, tzinfo=UTC))


def test_horizon_is_local_calendar_days_and_end_is_exclusive() -> None:
    now = datetime(2026, 10, 16, 19, tzinfo=UTC)
    validate_range(now, datetime(2026, 11, 15, 19, tzinfo=UTC), now=now)
    window = ScheduleWindow(
        weekday=0,
        local_start=time(0),
        local_end=time(0, 30),
        effective_from=date(2026, 11, 16),
        effective_to=date(2026, 11, 16),
    )
    assert intervals(window, now=now) == []


@pytest.mark.parametrize(
    "day,wall", [(date(2026, 3, 8), time(2, 30)), (date(2026, 11, 1), time(1, 30))]
)
def test_nonexistent_and_ambiguous_wall_times_fail(day: date, wall: time) -> None:
    with pytest.raises(ValueError):
        local_instant(day, wall, ZoneInfo("America/New_York"))


@pytest.mark.parametrize(
    "changes",
    [
        {"weekday": 7},
        {"local_start": "23:00", "local_end": "01:00"},
        {"local_start": "09:00+05:00"},
        {"local_end": "09:45"},
        {"effective_to": "2026-10-16"},
        {"local_start": "09:00:01"},
    ],
)
def test_invalid_schedule_windows_fail(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ScheduleWindow.model_validate(
            {
                "weekday": 5,
                "local_start": "09:00",
                "local_end": "10:00",
                "effective_from": "2026-10-17",
                "effective_to": "2026-10-17",
                **changes,
            }
        )


def test_operator_cli_refuses_unconfirmed_writes_safely() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "careflow.schedule_operator",
            "generate",
            "--doctor-id",
            "00000000-0000-4000-8000-000000000201",
        ],
        env={
            **os.environ,
            "DATABASE_URL": "postgresql+psycopg://operator:secret-sentinel@127.0.0.1/careflow_demo",
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "confirmation" in result.stderr
    assert "secret-sentinel" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://localhost/production",
        "postgresql+psycopg://outside.example.invalid/careflow_demo",
        "postgresql+psycopg://localhost/careflow_demo?host=outside.example.invalid",
    ],
)
def test_operator_refuses_unsafe_targets(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uuid import UUID

    from careflow.schedule_operator import run_operation

    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(ValueError):
        run_operation("generate", UUID(int=201), {}, confirmed=True)


def test_same_day_window_can_end_at_exclusive_midnight() -> None:
    window = ScheduleWindow.model_validate(
        {
            "weekday": 5,
            "local_start": "23:30",
            "local_end": "24:00",
            "effective_from": "2026-10-17",
            "effective_to": "2026-10-17",
        }
    )
    assert intervals(window, now=datetime(2026, 10, 17, tzinfo=UTC)) == [
        (
            datetime(2026, 10, 17, 18, 30, tzinfo=UTC),
            datetime(2026, 10, 17, 19, tzinfo=UTC),
        )
    ]
