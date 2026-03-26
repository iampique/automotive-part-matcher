"""
LangGraph-based agent for orchestrating connector matching workflow.

This module implements a multi-node workflow using LangGraph that:
1. Parses requirements from user input using LLM
2. Searches Qdrant vector database for candidate connectors
3. Scores matches using hybrid hard/soft scoring algorithm
4. Ranks and returns top results

The agent tracks execution traces for visualization and debugging,
allowing insight into each step of the matching process.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from app.matching_config import tolerances
from app.models import Connector, CustomerRequirement, MatchResult
from app.services.llm_service import LLMService
from app.services.qdrant_service import QdrantService
from app.services.scoring import calculate_match_score

# Configure logging
logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """
    State definition for the LangGraph agent workflow.
    
    This TypedDict defines all state fields that flow through the graph nodes.
    Each node can read and update these fields as needed.
    """
    input_text: str  # Original user input text
    parsed_requirements: Optional[CustomerRequirement]  # Extracted requirements from LLM
    search_results: List[Tuple[Connector, float]]  # List of (connector, semantic_score) tuples
    scored_matches: List[MatchResult]  # Match results after scoring
    final_results: List[MatchResult]  # Final ranked results (top 10)
    error: Optional[str]  # Error message if any step fails
    execution_trace: List[Dict]  # Execution trace for visualization
    acorn_used: bool  # Whether ACORN algorithm was used in search
    enable_acorn: bool  # Whether to enable ACORN for this search
    hybrid_search_used: bool  # Whether hybrid search was used
    hybrid_search_metadata: Optional[Dict]  # Metadata about hybrid search (keywords, breakdown, etc.)
    fallback_used: bool  # Whether fallback matching was used
    matches_passed_hard_requirements: int  # Number of matches that passed hard requirements


class PartMatcherAgent:
    """
    LangGraph-based agent for orchestrating connector matching workflow.
    
    This agent coordinates multiple services to:
    - Parse requirements from natural language input
    - Search for candidate connectors using semantic similarity
    - Score matches using hybrid hard/soft requirements
    - Rank and return top results
    
    The workflow is visualized through execution traces that track
    each step's duration, status, and output.
    
    Workflow:
    1. parse_requirements -> Extract structured requirements from text
    2. search_qdrant -> Find candidate connectors via vector search
    3. score_matches -> Score each candidate using hybrid algorithm
    4. rank_results -> Select top 10 matches
    """
    
    def __init__(self, llm_service: LLMService, qdrant_service: QdrantService) -> None:
        """
        Initialize the PartMatcherAgent with required services.
        
        Args:
            llm_service: LLM service for requirement extraction
            qdrant_service: Qdrant service for vector search
        """
        self.llm_service = llm_service
        self.qdrant_service = qdrant_service
        
        # Build and compile the LangGraph workflow
        self.graph = self._build_graph()
        
        logger.info("PartMatcherAgent initialized with LangGraph workflow")
    
    def _build_graph(self) -> StateGraph:
        """
        Build and compile the LangGraph workflow.
        
        Creates a state graph with four nodes connected in sequence:
        parse_requirements -> search_qdrant -> score_matches -> rank_results -> END
        
        Returns:
            Compiled StateGraph ready for execution
        """
        # Create StateGraph with AgentState type
        workflow = StateGraph(AgentState)
        
        # Add nodes to the graph
        workflow.add_node("parse_requirements", self._parse_requirements_node)
        workflow.add_node("search_qdrant", self._search_node)
        workflow.add_node("score_matches", self._score_node)
        workflow.add_node("rank_results", self._rank_node)
        
        # Define the workflow edges (execution order)
        workflow.set_entry_point("parse_requirements")
        workflow.add_edge("parse_requirements", "search_qdrant")
        workflow.add_edge("search_qdrant", "score_matches")
        workflow.add_edge("score_matches", "rank_results")
        workflow.add_edge("rank_results", END)
        
        # Compile the graph
        compiled_graph = workflow.compile()
        
        logger.info("LangGraph workflow compiled successfully")
        return compiled_graph
    
    def _parse_requirements_node(self, state: AgentState) -> AgentState:
        """
        Parse requirements from user input using LLM service.
        
        This node extracts structured requirements from natural language text.
        It uses the LLM service to convert free-form input into a CustomerRequirement
        model with specifications, certifications, and other structured fields.
        
        Args:
            state: Current agent state with input_text
            
        Returns:
            Updated state with parsed_requirements populated (or error set)
        """
        start_time = time.time()
        node_name = "parse"
        
        try:
            logger.info(f"Node '{node_name}': Parsing requirements from input text")
            
            # Extract requirements using LLM service
            parsed_requirements = self.llm_service.extract_requirements(state["input_text"])
            
            # Check if parsing actually failed (LLM service returns fallback with error message)
            # The LLM service catches validation errors and returns a fallback requirement
            # with an error message in the description, so we need to detect this
            description = parsed_requirements.description or ""
            parsing_failed = (
                description.startswith("Error") or 
                "error" in description.lower()[:50] or
                "failed" in description.lower()[:50]
            )
            
            # Update state with parsed requirements
            state["parsed_requirements"] = parsed_requirements
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Create output summary
            output_summary = (
                f"Extracted: {parsed_requirements.description[:100]}..."
                if len(parsed_requirements.description) > 100
                else f"Extracted: {parsed_requirements.description}"
            )
            
            # Record in execution trace - mark as error if parsing failed
            if parsing_failed:
                # Parsing failed but we got a fallback requirement
                # Still allow workflow to continue (search can use input_text)
                state["execution_trace"].append({
                    "node": node_name,
                    "duration_ms": duration_ms,
                    "output": output_summary,
                    "status": "error"
                })
                logger.warning(
                    f"Node '{node_name}': Parsing failed but fallback requirement created. "
                    f"Workflow will continue using original input text. ({duration_ms:.1f}ms)"
                )
            else:
                # Record success in execution trace
                state["execution_trace"].append({
                    "node": node_name,
                    "duration_ms": duration_ms,
                    "output": output_summary,
                    "status": "success"
                })
                logger.info(f"Node '{node_name}': Successfully parsed requirements ({duration_ms:.1f}ms)")
            
        except Exception as e:
            error_msg = f"Failed to parse requirements: {str(e)}"
            logger.error(f"Node '{node_name}': {error_msg}")
            
            # Update state with error
            state["error"] = error_msg
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Record failure in execution trace
            state["execution_trace"].append({
                "node": node_name,
                "duration_ms": duration_ms,
                "output": error_msg,
                "status": "error"
            })
        
        # Always return the updated state (required by LangGraph)
        return state
    
    def _detect_product_keywords(self, text: str, parsed_requirements: Optional[CustomerRequirement]) -> List[str]:
        """
        Detect if user query contains specific product name keywords.
        
        Checks both the input text and parsed requirements for potential
        product names or connector identifiers that would benefit from
        hybrid search.
        
        Args:
            text: Original input text
            parsed_requirements: Parsed requirements (may contain part_number or name)
            
        Returns:
            List of detected keywords, empty if none detected
        """
        keywords = []
        
        # Check parsed requirements for part number or name
        if parsed_requirements:
            if parsed_requirements.part_number:
                keywords.append(parsed_requirements.part_number)
            if parsed_requirements.name:
                # Split name into words
                name_words = parsed_requirements.name.split()
                keywords.extend([w for w in name_words if len(w) > 2])
        
        # Extract keywords from input text using QdrantService helper
        # We'll use a simple heuristic: look for capitalized words or quoted strings
        # that might be product names. Skip specification values like IP67, 48V, etc.
        common_words = {
            "need", "needs", "required", "requires", "looking", "search", "find", 
            "want", "wants", "connector", "connectors", "for", "with", "and", "or",
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "should",
            "could", "may", "might", "must", "can", "from", "on", "at", "to", "of",
            "in", "by", "about", "into", "through", "during", "minimum", "maximum",
            "design", "mixed", "iso", "iec", "ul", "per", "section", "contact"
        }
        # Specification patterns to skip (these are values, not product names)
        spec_patterns = ["ip", "v", "a", "c", "°c", "°f", "pin", "pins", "hz", "db", "n", "g"]
        text_keywords = []
        words = text.split()
        for word in words:
            cleaned_word = word.strip('.,!?;:()[]{}"\'').lower()
            # Skip common words
            if cleaned_word in common_words or len(cleaned_word) <= 2:
                continue
            # Skip specification values (IP67, 48V, etc.)
            if any(pattern in cleaned_word for pattern in spec_patterns):
                continue
            # Skip if it starts with a number (likely a spec value like 48V, 120-pin)
            if cleaned_word[0].isdigit():
                continue
            # Skip if it's all uppercase and short (likely an acronym like ISO, IEC, UL)
            if word.isupper() and len(word) <= 5:
                continue
            # Check for quoted strings (likely product names)
            if word.startswith('"') and word.endswith('"'):
                text_keywords.append(word.strip('"'))
            # Check for capitalized words (potential product names) - but skip if it's a common word
            # Only consider words that are proper nouns (capitalized, not at start of sentence)
            elif word[0].isupper() and len(word) > 3 and cleaned_word not in common_words:
                # Additional check: skip if it looks like a section header (all caps or mixed case with numbers)
                if not (word.isupper() or any(c.isdigit() for c in word)):
                    text_keywords.append(word)
        
        keywords.extend(text_keywords)
        
        # Remove duplicates and return - but only if we have meaningful keywords
        # If keywords are too generic, return empty list to avoid hybrid search
        meaningful_keywords = [kw for kw in keywords if len(kw) > 3 and kw.lower() not in common_words]
        return list(set(meaningful_keywords))[:5]  # Limit to 5 keywords
    
    def _search_node(self, state: AgentState) -> AgentState:
        """
        Search Qdrant vector database for candidate connectors.
        
        This node performs semantic search using the parsed requirements.
        It extracts filters from requirements (voltage, current, etc.) and
        searches for connectors that match both semantically and structurally.
        
        Args:
            state: Current agent state with parsed_requirements
            
        Returns:
            Updated state with search_results populated (or error set)
        """
        start_time = time.time()
        node_name = "search"
        
        try:
            logger.info(f"Node '{node_name}': Searching Qdrant for connectors")
            
            # Check if requirements were parsed successfully
            parsed_requirements = state.get("parsed_requirements")
            if parsed_requirements is None:
                error_msg = "Cannot search: requirements not parsed"
                state["error"] = error_msg
                duration_ms = (time.time() - start_time) * 1000
                state["execution_trace"].append({
                    "node": node_name,
                    "duration_ms": duration_ms,
                    "output": error_msg,
                    "status": "error"
                })
                return state
            
            # Note: Even if parsing failed (validation error), parsed_requirements may contain
            # a fallback requirement object with an error message in the description.
            # We still proceed with search using the original input_text, which allows
            # semantic search to work even without properly structured requirements.
            # This is why you may see parsing errors but still get search results.
            
            # Create search query from input text (use original input for semantic search)
            query_text = state["input_text"]
            
            # Detect if query contains product name keywords
            # Only use hybrid search for actual product names/part numbers, not generic terms
            detected_keywords = self._detect_product_keywords(query_text, parsed_requirements)
            # Filter out common words that aren't useful for text matching
            common_words = {"need", "needs", "required", "requires", "looking", "search", "find", "want", "wants"}
            detected_keywords = [kw for kw in detected_keywords if kw.lower() not in common_words]
            
            # Use regular semantic search only (no hybrid) so same query → same code path every time.
            use_hybrid = False
            
            # Initialize hybrid_search_used early to ensure it's always a boolean
            state["hybrid_search_used"] = use_hybrid
            
            if use_hybrid:
                logger.info(f"Detected product name keywords: {detected_keywords}. Using hybrid search mode.")
            
            # Build filters from requirements if specifications exist and are valid
            # NOTE: Apply lenient filters to match scoring logic - for very high requirements,
            # use relaxed thresholds so semantic search can find candidates that will be scored
            filters = None
            try:
                if parsed_requirements.specifications:
                    filter_conditions = {}
                    
                    # Extract voltage filter if specified and valid
                    # Uses centralized tolerance configuration from matching_config.py
                    if (parsed_requirements.specifications.voltage_rating is not None and 
                        isinstance(parsed_requirements.specifications.voltage_rating, (int, float)) and
                        parsed_requirements.specifications.voltage_rating > 0):
                        if "gte" not in filter_conditions:
                            filter_conditions["gte"] = {}
                        
                        voltage_req = int(parsed_requirements.specifications.voltage_rating)
                        threshold = tolerances.get_voltage_threshold(voltage_req)
                        
                        if threshold == 0.0:
                            # Extremely high voltage - skip filter (let semantic search handle it)
                            pass
                        elif threshold < 1.0:
                            # High/very high voltage: use lenient threshold
                            min_voltage = voltage_req * threshold
                            filter_conditions["gte"]["specifications.voltage_rating"] = min_voltage
                            logger.info(f"Using lenient voltage filter: {min_voltage}V ({threshold*100}% of required {voltage_req}V)")
                        else:
                            # Standard voltage: use strict threshold
                            filter_conditions["gte"]["specifications.voltage_rating"] = voltage_req
                    
                    # Extract current filter if specified and valid
                    # Uses centralized tolerance configuration from matching_config.py
                    if (parsed_requirements.specifications.current_rating is not None and 
                        isinstance(parsed_requirements.specifications.current_rating, (int, float)) and
                        parsed_requirements.specifications.current_rating > 0):
                        if "gte" not in filter_conditions:
                            filter_conditions["gte"] = {}
                        
                        current_req = int(parsed_requirements.specifications.current_rating)
                        threshold = tolerances.get_current_threshold(current_req)
                        
                        if threshold == 0.0:
                            # Extremely high current - skip filter (let semantic search handle it)
                            pass
                        elif threshold < 1.0:
                            # High/very high current: use lenient threshold
                            min_current = current_req * threshold
                            filter_conditions["gte"]["specifications.current_rating"] = min_current
                            logger.info(f"Using lenient current filter: {min_current}A ({threshold*100}% of required {current_req}A)")
                        else:
                            # Standard current: use strict threshold
                            filter_conditions["gte"]["specifications.current_rating"] = current_req
                    
                    # Extract pin count filter if specified and valid
                    # Uses centralized tolerance configuration from matching_config.py
                    if (parsed_requirements.specifications.pin_count is not None and 
                        isinstance(parsed_requirements.specifications.pin_count, (int, float)) and
                        parsed_requirements.specifications.pin_count > 0):
                        if "range" not in filter_conditions:
                            filter_conditions["range"] = {}
                        
                        pin_req = int(parsed_requirements.specifications.pin_count)
                        tolerance_percent = tolerances.get_pin_count_tolerance(pin_req)
                        tolerance = int(pin_req * tolerance_percent)
                        min_pins = max(1, pin_req - tolerance)
                        max_pins = pin_req + tolerance
                        
                        filter_conditions["range"]["specifications.pin_count"] = {
                            "gte": min_pins,
                            "lte": max_pins
                        }
                        logger.info(f"Using pin count filter: {min_pins}-{max_pins} pins (required: {pin_req}, tolerance: {tolerance_percent*100}%)")
                    
                    # Extract temperature range filter if specified
                    if (parsed_requirements.specifications.min_operating_temp is not None and
                        parsed_requirements.specifications.max_operating_temp is not None):
                        if "range" not in filter_conditions:
                            filter_conditions["range"] = {}
                        
                        # Connector must support at least the required temperature range
                        # Filter: connector's max_temp >= required max_temp AND connector's min_temp <= required min_temp
                        # We'll use a lenient approach: connector's range should overlap with required range
                        min_temp_req = parsed_requirements.specifications.min_operating_temp
                        max_temp_req = parsed_requirements.specifications.max_operating_temp
                        
                        # Connector's max temp must be >= required min temp (allows overlap)
                        # Connector's min temp must be <= required max temp (allows overlap)
                        # Uses centralized temperature buffer from matching_config.py
                        temp_buffer = tolerances.TEMPERATURE_BUFFER_C
                        filter_conditions["range"]["specifications.max_operating_temp"] = {
                            "gte": min_temp_req - temp_buffer
                        }
                        filter_conditions["range"]["specifications.min_operating_temp"] = {
                            "lte": max_temp_req + temp_buffer
                        }
                        logger.info(f"Using temperature filter: max_temp >= {min_temp_req - temp_buffer}°C, min_temp <= {max_temp_req + temp_buffer}°C")
                    
                    # Extract IP rating filter if specified
                    # IP rating uses hierarchical matching (IP69K > IP68 > IP67 > IP54)
                    if parsed_requirements.specifications.ip_rating:
                        if "match" not in filter_conditions:
                            filter_conditions["match"] = {}
                        # For IP rating, we'll allow exact match or better (handled in scoring)
                        # Here we just filter for exact match, scoring will handle "better" ratings
                        filter_conditions["match"]["specifications.ip_rating"] = parsed_requirements.specifications.ip_rating
                        logger.info(f"Using IP rating filter: {parsed_requirements.specifications.ip_rating}")
                    
                    # Extract connector type filter if specified
                    if parsed_requirements.connector_type:
                        if "match" not in filter_conditions:
                            filter_conditions["match"] = {}
                        filter_conditions["match"]["connector_type"] = parsed_requirements.connector_type
                    
                    if filter_conditions:
                        filters = filter_conditions
            except Exception as e:
                logger.warning(f"Failed to build filters from requirements: {e}. Proceeding without filters.")
                filters = None
            
            # Always use semantic-only search (no filters) so same query → same candidate set every time.
            filters = None
            
            # Perform search with ACORN and hybrid settings from state
            enable_acorn = state.get("enable_acorn", True)  # Default to True if not set
            
            # ACORN is only beneficial when filters are present (it improves recall for restrictive filters)
            # If no filters were built (e.g., parsing failed), ACORN doesn't provide benefit
            has_filters = filters is not None and len(filters) > 0
            # Only use ACORN if filters exist AND it's enabled
            # (QdrantService will also check settings.acorn_enabled internally)
            actual_acorn_enabled = enable_acorn and has_filters
            
            # Use hybrid_search method if keywords detected, otherwise use regular search
            hybrid_metadata = None
            if use_hybrid:
                search_results_with_types, hybrid_metadata = self.qdrant_service.hybrid_search(
                    query_text=query_text,
                    text_keywords=detected_keywords,
                    filters=filters,
                    limit=50,  # Get larger candidate pool for scoring
                    enable_acorn=actual_acorn_enabled
                )
                # Extract (connector, score) tuples from hybrid results
                search_results = [(conn, score) for conn, score, _ in search_results_with_types]
            else:
                search_results = self.qdrant_service.search(
                    query_text=query_text,
                    filters=filters,
                    limit=50,  # Get larger candidate pool for scoring
                    enable_acorn=actual_acorn_enabled,
                    use_hybrid=False
                )
            
            # If search returned no results and we have filters, try again without filters
            # This ensures we always get some candidates for scoring, even if they don't meet strict requirements
            if len(search_results) == 0 and filters:
                logger.warning(
                    f"Search with filters returned 0 results. Retrying without filters to find candidates for scoring."
                )
                if use_hybrid:
                    search_results_with_types, hybrid_metadata = self.qdrant_service.hybrid_search(
                        query_text=query_text,
                        text_keywords=detected_keywords,
                        filters=None,  # Remove filters
                        limit=50,
                        enable_acorn=False  # ACORN not needed without filters
                    )
                    search_results = [(conn, score) for conn, score, _ in search_results_with_types]
                else:
                    search_results = self.qdrant_service.search(
                        query_text=query_text,
                        filters=None,  # Remove filters
                        limit=50,
                        enable_acorn=False,  # ACORN not needed without filters
                        use_hybrid=False
                    )
                # Update ACORN status since we're not using it anymore
                actual_acorn_enabled = False
            
            # Use Qdrant's actual similarity scores for deterministic, consistent ranking
            # (Previously MVP used random scores, which caused different results on every search.)
            scored_results = list(search_results)
            
            # Update state with search results
            # Only mark ACORN as used if it was actually enabled AND filters exist
            # (Note: actual_acorn_enabled may be False if fallback search was used)
            state["search_results"] = scored_results
            state["acorn_used"] = actual_acorn_enabled
            state["hybrid_search_used"] = use_hybrid
            state["hybrid_search_metadata"] = hybrid_metadata
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Record success in execution trace
            trace_entry = {
                "node": node_name,
                "duration_ms": duration_ms,
                "output": f"{len(scored_results)} candidates found",
                "acorn_used": actual_acorn_enabled,  # Only true if filters exist
                "hybrid_search_used": use_hybrid,
                "status": "success"
            }
            if hybrid_metadata:
                trace_entry["hybrid_metadata"] = hybrid_metadata
            state["execution_trace"].append(trace_entry)
            
            logger.info(
                f"Node '{node_name}': Found {len(scored_results)} candidates "
                f"({duration_ms:.1f}ms, ACORN: {actual_acorn_enabled}, Hybrid: {use_hybrid}, Filters: {has_filters})"
            )
            
        except Exception as e:
            error_msg = f"Search failed: {str(e)}"
            logger.error(f"Node '{node_name}': {error_msg}")
            
            # Update state with error and ensure boolean fields are set
            state["error"] = error_msg
            state["search_results"] = []
            state["acorn_used"] = state.get("enable_acorn", False)
            state["hybrid_search_used"] = False  # Ensure it's always a boolean
            state["hybrid_search_metadata"] = None
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Record failure in execution trace
            state["execution_trace"].append({
                "node": node_name,
                "duration_ms": duration_ms,
                "output": error_msg,
                "status": "error"
            })
        
        # Always return the updated state
        return state
    
    def _score_node(self, state: AgentState) -> AgentState:
        """
        Score each candidate connector using hybrid matching algorithm.
        
        This node applies the hybrid scoring algorithm to each candidate connector.
        It checks hard requirements first (must-match criteria), then calculates
        soft scores for connectors that pass. Only connectors with score > 0
        (passed hard requirements) are included in results.
        
        Args:
            state: Current agent state with parsed_requirements and search_results
            
        Returns:
            Updated state with scored_matches populated (or error set)
        """
        start_time = time.time()
        node_name = "score"
        
        try:
            logger.info(f"Node '{node_name}': Scoring candidate connectors")
            
            # Get required state fields
            parsed_requirements = state.get("parsed_requirements")
            search_results = state.get("search_results", [])
            
            if parsed_requirements is None:
                error_msg = "Cannot score: requirements not parsed"
                state["error"] = error_msg
                duration_ms = (time.time() - start_time) * 1000
                state["execution_trace"].append({
                    "node": node_name,
                    "duration_ms": duration_ms,
                    "output": error_msg,
                    "status": "error"
                })
                return state
            
            # Score each candidate connector
            scored_matches = []
            all_scored = []  # Keep all scored connectors for fallback
            
            for connector, semantic_score in search_results:
                try:
                    # Qdrant returns score in 0-100; scoring expects 0-100 (no conversion needed)
                    semantic_score_100 = min(max(semantic_score, 0.0), 100.0)
                    
                    # Calculate match score using hybrid algorithm
                    match_score, explanation = calculate_match_score(
                        requirement=parsed_requirements,
                        connector=connector,
                        semantic_score=semantic_score_100
                    )
                    
                    # Store all scored connectors (for fallback if none pass)
                    match_result = MatchResult(
                        part_number=connector.part_number,
                        name=connector.name,
                        match_score=match_score,
                        match_explanation=explanation,
                        connector=connector
                    )
                    all_scored.append(match_result)
                    
                    # Only include connectors that passed hard requirements (score > 0)
                    if match_score > 0:
                        scored_matches.append(match_result)
                        
                except Exception as e:
                    logger.warning(f"Failed to score connector {connector.part_number}: {e}")
                    continue
            
            # Track if fallback is used
            fallback_used = False
            
            # If no connectors passed hard requirements, use top semantic matches anyway
            # This ensures we always return some results, even if they don't fully meet requirements
            if len(scored_matches) == 0 and len(all_scored) > 0:
                logger.warning(
                    f"No connectors passed hard requirements. Returning top {min(10, len(all_scored))} "
                    f"semantic matches with low scores to ensure results are shown."
                )
                fallback_used = True
                # Sort by semantic score descending, then part_number for deterministic tie-breaking
                all_scored.sort(key=lambda x: (-x.match_score, x.part_number))
                # Take top 10 and mark them as fallback matches
                for match in all_scored[:10]:
                    # Set minimum score of 10 so they appear in results
                    match.match_score = max(10.0, match.match_score)
                    match.is_fallback_match = True
                    match.match_explanation = (
                        f"⚠️ FALLBACK MATCH: This connector did not pass all hard requirements but is shown "
                        f"based on semantic similarity. {match.match_explanation}"
                    )
                scored_matches = all_scored[:10]
            else:
                # Sort by score descending, then part_number for deterministic tie-breaking
                scored_matches.sort(key=lambda x: (-x.match_score, x.part_number))
                # Mark all as non-fallback
                for match in scored_matches:
                    match.is_fallback_match = False
            
            # Store fallback metadata in state for response
            # When fallback_used is False, all matches in scored_matches passed hard requirements
            # When fallback_used is True, no matches passed hard requirements (all are fallback)
            state["fallback_used"] = fallback_used
            state["matches_passed_hard_requirements"] = len(scored_matches) if not fallback_used else 0
            
            # Update state with scored matches
            state["scored_matches"] = scored_matches
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Count how many passed hard requirements
            passed_count = len(scored_matches)
            total_count = len(search_results)
            
            # Record success in execution trace
            state["execution_trace"].append({
                "node": node_name,
                "duration_ms": duration_ms,
                "output": f"{total_count} matches scored, {passed_count} passed hard requirements",
                "status": "success"
            })
            
            logger.info(
                f"Node '{node_name}': Scored {total_count} candidates, "
                f"{passed_count} passed ({duration_ms:.1f}ms)"
            )
            
        except Exception as e:
            error_msg = f"Scoring failed: {str(e)}"
            logger.error(f"Node '{node_name}': {error_msg}")
            
            # Update state with error
            state["error"] = error_msg
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Record failure in execution trace
            state["execution_trace"].append({
                "node": node_name,
                "duration_ms": duration_ms,
                "output": error_msg,
                "status": "error"
            })
        
        # Always return the updated state
        return state
    
    def _rank_node(self, state: AgentState) -> AgentState:
        """
        Rank results and select top matches.
        
        This node selects the top 10 matches from the scored results.
        Since results are already sorted by score, it simply takes the first 10.
        
        Args:
            state: Current agent state with scored_matches
            
        Returns:
            Updated state with final_results populated
        """
        start_time = time.time()
        node_name = "rank"
        
        try:
            logger.info(f"Node '{node_name}': Ranking and selecting top matches")
            
            # Get scored matches
            scored_matches = state.get("scored_matches", [])
            
            # Select top 10 (or fewer if less available)
            top_n = min(10, len(scored_matches))
            final_results = scored_matches[:top_n]
            
            # Update state with final results
            state["final_results"] = final_results
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Record success in execution trace
            state["execution_trace"].append({
                "node": node_name,
                "duration_ms": duration_ms,
                "output": f"Top {top_n} selected",
                "status": "success"
            })
            
            logger.info(f"Node '{node_name}': Selected top {top_n} matches ({duration_ms:.1f}ms)")
            
        except Exception as e:
            error_msg = f"Ranking failed: {str(e)}"
            logger.error(f"Node '{node_name}': {error_msg}")
            
            # Update state with error
            state["error"] = error_msg
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Record failure in execution trace
            state["execution_trace"].append({
                "node": node_name,
                "duration_ms": duration_ms,
                "output": error_msg,
                "status": "error"
            })
        
        # Always return the updated state
        return state
    
    def run(self, input_text: str, enable_acorn: bool = True) -> Dict:
        """
        Execute the complete matching workflow.
        
        This is the main entry point for the agent. It creates an initial state,
        invokes the compiled graph, and returns the final results with execution trace.
        
        Args:
            input_text: User's natural language input describing connector requirements
            enable_acorn: Whether to enable ACORN algorithm for this search (default: True)
            
        Returns:
            Dictionary containing:
            - results: List of MatchResult objects (top 10 matches)
            - execution_trace: List of execution step traces for visualization
            - acorn_used: Boolean indicating if ACORN was used
            
        Raises:
            Exception: If any workflow step fails and sets an error in state
        """
        logger.info(f"Starting matching workflow for input: {input_text[:100]}... (ACORN: {enable_acorn})")
        
        # Create initial state
        initial_state: AgentState = {
            "input_text": input_text,
            "parsed_requirements": None,
            "search_results": [],
            "scored_matches": [],
            "final_results": [],
            "error": None,
            "execution_trace": [],
            "acorn_used": False,
            "enable_acorn": enable_acorn,
            "hybrid_search_used": False,
            "hybrid_search_metadata": None,
            "fallback_used": False,
            "matches_passed_hard_requirements": 0
        }
        
        # Invoke the compiled graph
        try:
            final_state = self.graph.invoke(initial_state)
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            raise
        
        # Check for errors in final state
        if final_state.get("error"):
            error_msg = final_state["error"]
            logger.error(f"Workflow completed with error: {error_msg}")
            raise Exception(error_msg)
        
        # Extract results
        results = final_state.get("final_results", [])
        execution_trace = final_state.get("execution_trace", [])
        acorn_used = final_state.get("acorn_used", False)
        hybrid_search_used = final_state.get("hybrid_search_used", False)
        hybrid_search_metadata = final_state.get("hybrid_search_metadata")
        fallback_used = final_state.get("fallback_used", False)
        matches_passed_hard_requirements = final_state.get("matches_passed_hard_requirements", 0)
        
        # Log execution summary
        total_duration = sum(step.get("duration_ms", 0) for step in execution_trace)
        logger.info(
            f"Workflow completed successfully: {len(results)} results in {total_duration:.1f}ms "
            f"(ACORN: {acorn_used}, Hybrid: {hybrid_search_used}, "
            f"Fallback: {fallback_used}, Passed hard requirements: {matches_passed_hard_requirements})"
        )
        
        return {
            "results": results,
            "execution_trace": execution_trace,
            "acorn_used": acorn_used,
            "hybrid_search_used": hybrid_search_used,
            "hybrid_search_metadata": hybrid_search_metadata,
            "fallback_used": fallback_used,
            "matches_passed_hard_requirements": matches_passed_hard_requirements
        }
    
    def export_workflow_diagram(self, output_path: str) -> str:
        """
        Export workflow diagram as Mermaid code and PNG image.
        
        Generates a visual representation of the LangGraph workflow using
        Mermaid diagram syntax. Also saves a PNG image if graphviz is available.
        
        Args:
            output_path: Path to save the diagram (without extension)
            
        Returns:
            Mermaid diagram code as string
        """
        try:
            # Create custom Mermaid diagram that accurately represents our 4-node workflow
            # LangGraph's built-in draw_mermaid() returns a generic graph, so we create our own
            mermaid_code = """%%{init: {'flowchart': {'curve': 'basis', 'padding': 30, 'nodeSpacing': 50, 'rankSpacing': 80}, 'theme': 'base', 'themeVariables': {'primaryColor': '#e3f2fd', 'primaryTextColor': '#1976d2', 'primaryBorderColor': '#1976d2', 'lineColor': '#64b5f6', 'secondaryColor': '#fff3e0', 'tertiaryColor': '#e8f5e9'}}}%%
