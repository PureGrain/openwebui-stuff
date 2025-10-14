"""
title: TimeWeaver - Timezone & Date/Time Tool
author: PureGrain at SLA Ops, LLC
author_url: https://github.com/PureGrain
repo_url: https://github.com/PureGrain/my-openwebui
funding_url: https://github.com/open-webui
version: 1.1.0
license: MIT
required_open_webui_version: 0.3.9
description: Weaves timezone rules, DST transitions, and temporal calculations into a seamless fabric of accurate date and time information for any location worldwide.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        default_timezone: str = Field(
            default="UTC",
            description="Default timezone for date/time operations (e.g., 'UTC', 'America/New_York', 'Europe/London')",
        )

    class UserValves(BaseModel):
        user_timezone: Optional[str] = Field(
            default=None,
            description="User-specific timezone override (e.g., 'America/Los_Angeles', 'Asia/Tokyo')",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.user_valves = self.UserValves()

    def _get_timezone(self) -> ZoneInfo:
        """
        Get the appropriate timezone, prioritizing user settings over defaults.
        :return: ZoneInfo object for the selected timezone
        """
        tz_string = self.user_valves.user_timezone or self.valves.default_timezone
        return ZoneInfo(tz_string)

    def get_current_date(self, timezone: Optional[str] = None) -> str:
        """
        Get the current date in the specified timezone.
        :param timezone: Optional timezone string (e.g., 'America/New_York'). If None, uses configured timezone.
        :return: The current date as a string.
        """
        if timezone:
            tz = ZoneInfo(timezone)
        else:
            tz = self._get_timezone()

        current_date = datetime.now(tz).strftime("%A, %B %d, %Y")
        tz_name = datetime.now(tz).strftime("%Z")
        return f"Today's date is {current_date} ({tz_name})"

    def get_current_time(self, timezone: Optional[str] = None) -> str:
        """
        Get the current time in the specified timezone.
        :param timezone: Optional timezone string (e.g., 'Europe/London'). If None, uses configured timezone.
        :return: The current time as a string.
        """
        if timezone:
            tz = ZoneInfo(timezone)
        else:
            tz = self._get_timezone()

        now = datetime.now(tz)
        current_time = now.strftime("%H:%M:%S")
        tz_name = now.strftime("%Z")
        offset = now.strftime("%z")
        return f"Current Time: {current_time} {tz_name} (UTC{offset[:3]}:{offset[3:]})"

    def get_current_datetime(self, timezone: Optional[str] = None) -> str:
        """
        Get both the current date and time in the specified timezone.
        :param timezone: Optional timezone string (e.g., 'Asia/Tokyo'). If None, uses configured timezone.
        :return: The current date and time as a string.
        """
        if timezone:
            tz = ZoneInfo(timezone)
        else:
            tz = self._get_timezone()

        now = datetime.now(tz)
        current_datetime = now.strftime("%A, %B %d, %Y at %H:%M:%S")
        tz_name = now.strftime("%Z")
        offset = now.strftime("%z")
        return f"{current_datetime} {tz_name} (UTC{offset[:3]}:{offset[3:]})"
