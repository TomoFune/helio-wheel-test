"""Astrological degree/sign formatting.

Two related but distinct conventions live here (clarified 2026-08-27
after the default got this backwards at first):

- **Everyday display** (`format_astrological`, the default/primary
  notation): plain raw decimal degree-in-sign, e.g. "牡牛座0°33'00\"".
  This is what most astrology software shows and what the user wants
  for normal chart reading.
- **Sabian-symbol "counting" degree number** (`format_sabian_degree`):
  the traditional 1-30 ordinal band label, where 0°00'00"-0°59'59" of
  a sign is "degree 1" (the rule from the original spec's section 5) --
  nothing is shifted by +1 in the underlying arithmetic, only the
  integer label is offset by one. This convention is used **only**
  when indexing into a Sabian symbol list (Sabian text/data itself
  isn't implemented yet -- deferred pending rights clearance, spec
  sections 19-20), not for everyday display. e.g. a raw position of
  3deg30m into Gemini is Sabian "degree 4" (`format_sabian_degree` ->
  "双子座4度") while the everyday display is "双子座3°30'00\""
  (`format_astrological`).
"""
from __future__ import annotations

from dataclasses import dataclass

SIGNS: list[tuple[str, str, str]] = [
    # (Japanese name, English name, symbol)
    ("牡羊座", "Aries", "♈"),
    ("牡牛座", "Taurus", "♉"),
    ("双子座", "Gemini", "♊"),
    ("蟹座", "Cancer", "♋"),
    ("獅子座", "Leo", "♌"),
    ("乙女座", "Virgo", "♍"),
    ("天秤座", "Libra", "♎"),
    ("蠍座", "Scorpio", "♏"),
    ("射手座", "Sagittarius", "♐"),
    ("山羊座", "Capricorn", "♑"),
    ("水瓶座", "Aquarius", "♒"),
    ("魚座", "Pisces", "♓"),
]


def normalize_longitude(lon_deg: float) -> float:
    """Wrap a longitude into [0, 360)."""
    lon = lon_deg % 360.0
    if lon < 0:
        lon += 360.0
    return lon


def split_dms(decimal_degrees: float) -> tuple[int, int, int]:
    """Split a non-negative decimal degree value into (deg, min, sec),
    rounded to the nearest second, with correct carry on rollover."""
    total_seconds = round(decimal_degrees * 3600)
    deg, rem = divmod(total_seconds, 3600)
    minute, sec = divmod(rem, 60)
    return int(deg), int(minute), int(sec)


@dataclass(frozen=True)
class SignPosition:
    longitude: float  # 0-360, normalized
    sign_index: int  # 0-11
    sign_name_ja: str
    sign_name_en: str
    sign_symbol: str
    raw_degree_in_sign: int  # 0-29, true integer part of degree-in-sign
    sabian_degree_number: int  # 1-30, Sabian-style counting band label (raw + 1)
    minute: int
    second: int


def longitude_to_sign_position(lon_deg: float) -> SignPosition:
    lon = normalize_longitude(lon_deg)
    sign_index = int(lon // 30)
    # Guard against the 359.9999...->360 rounding carrying past Pisces.
    sign_index = min(sign_index, 11)
    deg_in_sign = lon - sign_index * 30
    raw_deg, minute, second = split_dms(deg_in_sign)
    if raw_deg >= 30:
        # Rounding pushed us into the next sign (e.g. 29d59m59.6s -> 30d00m00s).
        sign_index = (sign_index + 1) % 12
        raw_deg, minute, second = 0, 0, 0
    name_ja, name_en, symbol = SIGNS[sign_index]
    return SignPosition(
        longitude=lon,
        sign_index=sign_index,
        sign_name_ja=name_ja,
        sign_name_en=name_en,
        sign_symbol=symbol,
        raw_degree_in_sign=raw_deg,
        sabian_degree_number=raw_deg + 1,
        minute=minute,
        second=second,
    )


def format_astrological(lon_deg: float, *, use_symbol: bool = False) -> str:
    """e.g. "牡牛座0°33'00\"" or "♉0°33'00\"" -- everyday plain decimal
    degree-in-sign notation. This is the default/primary display."""
    p = longitude_to_sign_position(lon_deg)
    label = p.sign_symbol if use_symbol else p.sign_name_ja
    return f"{label}{p.raw_degree_in_sign}°{p.minute:02d}'{p.second:02d}\""


def format_sabian_degree(lon_deg: float) -> str:
    """e.g. "双子座4度" -- the traditional Sabian-symbol "counting"
    ordinal band label (1-30), for indexing into a Sabian symbol list
    only. Not for everyday chart display -- use `format_astrological`."""
    p = longitude_to_sign_position(lon_deg)
    return f"{p.sign_name_ja}{p.sabian_degree_number}度"


def format_ecliptic_360(lon_deg: float) -> str:
    """e.g. "64°32'18\"" — plain 0-360 ecliptic longitude (section 13, 360度黄経)."""
    lon = normalize_longitude(lon_deg)
    deg, minute, second = split_dms(lon)
    deg %= 360
    return f"{deg}°{minute:02d}'{second:02d}\""
