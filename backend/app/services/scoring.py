"""
Scoring service implementing hybrid matching algorithm for connector requirements.

This module provides functions to score connector matches based on requirement fit using
a hybrid approach that combines hard requirements (must-match criteria) with weighted
soft scoring (preference-based criteria). The scoring system is designed to be
transparent and explainable, providing clear feedback on why connectors match or fail.

Scoring Philosophy:
- Hard Requirements: Must-pass criteria that immediately disqualify connectors if not met
- Soft Scoring: Weighted preference-based scoring that ranks acceptable connectors
- Final Score: Hard requirements act as a gate; only connectors passing all hard checks
  receive soft scores. This ensures safety and compliance while allowing nuanced ranking.

Weight Distribution (Soft Scoring):
- Semantic Similarity (40%): Text-based matching from vector search
- Temperature Range (20%): Operating temperature compatibility
- Price Competitiveness (20%): Cost optimization
- Lead Time (10%): Delivery speed
- Certification Bonus (10%): Standards compliance bonus

Examples:
    >>> requirement = CustomerRequirement(
    ...     description="12V automotive connector",
    ...     specifications=ConnectorSpecifications(voltage_rating=12, pin_count=4)
    ... )
    >>> connector = Connector(...)  # Has voltage_rating=24, pin_count=4
    >>> passes, failures = check_hard_requirements(requirement, connector)
    >>> score, explanation = calculate_match_score(requirement, connector, 85.0)
"""

from typing import List, Tuple

from app.matching_config import tolerances
from app.models import Connector, CustomerRequirement

# IP rating hierarchy (higher index = better protection)
# Used for comparing IP ratings: IP69K > IP68 > IP67 > IP54
IP_RATING_HIERARCHY = {
    "IP54": 1,
    "IP67": 2,
    "IP68": 3,
    "IP69K": 4,
}

# Scoring weights for soft score components
SEMANTIC_WEIGHT = 0.30  # 30% weight for semantic similarity
TEMPERATURE_WEIGHT = 0.15  # 15% weight for temperature range match
VOLTAGE_CURRENT_WEIGHT = 0.20  # 20% weight for voltage/current matching
PIN_COUNT_WEIGHT = 0.15  # 15% weight for pin count matching
PRICE_WEIGHT = 0.10  # 10% weight for price competitiveness
LEAD_TIME_WEIGHT = 0.05  # 5% weight for lead time
CERTIFICATION_WEIGHT = 0.05  # 5% weight for certification bonus

# Constants for normalization
MAX_REASONABLE_PRICE_USD = 50.0  # Maximum price for normalization
MAX_REASONABLE_LEAD_TIME_DAYS = 60  # Maximum lead time for normalization
# Note: Pin count tolerance moved to matching_config.py for centralized configuration


