---
id: com.argo.alarm
name: Alarm
version: "1.0.0"
description: Set an alarm at a given time with an optional weekly repeat
author: argo
tools: []
triggers: [alarm, wake, reminder, schedule, snooze]
---

# Alarm Skill

Set an alarm at a given clock time, optionally repeating on chosen weekdays. Implemented locally — no external API required.

## Function

### set_alarm

Schedule an alarm at a specific time, with an optional weekly repeat pattern.

```python
set_alarm(time: str, repeat: list[str] = []) -> dict
```

#### Arguments

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `time` | str | Yes | - | Alarm time in 24-hour `HH:MM` format (e.g., "07:30", "22:00") |
| `repeat` | list[str] | No | `[]` | Days of the week to repeat on, lowercase 3-letter abbreviations (e.g., `["mon", "tue", "wed", "thu", "fri"]`) |

Valid `repeat` values: `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`.

#### Behavior

- **One-shot** (`repeat=[]` or omitted): Alarm rings once at the next occurrence of `time`.
  ```python
  set_alarm("07:30")
  # Rings once at the next 07:30
  ```

- **Weekly repeat** (`repeat` non-empty): Alarm rings on each listed weekday at `time`, every week, until cancelled.
  ```python
  set_alarm("07:00", repeat=["mon", "tue", "wed", "thu", "fri"])
  # Weekday wake-up alarm
  ```

## Examples

```python
# One-shot tomorrow morning
set_alarm("06:30")

# Weekend lie-in
set_alarm("09:00", repeat=["sat", "sun"])

# Every weekday at 7am
set_alarm("07:00", repeat=["mon", "tue", "wed", "thu", "fri"])

# Just Wednesdays at 8pm
set_alarm("20:00", repeat=["wed"])

# Late-night reminder
set_alarm("23:45")
```

## Error Handling

- Invalid `time` format (anything other than 24-hour `HH:MM`, e.g. `"7:30 AM"` or `"25:00"`) should be rejected with a clear message.
- Day strings in `repeat` must be lowercase 3-letter abbreviations from the set above; anything else is invalid.
- Duplicate day strings should be deduplicated silently.
