"""
title: TimeWeaver
author: PureGrain at SLA Ops, LLC
author_url: https://github.com/PureGrain
repo_url: https://github.com/PureGrain/openwebui-stuff/tree/main/tools/timeweaver
funding_url: https://github.com/sponsors/PureGrain
version: 2.0.1
license: MIT
required_open_webui_version: 0.10.0
description: Time, dates and time zones done right. Current time anywhere by city, zone or abbreviation, time zone conversion, date math, countdowns, public holidays for 100+ countries, sunrise, sunset, twilight and moon phase, plus a live world clock in the chat. No API keys, no extra packages.
"""

import asyncio
import calendar
import html
import json
import math
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional
from zoneinfo import ZoneInfo, available_timezones

import httpx
from pydantic import BaseModel, Field

Emitter = Optional[Callable[[dict], Awaitable[Any]]]

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
HOLIDAY_URL = "https://date.nager.at/api/v3"
USER_AGENT = "TimeWeaver/2.0 (github.com/PureGrain/openwebui-stuff)"

# Abbreviations people and models actually type, mapped to real zones so daylight saving is right.
# EST, MST and HST also exist as fixed zones, which are an hour off in summer, so these win.
ABBREVIATIONS = {
    "ET": "America/New_York", "EST": "America/New_York", "EDT": "America/New_York", "EASTERN": "America/New_York",
    "CT": "America/Chicago", "CST": "America/Chicago", "CDT": "America/Chicago", "CENTRAL": "America/Chicago",
    "MT": "America/Denver", "MST": "America/Denver", "MDT": "America/Denver", "MOUNTAIN": "America/Denver",
    "ARIZONA": "America/Phoenix",
    "PT": "America/Los_Angeles", "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles", "PACIFIC": "America/Los_Angeles",
    "AKST": "America/Anchorage", "AKDT": "America/Anchorage", "ALASKA": "America/Anchorage",
    "HST": "Pacific/Honolulu", "HAWAII": "Pacific/Honolulu",
    "AST": "America/Halifax", "ADT": "America/Halifax", "NST": "America/St_Johns", "NDT": "America/St_Johns",
    "UTC": "UTC", "GMT": "UTC", "Z": "UTC", "ZULU": "UTC",
    "BST": "Europe/London", "WET": "Europe/Lisbon", "WEST": "Europe/Lisbon",
    "CET": "Europe/Paris", "CEST": "Europe/Paris", "EET": "Europe/Athens", "EEST": "Europe/Athens",
    "MSK": "Europe/Moscow", "IST": "Asia/Kolkata", "PKT": "Asia/Karachi", "SGT": "Asia/Singapore",
    "HKT": "Asia/Hong_Kong", "JST": "Asia/Tokyo", "KST": "Asia/Seoul",
    "AEST": "Australia/Sydney", "AEDT": "Australia/Sydney", "ACST": "Australia/Adelaide", "ACDT": "Australia/Adelaide",
    "AWST": "Australia/Perth", "NZST": "Pacific/Auckland", "NZDT": "Pacific/Auckland",
}

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico",
}

COUNTRY_ALIASES = {"usa": "US", "us": "US", "united states": "US", "america": "US", "uk": "GB", "england": "GB", "britain": "GB", "great britain": "GB"}

# Lets "Paris, France" stay one place when a list of places is split on commas.
COUNTRIES = {
    c.strip()
    for c in (
        "afghanistan, albania, algeria, andorra, angola, argentina, armenia, australia, austria, azerbaijan, bahamas, "
        "bahrain, bangladesh, barbados, belarus, belgium, belize, benin, bhutan, bolivia, bosnia, botswana, brazil, "
        "brunei, bulgaria, burkina faso, burundi, cambodia, cameroon, canada, chad, chile, china, colombia, comoros, "
        "congo, costa rica, croatia, cuba, cyprus, czechia, czech republic, denmark, djibouti, dominica, "
        "dominican republic, ecuador, egypt, el salvador, estonia, eswatini, ethiopia, fiji, finland, france, gabon, "
        "gambia, germany, ghana, greece, greenland, grenada, guatemala, guinea, guyana, haiti, honduras, hong kong, "
        "hungary, iceland, india, indonesia, iran, iraq, ireland, israel, italy, jamaica, japan, jordan, kazakhstan, "
        "kenya, kiribati, korea, south korea, north korea, kosovo, kuwait, kyrgyzstan, laos, latvia, lebanon, lesotho, "
        "liberia, libya, liechtenstein, lithuania, luxembourg, madagascar, malawi, malaysia, maldives, mali, malta, "
        "mauritania, mauritius, mexico, moldova, monaco, mongolia, montenegro, morocco, mozambique, myanmar, namibia, "
        "nauru, nepal, netherlands, holland, new zealand, nicaragua, niger, nigeria, north macedonia, norway, oman, "
        "pakistan, palau, panama, papua new guinea, paraguay, peru, philippines, poland, portugal, puerto rico, qatar, "
        "romania, russia, rwanda, samoa, san marino, saudi arabia, scotland, senegal, serbia, seychelles, sierra leone, "
        "singapore, slovakia, slovenia, somalia, south africa, spain, sri lanka, sudan, suriname, sweden, switzerland, "
        "syria, taiwan, tajikistan, tanzania, thailand, togo, tonga, trinidad, tunisia, turkey, turkiye, turkmenistan, "
        "uganda, ukraine, united arab emirates, uae, uruguay, uzbekistan, vanuatu, vatican, venezuela, vietnam, wales, "
        "yemen, zambia, zimbabwe"
    ).split(",")
}

MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
MONTHS["sept"] = 9
WEEKDAYS = {name.lower(): i for i, name in enumerate(calendar.day_name)}
WEEKDAYS.update({name.lower(): i for i, name in enumerate(calendar.day_abbr)})