def check_hard_requirements(
    requirement: CustomerRequirement,
    connector: Connector
) -> Tuple[bool, List[str]]:
    """
    Check if connector meets all hard (must-match) requirements.
    
    Hard requirements are criteria that must be satisfied for a connector to be
    considered a valid match. If any hard requirement fails, the connector is
    disqualified regardless of other factors.
    
    IMPORTANT: For extremely high requirements (specialized applications like EV),
    hard requirements are relaxed to allow semantic matching to find relevant connectors.
    This prevents the system from rejecting all connectors when requirements are beyond
    what's available in the database.
    
    Checks performed (with adaptive leniency):
    1. Voltage rating: Connector must meet or exceed required voltage
       - For extremely high voltage (>500V): Skip hard requirement (treat as soft)
       - For very high voltage (200-500V): Use 20% threshold
       - For high voltage (100-200V): Use 50% threshold
       - For standard voltage: Strict matching required
    2. Current rating: Connector must meet or exceed required current
       - For extremely high current (>200A): Skip hard requirement (treat as soft)
       - For very high current (100-200A): Use 20% threshold
       - For high current (50-100A): Use 50% threshold
       - For standard current: Strict matching required
    3. IP rating: Connector must be within one level of required protection
       - (e.g., IP69K requirement allows IP67)
    4. Certifications: Treated as soft requirement (affects score, not disqualification)
    5. Pin count: Connector pin count must be within tolerance
       - For very high pin counts (>100): 40% tolerance
       - For high pin counts (50-100): 30% tolerance
       - For standard counts: 20% tolerance
    
    Args:
        requirement: Customer requirement with optional specifications
        connector: Connector to check against requirements
        
    Returns:
        Tuple of (pass/fail boolean, list of failure messages).
        Returns (True, []) if all requirements pass.
        Returns (False, [messages]) if any requirement fails.
        
    Example:
        >>> requirement = CustomerRequirement(
        ...     specifications=ConnectorSpecifications(voltage_rating=24, pin_count=4)
        ... )
        >>> connector = Connector(
        ...     specifications=ConnectorSpecifications(voltage_rating=12, pin_count=4)
        ... )
        >>> passes, failures = check_hard_requirements(requirement, connector)
        >>> assert not passes
        >>> assert "Voltage" in failures[0]
    """
    failures: List[str] = []
    
    # Get requirement specifications if available
    req_specs = requirement.specifications
    conn_specs = connector.specifications
    
    # NOTE: Certifications are now treated as soft requirements (affect score but don't disqualify)
    # This allows results to be shown even if specific certifications aren't met,
    # which is important when requirements are very strict (e.g., ISO 26262 ASIL-D)
    
    # If no specifications, pass (no hard requirements to check)
    if not req_specs:
        return (True, [])  # Always pass if no specs to check
    
    # 1. Voltage requirement check (adaptive leniency for specialized applications)
    # Uses centralized tolerance configuration from matching_config.py
    if req_specs.voltage_rating is not None:
        threshold = tolerances.get_voltage_threshold(req_specs.voltage_rating)
        
        if threshold == 0.0:
            # Extremely high voltage - skip hard requirement (treat as soft requirement)
            # Allow semantic matching to find relevant connectors
            pass  # No hard requirement check for extreme cases
        elif threshold < 1.0:
            # High/very high voltage - use lenient threshold
            min_voltage = req_specs.voltage_rating * threshold
            if conn_specs.voltage_rating < min_voltage:
                failures.append(
                    f"Voltage {conn_specs.voltage_rating}V insufficient for required "
                    f"{req_specs.voltage_rating}V (minimum acceptable: {min_voltage:.0f}V)"
                )
        else:
            # Standard voltage requirement - strict matching (100% threshold)
            if conn_specs.voltage_rating < req_specs.voltage_rating:
                failures.append(
                    f"Voltage {conn_specs.voltage_rating}V insufficient for required "
                    f"{req_specs.voltage_rating}V"
                )
    
    # 2. Current requirement check (adaptive leniency for specialized applications)
    # Uses centralized tolerance configuration from matching_config.py
    if req_specs.current_rating is not None:
        threshold = tolerances.get_current_threshold(req_specs.current_rating)
        
        if threshold == 0.0:
            # Extremely high current - skip hard requirement (treat as soft requirement)
            # Allow semantic matching to find relevant connectors
            pass  # No hard requirement check for extreme cases
        elif threshold < 1.0:
            # High/very high current - use lenient threshold
            min_current = req_specs.current_rating * threshold
            if conn_specs.current_rating < min_current:
                failures.append(
                    f"Current {conn_specs.current_rating}A insufficient for required "
                    f"{req_specs.current_rating}A (minimum acceptable: {min_current:.0f}A)"
                )
        else:
            # Standard current requirement - strict matching (100% threshold)
            if conn_specs.current_rating < req_specs.current_rating:
                failures.append(
                    f"Current {conn_specs.current_rating}A insufficient for required "
                    f"{req_specs.current_rating}A"
                )
    
    # 3. Temperature range requirement check
    # Connector must support the full required temperature range
    # Uses centralized temperature buffer from matching_config.py
    if (req_specs.min_operating_temp is not None and 
        req_specs.max_operating_temp is not None):
        # Connector must support at least the required temperature range
        # Allow configurable buffer for leniency (connector can be slightly outside range)
        temp_buffer = tolerances.TEMPERATURE_BUFFER_C
        if (conn_specs.max_operating_temp < req_specs.min_operating_temp - temp_buffer or
            conn_specs.min_operating_temp > req_specs.max_operating_temp + temp_buffer):
            failures.append(
                f"Temperature range {conn_specs.min_operating_temp}°C to {conn_specs.max_operating_temp}°C "
                f"does not cover required range {req_specs.min_operating_temp}°C to {req_specs.max_operating_temp}°C"
            )
    
    # 4. IP rating requirement check (balanced leniency)
    # Uses centralized IP rating configuration from matching_config.py
    if req_specs.ip_rating:
        req_ip_rank = _get_ip_rating_rank(req_specs.ip_rating)
        conn_ip_rank = _get_ip_rating_rank(conn_specs.ip_rating)
        
        # For very high IP requirements (IP69K), allow IP67+ (rank 2+)
        # For high IP (IP68), allow IP67+ (rank 2+)
        # For standard IP, allow within configured tolerance levels
        min_ip_rank_for_very_high = _get_ip_rating_rank(tolerances.IP_RATING_VERY_HIGH_MINIMUM)
        min_ip_rank_for_high = _get_ip_rating_rank(tolerances.IP_RATING_HIGH_MINIMUM)
        standard_tolerance = tolerances.IP_RATING_STANDARD_TOLERANCE_LEVELS
        
        if req_ip_rank >= 4:  # IP69K
            # Very high IP requirement - allow configured minimum or better
            if conn_ip_rank < min_ip_rank_for_very_high:
                failures.append(
                    f"IP rating {conn_specs.ip_rating} insufficient for required "
                    f"{req_specs.ip_rating} (minimum acceptable: {tolerances.IP_RATING_VERY_HIGH_MINIMUM})"
                )
        elif req_ip_rank == 3:  # IP68
            # High IP requirement - allow configured minimum or better
            if conn_ip_rank < min_ip_rank_for_high:
                failures.append(
                    f"IP rating {conn_specs.ip_rating} insufficient for required "
                    f"{req_specs.ip_rating} (minimum acceptable: {tolerances.IP_RATING_HIGH_MINIMUM})"
                )
        elif req_ip_rank > conn_ip_rank + standard_tolerance:
            # Standard IP requirement - allow within configured tolerance levels
            failures.append(
                f"IP rating {conn_specs.ip_rating} insufficient for required "
                f"{req_specs.ip_rating}"
            )
    
    # 5. Pin count requirement check (adaptive leniency for specialized applications)
    # Uses centralized tolerance configuration from matching_config.py
    # For very high pin counts (>100), treats requirement as "minimum" and allows connectors
    # with at least 50% of required pins, since specialized connectors may have fewer pins
    # but still be suitable for the application.
    if req_specs.pin_count is not None:
        tolerance_percent = tolerances.get_pin_count_tolerance(req_specs.pin_count)
        
        # For very high pin counts (>100), use asymmetric tolerance (minimum-based)
        # This handles "120 pins minimum" type requirements where connectors with fewer
        # pins might still be suitable, especially for specialized applications like EV.
        # For very high pin counts, we're more lenient since exact pin count matches
        # may not exist in the database, but connectors with fewer pins can still be
        # relevant (e.g., can be used in parallel or have similar functionality).
        if req_specs.pin_count > tolerances.PIN_COUNT_VERY_HIGH_THRESHOLD:
            # Allow connectors with at least 30% of required pins (e.g., 36+ pins for 120 requirement)
            # This ensures connectors are still reasonably sized while being lenient enough
            # to find relevant matches for specialized high-pin-count applications
            min_pins = int(req_specs.pin_count * tolerance_percent)
            # No upper limit - connectors with more pins are always acceptable
            if conn_specs.pin_count < min_pins:
                failures.append(
                    f"Pin count {conn_specs.pin_count} below minimum acceptable "
                    f"({min_pins}+) for required {req_specs.pin_count} pins minimum"
                )
        else:
            # Standard symmetric tolerance for lower pin counts
            tolerance = int(req_specs.pin_count * tolerance_percent)
            min_pins = max(1, req_specs.pin_count - tolerance)
            max_pins = req_specs.pin_count + tolerance
            
            if not (min_pins <= conn_specs.pin_count <= max_pins):
                failures.append(
                    f"Pin count {conn_specs.pin_count} outside tolerance range "
                    f"({min_pins}-{max_pins}) for required {req_specs.pin_count} pins"
                )
    
    # Return pass/fail based on whether any failures occurred
    return (len(failures) == 0, failures)


