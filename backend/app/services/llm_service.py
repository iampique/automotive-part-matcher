"""
LLM service for natural language understanding in requirement extraction and match explanation.

This module provides functionality to extract structured requirements from document text
and generate human-readable explanations for connector matches using large language models.
Supports both Claude (Anthropic) and OpenAI providers with comprehensive error handling
and retry logic for production reliability.

Token Costs and API Limits:
- Claude Sonnet 4.5: ~$3 per 1M input tokens, ~$15 per 1M output tokens
- GPT-4o: ~$2.50 per 1M input tokens, ~$10 per 1M output tokens
- Both providers have rate limits that vary by tier
- Retry logic handles transient failures (rate limits, timeouts)
"""

import json
import logging
import re
import time
from typing import Optional

from anthropic import Anthropic
from anthropic._exceptions import OverloadedError as AnthropicOverloadedError
from openai import OpenAI

from app.config import settings
from app.models import Connector, CustomerRequirement, PartialConnectorSpecifications

# Configure logging
logger = logging.getLogger(__name__)

# Retry configuration for transient failures
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0


class LLMService:
    """
    LLM service for requirement extraction and match explanation generation.
    
    Provides methods to interact with large language models (Claude or OpenAI) for:
    - Extracting structured requirements from unstructured document text
    - Generating explanations for connector matches
    
    The service handles provider selection, API calls, error handling, and response
    parsing with graceful degradation for production reliability.
    
    Supported Providers:
    - Claude (Anthropic): Uses claude-sonnet-4-5-20250929 model
    - OpenAI: Uses gpt-4o model with JSON mode
    """
    
    def __init__(self, provider: Optional[str] = None) -> None:
        """
        Initialize LLM service with specified or default provider.
        
        Sets up the appropriate LLM client based on provider selection. Validates
        provider choice and initializes API clients with keys from settings.
        
        Args:
            provider: Optional provider override ('claude' or 'openai').
                     If None, uses provider from settings.
        
        Raises:
            ValueError: If provider is invalid (not 'claude' or 'openai')
        """
        # Determine provider (parameter override or settings default)
        self.provider = (provider or settings.llm_provider).lower()
        
        # Validate provider
        if self.provider not in ("claude", "openai"):
            error_msg = f"Invalid LLM provider: {self.provider}. Must be 'claude' or 'openai'"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Initialize appropriate client
        if self.provider == "claude":
            self.client = Anthropic(api_key=settings.anthropic_api_key)
            logger.info("Initialized LLM service with Claude (Anthropic) provider")
        else:  # openai
            self.client = OpenAI(api_key=settings.openai_api_key)
            logger.info("Initialized LLM service with OpenAI provider")
    
    def extract_requirements(self, document_text: str) -> CustomerRequirement:
        """
        Extract structured requirements from document text using LLM.
        
        Processes unstructured document text and extracts structured connector
        requirements matching the CustomerRequirement model. Handles various
        edge cases including incomplete information, parsing errors, and API failures.
        
        Args:
            document_text: Raw text content from parsed document
            
        Returns:
            CustomerRequirement model instance with extracted fields.
            If extraction fails, returns minimal requirement with description only.
            
        Note:
            Uses retry logic for transient API failures. Returns graceful fallback
            if all retries fail or JSON parsing fails.
        """
        try:
            logger.info(f"Starting requirement extraction using {self.provider} provider")
            
            # Validate input
            if not document_text or not document_text.strip():
                logger.warning("Empty document text provided, returning minimal requirement")
                return CustomerRequirement(description="No requirements found in document")
            
            # Create prompts
            system_prompt = self._get_extraction_system_prompt()
            user_prompt = self._get_extraction_user_prompt(document_text)
            
            # Make API call with retry logic (JSON mode for structured extraction)
            response_text = self._call_llm_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                operation="requirement_extraction",
                use_json_mode=True,
                max_tokens=2000
            )
            
            # Parse and validate response
            requirement = self._parse_requirement_response(response_text)
            
            # Log successful extraction
            extracted_fields = []
            if requirement.description:
                extracted_fields.append("description")
            if requirement.specifications:
                extracted_fields.append("specifications")
            if requirement.connector_type:
                extracted_fields.append("connector_type")
            if requirement.certifications:
                extracted_fields.append("certifications")
            if requirement.required_certifications:
                extracted_fields.append("required_certifications")
            if requirement.applications:
                extracted_fields.append("applications")
            if requirement.pricing:
                extracted_fields.append("pricing")
            
            logger.info(
                f"Successfully extracted requirements with fields: {', '.join(extracted_fields)}"
            )
            
            return requirement
            
        except Exception as e:
            error_str = str(e)
            # Provide user-friendly error messages
            if "529" in error_str or "overloaded" in error_str.lower():
                error_msg = (
                    "Anthropic API is temporarily overloaded. "
                    "Please try again in a few moments. "
                    "If the issue persists, you can switch to OpenAI provider in settings."
                )
            elif "rate limit" in error_str.lower() or "429" in error_str:
                error_msg = (
                    "API rate limit exceeded. Please wait a moment and try again."
                )
            else:
                error_msg = f"Error extracting requirements: {error_str}. Please review document manually."
            
            logger.error(f"Failed to extract requirements: {e}")
            # Return graceful fallback
            return CustomerRequirement(
                description=error_msg
            )
    
    def generate_explanation(
        self,
        requirement: CustomerRequirement,
        connector: Connector,
        match_score: float
    ) -> str:
        """
        Generate explanation for why a connector matches the requirements.
        
        Creates a human-readable explanation that highlights key strengths,
        considerations, and provides a recommendation. Designed to be concise
        and professional for end-user consumption.
        
        Args:
            requirement: Customer requirement that was matched
            connector: Connector that matched the requirement
            match_score: Match score between 0.0 and 100.0
            
        Returns:
            Explanation string (under 150 words). Returns fallback explanation
            if LLM call fails.
        """
        try:
            logger.info(
                f"Generating match explanation for connector {connector.part_number} "
                f"(score: {match_score:.1f})"
            )
            
            # Create explanation prompt
            prompt = self._get_explanation_prompt(requirement, connector, match_score)
            
            # Make API call with retry logic (non-JSON mode for explanations)
            system_prompt = "You are an expert technical writer specializing in automotive connector specifications."
            response_text = self._call_llm_with_retry(
                system_prompt=system_prompt,
                user_prompt=prompt,
                operation="explanation_generation",
                use_json_mode=False,
                max_tokens=300  # Limit for concise explanations
            )
            
            # Clean and return explanation
            explanation = response_text.strip()
            
            logger.info(f"Generated explanation ({len(explanation)} characters)")
            return explanation
            
        except Exception as e:
            logger.warning(f"Failed to generate explanation: {e}. Using fallback explanation.")
            return self._get_fallback_explanation(match_score)
    
    def _get_extraction_system_prompt(self) -> str:
        """Get system prompt for requirement extraction."""
        return """You are an expert at extracting technical requirements for automotive connectors from documents.

Your task is to analyze document text and extract structured connector requirements.

CRITICAL INSTRUCTIONS:
- Return ONLY valid JSON (no markdown, no preamble, no code blocks)
- Match the CustomerRequirement structure exactly
- Use null for fields not found in the text
- Be precise with numbers and units
- Extract specifications only if explicitly mentioned
- Return empty arrays [] for lists if no items found
- Return null for optional objects if not found

JSON Schema to return:
{
  "description": "string (required - main requirement description)",
  "specifications": {
    "pin_count": integer or null,
    "voltage_rating": integer or null,
    "current_rating": integer or null,
    "min_operating_temp": integer or null,
    "max_operating_temp": integer or null,
    "ip_rating": "string or null (e.g., IP67, IP68)",
    "housing_material": "string or null",
    "contact_material": "string or null",
    "contact_plating": "string or null"
  } or null,
  "required_certifications": ["string"] or null,
  "connector_type": "string or null",
  "applications": ["string"] or null,
  "pricing": {
    "unit_price_usd": float (MUST be > 0 if pricing is included),
    "lead_time_days": integer (MUST be >= 0 if pricing is included)
  } or null
}

IMPORTANT RULES:
- Include "specifications" with ANY fields that are explicitly mentioned (partial specifications are allowed)
- Extract individual specification fields independently (e.g., if only pin_count is mentioned, include just pin_count)
- Only include "pricing" if BOTH unit_price_usd (> 0) AND lead_time_days (>= 0) are explicitly mentioned in the document
- If pricing information is incomplete (e.g., only lead time mentioned without price), set "pricing" to null
- If NO specification fields are found, set "specifications" to null

Remember: Return ONLY the JSON object, nothing else."""
    
    def _get_extraction_user_prompt(self, document_text: str) -> str:
        """Get user prompt for requirement extraction."""
        # Truncate document text if too long (leave room for prompt)
        max_doc_length = 100000  # Leave room for prompt overhead
        if len(document_text) > max_doc_length:
            document_text = document_text[:max_doc_length] + "\n\n[Document truncated...]"
        
        return f"""Extract connector requirements from the following document text.

Document text:
{document_text}

Extract all connector requirements following the JSON schema. Be precise and use null for unknown values. Return ONLY the JSON object."""
    
    def _get_explanation_prompt(
        self,
        requirement: CustomerRequirement,
        connector: Connector,
        match_score: float
    ) -> str:
        """Get prompt for explanation generation."""
        # Format requirement details
        req_lines = [f"Description: {requirement.description}"]
        if requirement.connector_type:
            req_lines.append(f"Type: {requirement.connector_type}")
        if requirement.specifications:
            spec = requirement.specifications
            req_lines.append(f"Specifications:")
            req_lines.append(f"  - Pins: {spec.pin_count if spec.pin_count is not None else 'Not specified'}")
            req_lines.append(f"  - Voltage: {spec.voltage_rating}V" if spec.voltage_rating is not None else "  - Voltage: Not specified")
            req_lines.append(f"  - Current: {spec.current_rating}A" if spec.current_rating is not None else "  - Current: Not specified")
            req_lines.append(f"  - Temperature: {spec.min_operating_temp}°C to {spec.max_operating_temp}°C" if spec.min_operating_temp is not None and spec.max_operating_temp is not None else "  - Temperature: Not specified")
            req_lines.append(f"  - IP Rating: {spec.ip_rating}" if spec.ip_rating else "  - IP Rating: Not specified")
        if requirement.required_certifications:
            req_lines.append(f"Required Certifications: {', '.join(requirement.required_certifications)}")
        if requirement.applications:
            req_lines.append(f"Applications: {', '.join(requirement.applications)}")
        
        requirement_text = "\n".join(req_lines)
        
        # Format connector details
        connector_lines = [
            f"Part Number: {connector.part_number}",
            f"Name: {connector.name}",
            f"Description: {connector.description}",
            f"Type: {connector.connector_type}",
            f"Specifications:",
            f"  - Pins: {connector.specifications.pin_count}",
            f"  - Voltage: {connector.specifications.voltage_rating}V",
            f"  - Current: {connector.specifications.current_rating}A",
            f"  - Temperature: {connector.specifications.min_operating_temp}°C to {connector.specifications.max_operating_temp}°C",
            f"  - IP Rating: {connector.specifications.ip_rating}",
            f"  - Housing Material: {connector.specifications.housing_material}",
            f"  - Contact Material: {connector.specifications.contact_material}",
            f"  - Contact Plating: {connector.specifications.contact_plating}",
        ]
        if connector.certifications:
            connector_lines.append(f"Certifications: {', '.join(connector.certifications)}")
        if connector.applications:
            connector_lines.append(f"Applications: {', '.join(connector.applications)}")
        
        connector_text = "\n".join(connector_lines)
        
        return f"""Explain why this connector matches the customer requirements.

Tone: Concise (under 150 words), professional, specific

Customer Requirements:
{requirement_text}

Connector Details:
{connector_text}

Match Score: {match_score:.1f}/100.0

Provide an explanation with:
1. Key strengths (why it's a good match)
2. Considerations or trade-offs (if any)
3. Brief summary recommendation

Keep it concise and professional."""
    
    def _call_llm_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        operation: str,
        use_json_mode: bool = True,
        max_tokens: int = 2000
    ) -> str:
        """
        Call LLM API with retry logic for transient failures.
        
        Implements exponential backoff retry for rate limits, timeouts, and
        other transient API errors. Logs token usage and latency.
        
        Args:
            system_prompt: System prompt for the LLM
            user_prompt: User prompt for the LLM
            operation: Operation name for logging (e.g., "requirement_extraction")
            use_json_mode: Whether to use JSON mode for OpenAI (default: True)
            max_tokens: Maximum tokens in response (default: 2000)
            
        Returns:
            Response text from LLM
            
        Raises:
            Exception: If all retries fail or non-transient error occurs
        """
        last_exception = None
        
        for attempt in range(MAX_RETRIES):
            try:
                start_time = time.time()
                
                if self.provider == "claude":
                    response = self.client.messages.create(
                        model="claude-sonnet-4-5-20250929",
                        max_tokens=max_tokens,
                        temperature=settings.extraction_temperature,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}]
                    )
                    
                    # Extract response text
                    response_text = response.content[0].text
                    
                    # Log token usage if available
                    if hasattr(response, 'usage'):
                        usage = response.usage
                        logger.info(
                            f"Claude API call completed - "
                            f"Input tokens: {usage.input_tokens}, "
                            f"Output tokens: {usage.output_tokens}"
                        )
                
                else:  # openai
                    # Build OpenAI request parameters
                    request_params = {
                        "model": "gpt-4o",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "max_tokens": max_tokens,
                        "temperature": settings.extraction_temperature,
                    }
                    if settings.extraction_temperature == 0.0:
                        request_params["seed"] = 42  # reproducible when temperature is 0
                    if use_json_mode:
                        request_params["response_format"] = {"type": "json_object"}
                    
                    response = self.client.chat.completions.create(**request_params)
                    
                    # Extract response text
                    response_text = response.choices[0].message.content
                    
                    # Log token usage if available
                    if hasattr(response, 'usage'):
                        usage = response.usage
                        logger.info(
                            f"OpenAI API call completed - "
                            f"Input tokens: {usage.prompt_tokens}, "
                            f"Output tokens: {usage.completion_tokens}"
                        )
                
                latency_ms = (time.time() - start_time) * 1000
                logger.info(f"{operation} completed in {latency_ms:.1f}ms using {self.provider}")
                
                return response_text
                
            except AnthropicOverloadedError as e:
                # Handle Anthropic's OverloadedError (529) specifically
                # Overloaded errors need longer retry delays
                last_exception = e
                is_retryable = True
                if attempt < MAX_RETRIES - 1:
                    # Longer delay for overloaded errors: 2s, 4s, 8s
                    wait_time = RETRY_DELAY_SECONDS * 2 * (2 ** attempt)
                    logger.warning(
                        f"{operation} failed: Anthropic API is overloaded (529). "
                        f"This is a temporary issue. Retrying in {wait_time:.1f}s... "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"{operation} failed after {MAX_RETRIES} attempts: API overloaded")
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                
                # Check if error is retryable (rate limit, timeout, network, overloaded)
                # Error 529 is Anthropic's OverloadedError - API is temporarily overloaded
                is_retryable = any(keyword in error_msg for keyword in [
                    "rate limit",
                    "timeout",
                    "network",
                    "connection",
                    "temporarily unavailable",
                    "overloaded",
                    "503",
                    "429",
                    "529"
                ]) or (hasattr(e, 'status_code') and e.status_code in [429, 503, 529])
                
                if is_retryable and attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"{operation} failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                else:
                    # Non-retryable error or last attempt
                    logger.error(f"{operation} failed: {e}")
                    if attempt == MAX_RETRIES - 1:
                        raise Exception(f"{operation} failed after {MAX_RETRIES} attempts: {e}") from last_exception
                    raise
        
        # Should not reach here, but handle just in case
        raise Exception(f"{operation} failed after {MAX_RETRIES} attempts") from last_exception
    
    def _parse_requirement_response(self, response_text: str) -> CustomerRequirement:
        """
        Parse LLM response text into CustomerRequirement model.
        
        Handles markdown code blocks, JSON parsing errors, and invalid structures.
        Returns graceful fallback if parsing fails.
        
        Args:
            response_text: Raw response text from LLM
            
        Returns:
            CustomerRequirement instance. Falls back to minimal requirement if parsing fails.
        """
        try:
            # Clean response text (remove markdown code blocks if present)
            cleaned_text = self._clean_json_response(response_text)
            
            # Parse JSON
            parsed_data = json.loads(cleaned_text)
            
            # Validate that description exists (required field)
            if not parsed_data.get("description"):
                logger.warning("LLM response missing required 'description' field")
                parsed_data["description"] = "Requirements extracted but description not found"
            
            # Clean up specifications - PartialConnectorSpecifications allows partial fields
            # Include specifications if ANY field is provided (partial specifications are supported)
            if "specifications" in parsed_data and parsed_data["specifications"]:
                specs = parsed_data["specifications"]
                
                # Remove None values and empty strings, keep only fields with actual values
                cleaned_specs = {
                    k: v for k, v in specs.items() 
                    if v is not None and v != "" and (not isinstance(v, (int, float)) or v > 0)
                }
                
                # Only include specifications if at least one field was extracted
                if cleaned_specs:
                    parsed_data["specifications"] = cleaned_specs
                    logger.info(f"Extracted partial specifications with fields: {list(cleaned_specs.keys())}")
                else:
                    # No valid specification fields found - set to None
                    logger.info("No valid specification fields found, setting specifications to None")
                    parsed_data["specifications"] = None
            else:
                # No specifications provided at all
                parsed_data["specifications"] = None
            
            # Clean up pricing - ConnectorPricing has required fields
            # If pricing is provided but incomplete, set to None
            if "pricing" in parsed_data and parsed_data["pricing"]:
                pricing = parsed_data["pricing"]
                
                # Handle empty dict or None
                if not pricing or (isinstance(pricing, dict) and len(pricing) == 0):
                    logger.warning("Pricing is empty dict, setting to None")
                    parsed_data["pricing"] = None
                else:
                    # ConnectorPricing requires unit_price_usd > 0.0 and lead_time_days >= 0
                    unit_price = pricing.get("unit_price_usd")
                    lead_time = pricing.get("lead_time_days")
                    
                    # Check if pricing is valid
                    has_valid_price = (
                        unit_price is not None and 
                        isinstance(unit_price, (int, float)) and 
                        float(unit_price) > 0.0
                    )
                    has_valid_lead_time = (
                        lead_time is not None and 
                        isinstance(lead_time, (int, float)) and 
                        int(lead_time) >= 0
                    )
                    
                    if has_valid_price and has_valid_lead_time:
                        # Pricing is valid, keep it
                        parsed_data["pricing"] = {
                            "unit_price_usd": float(unit_price),
                            "lead_time_days": int(lead_time)
                        }
                    else:
                        # Pricing is incomplete or invalid - set to None
                        logger.warning(
                            f"Pricing provided but invalid (unit_price_usd: {unit_price}, "
                            f"lead_time_days: {lead_time}), setting to None"
                        )
                        parsed_data["pricing"] = None
            
            # Create CustomerRequirement model
            requirement = CustomerRequirement(**parsed_data)
            
            return requirement
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}...")  # Log first 500 chars
            # Return minimal requirement with error message
            return CustomerRequirement(
                description=f"Error parsing requirements: {str(e)}. Please review document manually."
            )
        except Exception as e:
            logger.warning(f"Failed to create CustomerRequirement from parsed data: {e}")
            logger.debug(f"Parsed data: {parsed_data if 'parsed_data' in locals() else 'N/A'}")
            # Return minimal requirement
            return CustomerRequirement(
                description=f"Error creating requirement model: {str(e)}. Please review document manually."
            )
    
    def _clean_json_response(self, text: str) -> str:
        """
        Clean JSON response by removing markdown code blocks.
        
        Removes ```json and ``` markers that LLMs sometimes wrap JSON in.
        
        Args:
            text: Raw response text
            
        Returns:
            Cleaned text with markdown markers removed
        """
        # Remove markdown code blocks
        text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'```$', '', text)
        text = text.strip()
        
        return text
    
    def _get_fallback_explanation(self, match_score: float) -> str:
        """
        Generate fallback explanation when LLM call fails.
        
        Creates a generic explanation based on match score.
        
        Args:
            match_score: Match score between 0.0 and 100.0
            
        Returns:
            Generic explanation string
        """
        if match_score >= 80.0:
            return (
                f"This connector is an excellent match (score: {match_score:.1f}/100) "
                "for your requirements. It meets the key technical specifications and "
                "is recommended for your application."
            )
        elif match_score >= 60.0:
            return (
                f"This connector is a good match (score: {match_score:.1f}/100) "
                "for your requirements. Review the specifications to ensure all "
                "critical requirements are met."
            )
        else:
            return (
                f"This connector is a partial match (score: {match_score:.1f}/100). "
                "Please review the specifications carefully to determine if it meets "
                "your specific needs."
            )

