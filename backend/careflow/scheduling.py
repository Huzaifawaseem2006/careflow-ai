"""Karachi calendar policy and deterministic capacity-one intervals."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ZONE = ZoneInfo("Asia/Karachi")
DURATION = timedelta(minutes=30)


def explicit_timestamp(value: object) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Explicit ISO timestamp with UTC offset required")
    return value


def local_instant(day: date, wall_time: time, zone: ZoneInfo = ZONE) -> datetime:
    naive = datetime.combine(day, wall_time)
    candidates = {
        naive.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        for fold in (0, 1)
        if naive.replace(tzinfo=zone, fold=fold)
        .astimezone(UTC)
        .astimezone(zone)
        .replace(tzinfo=None)
        == naive
    }
    if len(candidates) != 1:
        raise ValueError("Ambiguous or nonexistent local time")
    return candidates.pop()


def horizon(now: datetime) -> tuple[datetime, datetime]:
    if now.utcoffset() is None:
        raise ValueError("Offset-aware time required")
    today = now.astimezone(ZONE).date()
    return local_instant(today, time()), local_instant(
        today + timedelta(days=30), time()
    )


def validate_range(start: datetime, end: datetime, *, now: datetime) -> None:
    lower, upper = horizon(now)
    if (
        start.utcoffset() is None
        or end.utcoffset() is None
        or not lower <= start < end <= upper
    ):
        raise ValueError("Invalid availability range")


class ScheduleWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weekday: int = Field(ge=0, le=6)
    local_start: time
    local_end: time | Literal["24:00"]
    effective_from: date
    effective_to: date

    @field_validator("local_end", mode="before")
    @classmethod
    def midnight_end(cls, value: object) -> object:
        return "24:00" if value == "24:00:00" else value

    @model_validator(mode="after")
    def valid_window(self) -> "ScheduleWindow":
        if (
            self.local_start.tzinfo is not None
            or self.effective_from > self.effective_to
            or self.local_start.second
            or self.local_start.microsecond
            or (
                isinstance(self.local_end, time)
                and (
                    self.local_end.tzinfo is not None
                    or self.local_end.second
                    or self.local_end.microsecond
                )
            )
        ):
            raise ValueError("Invalid same-day schedule")
        start = datetime.combine(date.min, self.local_start)
        end = (
            datetime.combine(date.min + timedelta(days=1), time())
            if self.local_end == "24:00"
            else datetime.combine(date.min, self.local_end)
        )
        if start >= end or (end - start) % DURATION:
            raise ValueError("Schedule must contain whole 30-minute slots")
        return self


def intervals(
    window: ScheduleWindow, *, now: datetime
) -> list[tuple[datetime, datetime]]:
    start, end = horizon(now)
    day = max(start.astimezone(ZONE).date(), window.effective_from)
    last = min((end.astimezone(ZONE) - timedelta(days=1)).date(), window.effective_to)
    result = []
    while day <= last:
        if day.weekday() == window.weekday:
            cursor = local_instant(day, window.local_start)
            stop = (
                local_instant(day + timedelta(days=1), time())
                if window.local_end == "24:00"
                else local_instant(day, window.local_end)
            )
            while cursor + DURATION <= stop:
                if cursor >= now:
                    result.append((cursor, cursor + DURATION))
                cursor += DURATION
        day += timedelta(days=1)
    return result