SYNODIC_MONTH = 29.530588853
KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)


class WeaverError(Exception):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


def _split_places(text: str) -> list:
    """Split 'Louisville, KY, London; Tokyo' into places, keeping 'City, State' and 'City, Country' together."""
    parts = [p.strip() for p in re.split(r"[;,]|\s+and\s+", str(text or "")) if p.strip()]
    qualifiers = {s.lower() for s in US_STATES.values()} | set(COUNTRY_ALIASES) | COUNTRIES
    places: list = []
    for part in parts:
        is_qualifier = (len(part) == 2 and part.isalpha()) or part.lower() in qualifiers
        if places and is_qualifier:
            places[-1] = f"{places[-1]}, {part}"
        else:
            places.append(part)
    return places


async def _emit(emitter: Emitter, text: str, done: bool = False) -> None:
    if emitter:
        try:
            await emitter({"type": "status", "data": {"description": text, "done": done}})
        except Exception:
            pass


# ============= DATES =============


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th weekday of a month (n = -1 for the last one). Monday is 0."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


# Named days that can be used anywhere a date is accepted ("days until thanksgiving").
NAMED_DAYS = {
    "new year's day": lambda y: date(y, 1, 1),
    "new years day": lambda y: date(y, 1, 1),
    "new year": lambda y: date(y, 1, 1),
    "mlk day": lambda y: _nth_weekday(y, 1, 0, 3),
    "martin luther king day": lambda y: _nth_weekday(y, 1, 0, 3),
    "groundhog day": lambda y: date(y, 2, 2),
    "valentine's day": lambda y: date(y, 2, 14),
    "valentines day": lambda y: date(y, 2, 14),
    "valentines": lambda y: date(y, 2, 14),
    "presidents day": lambda y: _nth_weekday(y, 2, 0, 3),
    "presidents' day": lambda y: _nth_weekday(y, 2, 0, 3),
    "st patrick's day": lambda y: date(y, 3, 17),
    "st patricks day": lambda y: date(y, 3, 17),
    "good friday": lambda y: _easter(y) - timedelta(days=2),
    "easter": lambda y: _easter(y),
    "mother's day": lambda y: _nth_weekday(y, 5, 6, 2),
    "mothers day": lambda y: _nth_weekday(y, 5, 6, 2),
    "memorial day": lambda y: _nth_weekday(y, 5, 0, -1),
    "father's day": lambda y: _nth_weekday(y, 6, 6, 3),
    "fathers day": lambda y: _nth_weekday(y, 6, 6, 3),
    "juneteenth": lambda y: date(y, 6, 19),
    "independence day": lambda y: date(y, 7, 4),
    "fourth of july": lambda y: date(y, 7, 4),
    "4th of july": lambda y: date(y, 7, 4),
    "july 4th": lambda y: date(y, 7, 4),
    "labor day": lambda y: _nth_weekday(y, 9, 0, 1),
    "columbus day": lambda y: _nth_weekday(y, 10, 0, 2),
    "indigenous peoples day": lambda y: _nth_weekday(y, 10, 0, 2),
    "halloween": lambda y: date(y, 10, 31),
    "veterans day": lambda y: date(y, 11, 11),
    "thanksgiving": lambda y: _nth_weekday(y, 11, 3, 4),
    "black friday": lambda y: _nth_weekday(y, 11, 3, 4) + timedelta(days=1),
    "christmas eve": lambda y: date(y, 12, 24),
    "christmas": lambda y: date(y, 12, 25),
    "christmas day": lambda y: date(y, 12, 25),
    "new year's eve": lambda y: date(y, 12, 31),
    "new years eve": lambda y: date(y, 12, 31),
}


def _parse_date(text: str, today: date) -> date:
    """Understands today/tomorrow, ISO and US dates, month names, weekdays, 'in 3 weeks', '2 days ago' and holiday names."""
    raw = str(text or "").strip()
    t = raw.lower().strip().rstrip(".")
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", t)
    if t in ("", "today", "now", "tonight"):
        return today
    if t == "tomorrow":
        return today + timedelta(days=1)
    if t == "yesterday":
        return today - timedelta(days=1)

    m = re.fullmatch(r"(?:in\s+)?(\d+)\s+(day|week|month|year)s?(\s+ago|\s+from\s+(?:now|today))?", t)
    if m:
        n, unit, tail = int(m.group(1)), m.group(2), (m.group(3) or "").strip()
        sign = -1 if tail == "ago" else 1
        return _add(today, **{unit + "s": sign * n})

    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?", t)
    if m:
        year = int(m.group(3)) if m.group(3) else today.year
        if year < 100:
            year += 2000
        candidate = date(year, int(m.group(1)), int(m.group(2)))
        return candidate if m.group(3) or candidate >= today else candidate.replace(year=year + 1)

    m = re.fullmatch(r"(?:\w+,?\s+)?([a-z]+)\.?\s+(\d{1,2}),?(?:\s+(\d{4}))?", t) or None
    if m and m.group(1) in MONTHS:
        year = int(m.group(3)) if m.group(3) else today.year
        candidate = date(year, MONTHS[m.group(1)], int(m.group(2)))
        return candidate if m.group(3) or candidate >= today else candidate.replace(year=year + 1)
    m = re.fullmatch(r"(\d{1,2})\s+([a-z]+)\.?,?(?:\s+(\d{4}))?", t)
    if m and m.group(2) in MONTHS:
        year = int(m.group(3)) if m.group(3) else today.year
        candidate = date(year, MONTHS[m.group(2)], int(m.group(1)))
        return candidate if m.group(3) or candidate >= today else candidate.replace(year=year + 1)

    m = re.fullmatch(r"(this|next|last)?\s*([a-z]+)", t)
    if m and m.group(2) in WEEKDAYS:
        target = WEEKDAYS[m.group(2)]
        if m.group(1) == "last":
            back = (today.weekday() - target) % 7 or 7
            return today - timedelta(days=back)
        ahead = (target - today.weekday()) % 7
        if m.group(1) == "next" and ahead == 0:
            ahead = 7
        return today + timedelta(days=ahead)

    m = re.fullmatch(r"(?:next\s+|this\s+)?(.+?)(?:\s+(\d{4}))?", t)
    if m and m.group(1).strip() in NAMED_DAYS:
        fn = NAMED_DAYS[m.group(1).strip()]
        if m.group(2):
            return fn(int(m.group(2)))
        candidate = fn(today.year)
        return candidate if candidate >= today else fn(today.year + 1)

    raise WeaverError(
        f"Could not understand the date '{raw}'.",
        "Use a date like 2026-12-25, 12/25, Dec 25 2026, next friday, in 3 weeks, or a holiday such as thanksgiving.",
    )


