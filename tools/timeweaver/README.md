# TimeWeaver: Time, Dates and Time Zones for Open WebUI

Current time anywhere by city, zone or abbreviation, time zone conversion, date math, countdowns, public holidays for 100+ countries, sunrise, sunset, twilight and moon phase, and a live world clock in the chat. No API keys, no extra packages.

**Version:** 2.0.1
**Author:** PureGrain at SLA Ops, LLC
**License:** MIT

## What Changed from 1.x

| | 1.x | 2.0 |
|---|---|---|
| Places | Only zone names like `America/New_York`; "New York" or "Louisville" crashed | Cities ("Tokyo", "Louisville KY", "Paris, France"), zone names, abbreviations ("PST"), and offsets ("UTC+5:30") |
| "EST" in summer | Answered in fixed UTC-5, an hour off during daylight saving time | Read as US Eastern time, so daylight saving is applied, and the answer says so |
| Your time zone | Per-user setting was never read; everyone got the default | Uses your TimeWeaver user setting, then your Open WebUI profile time zone, then the default |
| Functions | 3 near-identical (date, time, date and time) | 7: time anywhere, conversion, date math, countdowns, holidays, sun and moon, world clock |
| Execution | Synchronous | Async, with status updates in the chat |
| Errors | Crashed on bad input | Clear message with a hint |

Function names: `get_current_date` and `get_current_datetime` are now both covered by `get_current_time`. If a system prompt names the old ones, update it.

## Features

| Function | What it does |
|---|---|
| `get_current_time` | Date and time for you or any list of places, with UTC offset, daylight saving, hours ahead or behind you, and the next clock change |
| `convert_time` | "3pm in Louisville to London and Tokyo", with next-day and previous-day flags |
| `calculate_date` | Add or subtract days, weeks, months, years or business days, or look up a date: weekday, week number, quarter, days left in the year, holiday |
| `time_between` | Countdowns and durations: days, weeks, calendar months and years, business days, and hours when times are given |
| `get_holidays` | Official public holidays for 100+ countries, with days until each (from Nager.Date) |
| `get_sun_and_moon` | Sunrise, sunset, solar noon, day length and change from yesterday, dawn and dusk, golden hours, moon phase with next full and new moon. Works for any date, including polar day and night |
| `show_world_clock` | Live, ticking clocks drawn in the chat, shaded for night |

Dates can be written as `2026-12-25`, `12/25`, `Dec 25 2026`, `25 December`, `next friday`, `in 3 weeks`, `2 days ago`, or a holiday name such as `thanksgiving`, `easter`, `christmas`, `memorial day` or `mother's day`.

## Installation

1. In Open WebUI go to **Workspace > Tools > +**, paste in `timeweaver.py`, and click **Save**. (Or click **Get** on the tool's openwebui.com page.)
2. Enable it on your model (**Workspace > Models >** edit **> Tools**) or per chat with the **+** button.
3. Set **Function Calling** to **Native** in the model's **Advanced Params**.

Requires Open WebUI 0.10.0 or newer. Network access is used only for city lookups (Open-Meteo geocoding) and holidays (Nager.Date); everything else is calculated locally.

## Settings

**Valves** (admin, gear icon on the tool):

| Valve | Default | Purpose |
|---|---|---|
| `default_timezone` | empty | Fallback zone, for example `America/New_York`. Empty uses each user's Open WebUI time zone, then UTC |
| `time_format` | `12h` | `12h` (3:05 PM) or `24h` (15:05) |
| `default_country` | `US` | Country for `get_holidays` when none is named |

**User Valves** (each user, in **Chat Controls > Valves**):

| Valve | Purpose |
|---|---|
| `user_timezone` | Your time zone. Overrides everything else |
| `user_location` | Your city, used for sunrise and sunset when no place is named |

## Example Questions

- "What time is it?" / "What time is it in Tokyo and London?"
- "If it's 3pm here, what time is it in Sydney?"
- "What's the date 90 days from today?" / "What day of the week is July 4 2027?"
- "How many days until Christmas?" / "How long since March 1 2019?"
- "What are the public holidays in Germany this year?"
- "When is sunset tonight? When's golden hour?" / "What's the moon phase?"
- "Show me a world clock for Louisville, London and Tokyo."

## Accuracy Notes

- Sun times are calculated with the NOAA solar equations and are accurate to about a minute.
- Moon phase is calculated from the mean lunar cycle and is accurate to within about a day.
- Business days count Monday to Friday and do not skip holidays.
- Abbreviations are ambiguous worldwide (IST is read as India, CST as US Central); the answer always says how it read them.

## Changelog

### Version 2.0.1 (2026-10-26)

- The world clock's summary for the model now tells it the clock is already on screen, so small models stop printing the raw data as JSON or tags

### Version 2.0.0 (2026-10-26)

- City names, abbreviations and UTC offsets accepted everywhere; EST, CST, MST and PST now follow daylight saving time
- Fixed per-user settings never being read; now also uses the Open WebUI profile time zone
- New: `convert_time`, `calculate_date`, `time_between`, `get_holidays`, `get_sun_and_moon`, `show_world_clock`
- `get_current_time` replaces `get_current_date` and `get_current_datetime`, and handles several places at once
- Async with status updates; clear errors instead of crashes

### Version 1.1.0

- Added `get_current_datetime`

## License

MIT. See the LICENSE file in the repository root.