def calculate_soft_score(
    requirement: CustomerRequirement,
    connector: Connector,
    semantic_score: float
) -> float:
    """
    Calculate weighted soft score for connector match.
    
    Soft scoring evaluates preference-based criteria that help rank connectors
    that pass hard requirements. The score combines multiple factors with
    weighted importance to produce a final ranking score from 0-100.
    
    Scoring Components:
    1. Semantic Similarity (30%): How well text descriptions match
    2. Voltage/Current Matching (20%): How well electrical ratings match
    3. Pin Count Matching (15%): How well pin count matches requirements
    4. Temperature Range (15%): Operating temperature compatibility
    5. Price Competitiveness (10%): Cost optimization (lower is better)
    6. Lead Time (5%): Delivery speed (shorter is better)
    7. Certification Bonus (5%): Standards compliance coverage
    
    Args:
        requirement: Customer requirement with optional specifications
        connector: Connector to score
        semantic_score: Semantic similarity score from vector search (0-100)
        
    Returns:
        Float score from 0.0 to 100.0 representing overall match quality
        
    Example:
        >>> requirement = CustomerRequirement(description="12V connector")
        >>> connector = Connector(
        ...     specifications=ConnectorSpecifications(
        ...         min_operating_temp=-40, max_operating_temp=85
        ...     ),
        ...     pricing=ConnectorPricing(unit_price_usd=25.0, lead_time_days=14)
        ... )
        >>> score = calculate_soft_score(requirement, connector, 85.0)
        >>> assert 0.0 <= score <= 100.0
    """
    total_score = 0.0
    
    # 1. Semantic similarity component (35% weight)
    # Use the semantic score directly, normalized to 0-100 range
    semantic_component = min(max(semantic_score, 0.0), 100.0) * SEMANTIC_WEIGHT
    total_score += semantic_component
    
    # 2. Voltage/Current matching component (20% weight)
    # Penalize connectors that don't meet voltage/current requirements
    voltage_current_score = _calculate_voltage_current_score(requirement, connector)
    total_score += voltage_current_score * VOLTAGE_CURRENT_WEIGHT
    
    # 3. Pin count matching component (15% weight)
    # Penalize connectors that don't meet pin count requirements
    pin_count_score = _calculate_pin_count_score(requirement, connector)
    total_score += pin_count_score * PIN_COUNT_WEIGHT
    
    # 4. Temperature range component (15% weight)
    temp_score = _calculate_temperature_score(requirement, connector)
    total_score += temp_score * TEMPERATURE_WEIGHT
    
    # 5. Price competitiveness component (10% weight)
    price_score = _calculate_price_score(connector)
    total_score += price_score * PRICE_WEIGHT
    
    # 6. Lead time component (5% weight)
    lead_time_score = _calculate_lead_time_score(connector)
    total_score += lead_time_score * LEAD_TIME_WEIGHT
    
    # 7. Certification bonus component (5% weight)
    cert_score = _calculate_certification_score(requirement, connector)
    total_score += cert_score * CERTIFICATION_WEIGHT
    
    # Cap total score at 100.0
    return min(total_score, 100.0)