def _parse_time_of_day(text: str) -> Optional[time]:
    t = text.lower().strip().replace(".", "")
    if t in ("noon", "midday"):
        return time(12, 0)
    if t == "midnight":
        return time(0, 0)
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)?", t)
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ampm:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if ampm.startswith("p") else 0)
    elif m.group(2) is None:
        return None
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def _split_datetime(text: str) -> tuple:
    """Split '3pm tomorrow' or '2026-11-02 09:30' into (date_text, time)."""
    t = str(text or "").strip()
    if t.lower() in ("now", ""):
        return "", None
    m = re.search(r"\b(noon|midday|midnight|\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?|a|p)\b|\d{1,2}:\d{2})", t, re.IGNORECASE)
    if not m:
        return t, None
    clock = _parse_time_of_day(m.group(1))
    rest = (t[: m.start()] + " " + t[m.end():]).replace(" at ", " ").strip(" ,@")
    rest = re.sub(r"^at\s+|\s+at$", "", rest.strip()).strip()
    return rest, clock


def _add(start: date, days: int = 0, weeks: int = 0, months: int = 0, years: int = 0) -> date:
    total_months = start.month - 1 + months + 12 * years
    year, month = start.year + total_months // 12, total_months % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day) + timedelta(days=days + 7 * weeks)


def _add_business_days(start: date, count: int) -> date:
    step = 1 if count >= 0 else -1
    current, left = start, abs(count)
    while left:
        current += timedelta(days=step)
        if current.weekday() < 5:
            left -= 1
    return current


def _business_days_between(a: date, b: date) -> int:
    if b < a:
        return -_business_days_between(b, a)
    days = (b - a).days
    full_weeks, extra = divmod(days, 7)
    count = full_weeks * 5
    for i in range(1, extra + 1):
        if (a + timedelta(days=full_weeks * 7 + i)).weekday() < 5:
            count += 1
    return count


def _calendar_diff(a: date, b: date) -> str:
    """Years, months and days from a to b (a <= b)."""
    years = b.year - a.year
    months = b.month - a.month
    days = b.day - a.day
    if days < 0:
        months -= 1
        prev_month = (b.month - 2) % 12 + 1
        prev_year = b.year if b.month > 1 else b.year - 1
        days += calendar.monthrange(prev_year, prev_month)[1]
    if months < 0:
        years -= 1
        months += 12
    parts = [f"{n} {unit}{'s' if n != 1 else ''}" for n, unit in ((years, "year"), (months, "month"), (days, "day")) if n]
    return ", ".join(parts) or "0 days"


def _date_facts(d: date, today: date) -> dict:
    iso_year, iso_week, _ = d.isocalendar()
    days_in_year = 366 if calendar.isleap(d.year) else 365
    delta = (d - today).days
    return {
        "date": d.isoformat(),
        "weekday": d.strftime("%A"),
        "written": d.strftime("%A, %B %-d, %Y"),
        "relative": "today" if delta == 0 else (f"in {delta} days" if delta > 0 else f"{-delta} days ago"),
        "week_number": iso_week,
        "day_of_year": f"{d.timetuple().tm_yday} of {days_in_year}",
        "quarter": f"Q{(d.month - 1) // 3 + 1}",
        "leap_year": calendar.isleap(d.year),
        "days_left_in_year": days_in_year - d.timetuple().tm_yday,
    }


# ============= SUN AND MOON =============


def _sun_event(day: date, lat: float, lon: float, altitude: float) -> tuple:
    """(rise, set) in UTC for the sun crossing an altitude in degrees, or a 'polar' marker."""
    n = (day - date(2000, 1, 1)).days
    j_star = n - lon / 360.0
    mean_anomaly = (357.5291 + 0.98560028 * j_star) % 360
    m_rad = math.radians(mean_anomaly)
    center = 1.9148 * math.sin(m_rad) + 0.0200 * math.sin(2 * m_rad) + 0.0003 * math.sin(3 * m_rad)
    ecliptic = math.radians((mean_anomaly + center + 180 + 102.9372) % 360)
    transit = 2451545.0 + j_star + 0.0053 * math.sin(m_rad) - 0.0069 * math.sin(2 * ecliptic)
    declination = math.asin(math.sin(ecliptic) * math.sin(math.radians(23.4397)))
    lat_rad = math.radians(lat)
    cos_hour = (math.sin(math.radians(altitude)) - math.sin(lat_rad) * math.sin(declination)) / (math.cos(lat_rad) * math.cos(declination))
    noon = datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=transit - 2451545.0)
    if cos_hour > 1:
        return None, None, "never rises", noon
    if cos_hour < -1:
        return None, None, "never sets", noon
    hour_angle = math.degrees(math.acos(cos_hour)) / 360.0
    return noon - timedelta(days=hour_angle), noon + timedelta(days=hour_angle), None, noon


