"""Turn stored schedule jobs into the shape the admin editor works with, and back."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Iterable

from .data_helpers import as_bool
from .schedule_runner import CronError, next_fire_time_utc, parse_cron
from .schedule_store import job_settings

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class ScheduleInputError(ValueError):
    """The editor sent a time or weekday list that cannot be turned into a cron."""


def build_cron(time_text: str, weekdays: Iterable[Any]) -> str:
    """'HH:MM' plus weekdays (0 = Sunday .. 6 = Saturday) as a cron; none or all means every day."""
    match = _TIME_RE.match(str(time_text or "").strip())
    if match is None:
        raise ScheduleInputError("time must look like 07:30")
    days: set[int] = set()
    for item in weekdays or []:
        try:
            day = int(item)
        except (TypeError, ValueError) as exc:
            raise ScheduleInputError(f"weekday must be 0-6, got {item!r}") from exc
        if not 0 <= day <= 6:
            raise ScheduleInputError(f"weekday must be 0-6, got {item!r}")
        days.add(day)
    dow = "*" if not days or len(days) == 7 else ",".join(str(day) for day in sorted(days))
    return f"{int(match.group(2))} {int(match.group(1))} * * {dow}"


def job_view(
    job: dict[str, Any],
    *,
    default_timezone: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """One job as the editor shows it.

    ``simple`` is False for crons the editor can't represent (several times a day,
    or restricted to a date); those are listed read-only so they aren't mangled.
    """
    cron = str(job.get("cron") or "")
    time_text: str | None = None
    weekdays: list[int] | None = None
    simple = False
    try:
        spec = parse_cron(cron)
    except CronError:
        spec = None
    if spec is not None and len(spec.minutes) == 1 and len(spec.hours) == 1:
        if not spec.dom_restricted and len(spec.months) == 12:
            simple = True
            time_text = f"{spec.hours[0]:02d}:{spec.minutes[0]:02d}"
            weekdays = sorted(spec.days_of_week) if len(spec.days_of_week) < 7 else []
    upcoming = next_fire_time_utc(job, default_timezone=default_timezone, now=now)
    return {
        "id": job.get("id"),
        "enabled": as_bool(job.get("enabled", True), True),
        "repeated": as_bool(job.get("repeated", True), True),
        "cron": cron,
        "time": time_text,
        "weekdays": weekdays,
        "simple": simple,
        "time_zone": str(job.get("timeZoneId") or ""),
        "next_fire_time": upcoming.strftime("%Y-%m-%dT%H:%M:%SZ") if upcoming is not None else None,
        "settings": job_settings(job),
    }
