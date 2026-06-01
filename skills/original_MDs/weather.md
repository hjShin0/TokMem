---
id: com.argo.weather
name: Weather
version: "1.0.0"
description: Get current weather and forecasts via wttr.in
author: argo
tool_refs: [http_fetch]
tools: []
triggers: [weather, temperature, forecast, rain, snow]
---

# Weather Skill

Fetch current conditions and multi-day forecasts using the free wttr.in JSON API. No API key required.

## Authentication

None. Include a descriptive `User-Agent` header as a courtesy:
```
User-Agent: argo/1.0
```

## Location Formats

| Format | Example |
|--------|---------|
| City name | `London`, `Seoul`, `New+York` |
| lat,lon | `51.5,-0.12` |
| Airport IATA | `JFK` |
| IP-based (current location) | leave blank or use `~` |

URL-encode spaces as `+` or `%20`.

## Verbs

### current
Get current conditions for a location.

```
GET https://wttr.in/{location}?format=j1
Headers: User-Agent: argo/1.0
```

Key fields from `current_condition[0]`:

| Field | Description |
|-------|-------------|
| `temp_C` / `temp_F` | Current temperature |
| `FeelsLikeC` / `FeelsLikeF` | Feels-like temperature |
| `weatherDesc[0].value` | Text description, e.g. "Partly cloudy" |
| `humidity` | Relative humidity % |
| `windspeedKmph` | Wind speed in km/h |
| `winddirDegree` | Wind direction in degrees |
| `winddir16Point` | Wind direction as compass point, e.g. "NNE" |
| `precipMM` | Precipitation in mm |
| `visibility` | Visibility in km |
| `uvIndex` | UV index |
| `pressure` | Pressure in hPa |
| `cloudcover` | Cloud cover % |

Also includes `nearest_area[0]` with `areaName`, `country`, `region`, `latitude`, `longitude`.

### forecast
Get a 3-day forecast (today + 2 more days). Same endpoint and response as `current` — the forecast lives in the `weather[]` array.

```
GET https://wttr.in/{location}?format=j1
Headers: User-Agent: argo/1.0
```

Each element of `weather[]`:

| Field | Description |
|-------|-------------|
| `date` | YYYY-MM-DD |
| `maxtempC` / `mintempC` | Day high/low in °C |
| `maxtempF` / `mintempF` | Day high/low in °F |
| `uvIndex` | Peak UV index |
| `hourly[]` | Array of 8 3-hour slots |

Each `hourly` slot has `time` (0–2100 in steps of 300), `tempC`, `FeelsLikeC`, `weatherDesc[0].value`, `precipMM`, `chanceofrain`, `chanceofsnow`, `windspeedKmph`.

### ascii
Get a human-readable ASCII art weather report (not JSON).

```
GET https://wttr.in/{location}
Headers: User-Agent: argo/1.0
```

Useful for embedding in plain-text messages. Add `?format=3` for a one-liner like `Seoul: ⛅  +18°C`.

## Error Handling

- wttr.in returns HTTP 200 even for unknown locations; check that `nearest_area` is populated.
- If the location string is ambiguous, wttr.in picks the closest match — include country name to disambiguate (e.g., `Paris,France`).
- On network failure, inform the user and suggest retrying.