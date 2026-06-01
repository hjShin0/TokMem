---
id: com.argo.weather
name: Weather
version: "1.0.0"
description: Get weather information for a location and time via wttr.in
author: argo
tool_refs: [http_fetch]
tools: []
triggers: [weather, temperature, forecast, rain, snow]
---

# Weather Skill

Fetch weather information using a single unified function. The API uses the free wttr.in JSON API. No API key required.

## Authentication

None. Include a descriptive `User-Agent` header as a courtesy:
```
User-Agent: argo/1.0
```

## Function

### get_weather

Get weather information for a specific location and time.

```python
get_weather(location: str, time: str, forecast_days: int = 0) -> dict
```

#### Arguments

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `location` | str | Yes | - | Location to get weather for (e.g., "Seoul", "New+York", "51.5,-0.12") |
| `time` | str | Yes | - | Time to get weather for (e.g., "2024-01-15", "now", "today") |
| `forecast_days` | int | No | 0 | Number of days to forecast (0 = current weather only, 1-3 = forecast) |

#### Behavior

- **Current weather** (`forecast_days=0` or omitted): Returns current conditions for the given location and time.
  ```python
  get_weather("Seoul", "2024-01-15")
  # or
  get_weather("Seoul", "now")
  ```

- **Forecast** (`forecast_days > 0`): Returns forecast for the specified number of days (max 3).
  ```python
  get_weather("Seoul", "2024-01-15", forecast_days=3)
  # Returns forecast for Jan 15, 16, 17
  ```

## Examples

```python
# Current weather in Seoul
get_weather("Seoul", "now")

# Current weather in New York
get_weather("New+York", "2024-01-15")

# 3-day forecast starting from today
get_weather("Seoul", "today", forecast_days=3)

# Weather at specific coordinates
get_weather("51.5,-0.12", "2024-06-01")
```

## Error Handling

- wttr.in returns HTTP 200 even for unknown locations; check that `nearest_area` is populated.
- If the location string is ambiguous, wttr.in picks the closest match — include country name to disambiguate (e.g., `Paris,France`).
- On network failure, inform the user and suggest retrying.