graph LR
    Start([Start]):::startclass
    Parse["`**1. Parse Requirements**
    Extract structured specs
    from natural language`"]:::processclass
    Search["`**2. Search Qdrant**
    Find candidates via
    vector similarity`"]:::processclass
    Score["`**3. Score Matches**
    Evaluate using
    hard/soft requirements`"]:::processclass
    Rank["`**4. Rank Results**
    Select top 10
    matches`"]:::processclass
    End([End]):::endclass
    
    Start --> Parse
    Parse --> Search
    Search --> Score
    Score --> Rank
    Rank --> End
    
    classDef startclass fill:#fff3e0,stroke:#ff9800,stroke-width:3px,color:#e65100,font-weight:bold
    classDef endclass fill:#e8f5e9,stroke:#4caf50,stroke-width:3px,color:#2e7d32,font-weight:bold
    classDef processclass fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1,font-size:14px
"""
            
            # Save Mermaid code to file
            mermaid_path = f"{output_path}.mmd"
            with open(mermaid_path, "w") as f:
                f.write(mermaid_code)
            logger.info(f"Workflow diagram saved to {mermaid_path}")
            
            # Try to generate PNG if graphviz is available
            try:
                png_path = f"{output_path}.png"
                # Use mermaid-cli to convert Mermaid to PNG
                import subprocess
                result = subprocess.run(
                    ['mmdc', '-i', mermaid_path, '-o', png_path],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    logger.warning(f"mmdc failed: {result.stderr}")
                    raise Exception(f"mmdc failed: {result.stderr}")
                logger.info(f"Workflow diagram PNG saved to {png_path}")
            except FileNotFoundError:
                logger.warning("mermaid-cli (mmdc) not found. Install with: npm install -g @mermaid-js/mermaid-cli")
            except Exception as e:
                logger.warning(f"Could not generate PNG diagram: {e}")
            
            return mermaid_code
            
        except Exception as e:
            logger.error(f"Failed to export workflow diagram: {e}")
            # Return a simple text representation if diagram export fails
            return """%%{init: {'flowchart': {'curve': 'linear'}}}%%
graph TD
    Start([Start]) --> Parse[parse_requirements]
    Parse --> Search[search_qdrant]
    Search --> Score[score_matches]
    Score --> Rank[rank_results]
    Rank --> End([End])
"""