def _moon(moment: datetime) -> dict:
    age = ((moment - KNOWN_NEW_MOON).total_seconds() / 86400.0) % SYNODIC_MONTH
    illumination = (1 - math.cos(2 * math.pi * age / SYNODIC_MONTH)) / 2
    phases = [
        (1.0, "New Moon", "🌑"), (6.4, "Waxing Crescent", "🌒"), (8.4, "First Quarter", "🌓"),
        (13.8, "Waxing Gibbous", "🌔"), (15.8, "Full Moon", "🌕"), (21.1, "Waning Gibbous", "🌖"),
        (23.1, "Last Quarter", "🌗"), (28.5, "Waning Crescent", "🌘"), (99, "New Moon", "🌑"),
    ]
    name, icon = next((n, i) for limit, n, i in phases if age < limit)
    full_in = (14.765 - age) % SYNODIC_MONTH
    new_in = (SYNODIC_MONTH - age) % SYNODIC_MONTH
    return {
        "phase": name,
        "icon": icon,
        "illuminated_pct": round(illumination * 100),
        "age_days": round(age, 1),
        "next_full_moon": (moment + timedelta(days=full_in)).date().isoformat(),
        "next_new_moon": (moment + timedelta(days=new_in)).date().isoformat(),
        "note": "Moon phase is calculated, accurate to within about a day.",
    }


