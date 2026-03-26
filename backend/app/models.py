"""
Data models for the automotive part matcher.

This module defines Pydantic models representing the core data structures for the
connector matching system. These models provide type safety, validation, and
serialization for connectors, customer requirements, and search results.

The models are designed to work with:
- Qdrant vector database for similarity search
- FastAPI for API request/response serialization
- ORM/database systems via model_config settings

Qdrant 1.16 Features:
- ACORN (Approximate Clustering for Retrieval Networks) can be enabled for improved
  search performance on large collections
- The SearchRequest model includes an enable_acorn flag to control ACORN usage
- Match scores and execution traces support ACORN result visualization
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class PartialConnectorSpecifications(BaseModel):
    """
    Partial technical specifications for customer requirements.
    
    This model allows individual specification fields to be optional, enabling
    partial requirement extraction from natural language queries. Each field
    can be extracted independently and used for filtering/scoring.
    """
    
    model_config = {"from_attributes": True}
    
    pin_count: Optional[int] = Field(
        default=None,
        description="Number of electrical pins/contacts in the connector",
        gt=0
    )
    
    voltage_rating: Optional[int] = Field(
        default=None,
        description="Maximum voltage rating in volts",
        gt=0
    )
    
    current_rating: Optional[int] = Field(
        default=None,
        description="Maximum current rating in amps",
        gt=0
    )
    
    min_operating_temp: Optional[int] = Field(
        default=None,
        description="Minimum operating temperature in degrees Celsius"
    )
    
    max_operating_temp: Optional[int] = Field(
        default=None,
        description="Maximum operating temperature in degrees Celsius"
    )
    
    ip_rating: Optional[str] = Field(
        default=None,
        description="IP (Ingress Protection) rating indicating protection level against dust and water (e.g., IP67, IP68)"
    )
    
    housing_material: Optional[str] = Field(
        default=None,
        description="Material used for the connector housing (e.g., 'Nylon', 'Polyamide', 'Metal')"
    )
    
    contact_material: Optional[str] = Field(
        default=None,
        description="Material used for the electrical contacts (e.g., 'Copper', 'Brass', 'Phosphor Bronze')"
    )
    
    contact_plating: Optional[str] = Field(
        default=None,
        description="Surface plating on contacts for corrosion resistance and conductivity (e.g., 'Tin', 'Gold', 'Silver')"
    )
    
    @model_validator(mode="after")
    def validate_temperature_range(self) -> "PartialConnectorSpecifications":
        """Validate that maximum temperature is greater than minimum temperature if both are provided."""
        if (self.min_operating_temp is not None and 
            self.max_operating_temp is not None and 
            self.max_operating_temp < self.min_operating_temp):
            raise ValueError("Maximum operating temperature must be greater than minimum operating temperature")
        return self
    
    def has_any_specification(self) -> bool:
        """Check if any specification field is provided."""
        return any([
            self.pin_count is not None,
            self.voltage_rating is not None,
            self.current_rating is not None,
            self.min_operating_temp is not None,
            self.max_operating_temp is not None,
            self.ip_rating is not None,
            self.housing_material is not None,
            self.contact_material is not None,
            self.contact_plating is not None
        ])


class ConnectorSpecifications(BaseModel):
    """
    Complete technical specifications for an automotive connector.
    
    This model represents the complete technical specifications required to
    match connectors based on electrical, environmental, and material properties.
    All fields are required for full connector specifications.
    """
    
    model_config = {"from_attributes": True}
    
    pin_count: int = Field(
        ...,
        description="Number of electrical pins/contacts in the connector",
        gt=0
    )
    
    voltage_rating: int = Field(
        ...,
        description="Maximum voltage rating in volts",
        gt=0
    )
    
    current_rating: int = Field(
        ...,
        description="Maximum current rating in amps",
        gt=0
    )
    
    min_operating_temp: int = Field(
        ...,
        description="Minimum operating temperature in degrees Celsius"
    )
    
    max_operating_temp: int = Field(
        ...,
        description="Maximum operating temperature in degrees Celsius"
    )
    
    ip_rating: str = Field(
        ...,
        description="IP (Ingress Protection) rating indicating protection level against dust and water (e.g., IP67, IP68)"
    )
    
    housing_material: str = Field(
        ...,
        description="Material used for the connector housing (e.g., 'Nylon', 'Polyamide', 'Metal')"
    )
    
    contact_material: str = Field(
        ...,
        description="Material used for the electrical contacts (e.g., 'Copper', 'Brass', 'Phosphor Bronze')"
    )
    
    contact_plating: str = Field(
        ...,
        description="Surface plating on contacts for corrosion resistance and conductivity (e.g., 'Tin', 'Gold', 'Silver')"
    )
    
    @model_validator(mode="after")
    def validate_temperature_range(self) -> "ConnectorSpecifications":
        """Validate that maximum temperature is greater than minimum temperature."""
        if self.max_operating_temp < self.min_operating_temp:
            raise ValueError("Maximum operating temperature must be greater than minimum operating temperature")
        return self


class ConnectorPricing(BaseModel):
    """
    Pricing and availability information for a connector.
    
    This model represents commercial information including unit pricing
    and lead time for procurement planning.
    """
    
    model_config = {"from_attributes": True}
    
    unit_price_usd: float = Field(
        ...,
        description="Unit price in US dollars",
        gt=0.0
    )
    
    lead_time_days: int = Field(
        ...,
        description="Lead time for delivery in days",
        ge=0
    )


class Connector(BaseModel):
    """
    Complete connector data model.
    
    This is the main data structure representing an automotive connector
    with all its specifications, certifications, applications, and pricing.
    Used for storage in the vector database and as the source of truth
    for connector information.
    """
    
    model_config = {"from_attributes": True}
    
    part_number: str = Field(
        ...,
        description="Unique part number identifier for the connector",
        min_length=1
    )
    
    name: str = Field(
        ...,
        description="Human-readable name of the connector",
        min_length=1
    )
    
    description: str = Field(
        ...,
        description="Detailed description of the connector, its features, and use cases",
        min_length=1
    )
    
    connector_type: str = Field(
        ...,
        description="Type or category of connector (e.g., 'Circular', 'Rectangular', 'Terminal Block')",
        min_length=1
    )
    
    specifications: ConnectorSpecifications = Field(
        ...,
        description="Complete technical specifications for the connector"
    )
    
    certifications: List[str] = Field(
        ...,
        description="List of certifications and standards the connector meets (e.g., 'ISO 9001', 'UL', 'CE')",
        min_length=0
    )
    
    applications: List[str] = Field(
        ...,
        description="List of automotive applications where this connector is commonly used",
        min_length=0
    )
    
    pricing: ConnectorPricing = Field(
        ...,
        description="Pricing and availability information"
    )


class CustomerRequirement(BaseModel):
    """
    Customer requirement model for connector matching.
    
    Represents parsed requirements from customer input where not all fields
    may be extracted. All fields except description are optional to handle
    incomplete requirement specifications. This model is used as input for
    the matching/search process.
    """
    
    model_config = {"from_attributes": True}
    
    part_number: Optional[str] = Field(
        default=None,
        description="Optional part number if customer specifies a known part"
    )
    
    name: Optional[str] = Field(
        default=None,
        description="Optional connector name if provided by customer"
    )
    
    description: str = Field(
        ...,
        description="Required description of the connector requirement - this is the primary search input",
        min_length=1
    )
    
    connector_type: Optional[str] = Field(
        default=None,
        description="Optional connector type if specified by customer"
    )
    
    specifications: Optional[PartialConnectorSpecifications] = Field(
        default=None,
        description="Optional technical specifications if extracted from customer input. Supports partial specifications where individual fields can be extracted independently."
    )
    
    certifications: Optional[List[str]] = Field(
        default=None,
        description="Optional list of required certifications"
    )
    
    applications: Optional[List[str]] = Field(
        default=None,
        description="Optional list of intended applications"
    )
    
    pricing: Optional[ConnectorPricing] = Field(
        default=None,
        description="Optional pricing constraints if specified"
    )
    
    required_certifications: Optional[List[str]] = Field(
        default=None,
        description="Additional list of required certifications beyond the standard certifications field"
    )


class MatchResult(BaseModel):
    """
    Search result for a matched connector.
    
    Represents a single connector match with its relevance score and explanation.
    Used in search responses to show why a connector was matched and how well
    it fits the requirements.
    """
    
    model_config = {"from_attributes": True}
    
    part_number: str = Field(
        ...,
        description="Part number of the matched connector",
        min_length=1
    )
    
    name: str = Field(
        ...,
        description="Name of the matched connector",
        min_length=1
    )
    
    match_score: float = Field(
        ...,
        description="Relevance match score between 0.0 and 100.0, where higher scores indicate better matches",
        ge=0.0,
        le=100.0
    )
    
    match_explanation: str = Field(
        ...,
        description="Human-readable explanation of why this connector was matched and how it meets the requirements",
        min_length=1
    )
    
    connector: Connector = Field(
        ...,
        description="Complete connector object with all specifications and details"
    )
    
    is_fallback_match: bool = Field(
        default=False,
        description="Whether this match is a fallback result (did not pass hard requirements but shown due to semantic similarity)"
    )
    
    @field_validator("match_score")
    @classmethod
    def validate_match_score(cls, v: float) -> float:
        """Validate that match score is between 0.0 and 100.0."""
        if not 0.0 <= v <= 100.0:
            raise ValueError(f"Match score must be between 0.0 and 100.0, got {v}")
        return v


class SearchRequest(BaseModel):
    """
    Request model for connector search operations.
    
    Represents the input parameters for searching and matching connectors
    against customer requirements. Supports both text-based and structured
    requirement searches.
    """
    
    model_config = {"from_attributes": True}
    
    text_input: Optional[str] = Field(
        default=None,
        description="Optional free-form text input describing connector requirements"
    )
    
    llm_provider: Optional[str] = Field(
        default=None,
        description="Optional LLM provider override ('claude' or 'openai') for requirement parsing"
    )
    
    top_k: int = Field(
        default=10,
        description="Number of top results to return (between 1 and 20)",
        ge=1,
        le=20
    )
    
    enable_acorn: bool = Field(
        default=True,
        description="Enable Qdrant 1.16 ACORN feature for improved search performance on large collections"
    )
    
    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        """Validate that top_k is between 1 and 20."""
        if not 1 <= v <= 20:
            raise ValueError(f"top_k must be between 1 and 20, got {v}")
        return v


class SearchResponse(BaseModel):
    """
    Response model for connector search operations.
    
    Contains the search results along with metadata about the search execution,
    including processing time, query summary, and execution trace for debugging
    and workflow visualization. Supports both ACORN and hybrid search features.
    """
    
    model_config = {"from_attributes": True}
    
    matches: List[MatchResult] = Field(
        ...,
        description="List of matched connectors ordered by relevance score (highest first)",
        min_length=0
    )
    
    processing_time_ms: float = Field(
        ...,
        description="Total processing time for the search operation in milliseconds",
        ge=0.0
    )
    
    query_summary: str = Field(
        ...,
        description="Summary of the parsed query and search strategy used",
        min_length=1
    )
    
    acorn_used: bool = Field(
        ...,
        description="Whether Qdrant 1.16 ACORN feature was used for this search"
    )
    
    hybrid_search_used: bool = Field(
        default=False,
        description="Whether hybrid search (combining vector similarity with text matching) was used"
    )
    
    hybrid_search_breakdown: Optional[Dict] = Field(
        default=None,
        description="Breakdown of hybrid search results showing which matches came from text vs semantic search. Includes match_breakdown with counts for 'vector', 'text', and 'both' match types, and text_keywords_used."
    )
    
    execution_trace: Optional[List[Dict]] = Field(
        default=None,
        description="Optional execution trace for workflow visualization and debugging. Contains step-by-step information about the search process"
    )
    
    fallback_used: bool = Field(
        default=False,
        description="Whether fallback matching was used (no connectors passed hard requirements, so semantic matches were returned)"
    )
    
    matches_passed_hard_requirements: int = Field(
        default=0,
        description="Number of matches that passed hard requirements (vs fallback matches)"
    )


class ACORNComparisonResponse(BaseModel):
    """
    Response model for ACORN comparison endpoint.
    
    Contains results from both ACORN-enabled and standard searches along with
    performance comparison metrics and recommendations.
    """
    
    model_config = {"from_attributes": True}
    
    acorn_results: SearchResponse = Field(
        ...,
        description="Search results with ACORN algorithm enabled"
    )
    
    standard_results: SearchResponse = Field(
        ...,
        description="Search results with ACORN algorithm disabled (standard search)"
    )
    
    comparison: Dict = Field(
        ...,
        description="Comparison metrics and recommendations including latency differences, result quality, and when ACORN helps"
    )
