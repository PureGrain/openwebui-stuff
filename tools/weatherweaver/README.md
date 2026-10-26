# WeatherWeaver: Weather for Open WebUI

Current conditions, hour by hour and 16-day forecasts, US severe weather alerts, air quality and pollen, past weather back to 1940, side-by-side city comparison, and a weather dashboard in the chat. Worldwide, free, no API keys, no extra packages.

**Version:** 2.0.0
**Author:** PureGrain at SLA Ops, LLC
**License:** MIT
**Credit:** original idea from **Keyless Weather** by spyci

## What Changed from 1.x

| | 1.x | 2.0 |
|---|---|---|
| Metric units | Current weather always came back in °F, even with metric set | Every function follows the unit setting |
| Places | "Louisville KY" not found; no way to tell which Louisville was used | "Louisville KY", "Paris, France", ZIP and postal codes; the answer names the exact place |
| Per-user settings | Never read | Your location and units from User Valves are used |
| Requests | Synchronous, no timeout (could hang Open WebUI) | Async with timeouts and status updates |
| Errors | Could crash on missing data; debug lines printed to the log | Clear messages with hints; no debug output |
| Functions | 2 | 8: current, daily, hourly, alerts, air quality, compare, past weather, dashboard |

The location argument was renamed from `city` to `location`. If a system prompt names the old argument, update it.

## Features

| Function | What it does |
|---|---|
| `get_current_weather` | Conditions, temperature, feels like, humidity, dew point, wind with direction and gusts, pressure, cloud cover, visibility, UV, today's high and low, chance of rain, sunrise and sunset, and active US alerts |
| `get_weather_forecast` | Up to 16 days: conditions, high and low, chance and amount of rain or snow, wind, UV, sunrise and sunset, plus warmest, coolest and wettest day |
| `get_hourly_forecast` | Up to 48 hours from now, with when rain becomes likely and the warmest and coolest hour |
| `get_weather_alerts` | Active National Weather Service warnings, watches and advisories with timing and what to do (US only) |
| `get_air_quality` | US AQI with health advice, European AQI, PM2.5, PM10, ozone, nitrogen dioxide, sulphur dioxide, carbon monoxide, UV, and pollen in Europe |
| `compare_weather` | Up to 8 places side by side, with which is warmest and coldest |
| `get_past_weather` | Any day or range up to 31 days, back to 1940: conditions, high, low, average, rain, snow, wind, and totals |
| `show_weather_dashboard` | Current conditions, the next 12 hours and the 7-day forecast drawn in the chat, with air quality and alerts |

## Installation

1. In Open WebUI go to **Workspace > Tools > +**, paste in `weatherweaver.py`, and click **Save**. (Or click **Get** on the tool's openwebui.com page.)
2. Enable it on your model (**Workspace > Models >** edit **> Tools**) or per chat with the **+** button.
3. Set **Function Calling** to **Native** in the model's **Advanced Params**.

Requires Open WebUI 0.10.0 or newer and outbound internet access to `open-meteo.com` and, for US alerts, `api.weather.gov`.

## Settings

**Valves** (admin, gear icon on the tool):

| Valve | Default | Purpose |
|---|---|---|
| `default_location` | `Louisville, KY` | Place used when none is named. City, "City, State", "City, Country" or postal code |
| `unit_system` | `imperial` | `imperial` (°F, mph, inches, inHg, miles) or `metric` (°C, km/h, mm, hPa, km) |
| `enable_us_alerts` | on | Include National Weather Service alerts for US places |

**User Valves** (each user, in **Chat Controls > Valves**):

| Valve | Purpose |
|---|---|
| `user_location` | Your place, used when you do not name one |
| `user_unit_system` | `imperial` or `metric`, overrides the default |

## Example Questions

- "What's the weather?" / "Weather in Paris, France?"
- "Will it rain this afternoon? What time does it start?"
- "What's the forecast for the next 10 days? Which day is warmest?"
- "Are there any weather alerts for 40202?"
- "How's the air quality? Is pollen bad in Berlin?"
- "Is it warmer in Miami or San Diego right now?"
- "What was the weather on July 4 2025?" / "How much rain fell last week?"
- "Show me the weather dashboard."

## Data Sources

- Forecasts, current conditions, history and air quality: [Open-Meteo](https://open-meteo.com) (free for non-commercial use, no key)
- US alerts: [National Weather Service API](https://www.weather.gov/documentation/services-web-api)
- Place lookup: Open-Meteo geocoding

## Changelog

### Version 2.0.0 (2026-10-26)

- Fixed current weather ignoring metric units
- Fixed per-user location and units never being read
- Smarter place matching ("City ST", "City, Country", postal codes) and the resolved place is named in every answer
- New: `get_hourly_forecast`, `get_weather_alerts`, `get_air_quality`, `compare_weather`, `get_past_weather`, `show_weather_dashboard`
- Current weather adds dew point, visibility, UV, pressure in inHg for imperial, wind direction, today's high, low and sun times
- Forecast adds snow, wind direction, and warmest, coolest and wettest day
- Async with timeouts and status updates; removed debug logging; `city` argument renamed to `location`

### Version 1.0.4

- Current weather and daily forecast from Open-Meteo

## License

MIT. See the LICENSE file in the repository root.