class Tools:
    class Valves(BaseModel):
        default_timezone: str = Field(
            default="",
            description="Fallback time zone, for example America/New_York. Empty uses each user's Open WebUI time zone, then UTC.",
        )
        time_format: str = Field(default="12h", description="12h (3:05 PM) or 24h (15:05)")
        default_country: str = Field(default="US", description="Two-letter country code for public holidays, for example US, GB, DE")

    class UserValves(BaseModel):
        user_timezone: Optional[str] = Field(default=None, description="Your time zone, for example America/Los_Angeles. Overrides everything else.")
        user_location: Optional[str] = Field(default=None, description="Your city, used for sunrise and sunset, for example Louisville, KY")

    def __init__(self):
        self.valves = self.Valves()
        self._zones_lower = None
        self._zone_cities = None
        self._geo_cache: dict = {}
        self._countries: Optional[list] = None

    # ============= HELPERS =============

    def _fmt_time(self, moment: datetime, seconds: bool = False) -> str:
        if str(self.valves.time_format).strip().lower().startswith("24"):
            return moment.strftime("%H:%M:%S" if seconds else "%H:%M")
        return moment.strftime("%-I:%M:%S %p" if seconds else "%-I:%M %p")

    def _user_valve(self, user: Optional[dict], name: str) -> Optional[str]:
        valves = (user or {}).get("valves")
        value = valves.get(name) if isinstance(valves, dict) else getattr(valves, name, None)
        return str(value).strip() if value else None

    def _home_zone(self, user: Optional[dict]) -> tuple:
        for source, value in (
            ("your TimeWeaver setting", self._user_valve(user, "user_timezone")),
            ("your Open WebUI profile", (user or {}).get("timezone")),
            ("the TimeWeaver default", self.valves.default_timezone),
        ):
            if value:
                try:
                    return ZoneInfo(str(value)), str(value), source
                except Exception:
                    continue
        return ZoneInfo("UTC"), "UTC", "fallback, no time zone is set"

    def _index_zones(self) -> None:
        if self._zones_lower is None:
            zones = available_timezones()
            self._zones_lower = {z.lower(): z for z in zones}
            cities: dict = {}
            for z in zones:
                if "/" in z and not z.startswith(("Etc/", "SystemV/")):
                    cities.setdefault(z.rsplit("/", 1)[-1].lower(), []).append(z)
            self._zone_cities = cities

    async def _geocode(self, client: httpx.AsyncClient, query: str) -> dict:
        key = query.strip().lower()
        if key in self._geo_cache:
            return self._geo_cache[key]
        parts = [p.strip() for p in query.split(",") if p.strip()]
        name, quals = (parts[0], parts[1:]) if parts else (query, [])
        if not quals:
            m = re.fullmatch(r"(.+?)\s+([A-Za-z]{2})", name)
            if m and m.group(2).upper() in US_STATES:
                name, quals = m.group(1), [m.group(2)]
        r = await client.get(GEOCODE_URL, params={"name": name, "count": 10, "language": "en", "format": "json"})
        r.raise_for_status()
        results = r.json().get("results") or []
        if quals and results:
            wanted = []
            for q in quals:
                q_low = q.lower()
                wanted.append({q_low, US_STATES.get(q.upper(), q).lower(), COUNTRY_ALIASES.get(q_low, q).lower()})

            def score(x: dict) -> int:
                fields = {str(x.get(k, "")).lower() for k in ("admin1", "admin2", "country", "country_code")}
                return sum(1 for options in wanted if fields & options)

            best = max(score(x) for x in results)
            if best:
                results = [x for x in results if score(x) == best]
        if not results:
            raise WeaverError(f"Could not find a place called '{query}'.", "Try 'City, State', 'City, Country', or a time zone like Europe/Paris.")
        top = results[0]
        label_parts = []
        for part in (top.get("name"), top.get("admin1"), top.get("country")):
            if part and part not in label_parts:
                label_parts.append(part)
        place = {
            "label": ", ".join(label_parts),
            "lat": top["latitude"],
            "lon": top["longitude"],
            "timezone": top.get("timezone") or "UTC",
            "country_code": top.get("country_code"),
        }
        self._geo_cache[key] = place
        return place

    async def _resolve_zone(self, client: httpx.AsyncClient, text: str, user: Optional[dict]) -> dict:
        """Turns a city, zone name, abbreviation or UTC offset into {zone, label, note}."""
        raw = str(text or "").strip()
        if not raw or raw.lower() in ("here", "local", "me", "my time", "home"):
            zone, name, source = self._home_zone(user)
            return {"zone": zone, "label": name, "note": f"Time zone from {source}."}
        self._index_zones()
        key = raw.upper().replace(".", "").strip()
        if key in ABBREVIATIONS:
            zone_name = ABBREVIATIONS[key]
            note = None if key in ("UTC", "GMT", "Z", "ZULU") else f"'{raw}' read as {zone_name}, so daylight saving time is applied."
            return {"zone": ZoneInfo(zone_name), "label": zone_name, "note": note}
        m = re.fullmatch(r"(?:UTC|GMT)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?", raw.upper())
        if m and (raw.upper().startswith(("UTC", "GMT")) or raw.startswith(("+", "-"))):
            sign = 1 if m.group(1) == "+" else -1
            offset = timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0)) * sign
            label = f"UTC{m.group(1)}{int(m.group(2)):02d}:{int(m.group(3) or 0):02d}"
            return {"zone": timezone(offset, label), "label": label, "note": "A fixed offset never changes for daylight saving time."}
        exact = self._zones_lower.get(raw.lower()) or self._zones_lower.get(raw.lower().replace(" ", "_"))
        if exact:
            return {"zone": ZoneInfo(exact), "label": exact, "note": None}
        city = self._zone_cities.get(raw.lower().replace(" ", "_"))
        if city and len(city) == 1:
            return {"zone": ZoneInfo(city[0]), "label": f"{raw} ({city[0]})", "note": None}
        place = await self._geocode(client, raw)
        return {"zone": ZoneInfo(place["timezone"]), "label": f"{place['label']} ({place['timezone']})", "note": None, "place": place}

    async def _resolve_place(self, client: httpx.AsyncClient, text: str, user: Optional[dict]) -> dict:
        """A place with coordinates, for sunrise and sunset."""
        query = str(text or "").strip() or self._user_valve(user, "user_location")
        if not query:
            raise WeaverError(
                "No place given for sunrise and sunset.",
                "Name a city, or set user_location in your TimeWeaver settings (Chat Controls > Valves).",
            )
        place = await self._geocode(client, query)
        return place

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=httpx.Timeout(10, connect=5), headers={"User-Agent": USER_AGENT})

    async def _run(self, emitter: Emitter, label: str, work: Callable[[httpx.AsyncClient], Awaitable[Any]]) -> Any:
        await _emit(emitter, f"{label}...")
        try:
            async with self._client() as client:
                result = await work(client)
            await _emit(emitter, label, done=True)
            return result
        except WeaverError as e:
            await _emit(emitter, f"{label} failed", done=True)
            return {"error": str(e), "hint": e.hint} if e.hint else {"error": str(e)}
        except httpx.HTTPError as e:
            await _emit(emitter, f"{label} failed", done=True)
            return {"error": f"A lookup service did not answer: {type(e).__name__}", "hint": "Try again in a moment."}
        except Exception as e:
            await _emit(emitter, f"{label} failed", done=True)
            return {"error": f"{type(e).__name__}: {e}"}

    def _next_dst_change(self, zone: Any, now: datetime) -> Optional[str]:
        """When the clocks next change in this zone, within a year."""
        if not isinstance(zone, ZoneInfo):
            return None
        current = now.utcoffset()
        step = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        for _ in range(370):
            nxt = step + timedelta(days=1)
            if nxt.astimezone(zone).utcoffset() != current:
                break
            step = nxt
        else:
            return None
        probe = step
        while probe.astimezone(zone).utcoffset() == current:
            probe += timedelta(minutes=15)
        shift = (probe.astimezone(zone).utcoffset() - current).total_seconds() / 3600
        wall = (probe + current).replace(tzinfo=None)  # the local clock reading when it changes
        plural = "s" if abs(shift) != 1 else ""
        return f"Clocks go {'forward' if shift > 0 else 'back'} {abs(shift):g} hour{plural} on {wall.strftime('%a %b %-d, %Y')} at {self._fmt_time(wall)}"

    def _clock_entry(self, info: dict, now_utc: datetime, home: Any) -> dict:
        zone = info["zone"]
        local = now_utc.astimezone(zone)
        offset = local.strftime("%z")
        entry = {
            "place": info["label"],
            "time": self._fmt_time(local),
            "date": local.strftime("%A, %B %-d, %Y"),
            "zone": f"{local.tzname()} (UTC{offset[:3]}:{offset[3:]})",
            "daylight_saving": bool(local.dst()) if isinstance(zone, ZoneInfo) else False,
        }
        diff = (local.utcoffset() - now_utc.astimezone(home).utcoffset()).total_seconds() / 3600
        if diff:
            entry["vs_you"] = f"{'+' if diff > 0 else '-'}{abs(diff):g}h"
        change = self._next_dst_change(zone, local)
        if change:
            entry["next_clock_change"] = change
        if info.get("note"):
            entry["note"] = info["note"]
        return entry

    # ============= TOOLS =============

    async def get_current_time(self, places: str = "", __user__: Optional[dict] = None, __event_emitter__: Emitter = None) -> dict:
        """
        Current date and time, here or anywhere. Use for "what time is it", "what's the date", or "time in Tokyo and London".
        :param places: One or more places, comma separated: a city ("Tokyo", "Louisville KY"), a time zone ("Europe/London"), or an abbreviation ("PST"). Leave empty for the user's own time.
        """

        async def work(client: httpx.AsyncClient) -> dict:
            now_utc = datetime.now(timezone.utc)
            home, home_name, source = self._home_zone(__user__)
            local = now_utc.astimezone(home)
            requested = _split_places(places)
            if not requested:
                entry = self._clock_entry({"zone": home, "label": home_name, "note": f"Time zone from {source}."}, now_utc, home)
                entry.update(
                    {
                        "week_number": local.isocalendar()[1],
                        "day_of_year": local.timetuple().tm_yday,
                        "unix_time": int(now_utc.timestamp()),
                    }
                )
                return entry
            infos = await asyncio.gather(*(self._resolve_zone(client, p, __user__) for p in requested), return_exceptions=True)
            clocks = []
            for text, info in zip(requested, infos):
                if isinstance(info, Exception):
                    clocks.append({"place": text, "error": str(info), "hint": getattr(info, "hint", "")})
                else:
                    clocks.append(self._clock_entry(info, now_utc, home))
            return {"your_time": f"{self._fmt_time(local)} {local.tzname()}", "clocks": clocks}

        return await self._run(__event_emitter__, "Checking the time", work)

    async def convert_time(
        self,
        time_text: str,
        from_place: str = "",
        to_places: str = "",
        __user__: Optional[dict] = None,
        __event_emitter__: Emitter = None,
    ) -> dict:
        """
        Convert a time from one place or time zone to others, for example "3pm in Louisville to London and Tokyo". Shows when the date changes.
        :param time_text: The time to convert, with an optional date: "3pm", "15:30", "9am tomorrow", "2026-11-02 18:00", or "now".
        :param from_place: Where that time is: city, time zone or abbreviation. Leave empty for the user's own time zone.
        :param to_places: Where to convert to, comma separated. Leave empty to convert into the user's own time zone.
        """

        async def work(client: httpx.AsyncClient) -> dict:
            source = await self._resolve_zone(client, from_place, __user__)
            zone = source["zone"]
            today = datetime.now(zone).date()
            date_text, clock = _split_datetime(time_text)
            if clock is None and time_text.strip().lower() not in ("now", ""):
                if date_text.strip():
                    raise WeaverError(f"Could not find a time in '{time_text}'.", "Include a time like 3pm, 15:30, noon or midnight.")
            day = _parse_date(date_text, today)
            moment = datetime.now(zone) if clock is None else datetime.combine(day, clock, tzinfo=zone)
            targets = _split_places(to_places) or [""]
            infos = await asyncio.gather(*(self._resolve_zone(client, p, __user__) for p in targets), return_exceptions=True)
            results = []
            for text, info in zip(targets, infos):
                if isinstance(info, Exception):
                    results.append({"place": text, "error": str(info)})
                    continue
                converted = moment.astimezone(info["zone"])
                shift = (converted.date() - moment.date()).days
                entry = {
                    "place": info["label"],
                    "time": self._fmt_time(converted),
                    "date": converted.strftime("%a, %b %-d"),
                    "zone": converted.tzname(),
                }
                if shift:
                    entry["day_change"] = "next day" if shift == 1 else ("previous day" if shift == -1 else f"{shift:+d} days")
                if info.get("note"):
                    entry["note"] = info["note"]
                results.append(entry)
            return {
                "from": {"place": source["label"], "time": self._fmt_time(moment), "date": moment.strftime("%a, %b %-d, %Y"), "zone": moment.tzname()},
                "to": results,
            }

        return await self._run(__event_emitter__, "Converting time", work)

    async def calculate_date(
        self,
        start: str = "today",
        days: int = 0,
        weeks: int = 0,
        months: int = 0,
        years: int = 0,
        business_days: bool = False,
        __user__: Optional[dict] = None,
        __event_emitter__: Emitter = None,
    ) -> dict:
        """
        Date math and date facts: add or subtract days, weeks, months or years ("90 days from today", "6 weeks before Christmas"), or look up a date ("what day of the week is July 4 2027"). Use negative numbers to go back.
        :param start: Starting date: "today", "2026-12-25", "Dec 25", "next friday", "thanksgiving", and so on.
        :param days: Days to add (negative to subtract).
        :param weeks: Weeks to add (negative to subtract).
        :param months: Months to add (negative to subtract).
        :param years: Years to add (negative to subtract).
        :param business_days: Count days as business days (Monday to Friday, holidays not skipped).
        """

        async def work(client: httpx.AsyncClient) -> dict:
            zone, _, _ = self._home_zone(__user__)
            today = datetime.now(zone).date()
            begin = _parse_date(start, today)
            if business_days:
                result = _add_business_days(_add(begin, months=months, years=years), days + 5 * weeks)
            else:
                result = _add(begin, days=days, weeks=weeks, months=months, years=years)
            out = _date_facts(result, today)
            if result != begin:
                out["from"] = f"{begin.strftime('%a, %b %-d, %Y')}"
                out["business_days_used"] = business_days
            holiday = next((name.title() for name, fn in NAMED_DAYS.items() if fn(result.year) == result), None)
            if holiday:
                out["holiday"] = holiday
            return out

        return await self._run(__event_emitter__, "Calculating the date", work)

    async def time_between(
        self,
        start: str = "now",
        end: str = "",
        __user__: Optional[dict] = None,
        __event_emitter__: Emitter = None,
    ) -> dict:
        """
        Time between two dates or moments: countdowns ("days until Christmas"), ages ("how long since 2019-03-01"), and durations. Gives days, weeks, months and years, business days, and hours when times are given.
        :param start: Start date or moment, for example "now", "today", "2019-03-01", "9am".
        :param end: End date or moment, for example "christmas", "2026-12-31 23:59", "friday 5pm".
        """

        async def work(client: httpx.AsyncClient) -> dict:
            zone, _, _ = self._home_zone(__user__)
            now = datetime.now(zone)
            today = now.date()

            def moment(text: str) -> tuple:
                date_text, clock = _split_datetime(text)
                if text.strip().lower() == "now":
                    return now, True
                day = _parse_date(date_text, today)
                return datetime.combine(day, clock or time(0, 0), tzinfo=zone), clock is not None

            if not end.strip():
                raise WeaverError("No end date given.", "Say what to count to, for example christmas or 2027-01-01.")
            a, a_timed = moment(start)
            b, b_timed = moment(end)
            forward = b >= a
            lo, hi = (a, b) if forward else (b, a)
            whole_days = (hi.date() - lo.date()).days
            out = {
                "from": a.strftime("%a, %b %-d, %Y") + (f" {self._fmt_time(a)}" if a_timed else ""),
                "to": b.strftime("%a, %b %-d, %Y") + (f" {self._fmt_time(b)}" if b_timed else ""),
                "direction": "future" if forward else "past",
                "days": whole_days,
                "weeks": f"{whole_days // 7} weeks, {whole_days % 7} days",
                "calendar": _calendar_diff(lo.date(), hi.date()),
                "business_days": abs(_business_days_between(lo.date(), hi.date())),
            }
            if a_timed or b_timed:
                seconds = int((hi - lo).total_seconds())
                out["exact"] = f"{seconds // 86400}d {seconds % 86400 // 3600}h {seconds % 3600 // 60}m"
                out["total_hours"] = round(seconds / 3600, 1)
            if not forward:
                out["summary"] = f"{out['to']} was {whole_days} days before {out['from']}"
            elif start.strip().lower() in ("now", "today", ""):
                out["summary"] = f"{whole_days} days until {out['to']}"
            else:
                out["summary"] = f"{whole_days} days from {out['from']} to {out['to']}"
            return out

        return await self._run(__event_emitter__, "Counting the time", work)

    async def get_holidays(
        self,
        country: str = "",
        year: int = 0,
        upcoming_only: bool = True,
        __user__: Optional[dict] = None,
        __event_emitter__: Emitter = None,
    ) -> dict:
        """
        Official public holidays for a country and year, with how many days until each. Over 100 countries.
        :param country: Country name or two-letter code, for example "US", "Germany", "GB". Leave empty for the default country.
        :param year: Year to list. Leave 0 for this year.
        :param upcoming_only: Only holidays that have not passed yet (for this year).
        """

        async def work(client: httpx.AsyncClient) -> dict:
            zone, _, _ = self._home_zone(__user__)
            today = datetime.now(zone).date()
            code = (country or self.valves.default_country or "US").strip()
            code = COUNTRY_ALIASES.get(code.lower(), code)
            if len(code) != 2:
                if self._countries is None:
                    r = await client.get(f"{HOLIDAY_URL}/AvailableCountries")
                    r.raise_for_status()
                    self._countries = r.json()
                match = next((c for c in self._countries if c["name"].lower() == code.lower()), None) or next(
                    (c for c in self._countries if code.lower() in c["name"].lower()), None
                )
                if not match:
                    raise WeaverError(f"No holiday data for '{country}'.", "Use a two-letter country code such as US, GB, DE or FR.")
                code = match["countryCode"]
            target_year = year or today.year
            r = await client.get(f"{HOLIDAY_URL}/PublicHolidays/{target_year}/{code.upper()}")
            if r.status_code in (204, 404) or not r.content:
                raise WeaverError(f"No holiday data for country code '{code}'.", "Use a two-letter country code such as US, GB, DE or FR.")
            r.raise_for_status()
            items = []
            for h in r.json():
                d = date.fromisoformat(h["date"])
                if upcoming_only and target_year == today.year and d < today:
                    continue
                entry = {"date": d.strftime("%a, %b %-d"), "name": h.get("name")}
                if h.get("localName") and h["localName"] != h.get("name"):
                    entry["local_name"] = h["localName"]
                delta = (d - today).days
                entry["when"] = "today" if delta == 0 else (f"in {delta} days" if delta > 0 else f"{-delta} days ago")
                if not h.get("global", True):
                    entry["regional"] = True
                items.append(entry)
            return {"country": code.upper(), "year": target_year, "count": len(items), "holidays": items or "No more public holidays this year."}

        return await self._run(__event_emitter__, "Looking up holidays", work)

    async def get_sun_and_moon(
        self,
        place: str = "",
        date_text: str = "today",
        __user__: Optional[dict] = None,
        __event_emitter__: Emitter = None,
    ) -> dict:
        """
        Sunrise, sunset, solar noon, day length, dawn and dusk (civil twilight), golden hour, and the moon phase for a place and date. Works for any date.
        :param place: City or place, for example "Louisville KY" or "Reykjavik". Leave empty for the user's saved location.
        :param date_text: Date, for example "today", "tomorrow", "2026-12-21", "June 21".
        """

        async def work(client: httpx.AsyncClient) -> dict:
            where = await self._resolve_place(client, place, __user__)
            zone = ZoneInfo(where["timezone"])
            today = datetime.now(zone).date()
            day = _parse_date(date_text, today)
            lat, lon = where["lat"], where["lon"]

            def local(moment: Optional[datetime]) -> Optional[str]:
                return self._fmt_time(moment.astimezone(zone)) if moment else None

            rise, sset, polar, noon = _sun_event(day, lat, lon, -0.833)
            dawn, dusk, _, _ = _sun_event(day, lat, lon, -6)
            golden_end, golden_start, _, _ = _sun_event(day, lat, lon, 6)
            out = {"place": where["label"], "date": day.strftime("%A, %B %-d, %Y"), "time_zone": where["timezone"]}
            if polar:
                out["sun"] = f"The sun {polar} on this date."
            else:
                length = (sset - rise).total_seconds()
                prev_rise, prev_set, _, _ = _sun_event(day - timedelta(days=1), lat, lon, -0.833)
                change = 0 if prev_rise is None else length - (prev_set - prev_rise).total_seconds()
                out.update(
                    {
                        "sunrise": local(rise),
                        "sunset": local(sset),
                        "solar_noon": local(noon),
                        "day_length": f"{int(length // 3600)}h {int(length % 3600 // 60)}m",
                        "vs_yesterday": f"{abs(change) / 60:.1f} min {'longer' if change >= 0 else 'shorter'}",
                        "dawn": local(dawn) or "no full darkness tonight (twilight all night)",
                        "dusk": local(dusk) or "no full darkness tonight (twilight all night)",
                        "morning_golden_hour": f"{local(rise)} to {local(golden_end)}" if golden_end else "sun stays low all day",
                        "evening_golden_hour": f"{local(golden_start)} to {local(sset)}" if golden_start else "sun stays low all day",
                    }
                )
            moment = datetime.combine(day, time(21, 0), tzinfo=zone)
            out["moon"] = _moon(moment.astimezone(timezone.utc))
            out["note"] = "Sun times are calculated and accurate to about a minute."
            return out

        return await self._run(__event_emitter__, "Working out sun and moon times", work)

    async def show_world_clock(self, places: str = "", __user__: Optional[dict] = None, __event_emitter__: Emitter = None) -> Any:
        """
        Show a live, ticking world clock in the chat for one or more places, with day and night shading. Use when the user wants to see clocks.
        :param places: Places, comma separated, for example "Louisville KY, London, Tokyo". Leave empty for the user's time plus UTC.
        """

        async def work(client: httpx.AsyncClient) -> Any:
            from fastapi.responses import HTMLResponse

            home, home_name, _ = self._home_zone(__user__)
            requested = _split_places(places)
            infos = [{"zone": home, "label": f"{home_name.rsplit('/', 1)[-1].replace('_', ' ')} · you"}]
            if requested:
                resolved = await asyncio.gather(*(self._resolve_zone(client, p, __user__) for p in requested), return_exceptions=True)
                infos += [i for i in resolved if not isinstance(i, Exception)]
            else:
                infos.append({"zone": ZoneInfo("UTC"), "label": "UTC"})
            clocks = []
            for info in infos:
                zone = info["zone"]
                key = getattr(zone, "key", None)
                if key is None:
                    offset = datetime.now(timezone.utc).astimezone(zone).utcoffset().total_seconds() / 3600
                    key = f"Etc/GMT{'-' if offset > 0 else '+'}{abs(int(offset))}" if offset == int(offset) else "UTC"
                clocks.append({"label": info["label"].split(" (")[0].split(",")[0], "tz": key})
            hour12 = "false" if str(self.valves.time_format).startswith("24") else "true"
            data = json.dumps(clocks)
            page = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
