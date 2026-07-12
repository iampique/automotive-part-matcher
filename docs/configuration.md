# Configuration

Matching tolerances and thresholds are centralized in [`backend/app/matching_config.py`](../backend/app/matching_config.py).

## Pin count (percentage)

| Pin range | Tolerance | Example (48 pins) |
|-----------|-----------|-------------------|
| 1–50 | 20% | 39–57 |
| 51–100 | 30% | 53–98 |
| >100 | 30% | e.g. 120 → 84–156 |

## Voltage (minimum threshold)

| Voltage range | Threshold | Meaning |
|---------------|-----------|---------|
| <100V | 100% | Strict minimum |
| 100–200V | 50% of required | Lower bar for mid-range |
| 200–500V | 20% of required | More lenient |
| >500V | 0% | Hard voltage check skipped |

## Current (minimum threshold)

| Current range | Threshold |
|---------------|-----------|
| <50A | 100% (strict) |
| 50–100A | 50% of required |
| 100–200A | 20% of required |
| >200A | Hard check skipped |

## Temperature

`TEMPERATURE_BUFFER_C = 20` — allows ±20°C buffer around the required operating range.

## IP rating

Hierarchical leniency (examples):

| Required | Minimum acceptable |
|----------|--------------------|
| IP69K | IP67 |
| IP68 | IP67 |
| Standard (e.g. IP54, IP67) | Within ±1 level |

## Usage in code

```python
from app.matching_config import tolerances

tolerances.get_pin_count_tolerance(48)
tolerances.get_voltage_threshold(600)
tolerances.TEMPERATURE_BUFFER_C
```

Used by `scoring.py` (hard requirements) and `agent.py` (search filtering).

Env-driven overrides are not wired yet; change values in `matching_config.py` for local experiments.
