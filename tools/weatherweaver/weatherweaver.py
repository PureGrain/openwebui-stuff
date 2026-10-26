"""
title: WeatherWeaver
author: PureGrain at SLA Ops, LLC
author_url: https://github.com/PureGrain
repo_url: https://github.com/PureGrain/openwebui-stuff/tree/main/tools/weatherweaver
funding_url: https://github.com/sponsors/PureGrain
version: 2.0.0
license: MIT
required_open_webui_version: 0.10.0
description: Weather done right, worldwide and free. Current conditions, hour by hour and 16-day forecasts, US severe weather alerts, air quality and pollen, past weather back to 1940, side-by-side city comparison, and a weather dashboard in the chat. Data from Open-Meteo and the US National Weather Service. No API keys, no extra packages.

Credit for the original idea: Keyless Weather by spyci
"""

import asyncio
import html
import re
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable, Optional
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field

Emitter = Optional[Callable[[dict], Awaitable[Any]]]

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
USER_AGENT = "WeatherWeaver/2.0 (github.com/PureGrain/openwebui-stuff)"

# WMO weather codes: (description, day icon, night icon)
WEATHER_CODES = {
    0: ("Clear sky", "☀️", "🌙"),
    1: ("Mainly clear", "🌤️", "🌙"),
    2: ("Partly cloudy", "⛅", "☁️"),
    3: ("Overcast", "☁️", "☁️"),
    45: ("Fog", "🌫️", "🌫️"),
    48: ("Freezing fog", "🌫️", "🌫️"),
    51: ("Light drizzle", "🌦️", "🌧️"),
    53: ("Drizzle", "🌦️", "🌧️"),
    55: ("Heavy drizzle", "🌧️", "🌧️"),
    56: ("Light freezing drizzle", "🌧️", "🌧️"),
    57: ("Freezing drizzle", "🌧️", "🌧️"),
    61: ("Light rain", "🌦️", "🌧️"),
    63: ("Rain", "🌧️", "🌧️"),
    65: ("Heavy rain", "🌧️", "🌧️"),
    66: ("Light freezing rain", "🌧️", "🌧️"),
    67: ("Freezing rain", "🌧️", "🌧️"),
    71: ("Light snow", "🌨️", "🌨️"),
    73: ("Snow", "🌨️", "🌨️"),
    75: ("Heavy snow", "❄️", "❄️"),
    77: ("Snow grains", "🌨️", "🌨️"),
    80: ("Light rain showers", "🌦️", "🌧️"),
    81: ("Rain showers", "🌧️", "🌧️"),
    82: ("Violent rain showers", "⛈️", "⛈️"),
    85: ("Light snow showers", "🌨️", "🌨️"),
    86: ("Heavy snow showers", "❄️", "❄️"),
    95: ("Thunderstorm", "⛈️", "⛈️"),
    96: ("Thunderstorm with hail", "⛈️", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️", "⛈️"),
}

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

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

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


class WeaverError(Exception):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


async def _emit(emitter: Emitter, text: str, done: bool = False) -> None:
    if emitter:
        try:
            await emitter({"type": "status", "data": {"description": text, "done": done}})
        except Exception:
            pass


def _split_places(text: str) -> list:
    """Split 'Louisville, KY, London; Tokyo' into places, keeping 'City, State' and 'City, Country' together."""
    parts = [p.strip() for p in re.split(r"[;,]|\s+and\s+|\s+vs\.?\s+", str(text or "")) if p.strip()]
    qualifiers = {s.lower() for s in US_STATES.values()} | set(COUNTRY_ALIASES) | COUNTRIES
    places: list = []
    for part in parts:
        is_qualifier = (len(part) == 2 and part.isalpha()) or part.lower() in qualifiers
        if places and is_qualifier:
            places[-1] = f"{places[-1]}, {part}"
        else:
            places.append(part)
    return places


def _compass(degrees: Optional[float]) -> str:
    if degrees is None:
        return ""
    return COMPASS[int((float(degrees) % 360) / 22.5 + 0.5) % 16]


def _describe(code: Any, is_day: Any = 1) -> str:
    text, day_icon, night_icon = WEATHER_CODES.get(int(code) if code is not None else -1, ("Unknown", "", ""))
    return f"{text} {day_icon if is_day in (1, True, None) else night_icon}".strip()


def _uv_label(uv: Optional[float]) -> Optional[str]:
    if uv is None:
        return None
    level = "Low" if uv < 3 else "Moderate" if uv < 6 else "High" if uv < 8 else "Very high" if uv < 11 else "Extreme"
    return f"{uv:.0f} ({level})"


def _aqi_label(aqi: Optional[float]) -> tuple:
    if aqi is None:
        return None, None
    bands = [
        (50, "Good", "Air quality is fine for everyone."),
        (100, "Moderate", "Unusually sensitive people should limit long or heavy outdoor exertion."),
        (150, "Unhealthy for sensitive groups", "Children, older adults and people with heart or lung conditions should cut back outdoors."),
        (200, "Unhealthy", "Everyone should limit long or heavy outdoor exertion."),
        (300, "Very unhealthy", "Everyone should avoid long or heavy outdoor exertion."),
        (10_000, "Hazardous", "Everyone should stay indoors and keep activity low."),
    ]
    return next((label, advice) for limit, label, advice in bands if aqi <= limit)


def _parse_past_date(text: str, today: date) -> date:
    """Dates for past weather: ISO, US style, month names, 'yesterday', '3 days ago', 'last year'."""
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", str(text or "").strip().lower().rstrip("."))
    if t in ("", "today", "now"):
        return today
    if t == "yesterday":
        return today - timedelta(days=1)
    if t == "tomorrow" or t.startswith(("next ", "in ")):
        return today + timedelta(days=1)
    if t in ("last year", "a year ago", "this day last year", "this date last year"):
        try:
            return today.replace(year=today.year - 1)
        except ValueError:
            return today.replace(year=today.year - 1, day=28)
    m = re.fullmatch(r"(\d+)\s+(day|week|month|year)s?\s+ago", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit == "day":
            return today - timedelta(days=n)
        if unit == "week":
            return today - timedelta(weeks=n)
        months = n if unit == "month" else 12 * n
        total = today.year * 12 + today.month - 1 - months
        year, month = divmod(total, 12)
        return date(year, month + 1, min(today.day, 28))
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?", t)
    if m:
        year = int(m.group(3)) if m.group(3) else today.year
        year = year + 2000 if year < 100 else year
        candidate = date(year, int(m.group(1)), int(m.group(2)))
        return candidate if m.group(3) or candidate <= today else candidate.replace(year=year - 1)
    m = re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2}),?(?:\s+(\d{4}))?", t) or re.fullmatch(r"(\d{1,2})\s+([a-z]+)\.?,?(?:\s+(\d{4}))?", t)
    if m:
        first, second = m.group(1), m.group(2)
        month_word, day_num = (first, second) if first in MONTHS else (second, first)
        if month_word in MONTHS:
            year = int(m.group(3)) if m.group(3) else today.year
            candidate = date(year, MONTHS[month_word], int(day_num))
            return candidate if m.group(3) or candidate <= today else candidate.replace(year=year - 1)
    raise WeaverError(
        f"Could not understand the date '{text}'.",
        "Use a date like 2025-07-04, 7/4/2025, July 4 2025, yesterday, or 10 days ago.",
    )