:root {{ --bg:#ffffff; --fg:#1f2328; --muted:#656d76; --card:#f6f8fa; --line:#d0d7de; --night:#1e2a44; --nightfg:#e6edf3; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0d1117; --fg:#e6edf3; --muted:#8d96a0; --card:#161b22; --line:#30363d; --night:#0b1222; }} }}
body {{ margin:0; padding:12px; font:14px system-ui,sans-serif; background:var(--bg); color:var(--fg); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:10px; }}
.clock {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px; }}
.clock.night {{ background:var(--night); color:var(--nightfg); border-color:var(--night); }}
.name {{ font-weight:600; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.time {{ font-size:28px; font-variant-numeric:tabular-nums; margin:4px 0 2px; }}
.meta {{ font-size:12px; opacity:.75; }}
</style></head><body><div class="grid" id="g"></div>
<script>
const clocks = {data};
const g = document.getElementById('g');
const cards = clocks.map(c => {{ const d = document.createElement('div'); d.className = 'clock';
  d.innerHTML = '<div class="name"></div><div class="time"></div><div class="meta"></div>';
  d.querySelector('.name').textContent = c.label; g.appendChild(d); return d; }});
function tick() {{ const now = new Date();
  clocks.forEach((c, i) => {{
    const t = new Intl.DateTimeFormat([], {{ timeZone: c.tz, hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: {hour12} }}).format(now);
    const meta = new Intl.DateTimeFormat([], {{ timeZone: c.tz, weekday: 'short', month: 'short', day: 'numeric', timeZoneName: 'short' }}).format(now);
    const h = Number(new Intl.DateTimeFormat('en-US', {{ timeZone: c.tz, hour: 'numeric', hour12: false }}).format(now)) % 24;
    cards[i].querySelector('.time').textContent = t;
    cards[i].querySelector('.meta').textContent = meta + (h < 6 || h >= 20 ? ' · night' : ' · day');
    cards[i].classList.toggle('night', h < 6 || h >= 20);
  }}); }}
tick(); setInterval(tick, 1000);
function reportHeight() {{ parent.postMessage({{ type: 'iframe:height', height: document.documentElement.scrollHeight }}, '*'); }}
window.addEventListener('load', reportHeight); new ResizeObserver(reportHeight).observe(document.body);
</script></body></html>"""
            now_utc = datetime.now(timezone.utc)
            context = {
                "shown": "A live, ticking world clock is already on the user's screen.",
                "instructions": "Do not repeat this data, and never print it as JSON, code or tags. Reply in one short plain sentence.",
                "clocks": [f"{html.escape(c['label'])}: {self._fmt_time(now_utc.astimezone(ZoneInfo(c['tz'])))}" for c in clocks],
            }
            return HTMLResponse(content=page, headers={"Content-Disposition": "inline"}), context

        return await self._run(__event_emitter__, "Building the world clock", work)