def calculate_match_score(
    requirement: CustomerRequirement,
    connector: Connector,
    semantic_score: float
) -> Tuple[float, str]:
    """
    Calculate final match score combining hard requirements and soft scoring.
    
    This is the main scoring function that implements the hybrid matching algorithm.
    It first checks hard requirements as a gate, then calculates soft scores for
    connectors that pass. The explanation provides transparency about the scoring
    decision.
    
    Algorithm:
    1. Check hard requirements (must-match criteria)
    2. If any hard requirement fails:
       - Return score of 0.0
       - Return explanation listing all failures
    3. If all hard requirements pass:
       - Calculate soft score using weighted components
       - Generate explanation based on score tier
       - Return (soft_score, explanation)
    
    Score Tiers:
    - >= 90: "Excellent match for your requirements."
    - >= 75: "Good match with minor trade-offs."
    - >= 60: "Acceptable match with some compromises."
    - < 60: "Partial match - review trade-offs carefully."
    
    Args:
        requirement: Customer requirement with optional specifications
        connector: Connector to score
        semantic_score: Semantic similarity score from vector search (0-100)
        
    Returns:
        Tuple of (final_score: float, explanation: str)
        Score is 0.0 if hard requirements fail, otherwise soft score (0-100)
        
    Example:
        >>> requirement = CustomerRequirement(
        ...     description="Automotive connector",
        ...     specifications=ConnectorSpecifications(voltage_rating=12)
        ... )
        >>> connector = Connector(
        ...     specifications=ConnectorSpecifications(voltage_rating=24)
        ... )
        >>> score, explanation = calculate_match_score(requirement, connector, 80.0)
        >>> assert isinstance(score, float)
        >>> assert isinstance(explanation, str)
    """
    # First check hard requirements
    passes_hard, failures = check_hard_requirements(requirement, connector)
    
    if not passes_hard:
        # Hard requirements failed - return 0.0 with explanation
        failure_text = "Hard requirements not met:\n"
        failure_text += "\n".join(f"  - {failure}" for failure in failures)
        return (0.0, failure_text)
    
    # All hard requirements passed - calculate soft score
    soft_score = calculate_soft_score(requirement, connector, semantic_score)
    
    # Check if this is an extreme case where hard requirements were skipped
    req_specs = requirement.specifications
    is_extreme_case = False
    if req_specs:
        if (req_specs.voltage_rating and req_specs.voltage_rating > 500) or \
           (req_specs.current_rating and req_specs.current_rating > 200) or \
           (req_specs.pin_count and req_specs.pin_count > 100):
            is_extreme_case = True
    
    # Generate explanation based on score tier
    if soft_score >= 90.0:
        explanation = "Excellent match for your requirements."
    elif soft_score >= 75.0:
        explanation = "Good match with minor trade-offs."
    elif soft_score >= 60.0:
        explanation = "Acceptable match with some compromises."
    else:
        explanation = "Partial match - review trade-offs carefully."
    
    # Add note for extreme cases
    if is_extreme_case:
        explanation += " Note: For specialized high-voltage/high-current applications, electrical ratings are evaluated as soft requirements to allow semantic matching to find relevant connectors."
    
    return (soft_score, explanation)


def _get_ip_rating_rank(ip_rating: str) -> int:
    """
    Get numeric rank for IP rating comparison.
    
    Higher rank indicates better protection. Unknown ratings are assigned
    rank 0 (lowest) to be conservative in comparisons.
    
    Args:
        ip_rating: IP rating string (e.g., "IP67", "IP68")
        
    Returns:
        Integer rank (higher = better protection)
    """
    ip_upper = ip_rating.upper()
    return IP_RATING_HIERARCHY.get(ip_upper, 0)


def _calculate_voltage_current_score(
    requirement: CustomerRequirement,
    connector: Connector
) -> float:
    """
    Calculate voltage and current matching score (0-100).
    
    Scores how well the connector's voltage and current ratings match the requirements.
    Connectors that meet or exceed requirements score 100. Connectors that fall short
    are penalized proportionally. This ensures connectors that don't meet electrical
    requirements get lower scores even when hard requirements are skipped for extreme cases.
    
    Args:
        requirement: Customer requirement
        connector: Connector to score
        
    Returns:
        Float score from 0.0 to 100.0
    """
    req_specs = requirement.specifications
    if not req_specs:
        # No requirements specified - award full points
        return 100.0
    
    conn_specs = connector.specifications
    
    voltage_score = 100.0
    current_score = 100.0
    
    # Calculate voltage match score
    if req_specs.voltage_rating is not None:
        if conn_specs.voltage_rating >= req_specs.voltage_rating:
            # Meets or exceeds requirement - full points
            voltage_score = 100.0
        else:
            # Falls short - penalize proportionally
            # Score based on how close it is (e.g., 300V for 600V requirement = 50%)
            ratio = conn_specs.voltage_rating / req_specs.voltage_rating
            voltage_score = max(0.0, ratio * 100.0)
    
    # Calculate current match score
    if req_specs.current_rating is not None:
        if conn_specs.current_rating >= req_specs.current_rating:
            # Meets or exceeds requirement - full points
            current_score = 100.0
        else:
            # Falls short - penalize proportionally
            ratio = conn_specs.current_rating / req_specs.current_rating
            current_score = max(0.0, ratio * 100.0)
    
    # Average voltage and current scores (or use voltage if current not specified, etc.)
    if req_specs.voltage_rating is not None and req_specs.current_rating is not None:
        return (voltage_score + current_score) / 2.0
    elif req_specs.voltage_rating is not None:
        return voltage_score
    elif req_specs.current_rating is not None:
        return current_score
    else:
        return 100.0  # No electrical requirements - full points


def _calculate_pin_count_score(
    requirement: CustomerRequirement,
    connector: Connector
) -> float:
    """
    Calculate pin count matching score (0-100).
    
    Scores how well the connector's pin count matches the requirements.
    Connectors that meet or are close to requirements score higher. Connectors
    that are far off are penalized proportionally.
    
    Args:
        requirement: Customer requirement
        connector: Connector to score
        
    Returns:
        Float score from 0.0 to 100.0
    """
    req_specs = requirement.specifications
    if not req_specs or req_specs.pin_count is None:
        # No pin count requirement specified - award full points
        return 100.0
    
    conn_specs = connector.specifications
    req_pins = req_specs.pin_count
    conn_pins = conn_specs.pin_count
    
    # If connector has exactly the required pins or more, full score
    if conn_pins >= req_pins:
        return 100.0
    
    # If connector has fewer pins, score based on ratio
    # But be lenient - allow connectors with at least 50% of required pins
    ratio = conn_pins / req_pins
    
    # Score based on how close it is (e.g., 60 pins for 120 requirement = 50%)
    # Minimum score is 0, maximum is 100
    score = max(0.0, ratio * 100.0)
    
    return score


