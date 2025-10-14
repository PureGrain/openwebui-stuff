
# TimeWeaver Tool for OpenWebUI

Weaves timezone complexity into simplicity. Delivering accurate dates and times anywhere, with DST intelligence woven in.

## What It Does

- Timezone-aware date/time for Open WebUI with automatic DST handling.
- Accurate date and time information worldwide, using Python's zoneinfo and DST rules.

## Quick Start

1. Download `timeweaver-export.json` from this folder.
2. In your Open WebUI panel, go to the Tools section and use the import feature to add the tool from the JSON file.
3. The tool will appear in your Open WebUI tools list, ready to use.
4. Default timezone is UTC.

## Configuration

To change the default timezone, edit the following line in the code:

```python
default="America/New_York"  # Change to your timezone, e.g., "Europe/London"
```

Find your timezone: [List of tz database time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

Examples: America/New_York, Europe/London, Asia/Tokyo, America/Los_Angeles, Australia/Sydney

## Usage

Basic:

```python
tools.get_current_date()           # Just the date
tools.get_current_time()           # Just the time
tools.get_current_datetime()       # Date and time together
```

Specify timezone:

```python
tools.get_current_date(timezone="Asia/Tokyo")
tools.get_current_time(timezone="Europe/London")
tools.get_current_datetime(timezone="Asia/Tokyo")
```

Output examples:

```text
Today's date is Monday, October 13, 2025 (EDT)
Current Time: 14:32:15 EDT (UTC-04:00)
Monday, October 13, 2025 at 14:32:15 EDT (UTC-04:00)
Tuesday, October 14, 2025 at 03:32:15 JST (UTC+09:00)
```

All functions work offline using your system clock—no internet needed!

## Version

- 1.1.0 (adds get_current_datetime)

## Requirements

- Python 3.9+

## Troubleshooting

- Invalid timezone? Use Continent/City format
- Wrong time? Check timezone setting in UserValves
- DST is automatic

---
