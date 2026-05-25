# Demo: get_weather

**Archetype:** External API (free, no key required)

## Description to pass to `create_tool`

```
Create a tool called get_weather that takes a city name and returns the current temperature in Celsius and weather conditions. Use the Open-Meteo API at api.open-meteo.com (free, no key needed). First geocode the city using their geocoding endpoint, then fetch the current weather for those coordinates.
```

## How to create it

In Claude Desktop:

> "Use create_tool with this description: Create a tool called get_weather that takes a city name and returns the current temperature in Celsius and weather conditions. Use the Open-Meteo API at api.open-meteo.com (free, no key needed). First geocode the city using their geocoding endpoint, then fetch the current weather for those coordinates."

## Expected tool input

```json
{ "city": "Lagos" }
```

## Expected tool output

```json
{
  "status": "success",
  "data": {
    "city": "Lagos",
    "temperature_celsius": 28.5,
    "weather_code": 1,
    "wind_speed_kmh": 12.3
  },
  "message": "Weather fetched successfully for Lagos."
}
```

## What this demonstrates

- Two-step external API call (geocode → weather)
- `requests` library usage
- Error handling for unknown cities
