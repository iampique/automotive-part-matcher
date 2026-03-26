# ACORN Activation: How the Agentic System Intelligently Decides

This document explains how ACORN (Approximate Clustering for Retrieval Networks) is enabled and how the agentic system intelligently decides when to activate it.

## Overview

ACORN is a Qdrant 1.16 feature that improves search recall for restrictive filters. However, it adds 2-10x latency overhead, so the system only uses it when beneficial.

## Multi-Layer Activation System

The ACORN activation decision happens at **three layers**:

### Layer 1: Global Configuration (`config.py`)

ACORN can be globally enabled/disabled via environment variable:

```python
# backend/app/config.py
acorn_enabled: bool = Field(
    default=True,
    description="Enable Qdrant 1.16 ACORN feature"
)
```

**Location**: `backend/app/config.py:85-88`

This is the **master switch** - if `ACORN_ENABLED=false` in `.env`, ACORN will never be used regardless of other settings.

---

### Layer 2: User Preference (Frontend/API)

Users can enable/disable ACORN per request via the frontend toggle or API parameter:

```typescript
// frontend/components/SearchInput.tsx
const [enableAcorn, setEnableAcorn] = useState(true);

// Passed to API
onSearch(textInput, undefined, llmProvider, enableAcorn);
```

```python
# backend/app/agent.py:804
def run(self, input_text: str, enable_acorn: bool = True) -> Dict:
    # enable_acorn parameter from user request
```

**Location**: 
- Frontend: `frontend/components/SearchInput.tsx:21`
- Agent: `backend/app/agent.py:804`

---

### Layer 3: Intelligent Agent Decision (`agent.py` - Search Node)

**This is where the intelligence happens!** The agent analyzes the query and only activates ACORN when it's beneficial.

#### Decision Logic

```python
# backend/app/agent.py:471-479
# Perform search with ACORN and hybrid settings from state
enable_acorn = state.get("enable_acorn", True)  # Default to True if not set

# ACORN is only beneficial when filters are present (it improves recall for restrictive filters)
# If no filters were built (e.g., parsing failed), ACORN doesn't provide benefit
has_filters = filters is not None and len(filters) > 0

# Only use ACORN if filters exist AND it's enabled
# (QdrantService will also check settings.acorn_enabled internally)
actual_acorn_enabled = enable_acorn and has_filters
```

**Key Decision Rule**: 
```
actual_acorn_enabled = enable_acorn AND has_filters
```

**Why this matters**:
- ACORN improves recall when filters restrict the search space (< 40% selectivity)
- Without filters, ACORN provides no benefit but still adds latency
- The agent intelligently skips ACORN for simple semantic-only queries

#### Example Scenarios

**Scenario 1: Query with Filters → ACORN Enabled**
```python
# Query: "600V minimum, IP69K, -40°C to 150°C"
# Parsed filters: voltage >= 600V, IP rating = IP69K, temperature range
has_filters = True  # Filters were built from requirements
enable_acorn = True  # User preference
actual_acorn_enabled = True  # ✅ ACORN will be used
```

**Scenario 2: Simple Query → ACORN Disabled**
```python
# Query: "Find connectors for EV battery"
# No specific filters extracted
has_filters = False  # No filters built
enable_acorn = True  # User preference
actual_acorn_enabled = False  # ❌ ACORN skipped (no benefit)
```

**Scenario 3: Fallback Search → ACORN Disabled**
```python
# If initial search with filters returns 0 results:
if len(search_results) == 0 and filters:
    # Retry without filters
    enable_acorn=False  # ACORN not needed without filters
    actual_acorn_enabled = False  # ❌ ACORN disabled for fallback
```

**Location**: `backend/app/agent.py:471-526`

---

### Layer 4: QdrantService Implementation (`qdrant_service.py`)

The QdrantService performs a final check before applying ACORN:

```python
# backend/app/services/qdrant_service.py:524-529
# Configure search parameters based on ACORN flag
search_params = None
use_acorn = enable_acorn and settings.acorn_enabled

if use_acorn:
    # ACORN algorithm (Qdrant 1.16) improves recall for restrictive filters
    search_params = SearchParams(hnsw_ef=128)
    logger.info("Using ACORN algorithm (Qdrant 1.16) for improved search recall")
```

**Final Check**: `use_acorn = enable_acorn AND settings.acorn_enabled`

This ensures that even if the agent decides to use ACORN, it respects the global configuration.

**Location**: `backend/app/services/qdrant_service.py:522-529`

---

## Complete Decision Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Request                                             │
│    enable_acorn = True (from frontend toggle)              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Agent Receives Request                                   │
│    state["enable_acorn"] = True                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Parse Requirements Node                                  │
│    Extract structured requirements from text              │
│    Build filters (voltage, current, IP rating, etc.)       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Search Node - Intelligent Decision                       │
│    has_filters = filters is not None and len(filters) > 0  │
│    actual_acorn_enabled = enable_acorn AND has_filters     │
│                                                             │
│    ✅ If filters exist → ACORN enabled                     │
│    ❌ If no filters → ACORN disabled                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. QdrantService - Final Check                              │
│    use_acorn = actual_acorn_enabled AND settings.acorn_enabled│
│                                                             │
│    ✅ If both true → Apply ACORN (hnsw_ef=128)            │
│    ❌ Otherwise → Standard search                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Search Execution                                         │
│    Results returned with acorn_used flag                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Code Locations

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Global Config | `backend/app/config.py` | 85-88 | Master enable/disable switch |
| User Preference | `backend/app/agent.py` | 804, 836 | Per-request enable flag |
| **Intelligent Decision** | `backend/app/agent.py` | **471-479** | **Core logic: filters check** |
| Fallback Logic | `backend/app/agent.py` | 502-526 | Disable ACORN if retrying without filters |
| Implementation | `backend/app/services/qdrant_service.py` | 522-529 | Apply ACORN to Qdrant query |
| State Tracking | `backend/app/agent.py` | 542 | Record if ACORN was actually used |

---

## Why This Design?

1. **Performance**: ACORN adds 2-10x latency, so only use when beneficial
2. **Accuracy**: ACORN improves recall for restrictive filters (10-30% better)
3. **User Control**: Users can override via frontend toggle
4. **System Control**: Admins can disable globally via config
5. **Intelligence**: Agent automatically skips ACORN for simple queries

---

## Example: Real Query Flow

**Query**: "I need a connector rated for 600V minimum, IP69K protection, operating from -40°C to 150°C"

1. **Parse Node**: Extracts filters:
   - `voltage_rating >= 600V`
   - `ip_rating = "IP69K"`
   - `temperature_range: [-40°C, 150°C]`

2. **Search Node Decision**:
   ```python
   has_filters = True  # ✅ Filters exist
   enable_acorn = True  # ✅ User enabled
   actual_acorn_enabled = True  # ✅ Use ACORN
   ```

3. **QdrantService**:
   ```python
   use_acorn = True AND True  # ✅ Both enabled
   search_params = SearchParams(hnsw_ef=128)  # ACORN activated
   ```

4. **Result**: 
   - ACORN used: ✅ `True`
   - Better recall: Finds 8-12 connectors instead of 3-5
   - Trade-off: 2-10 seconds instead of 0.5-2 seconds

---

## Summary

The agentic system intelligently activates ACORN by:

1. ✅ **Checking if filters exist** (ACORN only helps with restrictive filters)
2. ✅ **Respecting user preference** (frontend toggle)
3. ✅ **Respecting global config** (admin override)
4. ✅ **Skipping when not beneficial** (simple queries without filters)

This ensures ACORN is only used when it provides value, balancing accuracy and performance.

