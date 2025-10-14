# WeatherWeaver

Comprehensive, keyless weather tool for OpenWebUI. Get current conditions and forecasts for any city—no API key required.

**Repo:** [WeatherWeaver on GitHub](https://github.com/PureGrain/openwebui-stuff/tree/main/tools/weatherweaver)

## Features

- Current weather and multi-day forecasts for any city
- Supports imperial and metric units
- Uses Open-Meteo's free geocoding and weather APIs
- Valve system for user and default city/unit preferences

## Credits

- Original code and idea: **Keyless Weather** by spyci
- Enhanced and maintained by PureGrain at SLA Ops, LLC

## Installation

You can install WeatherWeaver in OpenWebUI by downloading the included `weatherweaver.json` file and importing it via the OpenWebUI admin panel.

## Usage

1. After installation, set your preferred city and units in the Valve settings (admin or user side).
2. Use the tool to get current weather or forecasts by city name, or let it use your valve/default settings.

## Example

```python
get_current_weather(city="Miami")
get_weather_forecast(city="Tokyo", days=5)
```

If no city is provided, WeatherWeaver uses your user valve or the default city.

## How to Prompt

You can ask for the weather in any city—just specify the city name in your prompt. If you don't provide a city, WeatherWeaver will use the valve set in the admin area of the tool.

Example prompts:

```python
get_current_weather(city="Miami")
get_weather_forecast(city="Tokyo", days=5)
```

## License

MIT

## Funding

<https://github.com/open-webui>

---
[Repository Link](https://github.com/PureGrain/openwebui-stuff)