class Tools:
    class Valves(BaseModel):
        default_location: str = Field(default="Louisville, KY", description="City used when none is given, for example 'Louisville, KY', 'Paris, France' or a postal code")
        unit_system: str = Field(default="imperial", description="imperial (°F, mph, inches) or metric (°C, km/h, mm)")
        enable_us_alerts: bool = Field(default=True, description="Include US National Weather Service alerts for US locations")

    class UserValves(BaseModel):
        user_location: Optional[str] = Field(default=None, description="Your city, used when you do not name one")
        user_unit_system: Optional[str] = Field(default=None, description="imperial or metric, overrides the default")

    def __init__(self):
        self.valves = self.Valves()
        self._geo_cache: dict = {}

    # ============= HELPERS =============

    def _user_valve(self, user: Optional[dict], name: str) -> Optional[str]:
        valves = (user or {}).get("valves")
        value = valves.get(name) if isinstance(valves, dict) else getattr(valves, name, None)
        return str(value).strip() if value else None

    def _units(self, user: Optional[dict]) -> dict:
        system = (self._user_valve(user, "user_unit_system") or self.valves.unit_system or "imperial").strip().lower()
        if system.startswith("metric"):
            return {"system": "metric", "temp": "°C", "wind": "km/h", "precip": "mm",
                    "params": {"temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm"}}
        return {"system": "imperial", "temp": "°F", "wind": "mph", "precip": "in",
                "params": {"temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "precipitation_unit": "inch"}}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=httpx.Timeout(15, connect=5), headers={"User-Agent": USER_AGENT})

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
            return {"error": f"The weather service did not answer: {type(e).__name__}", "hint": "Try again in a moment."}
        except Exception as e:
            await _emit(emitter, f"{label} failed", done=True)
            return {"error": f"{type(e).__name__}: {e}"}

    async def _geocode(self, client: httpx.AsyncClient, query: str, user: Optional[dict]) -> dict:
        text = str(query or "").strip() or self._user_valve(user, "user_location") or self.valves.default_location
        if not text:
            raise WeaverError("No location given.", "Name a city, or set a default location in the WeatherWeaver settings.")
        key = text.lower()
        if key in self._geo_cache:
            return self._geo_cache[key]
        parts = [p.strip() for p in text.split(",") if p.strip()]
        name, quals = (parts[0], parts[1:]) if parts else (text, [])
        if not quals:
            m = re.fullmatch(r"(.+?)\s+([A-Za-z]{2})", name)
            if m and m.group(2).upper() in US_STATES:
                name, quals = m.group(1), [m.group(2)]
        r = await client.get(GEOCODE_URL, params={"name": name, "count": 10, "language": "en", "format": "json"})
        r.raise_for_status()
        results = r.json().get("results") or []
        if quals and results:
            wanted = [{q.lower(), US_STATES.get(q.upper(), q).lower(), COUNTRY_ALIASES.get(q.lower(), q).lower()} for q in quals]

            def score(x: dict) -> int:
                fields = {str(x.get(k, "")).lower() for k in ("admin1", "admin2", "country", "country_code")}
                return sum(1 for options in wanted if fields & options)

            best = max(score(x) for x in results)
            if best:
                results = [x for x in results if score(x) == best]
        if not results:
            raise WeaverError(f"Could not find a place called '{text}'.", "Try 'City, State', 'City, Country', or a postal code.")
        top = results[0]
        label = []
        for part in (top.get("name"), top.get("admin1"), top.get("country")):
            if part and part not in label:
                label.append(part)
        place = {
            "label": ", ".join(label),
            "lat": top["latitude"],
            "lon": top["longitude"],
            "timezone": top.get("timezone") or "auto",
            "country_code": (top.get("country_code") or "").upper(),
            "elevation_m": top.get("elevation"),
        }
        self._geo_cache[key] = place
        return place

    async def _forecast(self, client: httpx.AsyncClient, place: dict, units: dict, **params: Any) -> dict:
        url = params.pop("_url", None) or FORECAST_URL
        query = {"latitude": place["lat"], "longitude": place["lon"], "timezone": place["timezone"], **units["params"]}
        query.update({k: v for k, v in params.items() if v is not None})
        r = await client.get(url, params=query)
        if r.status_code >= 400:
            try:
                reason = r.json().get("reason")
            except ValueError:
                reason = r.text[:200]
            raise WeaverError(f"The weather service rejected the request: {reason}")
        return r.json()

    async def _alerts(self, client: httpx.AsyncClient, place: dict) -> Optional[list]:
        """Active NWS alerts for a US point, or None outside the US or when turned off."""
        if not self.valves.enable_us_alerts or place.get("country_code") not in ("US", "PR"):
            return None
        r = await client.get(
            NWS_ALERTS_URL,
            params={"point": f"{place['lat']:.4f},{place['lon']:.4f}"},
            headers={"Accept": "application/geo+json"},
        )
        r.raise_for_status()
        zone = ZoneInfo(place["timezone"]) if place.get("timezone") not in (None, "auto") else None
        alerts = []
        for feature in r.json().get("features") or []:
            p = feature.get("properties") or {}

            def when(stamp: Optional[str]) -> Optional[str]:
                if not stamp:
                    return None
                moment = datetime.fromisoformat(stamp)
                if zone:
                    moment = moment.astimezone(zone)
                return moment.strftime("%a %-I:%M %p")

            alerts.append(
                {
                    "event": p.get("event"),
                    "severity": p.get("severity"),
                    "urgency": p.get("urgency"),
                    "headline": p.get("headline"),
                    "starts": when(p.get("onset") or p.get("effective")),
                    "ends": when(p.get("ends") or p.get("expires")),
                    "area": (p.get("areaDesc") or "")[:200],
                    "details": " ".join(str(p.get("description") or "").split())[:600],
                    "what_to_do": " ".join(str(p.get("instruction") or "").split())[:400] or None,
                }
            )
        return alerts

    def _visibility(self, meters: Optional[float], units: dict) -> Optional[str]:
        if meters is None:
            return None
        if units["system"] == "metric":
            return f"{meters / 1000:.0f} km" if meters >= 1000 else f"{meters:.0f} m"
        return f"{meters / 1609.344:.0f} mi" if meters >= 1609 else f"{meters * 3.28084:.0f} ft"

    def _pressure(self, hpa: Optional[float], units: dict) -> Optional[str]:
        if hpa is None:
            return None
        return f"{hpa:.0f} hPa" if units["system"] == "metric" else f"{hpa * 0.0295300:.2f} inHg"

    @staticmethod
    def _zone_name(stamp: Optional[str], place: dict, data: dict) -> str:
        """EDT rather than Open-Meteo's GMT-4."""
        try:
            return datetime.fromisoformat(stamp).replace(tzinfo=ZoneInfo(place["timezone"])).tzname()
        except Exception:
            return data.get("timezone_abbreviation", "")

    @staticmethod
    def _clock(stamp: Optional[str], minutes: bool = True) -> Optional[str]:
        if not stamp:
            return None
        moment = datetime.fromisoformat(stamp)
        return moment.strftime("%-I:%M %p" if minutes else "%-I %p")

    @staticmethod
    def _value(series: dict, key: str, i: int) -> Any:
        values = series.get(key) or []
        return values[i] if i < len(values) else None

    def _num(self, value: Optional[float], suffix: str = "", digits: int = 0) -> Optional[str]:
        if value is None:
            return None
        return f"{round(value, digits) if digits else round(value)}{suffix}"

    # ============= TOOLS =============

    async def get_current_weather(self, location: str = "", __user__: Optional[dict] = None, __event_emitter__: Emitter = None) -> dict:
        """
        Current weather right now: conditions, temperature, feels like, humidity, dew point, wind and gusts, pressure, visibility, UV, today's high and low, sunrise and sunset, and US severe weather alerts.
        :param location: City ("Louisville KY", "Paris, France") or postal code. Leave empty for the user's default location.
        """

        async def work(client: httpx.AsyncClient) -> dict:
            units = self._units(__user__)
            place = await self._geocode(client, location, __user__)
            data, alerts = await asyncio.gather(
                self._forecast(
                    client, place, units,
                    current="temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m,dew_point_2m,visibility,uv_index",
                    daily="temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max,precipitation_sum,uv_index_max",
                    forecast_days=1,
                ),
                self._safe_alerts(client, place),
            )
            c, d = data.get("current") or {}, data.get("daily") or {}
            t, w, p = units["temp"], units["wind"], units["precip"]
            out = {
                "place": place["label"],
                "as_of": f"{self._clock(c.get('time'))} {self._zone_name(c.get('time'), place, data)}".strip(),
                "conditions": _describe(c.get("weather_code"), c.get("is_day")),
                "temperature": self._num(c.get("temperature_2m"), t),
                "feels_like": self._num(c.get("apparent_temperature"), t),
                "humidity": self._num(c.get("relative_humidity_2m"), "%"),
                "dew_point": self._num(c.get("dew_point_2m"), t),
                "wind": f"{self._num(c.get('wind_speed_10m'))} {w} from {_compass(c.get('wind_direction_10m'))}, gusts {self._num(c.get('wind_gusts_10m'))} {w}",
                "pressure": self._pressure(c.get("pressure_msl"), units),
                "cloud_cover": self._num(c.get("cloud_cover"), "%"),
                "visibility": self._visibility(c.get("visibility"), units),
                "uv_index": _uv_label(c.get("uv_index")),
            }
            for key, label in (("rain", "rain"), ("showers", "showers"), ("snowfall", "snow")):
                amount = c.get(key) or 0
                if amount > 0:
                    out.setdefault("falling_now", []).append(f"{label} {amount} {p if key != 'snowfall' else ('cm' if units['system'] == 'metric' else 'in')}")
            out["today"] = {
                "high": self._num(self._value(d, "temperature_2m_max", 0), t),
                "low": self._num(self._value(d, "temperature_2m_min", 0), t),
                "chance_of_precipitation": self._num(self._value(d, "precipitation_probability_max", 0), "%"),
                "precipitation_total": self._num(self._value(d, "precipitation_sum", 0), f" {p}", 2),
                "max_uv": _uv_label(self._value(d, "uv_index_max", 0)),
                "sunrise": self._clock(self._value(d, "sunrise", 0)),
                "sunset": self._clock(self._value(d, "sunset", 0)),
            }
            if alerts is not None:
                out["alerts"] = [f"{a['event']}: {a['headline']}" for a in alerts] or "none"
            return {k: v for k, v in out.items() if v is not None}

        return await self._run(__event_emitter__, "Checking the weather", work)

    async def _safe_alerts(self, client: httpx.AsyncClient, place: dict) -> Optional[list]:
        try:
            return await self._alerts(client, place)
        except Exception:
            return None

    async def get_weather_forecast(
        self, location: str = "", days: int = 7, __user__: Optional[dict] = None, __event_emitter__: Emitter = None
    ) -> dict:
        """
        Daily forecast for up to 16 days: conditions, high and low, chance and amount of rain or snow, wind, UV, sunrise and sunset, plus the warmest and wettest days.
        :param location: City or postal code. Leave empty for the user's default location.
        :param days: Number of days, 1 to 16.
        """

        async def work(client: httpx.AsyncClient) -> dict:
            units = self._units(__user__)
            place = await self._geocode(client, location, __user__)
            count = max(1, min(16, int(days or 7)))
            data = await self._forecast(
                client, place, units,
                daily="weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,snowfall_sum,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,uv_index_max,sunrise,sunset",
                forecast_days=count,
            )
            d = data.get("daily") or {}
            t, w, p = units["temp"], units["wind"], units["precip"]
            snow_unit = "cm" if units["system"] == "metric" else "in"
            out_days = []
            for i, stamp in enumerate(d.get("time") or []):
                day = date.fromisoformat(stamp)
                label = "Today" if i == 0 else "Tomorrow" if i == 1 else day.strftime("%A")
                entry = {
                    "day": f"{label}, {day.strftime('%b %-d')}",
                    "conditions": _describe(self._value(d, "weather_code", i)),
                    "high": self._num(self._value(d, "temperature_2m_max", i), t),
                    "low": self._num(self._value(d, "temperature_2m_min", i), t),
                    "chance_of_precipitation": self._num(self._value(d, "precipitation_probability_max", i), "%"),
                    "wind": f"up to {self._num(self._value(d, 'wind_speed_10m_max', i))} {w} {_compass(self._value(d, 'wind_direction_10m_dominant', i))}, gusts {self._num(self._value(d, 'wind_gusts_10m_max', i))} {w}",
                    "uv": _uv_label(self._value(d, "uv_index_max", i)),
                    "sun": f"{self._clock(self._value(d, 'sunrise', i))} to {self._clock(self._value(d, 'sunset', i))}",
                }
                rain = self._value(d, "precipitation_sum", i) or 0
                snow = self._value(d, "snowfall_sum", i) or 0
                if rain > 0:
                    entry["precipitation"] = f"{round(rain, 2)} {p}"
                if snow > 0:
                    entry["snow"] = f"{round(snow, 1)} {snow_unit}"
                out_days.append({k: v for k, v in entry.items() if v is not None})
            highs = [(self._value(d, "temperature_2m_max", i), i) for i in range(len(out_days)) if self._value(d, "temperature_2m_max", i) is not None]
            wet = [(self._value(d, "precipitation_probability_max", i) or 0, i) for i in range(len(out_days))]
            summary = {}
            if highs:
                summary["warmest"] = out_days[max(highs)[1]]["day"]
                summary["coolest"] = out_days[min(highs)[1]]["day"]
            if wet and max(wet)[0] >= 30:
                summary["wettest"] = f"{out_days[max(wet)[1]]['day']} ({max(wet)[0]}% chance)"
            else:
                summary["wettest"] = "No day above a 30% chance of precipitation."
            return {"place": place["label"], "days": out_days, "summary": summary}

        return await self._run(__event_emitter__, "Getting the forecast", work)

    async def get_hourly_forecast(
        self, location: str = "", hours: int = 12, __user__: Optional[dict] = None, __event_emitter__: Emitter = None
    ) -> dict:
        """
        Hour by hour forecast from now: conditions, temperature, feels like, chance of rain, wind. Use for "will it rain this afternoon" or "what time does the rain start".
        :param location: City or postal code. Leave empty for the user's default location.
        :param hours: How many hours ahead, 1 to 48.
        """

        async def work(client: httpx.AsyncClient) -> dict:
            units = self._units(__user__)
            place = await self._geocode(client, location, __user__)
            count = max(1, min(48, int(hours or 12)))
            data = await self._forecast(
                client, place, units,
                hourly="temperature_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,is_day",
                forecast_hours=count,
            )
            h = data.get("hourly") or {}
            t, w, p = units["temp"], units["wind"], units["precip"]
            rows, first_day = [], None
            rain_start = None
            temps = []
            for i, stamp in enumerate(h.get("time") or []):
                moment = datetime.fromisoformat(stamp)
                first_day = first_day or moment.date()
                label = moment.strftime("%-I %p") + ("" if moment.date() == first_day else moment.strftime(" %a"))
                chance = self._value(h, "precipitation_probability", i)
                temp = self._value(h, "temperature_2m", i)
                if temp is not None:
                    temps.append((temp, label))
                if rain_start is None and chance is not None and chance >= 50:
                    rain_start = f"{label} ({chance}% chance)"
                row = {
                    "time": label,
                    "conditions": _describe(self._value(h, "weather_code", i), self._value(h, "is_day", i)),
                    "temp": self._num(temp, t),
                    "feels": self._num(self._value(h, "apparent_temperature", i), t),
                    "rain_chance": self._num(chance, "%"),
                    "wind": f"{self._num(self._value(h, 'wind_speed_10m', i))} {w}, gusts {self._num(self._value(h, 'wind_gusts_10m', i))}",
                }
                amount = self._value(h, "precipitation", i) or 0
                if amount > 0:
                    row["precipitation"] = f"{round(amount, 2)} {p}"
                rows.append(row)
            summary = {"precipitation": f"Likely from {rain_start}" if rain_start else f"No hour above a 50% chance in the next {count} hours."}
            if temps:
                summary["warmest"] = f"{self._num(max(temps)[0], t)} at {max(temps)[1]}"
                summary["coolest"] = f"{self._num(min(temps)[0], t)} at {min(temps)[1]}"
            return {"place": place["label"], "hours": rows, "summary": summary}

        return await self._run(__event_emitter__, "Getting the hourly forecast", work)

    async def get_weather_alerts(self, location: str = "", __user__: Optional[dict] = None, __event_emitter__: Emitter = None) -> dict:
        """
        Active severe weather alerts (warnings, watches, advisories) from the US National Weather Service, with what to do. US locations only.
        :param location: US city or ZIP code. Leave empty for the user's default location.
        """

        async def work(client: httpx.AsyncClient) -> dict:
            place = await self._geocode(client, location, __user__)
            if place.get("country_code") not in ("US", "PR"):
                return {"place": place["label"], "alerts": "Alerts are only available for US locations (National Weather Service)."}
            if not self.valves.enable_us_alerts:
                return {"place": place["label"], "alerts": "US alerts are turned off in the WeatherWeaver settings."}
            alerts = await self._alerts(client, place)
            return {"place": place["label"], "count": len(alerts or []), "alerts": alerts or "No active alerts."}

        return await self._run(__event_emitter__, "Checking weather alerts", work)

    async def get_air_quality(self, location: str = "", __user__: Optional[dict] = None, __event_emitter__: Emitter = None) -> dict:
        """
        Air quality right now: US AQI and European AQI with health advice, fine particles (PM2.5, PM10), ozone, nitrogen dioxide, UV, and pollen in Europe.
        :param location: City or postal code. Leave empty for the user's default location.
        """

        async def work(client: httpx.AsyncClient) -> dict:
            place = await self._geocode(client, location, __user__)
            r = await client.get(
                AIR_URL,
                params={
                    "latitude": place["lat"],
                    "longitude": place["lon"],
                    "timezone": place["timezone"],
                    "current": "us_aqi,european_aqi,pm2_5,pm10,ozone,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide,uv_index,alder_pollen,birch_pollen,grass_pollen,mugwort_pollen,olive_pollen,ragweed_pollen",
                },
            )
            r.raise_for_status()
            c = r.json().get("current") or {}
            category, advice = _aqi_label(c.get("us_aqi"))
            out = {
                "place": place["label"],
                "us_aqi": f"{c.get('us_aqi')} ({category})" if category else None,
                "advice": advice,
                "european_aqi": c.get("european_aqi"),
                "pm2_5": self._num(c.get("pm2_5"), " µg/m³", 1),
                "pm10": self._num(c.get("pm10"), " µg/m³", 1),
                "ozone": self._num(c.get("ozone"), " µg/m³"),
                "nitrogen_dioxide": self._num(c.get("nitrogen_dioxide"), " µg/m³", 1),
                "sulphur_dioxide": self._num(c.get("sulphur_dioxide"), " µg/m³", 1),
                "carbon_monoxide": self._num(c.get("carbon_monoxide"), " µg/m³"),
                "uv_index": _uv_label(c.get("uv_index")),
            }
            pollen = {name.replace("_pollen", ""): f"{value} grains/m³" for name, value in c.items() if name.endswith("_pollen") and value is not None}
            out["pollen"] = pollen or "Pollen data is only available in Europe."
            return {k: v for k, v in out.items() if v is not None}

        return await self._run(__event_emitter__, "Checking air quality", work)

    async def compare_weather(self, locations: str, __user__: Optional[dict] = None, __event_emitter__: Emitter = None) -> dict:
        """
        Compare the weather right now in several places side by side, with today's high and low and chance of rain, and which is warmest. Use for "where is it warmer" or travel planning.
        :param locations: Two or more places, comma separated, for example "Louisville KY, Miami, London".
        """

        async def work(client: httpx.AsyncClient) -> dict:
            units = self._units(__user__)
            names = _split_places(locations)[:8]
            if len(names) < 2:
                raise WeaverError("Give at least two places to compare.", "Separate places with commas, for example 'Louisville KY, Miami'.")

            async def one(name: str) -> dict:
                try:
                    place = await self._geocode(client, name, __user__)
                    data = await self._forecast(
                        client, place, units,
                        current="temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,wind_speed_10m",
                        daily="temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                        forecast_days=1,
                    )
                except Exception as e:
                    return {"place": name, "error": str(e)}
                c, d = data.get("current") or {}, data.get("daily") or {}
                t = units["temp"]
                return {
                    "place": place["label"],
                    "local_time": self._clock(c.get("time")),
                    "conditions": _describe(c.get("weather_code"), c.get("is_day")),
                    "temperature": self._num(c.get("temperature_2m"), t),
                    "feels_like": self._num(c.get("apparent_temperature"), t),
                    "humidity": self._num(c.get("relative_humidity_2m"), "%"),
                    "wind": f"{self._num(c.get('wind_speed_10m'))} {units['wind']}",
                    "today": f"high {self._num(self._value(d, 'temperature_2m_max', 0), t)}, low {self._num(self._value(d, 'temperature_2m_min', 0), t)}, {self._num(self._value(d, 'precipitation_probability_max', 0), '%')} chance of precipitation",
                    "_temp": c.get("temperature_2m"),
                }

            rows = await asyncio.gather(*(one(n) for n in names))
            ranked = sorted((r for r in rows if r.get("_temp") is not None), key=lambda r: r["_temp"], reverse=True)
            for r in rows:
                r.pop("_temp", None)
            out = {"places": rows}
            if ranked:
                out["warmest"] = ranked[0]["place"]
                out["coldest"] = ranked[-1]["place"]
            return out

        return await self._run(__event_emitter__, "Comparing the weather", work)

    async def get_past_weather(
        self,
        location: str = "",
        date_text: str = "yesterday",
        end_date: str = "",
        __user__: Optional[dict] = None,
        __event_emitter__: Emitter = None,
    ) -> dict:
        """
        Weather on a past date or date range, back to 1940: conditions, high, low and average temperature, rain, snow and wind. Use for "what was the weather on July 4 2025" or "how much rain fell last week".
        :param location: City or postal code. Leave empty for the user's default location.
        :param date_text: The date, or the first date of a range: "yesterday", "2025-07-04", "July 4 2025", "10 days ago", "last year".
        :param end_date: Last date of a range (up to 31 days). Leave empty for a single day.
        """

        async def work(client: httpx.AsyncClient) -> dict:
            units = self._units(__user__)
            place = await self._geocode(client, location, __user__)
            zone = ZoneInfo(place["timezone"]) if place["timezone"] != "auto" else None
            today = datetime.now(zone).date() if zone else date.today()
            start = _parse_past_date(date_text, today)
            end = _parse_past_date(end_date, today) if end_date.strip() else start
            if end < start:
                start, end = end, start
            if start >= today:
                raise WeaverError("That date is not in the past.", "Use get_weather_forecast for today and future days.")
            end = min(end, today - timedelta(days=1), start + timedelta(days=30))
            if start < date(1940, 1, 1):
                raise WeaverError("Weather history starts in 1940.")
            daily = "weather_code,temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,snowfall_sum,wind_speed_10m_max,wind_gusts_10m_max"
            recent = end >= today - timedelta(days=60)
            data = await self._forecast(
                client, place, units,
                _url=FORECAST_URL if recent else ARCHIVE_URL,
                daily=daily,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )
            d = data.get("daily") or {}
            t, w, p = units["temp"], units["wind"], units["precip"]
            snow_unit = "cm" if units["system"] == "metric" else "in"
            rows = []
            for i, stamp in enumerate(d.get("time") or []):
                if self._value(d, "temperature_2m_max", i) is None:
                    continue
                row = {
                    "date": date.fromisoformat(stamp).strftime("%a, %b %-d, %Y"),
                    "conditions": _describe(self._value(d, "weather_code", i)),
                    "high": self._num(self._value(d, "temperature_2m_max", i), t),
                    "low": self._num(self._value(d, "temperature_2m_min", i), t),
                    "average": self._num(self._value(d, "temperature_2m_mean", i), t),
                    "precipitation": f"{round(self._value(d, 'precipitation_sum', i) or 0, 2)} {p}",
                    "max_wind": f"{self._num(self._value(d, 'wind_speed_10m_max', i))} {w}, gusts {self._num(self._value(d, 'wind_gusts_10m_max', i))} {w}",
                }
                snow = self._value(d, "snowfall_sum", i) or 0
                if snow > 0:
                    row["snow"] = f"{round(snow, 1)} {snow_unit}"
                rows.append(row)
            if not rows:
                raise WeaverError("No weather history was found for that date yet.", "Very recent days can take a few days to appear; try an earlier date.")
            out = {"place": place["label"], "days": rows}
            if len(rows) > 1:
                highs = [x for x in (d.get("temperature_2m_max") or []) if x is not None]
                lows = [x for x in (d.get("temperature_2m_min") or []) if x is not None]
                rain = sum(x for x in (d.get("precipitation_sum") or []) if x)
                snow = sum(x for x in (d.get("snowfall_sum") or []) if x)
                out["totals"] = {
                    "highest": self._num(max(highs), t),
                    "lowest": self._num(min(lows), t),
                    "total_precipitation": f"{round(rain, 2)} {p}",
                    "total_snow": f"{round(snow, 1)} {snow_unit}" if snow else None,
                    "days_with_precipitation": sum(1 for x in (d.get("precipitation_sum") or []) if x and x > 0),
                }
            return out

        return await self._run(__event_emitter__, "Looking up past weather", work)

    async def show_weather_dashboard(self, location: str = "", __user__: Optional[dict] = None, __event_emitter__: Emitter = None) -> Any:
        """
        Show a visual weather dashboard in the chat: current conditions, the next 12 hours, the 7-day forecast, air quality, and any US alerts. Use when the user wants to see the weather.
        :param location: City or postal code. Leave empty for the user's default location.
        """

        async def work(client: httpx.AsyncClient) -> Any:
            from fastapi.responses import HTMLResponse

            units = self._units(__user__)
            place = await self._geocode(client, location, __user__)
            data, alerts, air = await asyncio.gather(
                self._forecast(
                    client, place, units,
                    current="temperature_2m,apparent_temperature,relative_humidity_2m,is_day,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,uv_index",
                    hourly="temperature_2m,precipitation_probability,weather_code,is_day",
                    daily="weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
                    forecast_days=7,
                    forecast_hours=12,
                ),
                self._safe_alerts(client, place),
                self._safe_air(client, place),
            )
            c, h, d = data.get("current") or {}, data.get("hourly") or {}, data.get("daily") or {}
            t, w = units["temp"], units["wind"]
            esc = html.escape
            icon = _describe(c.get("weather_code"), c.get("is_day")).split(" ")[-1]
            condition = _describe(c.get("weather_code"), c.get("is_day")).rsplit(" ", 1)[0]

            hours_html = ""
            for i, stamp in enumerate(h.get("time") or []):
                moment = datetime.fromisoformat(stamp)
                hour_icon = _describe(self._value(h, "weather_code", i), self._value(h, "is_day", i)).split(" ")[-1]
                chance = self._value(h, "precipitation_probability", i)
                hours_html += (
                    f'<div class="hr"><div class="muted">{"Now" if i == 0 else moment.strftime("%-I %p")}</div>'
                    f'<div class="ic">{hour_icon}</div><div>{self._num(self._value(h, "temperature_2m", i), "°")}</div>'
                    f'<div class="rain">{"" if not chance else f"💧{chance}%"}</div></div>'
                )

            highs = [x for x in (d.get("temperature_2m_max") or []) if x is not None]
            lows = [x for x in (d.get("temperature_2m_min") or []) if x is not None]
            span_lo, span_hi = (min(lows), max(highs)) if highs and lows else (0, 1)
            span = max(span_hi - span_lo, 1)
            days_html = ""
            for i, stamp in enumerate(d.get("time") or []):
                day = date.fromisoformat(stamp)
                lo, hi = self._value(d, "temperature_2m_min", i), self._value(d, "temperature_2m_max", i)
                if lo is None or hi is None:
                    continue
                left, width = (lo - span_lo) / span * 100, max((hi - lo) / span * 100, 4)
                chance = self._value(d, "precipitation_probability_max", i)
                days_html += (
                    f'<div class="day"><div class="dn">{"Today" if i == 0 else day.strftime("%a")}</div>'
                    f'<div class="ic">{_describe(self._value(d, "weather_code", i)).split(" ")[-1]}</div>'
                    f'<div class="rain">{"" if not chance else f"💧{chance}%"}</div>'
                    f'<div class="lo">{round(lo)}°</div><div class="track"><span style="left:{left:.0f}%;width:{width:.0f}%"></span></div>'
                    f'<div class="hi">{round(hi)}°</div></div>'
                )

            alert_html = ""
            for a in alerts or []:
                alert_html += f'<div class="alert">⚠️ <b>{esc(str(a["event"]))}</b>: {esc(str(a["headline"] or ""))}</div>'
            air_html = ""
            if air and air.get("us_aqi") is not None:
                category, _ = _aqi_label(air["us_aqi"])
                air_html = f'<span class="chip">Air quality {air["us_aqi"]} · {esc(category)}</span>'

            page = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
:root {{ --bg:#ffffff; --fg:#1f2328; --muted:#656d76; --card:#f6f8fa; --line:#d0d7de; --accent:#0969da; --warm:#d4a72c; --cool:#54aeff; --warn:#cf222e; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0d1117; --fg:#e6edf3; --muted:#8d96a0; --card:#161b22; --line:#30363d; --accent:#4493f8; }} }}
body {{ margin:0; padding:14px; font:14px system-ui,sans-serif; background:var(--bg); color:var(--fg); }}
.top {{ display:flex; align-items:center; gap:16px; flex-wrap:wrap; }}
.big {{ font-size:54px; line-height:1; }} .temp {{ font-size:44px; font-weight:600; }}
.muted {{ color:var(--muted); font-size:12px; }} .place {{ font-weight:600; font-size:16px; }}
.facts {{ display:flex; gap:14px; flex-wrap:wrap; margin:8px 0 12px; font-size:13px; color:var(--muted); }}
.chip {{ display:inline-block; padding:2px 8px; border:1px solid var(--line); border-radius:999px; font-size:12px; }}
.alert {{ background:rgba(207,34,46,.12); border:1px solid var(--warn); border-radius:8px; padding:8px; margin:6px 0; font-size:13px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px; margin-top:10px; }}
.hours {{ display:flex; gap:6px; overflow-x:auto; }} .hr {{ min-width:52px; text-align:center; font-size:13px; }}
.ic {{ font-size:22px; }} .rain {{ font-size:11px; color:var(--accent); min-height:14px; }}
.day {{ display:grid; grid-template-columns:52px 30px 48px 34px 1fr 34px; align-items:center; gap:6px; padding:4px 0; border-bottom:1px solid var(--line); }}
.day:last-child {{ border-bottom:0; }} .dn {{ font-weight:600; }} .lo {{ text-align:right; color:var(--muted); }}
.track {{ position:relative; height:6px; background:var(--line); border-radius:3px; }}
.track span {{ position:absolute; top:0; height:6px; border-radius:3px; background:linear-gradient(90deg,var(--cool),var(--warm)); }}
</style></head><body>
<div class="top"><div class="big">{icon}</div><div><div class="place">{esc(place["label"])}</div>
<div class="temp">{self._num(c.get("temperature_2m"), t)}</div><div class="muted">{esc(condition)} · feels like {self._num(c.get("apparent_temperature"), t)}</div></div></div>
<div class="facts"><span>💧 {self._num(c.get("relative_humidity_2m"), "%")}</span><span>💨 {self._num(c.get("wind_speed_10m"))} {w} {_compass(c.get("wind_direction_10m"))}</span>
<span>UV {esc(str(_uv_label(c.get("uv_index")) or "n/a"))}</span><span>🌅 {self._clock(self._value(d, "sunrise", 0))}</span><span>🌇 {self._clock(self._value(d, "sunset", 0))}</span>{air_html}</div>
{alert_html}
<div class="card"><div class="muted" style="margin-bottom:6px">Next 12 hours</div><div class="hours">{hours_html}</div></div>
<div class="card"><div class="muted" style="margin-bottom:4px">7 days</div>{days_html}</div>
<script>
function reportHeight() {{ parent.postMessage({{ type: 'iframe:height', height: document.documentElement.scrollHeight }}, '*'); }}
window.addEventListener('load', reportHeight); new ResizeObserver(reportHeight).observe(document.body);
</script></body></html>"""
            context = {
                "shown": f"A weather dashboard for {place['label']} is visible to the user.",
                "now": f"{condition}, {self._num(c.get('temperature_2m'), t)}, feels like {self._num(c.get('apparent_temperature'), t)}",
                "today": f"high {self._num(self._value(d, 'temperature_2m_max', 0), t)}, low {self._num(self._value(d, 'temperature_2m_min', 0), t)}",
                "alerts": [a["event"] for a in alerts] if alerts else "none",
            }
            return HTMLResponse(content=page, headers={"Content-Disposition": "inline"}), context

        return await self._run(__event_emitter__, "Building the weather dashboard", work)

    async def _safe_air(self, client: httpx.AsyncClient, place: dict) -> Optional[dict]:
        try:
            r = await client.get(AIR_URL, params={"latitude": place["lat"], "longitude": place["lon"], "current": "us_aqi"})
            r.raise_for_status()
            return r.json().get("current")
        except Exception:
            return None
