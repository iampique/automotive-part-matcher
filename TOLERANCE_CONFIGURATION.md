# Tolerance Configuration Summary

## Overview

All tolerance, threshold, and leniency values for specification matching have been centralized in `backend/app/matching_config.py`. This document summarizes all tolerance mechanisms found and their current values.

## Tolerance Mechanisms Found

### 1. Pin Count Tolerance (Percentage-based)

**Location:** `matching_config.py` - `MatchingTolerances` class

| Pin Count Range | Tolerance | Example (48 pins) | Acceptable Range |
|----------------|-----------|-------------------|------------------|
| **1-50 pins** (standard) | **20%** | 48 pins | 39-57 pins |
| **51-100 pins** (high) | **30%** | 75 pins | 53-98 pins |
| **>100 pins** (very high) | **30%** | 120 pins | 84-156 pins |

**Used in:**
- `scoring.py` - Hard requirements check
- `agent.py` - Search filtering

---

### 2. Voltage Rating Thresholds (Percentage-based minimum)

**Location:** `matching_config.py` - `MatchingTolerances` class

| Voltage Range | Threshold | Example (600V) | Minimum Acceptable |
|--------------|-----------|----------------|-------------------|
| **<100V** (standard) | **100%** (strict) | 48V | 48V minimum |
| **100-200V** (high) | **50%** | 150V | 75V minimum |
| **200-500V** (very high) | **20%** | 400V | 80V minimum |
| **>500V** (extreme) | **0%** (skip check) | 600V | No hard requirement |

**Used in:**
- `scoring.py` - Hard requirements check
- `agent.py` - Search filtering

---

### 3. Current Rating Thresholds (Percentage-based minimum)

**Location:** `matching_config.py` - `MatchingTolerances` class

| Current Range | Threshold | Example (150A) | Minimum Acceptable |
|--------------|-----------|----------------|-------------------|
| **<50A** (standard) | **100%** (strict) | 30A | 30A minimum |
| **50-100A** (high) | **50%** | 75A | 37.5A minimum |
| **100-200A** (very high) | **20%** | 150A | 30A minimum |
| **>200A** (extreme) | **0%** (skip check) | 300A | No hard requirement |

**Used in:**
- `scoring.py` - Hard requirements check
- `agent.py` - Search filtering

---

### 4. Temperature Range Buffer (°C)

**Location:** `matching_config.py` - `MatchingTolerances.TEMPERATURE_BUFFER_C`

| Buffer Value | Description |
|-------------|-------------|
| **20°C** | Allows ±20°C buffer for temperature range matching |

**Example:**
- Required: -40°C to 150°C
- Acceptable connector range: -60°C to 170°C (with buffer)

**Used in:**
- `scoring.py` - Hard requirements check
- `agent.py` - Search filtering

---

### 5. IP Rating Leniency (Hierarchical)

**Location:** `matching_config.py` - `MatchingTolerances` class

| IP Requirement | Minimum Acceptable | Tolerance |
|---------------|-------------------|-----------|
| **IP69K** (very high) | **IP67** | 2 levels below |
| **IP68** (high) | **IP67** | 1 level below |
| **Standard** (IP54, IP67) | **Within 1 level** | ±1 level |

**Used in:**
- `scoring.py` - Hard requirements check

---

## Configuration File

All tolerance values are defined in: **`backend/app/matching_config.py`**

### Key Methods:

- `get_pin_count_tolerance(pin_count: int) -> float`
- `get_voltage_threshold(voltage: int) -> float`
- `get_current_threshold(current: int) -> float`

### Access Pattern:

```python
from app.matching_config import tolerances

# Get pin count tolerance
tolerance = tolerances.get_pin_count_tolerance(48)  # Returns 0.20 (20%)

# Get voltage threshold
threshold = tolerances.get_voltage_threshold(600)  # Returns 0.20 (20%)

# Access temperature buffer
buffer = tolerances.TEMPERATURE_BUFFER_C  # Returns 20
```

---

## Changes Made

1. ✅ Created `matching_config.py` with centralized tolerance configuration
2. ✅ Updated `scoring.py` to use centralized tolerances
3. ✅ Updated `agent.py` to use centralized tolerances
4. ✅ Removed unused `PIN_COUNT_TOLERANCE_PERCENT` constant
5. ✅ Made all tolerance values consistent between files
6. ✅ Fixed discrepancy: Very high pin count tolerance now consistently 30% (was 40% in agent.py)

---

## Future Enhancements

To make these values configurable via environment variables, add to `config.py`:

```python
# Matching tolerance settings (optional, defaults from matching_config.py)
pin_count_tolerance_standard: float = Field(default=0.20, ...)
pin_count_tolerance_high: float = Field(default=0.30, ...)
voltage_threshold_high: float = Field(default=0.50, ...)
temperature_buffer_c: int = Field(default=20, ...)
```

Then update `matching_config.py` to read from settings if provided.

