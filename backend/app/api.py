"""
FastAPI application exposing HTTP endpoints for the connector matching system.

This module provides a REST API for the frontend to interact with the matching system.
Supports Qdrant 1.16 ACORN feature for improved search performance and includes
comprehensive error handling, logging, and performance metrics.
"""

import logging
import re
import time
from typing import Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.agent import PartMatcherAgent
from app.config import settings
from app.models import ACORNComparisonResponse, SearchResponse
from app.services.document_parser import DocumentParser
from app.services.llm_service import LLMService
from app.services.qdrant_service import QdrantService

# Configure logging
logger = logging.getLogger(__name__)


def _normalize_search_input(text: str) -> str:
    """
    Normalize search input so paste and file upload of the same content
    produce the same string for consistent embedding and LLM extraction.
    """
    if not text:
        return text
    # Strip and collapse any run of whitespace (spaces, newlines, tabs) to a single space
    return re.sub(r"\s+", " ", text.strip())

# Initialize FastAPI application
app = FastAPI(
    title="Automotive Connector Matcher API",
    version="1.0.0",
    description="REST API for automotive connector matching with Qdrant 1.16 ACORN support",
    tags_metadata=[
        {
            "name": "Search",
            "description": "Search and match connectors based on requirements",
        },
        {
            "name": "Health",
            "description": "Health check and API information endpoints",
        },
        {
            "name": "Stats",
            "description": "Collection statistics and monitoring",
        },
        {
            "name": "Connectors",
            "description": "Individual connector information",
        },
        {
            "name": "Workflow",
            "description": "Workflow visualization and documentation",
        },
    ],
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize global service instances (singletons reused across requests)
logger.info("Initializing global service instances...")
llm_service = LLMService(provider=settings.llm_provider)
qdrant_service = QdrantService()
# Ensure collection and indexes exist (including text index for hybrid search)
try:
    qdrant_service.create_collection()
    logger.info("Collection and indexes verified/created successfully")
except Exception as e:
    logger.warning(f"Failed to ensure collection indexes: {e}. Indexes may need to be created manually.")
agent = PartMatcherAgent(llm_service=llm_service, qdrant_service=qdrant_service)
document_parser = DocumentParser()
logger.info("Global service instances initialized successfully")


@app.get("/", tags=["Health"])
async def root() -> Dict[str, str]:
    """
    API root endpoint for discovery and basic health check.
    
    Returns:
        Dictionary with API name, version, and status
    """
    return {
        "name": "Automotive Connector Matcher API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint to verify service availability.
    
    Returns:
        Dictionary with health status and Qdrant connection status
    """
    try:
        # Optionally verify Qdrant connection
        stats = qdrant_service.get_collection_stats()
        qdrant_status = "connected" if stats else "disconnected"
    except Exception as e:
        logger.warning(f"Health check: Qdrant connection issue: {e}")
        qdrant_status = "disconnected"
    
    return {
        "status": "healthy",
        "qdrant": qdrant_status
    }


@app.post("/api/search", response_model=SearchResponse, tags=["Search"])
async def search_connectors(
    text_input: Optional[str] = Form(None, description="Free-form text describing connector requirements"),
    file: Optional[UploadFile] = File(None, description="PDF or DOCX document with requirements"),
    llm_provider: Optional[str] = Form(None, description="LLM provider override ('claude' or 'openai')"),
    top_k: int = Form(10, ge=1, le=20, description="Number of top results to return"),
    enable_acorn: bool = Form(True, description="Enable Qdrant 1.16 ACORN algorithm")
) -> SearchResponse:
    """
    Search for connectors matching the provided requirements.
    
    This endpoint accepts either:
    - Direct text input describing requirements
    - A PDF or DOCX file containing requirements
    
    The workflow:
    1. Parses requirements from input (using LLM if needed)
    2. Searches Qdrant vector database for candidates
    3. Scores matches using hybrid hard/soft requirements
    4. Returns top K ranked results
    
    Args:
        text_input: Optional text description of requirements
        file: Optional PDF or DOCX file with requirements
        llm_provider: Optional LLM provider override for this request
        top_k: Number of top results to return (1-20, default: 10)
        enable_acorn: Whether to use ACORN algorithm (default: True)
        
    Returns:
        SearchResponse with matched connectors, execution trace, and metadata
        
    Raises:
        HTTPException 400: If neither text_input nor file is provided
        HTTPException 500: If search fails
    """
    start_time = time.time()
    
    try:
        # Determine input text to process
        input_text = None
        
        if text_input and text_input.strip():
            # Use direct text input
            input_text = _normalize_search_input(text_input)
            logger.info(f"Search request: Using direct text input ({len(input_text)} characters)")
            
        elif file:
            # Process uploaded file
            logger.info(f"Search request: Processing uploaded file '{file.filename}'")
            
            # Read file bytes
            file_bytes = await file.read()
            
            if not file_bytes:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded file is empty"
                )
            
            # Extract text using document parser
            try:
                filename = file.filename or "document"
                # DocumentParser has static methods, but instance can call them
                raw_text = document_parser.parse_document(file_bytes, filename)
                input_text = _normalize_search_input(raw_text)
                logger.info(f"Extracted {len(input_text)} characters from document")
            except Exception as e:
                logger.error(f"Document parsing failed: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse document: {str(e)}"
                )
        else:
            # Neither provided
            raise HTTPException(
                status_code=400,
                detail="Either text_input or file must be provided"
            )
        
        # Determine which agent to use (may need new instance if provider changed)
        agent_to_use = agent
        
        if llm_provider and llm_provider.lower() != settings.llm_provider.lower():
            # Create new agent with specified provider for this request
            logger.info(f"Creating agent with provider override: {llm_provider}")
            request_llm_service = LLMService(provider=llm_provider)
            agent_to_use = PartMatcherAgent(
                llm_service=request_llm_service,
                qdrant_service=qdrant_service
            )
        
        # Run the agent workflow
        logger.info(f"Starting agent workflow with top_k={top_k}, enable_acorn={enable_acorn}")
        agent_result = agent_to_use.run(input_text, enable_acorn=enable_acorn)
        
        # Extract results
        results = agent_result["results"]
        execution_trace = agent_result["execution_trace"]
        acorn_used = agent_result["acorn_used"]
        hybrid_search_used = agent_result.get("hybrid_search_used", False)
        hybrid_search_metadata = agent_result.get("hybrid_search_metadata")
        fallback_used = agent_result.get("fallback_used", False)
        matches_passed_hard_requirements = agent_result.get("matches_passed_hard_requirements", 0)
        
        # Limit results to requested top_k
        limited_results = results[:top_k]
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Create query summary with fallback indicator
        search_mode = "hybrid" if hybrid_search_used else "semantic"
        if fallback_used:
            query_summary = (
                f"Found {len(limited_results)} connectors using {search_mode} search "
                f"(⚠️ Fallback: No connectors passed hard requirements, showing semantic matches)"
            )
        else:
            query_summary = (
                f"Found {len(limited_results)} matching connectors using {search_mode} search "
                f"({matches_passed_hard_requirements} passed hard requirements)"
            )
        
        # Build hybrid search breakdown if available
        hybrid_search_breakdown = None
        if hybrid_search_used and hybrid_search_metadata:
            hybrid_search_breakdown = {
                "match_breakdown": hybrid_search_metadata.get("match_breakdown", {}),
                "text_keywords_used": hybrid_search_metadata.get("text_keywords_used", []),
                "hybrid_used": hybrid_search_metadata.get("hybrid_used", False)
            }
        
        logger.info(
            f"Search completed: {len(limited_results)} results in {processing_time_ms:.1f}ms "
            f"(ACORN: {acorn_used}, Hybrid: {hybrid_search_used})"
        )
        
        # Create and return response
        return SearchResponse(
            matches=limited_results,
            processing_time_ms=processing_time_ms,
            query_summary=query_summary,
            acorn_used=acorn_used,
            hybrid_search_used=hybrid_search_used,
            hybrid_search_breakdown=hybrid_search_breakdown,
            execution_trace=execution_trace,
            fallback_used=fallback_used,
            matches_passed_hard_requirements=matches_passed_hard_requirements
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (they're already properly formatted)
        raise
    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )


@app.post("/api/search/compare-acorn", response_model=ACORNComparisonResponse, tags=["Search"])
async def compare_acorn_search(
    text_input: Optional[str] = Form(None, description="Free-form text describing connector requirements"),
    file: Optional[UploadFile] = File(None, description="PDF or DOCX document with requirements"),
    llm_provider: Optional[str] = Form(None, description="LLM provider override ('claude' or 'openai')"),
    top_k: int = Form(10, ge=1, le=20, description="Number of top results to return")
) -> ACORNComparisonResponse:
    """
    Compare search results with and without ACORN algorithm.
    
    This endpoint demonstrates the effectiveness of Qdrant 1.16 ACORN by running
    the same search twice - once with ACORN enabled and once disabled. It returns
    performance metrics, result quality comparisons, and recommendations on when
    to use ACORN.
    
    The endpoint accepts the same parameters as the regular search endpoint and
    executes both searches sequentially, tracking performance for each.
    
    Args:
        text_input: Optional text description of requirements
        file: Optional PDF or DOCX file with requirements
        llm_provider: Optional LLM provider override for this request
        top_k: Number of top results to return (1-20, default: 10)
        
    Returns:
        ACORNComparisonResponse with:
        - acorn_results: SearchResponse with ACORN enabled
        - standard_results: SearchResponse with ACORN disabled
        - comparison: Dictionary with metrics and recommendations
        
    Raises:
        HTTPException 400: If neither text_input nor file is provided
        HTTPException 500: If both searches fail
    """
    start_time = time.time()
    
    # Determine input text to process (same logic as regular search)
    input_text = None
    acorn_results = None
    standard_results = None
    acorn_error = None
    standard_error = None
    
    try:
        if text_input and text_input.strip():
            input_text = text_input.strip()
            logger.info(f"ACORN comparison request: Using direct text input ({len(input_text)} characters)")
        elif file:
            logger.info(f"ACORN comparison request: Processing uploaded file '{file.filename}'")
            file_bytes = await file.read()
            
            if not file_bytes:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded file is empty"
                )
            
            try:
                filename = file.filename or "document"
                input_text = document_parser.parse_document(file_bytes, filename)
                logger.info(f"Extracted {len(input_text)} characters from document")
            except Exception as e:
                logger.error(f"Document parsing failed: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse document: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Either text_input or file must be provided"
            )
        
        # Determine which agent to use
        agent_to_use = agent
        if llm_provider and llm_provider.lower() != settings.llm_provider.lower():
            logger.info(f"Creating agent with provider override: {llm_provider}")
            request_llm_service = LLMService(provider=llm_provider)
            agent_to_use = PartMatcherAgent(
                llm_service=request_llm_service,
                qdrant_service=qdrant_service
            )
        
        # Run search with ACORN enabled
        logger.info("=" * 60)
        logger.info("ACORN Comparison: Running search WITH ACORN enabled")
        logger.info("=" * 60)
        acorn_start = time.time()
        
        try:
            agent_result_acorn = agent_to_use.run(input_text, enable_acorn=True)
            results_acorn = agent_result_acorn["results"]
            execution_trace_acorn = agent_result_acorn["execution_trace"]
            acorn_used_acorn = agent_result_acorn["acorn_used"]
            limited_results_acorn = results_acorn[:top_k]
            acorn_time_ms = (time.time() - acorn_start) * 1000
            
            # Extract hybrid search info from ACORN results
            hybrid_search_used_acorn = agent_result_acorn.get("hybrid_search_used", False)
            hybrid_search_metadata_acorn = agent_result_acorn.get("hybrid_search_metadata")
            hybrid_search_breakdown_acorn = None
            if hybrid_search_used_acorn and hybrid_search_metadata_acorn:
                hybrid_search_breakdown_acorn = {
                    "match_breakdown": hybrid_search_metadata_acorn.get("match_breakdown", {}),
                    "text_keywords_used": hybrid_search_metadata_acorn.get("text_keywords_used", []),
                    "hybrid_used": hybrid_search_metadata_acorn.get("hybrid_used", False)
                }
            
            acorn_results = SearchResponse(
                matches=limited_results_acorn,
                processing_time_ms=acorn_time_ms,
                query_summary=f"Found {len(limited_results_acorn)} matching connectors (ACORN enabled)",
                acorn_used=acorn_used_acorn,
                hybrid_search_used=hybrid_search_used_acorn,
                hybrid_search_breakdown=hybrid_search_breakdown_acorn,
                execution_trace=execution_trace_acorn
            )
            
            logger.info(
                f"ACORN search completed: {len(limited_results_acorn)} results in {acorn_time_ms:.1f}ms"
            )
        except Exception as e:
            acorn_error = str(e)
            logger.error(f"ACORN search failed: {e}", exc_info=True)
            # Create empty results for comparison
            acorn_results = SearchResponse(
                matches=[],
                processing_time_ms=0.0,
                query_summary="ACORN search failed",
                acorn_used=False,
                execution_trace=None
            )
        
        # Run search with ACORN disabled
        logger.info("=" * 60)
        logger.info("ACORN Comparison: Running search WITHOUT ACORN (standard)")
        logger.info("=" * 60)
        standard_start = time.time()
        
        try:
            agent_result_standard = agent_to_use.run(input_text, enable_acorn=False)
            results_standard = agent_result_standard["results"]
            execution_trace_standard = agent_result_standard["execution_trace"]
            acorn_used_standard = agent_result_standard["acorn_used"]
            limited_results_standard = results_standard[:top_k]
            standard_time_ms = (time.time() - standard_start) * 1000
            
            # Extract hybrid search info from standard results
            hybrid_search_used_standard = agent_result_standard.get("hybrid_search_used", False)
            hybrid_search_metadata_standard = agent_result_standard.get("hybrid_search_metadata")
            hybrid_search_breakdown_standard = None
            if hybrid_search_used_standard and hybrid_search_metadata_standard:
                hybrid_search_breakdown_standard = {
                    "match_breakdown": hybrid_search_metadata_standard.get("match_breakdown", {}),
                    "text_keywords_used": hybrid_search_metadata_standard.get("text_keywords_used", []),
                    "hybrid_used": hybrid_search_metadata_standard.get("hybrid_used", False)
                }
            
            standard_results = SearchResponse(
                matches=limited_results_standard,
                processing_time_ms=standard_time_ms,
                query_summary=f"Found {len(limited_results_standard)} matching connectors (standard search)",
                acorn_used=acorn_used_standard,
                hybrid_search_used=hybrid_search_used_standard,
                hybrid_search_breakdown=hybrid_search_breakdown_standard,
                execution_trace=execution_trace_standard
            )
            
            logger.info(
                f"Standard search completed: {len(limited_results_standard)} results in {standard_time_ms:.1f}ms"
            )
        except Exception as e:
            standard_error = str(e)
            logger.error(f"Standard search failed: {e}", exc_info=True)
            # Create empty results for comparison
            standard_results = SearchResponse(
                matches=[],
                processing_time_ms=0.0,
                query_summary="Standard search failed",
                acorn_used=False,
                execution_trace=None
            )
        
        # Check if both searches failed
        if acorn_error and standard_error:
            raise HTTPException(
                status_code=500,
                detail=f"Both searches failed. ACORN error: {acorn_error}. Standard error: {standard_error}"
            )
        
        # Calculate comparison metrics
        latency_difference_ms = acorn_results.processing_time_ms - standard_results.processing_time_ms
        latency_increase_percent = 0.0
        if standard_results.processing_time_ms > 0:
            latency_increase_percent = (latency_difference_ms / standard_results.processing_time_ms) * 100
        
        result_count_acorn = len(acorn_results.matches)
        result_count_standard = len(standard_results.matches)
        
        # Get top scores
        top_score_acorn = acorn_results.matches[0].match_score if acorn_results.matches else 0.0
        top_score_standard = standard_results.matches[0].match_score if standard_results.matches else 0.0
        
        # Estimate filter selectivity (simplified heuristic)
        # If we have fewer results than top_k, filters are likely restrictive
        selectivity_estimate = (min(result_count_acorn, result_count_standard) / top_k) * 100 if top_k > 0 else 100
        
        # Determine recommendation
        recommendation = "Standard sufficient"
        explanation_parts = []
        
        if selectivity_estimate < 40:
            recommendation = "Use ACORN"
            explanation_parts.append(
                f"Filter selectivity is estimated at {selectivity_estimate:.1f}% (restrictive filters). "
                "ACORN is optimized for high-selectivity queries."
            )
        elif latency_increase_percent < 300 and top_score_acorn >= top_score_standard:
            # Less than 3x latency increase and equal or better results
            if top_score_acorn > top_score_standard:
                recommendation = "Use ACORN"
                explanation_parts.append(
                    f"ACORN provides better results ({top_score_acorn:.1f} vs {top_score_standard:.1f} top score) "
                    f"with only {latency_increase_percent:.1f}% latency increase."
                )
            else:
                recommendation = "Use ACORN"
                explanation_parts.append(
                    f"ACORN provides equivalent results with {latency_increase_percent:.1f}% latency increase, "
                    "which is acceptable for improved search quality."
                )
        else:
            if latency_increase_percent > 300:
                explanation_parts.append(
                    f"ACORN increases latency by {latency_increase_percent:.1f}% ({latency_difference_ms:.1f}ms), "
                    "which may not be justified for this query."
                )
            if top_score_acorn < top_score_standard:
                explanation_parts.append(
                    f"Standard search provides better results ({top_score_standard:.1f} vs {top_score_acorn:.1f} top score)."
                )
            explanation_parts.append("Standard search is sufficient for this query type.")
        
        explanation = " ".join(explanation_parts) if explanation_parts else "Both methods perform similarly for this query."
        
        # Add error context if present
        if acorn_error:
            explanation += f" Note: ACORN search encountered an error: {acorn_error}"
        if standard_error:
            explanation += f" Note: Standard search encountered an error: {standard_error}"
        
        comparison = {
            "latency_difference_ms": round(latency_difference_ms, 2),
            "latency_increase_percent": round(latency_increase_percent, 2),
            "result_count_acorn": result_count_acorn,
            "result_count_standard": result_count_standard,
            "top_score_acorn": round(top_score_acorn, 2),
            "top_score_standard": round(top_score_standard, 2),
            "selectivity_estimate": round(selectivity_estimate, 2),
            "recommendation": recommendation,
            "explanation": explanation
        }
        
        total_time_ms = (time.time() - start_time) * 1000
        logger.info("=" * 60)
        logger.info("ACORN Comparison Summary:")
        logger.info(f"  ACORN: {result_count_acorn} results in {acorn_results.processing_time_ms:.1f}ms (top score: {top_score_acorn:.1f})")
        logger.info(f"  Standard: {result_count_standard} results in {standard_results.processing_time_ms:.1f}ms (top score: {top_score_standard:.1f})")
        logger.info(f"  Latency difference: {latency_difference_ms:.1f}ms ({latency_increase_percent:.1f}%)")
        logger.info(f"  Selectivity estimate: {selectivity_estimate:.1f}%")
        logger.info(f"  Recommendation: {recommendation}")
        logger.info(f"  Total comparison time: {total_time_ms:.1f}ms")
        logger.info("=" * 60)
        
        return ACORNComparisonResponse(
            acorn_results=acorn_results,
            standard_results=standard_results,
            comparison=comparison
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"ACORN comparison failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )


@app.get("/api/stats", tags=["Stats"])
async def get_stats() -> Dict:
    """
    Get Qdrant collection statistics.
    
    Returns information about the connector collection including:
    - Total number of connectors (points)
    - Number of indexed vectors
    - Collection status
    - Segment count
    
    Returns:
        Dictionary with collection statistics
        
    Raises:
        HTTPException 500: If statistics retrieval fails
    """
    try:
        stats = qdrant_service.get_collection_stats()
        logger.info(f"Retrieved collection stats: {stats['points_count']} points")
        return stats
    except Exception as e:
        error_msg = f"Failed to retrieve statistics: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )


@app.get("/api/connector/{part_number}", tags=["Connectors"])
async def get_connector(part_number: str) -> Dict:
    """
    Get detailed information for a specific connector by part number.
    
    Searches the Qdrant collection for a connector with the specified part number
    and returns its complete information including specifications, certifications,
    applications, and pricing.
    
    Args:
        part_number: Part number of the connector to retrieve
        
    Returns:
        Dictionary containing the connector data
        
    Raises:
        HTTPException 404: If connector not found
        HTTPException 500: If search fails
    """
    try:
        logger.info(f"Searching for connector with part number: {part_number}")
        
        # Search for connector by part number using exact match filter
        results = qdrant_service.search(
            query_text=part_number,
            filters={"match": {"part_number": part_number}},
            limit=1,
            enable_acorn=False  # Not needed for exact match
        )
        
        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"Connector with part number '{part_number}' not found"
            )
        
        # Extract connector from results
        connector, _ = results[0]
        
        logger.info(f"Found connector: {connector.name}")
        
        # Return connector as dictionary
        return connector.model_dump()
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        error_msg = f"Failed to retrieve connector: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )


@app.get("/api/connector/{part_number}/similar", tags=["Connectors"])
async def get_similar_connectors(
    part_number: str,
    limit: int = 5,
) -> Dict:
    """
    Find similar connectors to the specified connector using Qdrant's recommendation API.
    
    Uses Qdrant's recommend method to discover alternative connectors with similar
    specifications, applications, and characteristics. This showcases Qdrant's
    recommendation capability beyond simple search, helping users discover alternatives
    when a specific connector might not be available or when exploring options.
    
    Args:
        part_number: Part number of the connector to find similar ones for
        limit: Maximum number of similar connectors to return (default: 5, max: 20)
        
    Returns:
        Dictionary containing:
        - similar_connectors: List of similar connectors with similarity scores
        - base_connector: The connector that was used as the reference
        - explanation: Explanation of why these connectors are similar
        
    Raises:
        HTTPException 404: If connector with part_number is not found
        HTTPException 400: If limit is invalid
        HTTPException 500: If recommendation fails
    """
    try:
        # Validate limit
        if limit < 1 or limit > 20:
            raise HTTPException(
                status_code=400,
                detail="Limit must be between 1 and 20"
            )
        
        logger.info(f"Finding similar connectors for part number: {part_number} (limit: {limit})")
        
        # First, get the base connector to include in response
        base_connector_results = qdrant_service.search(
            query_text=part_number,
            filters={"match": {"part_number": part_number}},
            limit=1,
            enable_acorn=False
        )
        
        if not base_connector_results:
            raise HTTPException(
                status_code=404,
                detail=f"Connector with part number '{part_number}' not found"
            )
        
        base_connector, _ = base_connector_results[0]
        
        # Find similar connectors using recommendation API
        similar_results = qdrant_service.find_similar_connectors(
            connector_part_number=part_number,
            limit=limit
        )
        
        # Build explanation of why connectors are similar
        # Compare key specifications
        base_specs = base_connector.specifications
        similar_connectors_data = []
        
        for similar_connector, similarity_score in similar_results:
            similar_specs = similar_connector.specifications
            
            # Build similarity explanation
            similarity_points = []
            
            if similar_specs.pin_count == base_specs.pin_count:
                similarity_points.append(f"same pin count ({similar_specs.pin_count})")
            
            if similar_connector.connector_type == base_connector.connector_type:
                similarity_points.append(f"same connector type ({similar_connector.connector_type})")
            
            if similar_specs.ip_rating == base_specs.ip_rating:
                similarity_points.append(f"same IP rating ({similar_specs.ip_rating})")
            
            # Check voltage range (within 20%)
            voltage_diff = abs(similar_specs.voltage_rating - base_specs.voltage_rating)
            if voltage_diff / base_specs.voltage_rating <= 0.2:
                similarity_points.append(f"similar voltage rating ({similar_specs.voltage_rating}V vs {base_specs.voltage_rating}V)")
            
            # Check current range (within 20%)
            current_diff = abs(similar_specs.current_rating - base_specs.current_rating)
            if current_diff / base_specs.current_rating <= 0.2:
                similarity_points.append(f"similar current rating ({similar_specs.current_rating}A vs {base_specs.current_rating}A)")
            
            # Check temperature range overlap
            temp_overlap = (
                max(similar_specs.min_operating_temp, base_specs.min_operating_temp) <=
                min(similar_specs.max_operating_temp, base_specs.max_operating_temp)
            )
            if temp_overlap:
                similarity_points.append("overlapping temperature range")
            
            # Build explanation
            if similarity_points:
                explanation = f"Similar because: {', '.join(similarity_points[:3])}."
            else:
                explanation = f"Similar based on overall specifications and semantic similarity ({similarity_score:.1f}% match)."
            
            similar_connectors_data.append({
                "connector": similar_connector.model_dump(),
                "similarity_score": round(similarity_score, 2),
                "explanation": explanation
            })
        
        # Build overall explanation
        overall_explanation = (
            f"Found {len(similar_connectors_data)} similar connectors to '{base_connector.name}'. "
            f"These connectors share similar specifications, applications, or characteristics "
            f"based on semantic similarity analysis."
        )
        
        logger.info(
            f"Found {len(similar_connectors_data)} similar connectors for '{part_number}'"
        )
        
        return {
            "similar_connectors": similar_connectors_data,
            "base_connector": base_connector.model_dump(),
            "explanation": overall_explanation,
            "count": len(similar_connectors_data)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        # Connector not found
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        error_msg = f"Failed to find similar connectors: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )


@app.get("/api/workflow-diagram", tags=["Workflow"])
async def get_workflow_diagram() -> Dict[str, str]:
    """
    Get workflow diagram in Mermaid format for visualization.
    
    Exports the LangGraph workflow as Mermaid diagram code that can be
    rendered in documentation or visualization tools.
    
    Returns:
        Dictionary with mermaid_code (and optionally png_base64 if available)
        
    Raises:
        HTTPException 500: If diagram export fails
    """
    try:
        logger.info("Exporting workflow diagram")
        
        # Export diagram (saves to temp file, returns Mermaid code)
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mmd") as tmp_file:
            temp_path = tmp_file.name
        
        try:
            mermaid_code = agent.export_workflow_diagram(temp_path)
            
            # Check if PNG was also generated
            png_path = temp_path.replace(".mmd", ".png")
            png_base64 = None
            
            if os.path.exists(png_path):
                import base64
                with open(png_path, "rb") as f:
                    png_data = f.read()
                    png_base64 = base64.b64encode(png_data).decode("utf-8")
                os.unlink(png_path)  # Clean up temp PNG
            
            # Clean up temp Mermaid file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            
            result = {"mermaid_code": mermaid_code}
            if png_base64:
                result["png_base64"] = png_base64
            
            logger.info("Workflow diagram exported successfully")
            return result
            
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
            
    except Exception as e:
        error_msg = f"Failed to export workflow diagram: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )
