"""
title: WeatherWeaver - Enhanced Weather Tool
author: PureGrain at SLA Ops, LLC
author_url: https://github.com/PureGrain
repo_url: https://github.com/PureGrain/my-openwebui/tree/main/tools/weatherweaver
funding_url: https://github.com/open-webui
version: 1.0.4
license: MIT
required_open_webui_version: 0.3.9
description: Enhanced weather tool with comprehensive data from Open-Meteo (free, no API key required).

# Credit for original code and idea:
title: Keyless Weather
author: spyci
"""

import requests
import urllib.parse
import datetime
from pydantic import BaseModel, Field
from typing import Optional


def get_city_info(city: str):
    """Get coordinates and timezone for a city."""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1&language=en&format=json"
    response = requests.get(url)

    if response.status_code == 200:
        try:
            data = response.json()["results"][0]
            return data["latitude"], data["longitude"], data["timezone"]
        except (KeyError, IndexError):
            print(f"City '{city}' not found")
            return None
    else:
        print(f"Failed to retrieve data for city '{city}': {response.status_code}")
        return None


wmo_weather_codes = {
    "0": "Clear sky",
    "1": "Mainly clear",
    "2": "Partly cloudy",
    "3": "Overcast",
    "45": "Foggy",
    "48": "Depositing rime fog",
    "51": "Light drizzle",
    "53": "Moderate drizzle",
    "55": "Dense drizzle",
    "56": "Light freezing drizzle",
    "57": "Dense freezing drizzle",
    "61": "Slight rain",
    "63": "Moderate rain",
    "65": "Heavy rain",
    "66": "Light freezing rain",
    "67": "Heavy freezing rain",
    "71": "Slight snow",
    "73": "Moderate snow",
    "75": "Heavy snow",
    "77": "Snow grains",
    "80": "Slight rain showers",
    "81": "Moderate rain showers",
    "82": "Violent rain showers",
    "85": "Slight snow showers",
    "86": "Heavy snow showers",
    "95": "Thunderstorm",
    "96": "Thunderstorm with slight hail",
    "99": "Thunderstorm with heavy hail",
}


def fetch_weather_data(base_url, params):
    """Fetch data from Open-Meteo API."""
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            return f"Error fetching weather data: {data.get('reason', 'Unknown error')}"
        return data
    except requests.RequestException as e:
        return f"Error fetching weather data: {str(e)}"


def format_date(date_str, date_format="%Y-%m-%dT%H:%M", output_format="%I:%M %p"):
    """Format datetime string."""
    dt = datetime.datetime.strptime(date_str, date_format)
    return dt.strftime(output_format)


class Tools:
    class Valves(BaseModel):
        default_location: str = Field(
            default="Louisville",
            description="Default city for weather lookups (e.g., 'Louisville', 'New York', 'Tokyo')",
        )
        unit_system: str = Field(
            default="imperial",
            description="Default is: Imperial -- Unit system: 'imperial' (°F, mph, inches) or 'metric' (°C, km/h, mm)",
        )

    class UserValves(BaseModel):
        user_location: Optional[str] = Field(
            default=None,
            description="Your preferred city for weather lookups (overrides default)",
        )
        user_unit_system: Optional[str] = Field(
            default=None,
            description="Your preferred units: 'imperial' or 'metric' (overrides default)",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.user_valves = self.UserValves()
        print(f"DEBUG: Initialized user_valves: {self.user_valves}")
        self.citation = True

    def _get_location(self, city: Optional[str] = None) -> str:
        """Get location: provided > user preference > default."""
        print(f"DEBUG: city={city}, user_location={self.user_valves.user_location}, default_location={self.valves.default_location}")
        if city:
            return city
        return self.user_valves.user_location or self.valves.default_location

    def _get_units(self) -> dict:
        """Get unit settings based on system preference."""
        system = self.user_valves.user_unit_system or self.valves.unit_system

        if system == "metric":
            return {
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
                "temp_symbol": "°C",
                "wind_symbol": "km/h",
                "precip_symbol": "mm",
            }
        else:  # imperial
            return {
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "temp_symbol": "°F",
                "wind_symbol": "mph",
                "precip_symbol": "in",
            }

    def get_current_weather(self, city: Optional[str] = None) -> str:
        """
        Get comprehensive current weather for a given city.
        :param city: The name of the city to get the weather for (optional).
        :return: Current weather information or error message.
        """
        city = self._get_location(city)
        if not city:
            return "Please provide a city name or set a default location in settings."

        city_info = get_city_info(city)
        if not city_info:
            return f"Could not find city: {city}"

        lat, lng, tmzone = city_info

        base_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lng,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "timezone": tmzone,
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "forecast_days": 1,
        }

        data = fetch_weather_data(base_url, params)
        if isinstance(data, str):
            return data

        current = data["current"]
        units = data["current_units"]

        formatted_timestamp = format_date(current["time"])
        weather_desc = wmo_weather_codes.get(str(current["weather_code"]), "Unknown")

        # Build comprehensive weather report
        temp = round(current["temperature_2m"])
        feels_like = round(current["apparent_temperature"])
        humidity = round(current["relative_humidity_2m"])
        cloud_cover = round(current["cloud_cover"])
        pressure = round(current["pressure_msl"], 1)
        wind_speed = round(current["wind_speed_10m"])
        wind_gusts = round(current["wind_gusts_10m"])

        report = f"""Current weather for {city} as of {formatted_timestamp} {data['timezone_abbreviation']}:

**Conditions:** {weather_desc}
**Temperature:** {temp}°F (Feels like {feels_like}°F)
**Humidity:** {humidity}%
**Cloud Cover:** {cloud_cover}%
**Pressure:** {pressure} hPa
**Wind:** {wind_speed} mph, gusts to {wind_gusts} mph"""

        # Add precipitation if present
        precip = current.get("precipitation", 0)
        rain = current.get("rain", 0)
        showers = current.get("showers", 0)
        snowfall = current.get("snowfall", 0)

        if precip > 0 or rain > 0 or showers > 0 or snowfall > 0:
            report += "\n**Precipitation:**"
            if rain > 0:
                report += f"\n• Rain: {round(rain, 2)} in"
            if showers > 0:
                report += f"\n• Showers: {round(showers, 2)} in"
            if snowfall > 0:
                report += f"\n• Snow: {round(snowfall, 2)} in"

        return report

    def get_weather_forecast(self, city: Optional[str] = None, days: int = 7) -> str:
        """
        Get weather forecast for a city.
        :param city: City name (optional - uses your default if not provided).
        :param days: Number of days to forecast (1-16, default 7).
        :return: Weather forecast or error message.
        """
        city = self._get_location(city)
        units = self._get_units()

        if not city:
            return "Please provide a city name or set a default location in settings."

        # Clamp days to valid range
        days = max(1, min(16, days))

        city_info = get_city_info(city)
        if not city_info:
            return f"Could not find city: {city}"

        lat, lng, tmzone = city_info

        base_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lng,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max",
            "timezone": tmzone,
            "temperature_unit": units["temperature_unit"],
            "wind_speed_unit": units["wind_speed_unit"],
            "precipitation_unit": units["precipitation_unit"],
            "forecast_days": days,
        }

        data = fetch_weather_data(base_url, params)
        if isinstance(data, str):
            return data

        daily = data["daily"]

        temp_sym = units["temp_symbol"]
        wind_sym = units["wind_symbol"]
        precip_sym = units["precip_symbol"]

        report_lines = [f"**{days}-Day Weather Forecast for {city}**\n"]

        for i in range(len(daily["time"])):
            date = daily["time"][i]

            # Format date nicely
            dt = datetime.datetime.fromisoformat(date)
            if i == 0:
                date_str = f"**Today** ({dt.strftime('%a, %b %d')})"
            elif i == 1:
                date_str = f"**Tomorrow** ({dt.strftime('%a, %b %d')})"
            else:
                date_str = f"**{dt.strftime('%A, %b %d')}**"

            weather_desc = wmo_weather_codes.get(
                str(daily["weather_code"][i]), "Unknown"
            )
            temp_max = round(daily["temperature_2m_max"][i])
            temp_min = round(daily["temperature_2m_min"][i])
            sunrise = format_date(daily["sunrise"][i])
            sunset = format_date(daily["sunset"][i])
            uv_index = round(daily["uv_index_max"][i], 1)
            precip_prob = round(daily["precipitation_probability_max"][i])
            precip_sum = round(daily["precipitation_sum"][i], 2)
            wind_max = round(daily["wind_speed_10m_max"][i])
            wind_gusts = round(daily["wind_gusts_10m_max"][i])

            day_report = f"\n{date_str}\n"
            day_report += f"• {weather_desc}\n"
            day_report += f"• High: {temp_max}{temp_sym} / Low: {temp_min}{temp_sym}\n"
            day_report += f"• Sunrise: {sunrise} / Sunset: {sunset}\n"
            day_report += f"• UV Index: {uv_index}\n"
            day_report += f"• Precipitation: {precip_prob}% chance"
            if precip_sum > 0:
                day_report += f" ({precip_sum} {precip_sym} expected)"
            day_report += (
                f"\n• Wind: Max {wind_max} {wind_sym}, gusts to {wind_gusts} {wind_sym}"
            )

            report_lines.append(day_report)

        return "\n".join(report_lines)
