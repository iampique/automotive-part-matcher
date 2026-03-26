"""
Matching tolerance and leniency configuration for specification requirements.

This module centralizes all tolerance, threshold, and leniency values used
for matching connectors against customer requirements. These values control
how strictly the system enforces specification requirements.

All values can be overridden via environment variables for fine-tuning.
"""

from app.config import settings


class MatchingTolerances:
    """
    Centralized tolerance configuration for specification matching.
    
    These values control how flexible the matching system is when comparing
    connector specifications against customer requirements. Higher tolerance
    values allow more variation, while lower values enforce stricter matching.
    """
    
    # Pin Count Tolerances (percentage-based)
    PIN_COUNT_TOLERANCE_STANDARD = 0.20  # 20% tolerance for standard pin counts (1-50 pins)
    PIN_COUNT_TOLERANCE_HIGH = 0.30  # 30% tolerance for high pin counts (51-100 pins)
    PIN_COUNT_TOLERANCE_VERY_HIGH = 0.30  # 30% minimum for very high pin counts (>100 pins) - allows connectors with at least 30% of required pins (e.g., 36+ pins for 120 requirement)
    
    # Voltage Rating Thresholds (percentage-based minimum)
    VOLTAGE_THRESHOLD_STANDARD = 1.0  # 100% - strict matching for standard voltage (<100V)
    VOLTAGE_THRESHOLD_HIGH = 0.50  # 50% - lenient for high voltage (100-200V)
    VOLTAGE_THRESHOLD_VERY_HIGH = 0.20  # 20% - very lenient for very high voltage (200-500V)
    VOLTAGE_THRESHOLD_EXTREME = 0.0  # Skip hard requirement for extreme voltage (>500V)
    
    # Voltage thresholds (V) for categorization
    VOLTAGE_HIGH_THRESHOLD = 100  # Above this is "high voltage"
    VOLTAGE_VERY_HIGH_THRESHOLD = 200  # Above this is "very high voltage"
    VOLTAGE_EXTREME_THRESHOLD = 500  # Above this skips hard requirement
    
    # Current Rating Thresholds (percentage-based minimum)
    CURRENT_THRESHOLD_STANDARD = 1.0  # 100% - strict matching for standard current (<50A)
    CURRENT_THRESHOLD_HIGH = 0.50  # 50% - lenient for high current (50-100A)
    CURRENT_THRESHOLD_VERY_HIGH = 0.20  # 20% - very lenient for very high current (100-200A)
    CURRENT_THRESHOLD_EXTREME = 0.0  # Skip hard requirement for extreme current (>200A)
    
    # Current thresholds (A) for categorization
    CURRENT_HIGH_THRESHOLD = 50  # Above this is "high current"
    CURRENT_VERY_HIGH_THRESHOLD = 100  # Above this is "very high current"
    CURRENT_EXTREME_THRESHOLD = 200  # Above this skips hard requirement
    
    # Pin Count Thresholds (pins) for categorization
    PIN_COUNT_HIGH_THRESHOLD = 50  # Above this is "high pin count"
    PIN_COUNT_VERY_HIGH_THRESHOLD = 100  # Above this is "very high pin count"
    
    # Temperature Range Buffer (°C)
    TEMPERATURE_BUFFER_C = 20  # Allow ±20°C buffer for temperature range matching
    
    # IP Rating Leniency
    IP_RATING_VERY_HIGH_MINIMUM = "IP67"  # Minimum acceptable for IP69K requirement
    IP_RATING_HIGH_MINIMUM = "IP67"  # Minimum acceptable for IP68 requirement
    IP_RATING_STANDARD_TOLERANCE_LEVELS = 1  # Allow within 1 level for standard IP ratings
    
    @classmethod
    def get_pin_count_tolerance(cls, pin_count: int) -> float:
        """
        Get pin count tolerance percentage based on pin count value.
        
        Args:
            pin_count: Required pin count
            
        Returns:
            Tolerance percentage (0.0-1.0)
        """
        if pin_count > cls.PIN_COUNT_VERY_HIGH_THRESHOLD:
            return cls.PIN_COUNT_TOLERANCE_VERY_HIGH
        elif pin_count > cls.PIN_COUNT_HIGH_THRESHOLD:
            return cls.PIN_COUNT_TOLERANCE_HIGH
        else:
            return cls.PIN_COUNT_TOLERANCE_STANDARD
    
    @classmethod
    def get_voltage_threshold(cls, voltage: int) -> float:
        """
        Get voltage threshold percentage based on voltage value.
        
        Args:
            voltage: Required voltage rating
            
        Returns:
            Threshold percentage (0.0-1.0), where 0.0 means skip hard requirement
        """
        if voltage > cls.VOLTAGE_EXTREME_THRESHOLD:
            return cls.VOLTAGE_THRESHOLD_EXTREME
        elif voltage > cls.VOLTAGE_VERY_HIGH_THRESHOLD:
            return cls.VOLTAGE_THRESHOLD_VERY_HIGH
        elif voltage > cls.VOLTAGE_HIGH_THRESHOLD:
            return cls.VOLTAGE_THRESHOLD_HIGH
        else:
            return cls.VOLTAGE_THRESHOLD_STANDARD
    
    @classmethod
    def get_current_threshold(cls, current: int) -> float:
        """
        Get current threshold percentage based on current value.
        
        Args:
            current: Required current rating
            
        Returns:
            Threshold percentage (0.0-1.0), where 0.0 means skip hard requirement
        """
        if current > cls.CURRENT_EXTREME_THRESHOLD:
            return cls.CURRENT_THRESHOLD_EXTREME
        elif current > cls.CURRENT_VERY_HIGH_THRESHOLD:
            return cls.CURRENT_THRESHOLD_VERY_HIGH
        elif current > cls.CURRENT_HIGH_THRESHOLD:
            return cls.CURRENT_THRESHOLD_HIGH
        else:
            return cls.CURRENT_THRESHOLD_STANDARD


# Module-level instance for easy access
tolerances = MatchingTolerances()

