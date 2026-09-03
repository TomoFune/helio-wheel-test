"""Resolve a local birth date/time + location into an absolute instant.

Uses the IANA tz database (via Python's zoneinfo/tzdata) so historical
offsets -- including pre-standard-time local mean time entries where the
zone database has them -- are applied automatically instead of assuming
today's UTC offset for the location.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from astropy.time import Time
from timezonefinder import TimezoneFinder

_tf = TimezoneFinder()


@dataclass(frozen=True)
class ResolvedBirthTime:
    local_dt: datetime  # naive local datetime as entered
    tz_name: str  # IANA zone name used
    utc_dt: datetime  # timezone-aware, UTC
    time: Time  # astropy Time (utc scale); use .tt / .tdb for calculations


def find_timezone(lat: float, lon: float) -> str:
    tz_name = _tf.timezone_at(lat=lat, lng=lon)
    if tz_name is None:
        raise ValueError(
            f"Could not resolve a timezone for lat={lat}, lon={lon} "
            "(likely open ocean - pass tz_name explicitly)"
        )
    return tz_name


def resolve_birth_time(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int = 0,
    *,
    lat: float | None = None,
    lon: float | None = None,
    tz_name: str | None = None,
) -> ResolvedBirthTime:
    """Resolve local birth date/time to UTC.

    Either pass `lat`/`lon` (timezone is looked up automatically) or an
    explicit IANA `tz_name` (e.g. when the birthplace no longer maps
    cleanly, or the user wants to override the lookup).
    """
    if tz_name is None:
        if lat is None or lon is None:
            raise ValueError("Provide either tz_name, or both lat and lon")
        tz_name = find_timezone(lat, lon)

    local_dt = datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo(tz_name))
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    t = Time(utc_dt, scale="utc")

    return ResolvedBirthTime(
        local_dt=local_dt.replace(tzinfo=None),
        tz_name=tz_name,
        utc_dt=utc_dt,
        time=t,
    )


def resolved_from_time(t: Time, tz_name: str | None = None) -> ResolvedBirthTime:
    """Wrap an already-known instant (e.g. a computed eclipse moment,
    not something typed in as local date/time/place) into the same
    `ResolvedBirthTime` shape the rest of the app expects. Defaults to
    displaying in UTC if no `tz_name` is given."""
    utc_dt = t.to_datetime(timezone=ZoneInfo("UTC"))
    zone = ZoneInfo(tz_name) if tz_name else ZoneInfo("UTC")
    local_dt = utc_dt.astimezone(zone)
    return ResolvedBirthTime(
        local_dt=local_dt.replace(tzinfo=None),
        tz_name=tz_name or "UTC",
        utc_dt=utc_dt,
        time=t,
    )