def _calculate_temperature_score(
    requirement: CustomerRequirement,
    connector: Connector
) -> float:
    """
    Calculate temperature range compatibility score (0-100).
    
    Calculates how much the connector's operating temperature range overlaps
    with the required range. Full overlap or better scores 100, partial overlap
    scores proportionally, no overlap scores 0.
    
    Args:
        requirement: Customer requirement
        connector: Connector to score
        
    Returns:
        Float score from 0.0 to 100.0
    """
    req_specs = requirement.specifications
    if not req_specs or not req_specs.min_operating_temp or not req_specs.max_operating_temp:
        # No temperature requirement specified - award full points
        return 100.0
    
    conn_specs = connector.specifications
    
    # Calculate overlap range
    overlap_min = max(req_specs.min_operating_temp, conn_specs.min_operating_temp)
    overlap_max = min(req_specs.max_operating_temp, conn_specs.max_operating_temp)
    
    if overlap_min > overlap_max:
        # No overlap - connector doesn't cover required range
        return 0.0
    
    overlap_range = overlap_max - overlap_min
    required_range = req_specs.max_operating_temp - req_specs.min_operating_temp
    
    if required_range == 0:
        # Degenerate case: required range is a single point
        return 100.0 if overlap_min == overlap_max else 0.0
    
    # Score based on overlap percentage
    overlap_ratio = overlap_range / required_range
    
    # If connector range fully covers required range, award full points
    if (conn_specs.min_operating_temp <= req_specs.min_operating_temp and
        conn_specs.max_operating_temp >= req_specs.max_operating_temp):
        return 100.0
    
    # Otherwise score based on overlap
    return min(overlap_ratio * 100.0, 100.0)


def _calculate_price_score(connector: Connector) -> float:
    """
    Calculate price competitiveness score (0-100).
    
    Lower prices score higher. Normalizes price against maximum reasonable
    price threshold. Prices above threshold score 0.
    
    Formula: (1 - min(price/MAX_PRICE, 1.0)) * 100
    
    Args:
        connector: Connector to score
        
    Returns:
        Float score from 0.0 to 100.0 (higher = better price)
    """
    price = connector.pricing.unit_price_usd
    
    # Normalize price: lower is better
    normalized_price = min(price / MAX_REASONABLE_PRICE_USD, 1.0)
    score = (1.0 - normalized_price) * 100.0
    
    return max(score, 0.0)


def _calculate_lead_time_score(connector: Connector) -> float:
    """
    Calculate lead time score (0-100).
    
    Shorter lead times score higher. Normalizes lead time against maximum
    reasonable lead time threshold. Lead times above threshold score 0.
    
    Formula: (1 - min(lead_time/MAX_LEAD_TIME, 1.0)) * 100
    
    Args:
        connector: Connector to score
        
    Returns:
        Float score from 0.0 to 100.0 (higher = shorter lead time)
    """
    lead_time = connector.pricing.lead_time_days
    
    # Normalize lead time: shorter is better
    normalized_lead_time = min(lead_time / MAX_REASONABLE_LEAD_TIME_DAYS, 1.0)
    score = (1.0 - normalized_lead_time) * 100.0
    
    return max(score, 0.0)


def _calculate_certification_score(
    requirement: CustomerRequirement,
    connector: Connector
) -> float:
    """
    Calculate certification bonus score (0-100).
    
    Scores based on how many required certifications the connector has.
    If all required certifications are present, scores 100. If no requirements
    specified, awards full points.
    
    Args:
        requirement: Customer requirement
        connector: Connector to score
        
    Returns:
        Float score from 0.0 to 100.0
    """
    required_certs = requirement.required_certifications or requirement.certifications
    
    if not required_certs:
        # No certification requirements - award full points
        return 100.0
    
    connector_certs = set(cert.upper() for cert in connector.certifications)
    required_certs_set = set(cert.upper() for cert in required_certs)
    
    matching_count = len(required_certs_set & connector_certs)
    required_count = len(required_certs_set)
    
    if required_count == 0:
        return 100.0
    
    # Score based on percentage of required certifications present
    return (matching_count / required_count) * 100.0

