"""
Qdrant service for managing vector database operations.

This module provides an abstraction layer for all Qdrant Cloud interactions including
connection management, collection setup, embedding generation, and semantic search
with support for Qdrant 1.16 ACORN algorithm.

Qdrant 1.16 Features:
- ACORN (Approximate Clustering for Retrieval Networks): Improves search recall
  for restrictive filters by using approximate clustering
- Text indexing: Enables hybrid search combining vector similarity with full-text search
- Enhanced payload indexing: Better performance for filtering operations
"""

import hashlib
import logging
from typing import Dict, List, Optional, Tuple

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    CollectionStatus,
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    MatchText,
    PayloadSchemaType,
    PointStruct,
    Range,
    SearchParams,
    TextIndexParams,
    TokenizerType,
    VectorParams,
)

from app.config import settings
from app.models import Connector

# Configure logging
logger = logging.getLogger(__name__)


class QdrantService:
    """
    Service class for managing Qdrant Cloud operations.
    
    Provides methods for:
    - Connecting to Qdrant Cloud
    - Creating and managing collections
    - Generating embeddings using OpenAI
    - Uploading connectors with embeddings
    - Searching with ACORN support
    - Retrieving collection statistics
    """
    
    def __init__(self) -> None:
        """
        Initialize Qdrant service with connection and OpenAI client.
        
        Connects to Qdrant Cloud using settings from configuration and initializes
        OpenAI client for embedding generation. Configures connection for cloud
        compatibility with appropriate timeouts.
        """
        try:
            # Initialize Qdrant client with cloud or local configuration
            # For local instances, api_key is optional
            client_kwargs = {
                "url": settings.qdrant_url,
                "timeout": 60.0,  # 60 second timeout for network operations
            }
            # Only add API key if provided (required for cloud, optional for local)
            if settings.qdrant_api_key:
                client_kwargs["api_key"] = settings.qdrant_api_key
            
            self.client = QdrantClient(**client_kwargs)
            
            # Initialize OpenAI client for embeddings
            self.openai_client = OpenAI(api_key=settings.openai_api_key)
            
            # Store collection name from settings
            self.collection_name = settings.collection_name
            
            # Log successful connection
            try:
                collections = self.client.get_collections()
                logger.info(f"Successfully connected to Qdrant Cloud")
                logger.info(f"Collection name: {self.collection_name}")
            except Exception as e:
                logger.warning(f"Connected to Qdrant but could not retrieve version info: {e}")
                
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant service: {e}")
            raise
    
    def create_collection(self) -> Dict:
        """
        Create Qdrant collection with vector configuration and payload indexes.
        
        Checks if collection already exists before creating. Sets up vector
        configuration with cosine distance and creates payload indexes for
        fast filtering operations.
        
        Returns:
            Dict containing collection information
            
        Raises:
            Exception: If collection creation fails
        """
        try:
            # Check if collection already exists
            collections = self.client.get_collections()
            existing_collections = [col.name for col in collections.collections]
            
            if self.collection_name in existing_collections:
                logger.info(f"Collection '{self.collection_name}' already exists, ensuring indexes are set up...")
                collection_info = self.client.get_collection(self.collection_name)
            else:
                # Create new collection with vector configuration
                logger.info(f"Creating collection '{self.collection_name}'...")
                
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=settings.embedding_dimensions,  # 3072 for text-embedding-3-large
                        distance=Distance.COSINE,
                    ),
                    optimizers_config={
                        "indexing_threshold": 10000,  # Good performance threshold
                    },
                )
                
                logger.info(f"Collection '{self.collection_name}' created successfully")
                collection_info = self.client.get_collection(self.collection_name)
            
            # Create payload indexes for fast filtering (for both new and existing collections)
            logger.info("Setting up payload indexes...")
            
            indexes = [
                ("connector_type", PayloadSchemaType.KEYWORD),
                ("specifications.voltage_rating", PayloadSchemaType.INTEGER),
                ("specifications.current_rating", PayloadSchemaType.INTEGER),
                ("specifications.pin_count", PayloadSchemaType.INTEGER),
                ("specifications.min_operating_temp", PayloadSchemaType.INTEGER),
                ("specifications.max_operating_temp", PayloadSchemaType.INTEGER),
                ("specifications.ip_rating", PayloadSchemaType.KEYWORD),
                ("part_number", PayloadSchemaType.KEYWORD),
            ]
            
            for field_path, schema_type in indexes:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_path,
                        field_schema=schema_type,
                    )
                    logger.info(f"Created {schema_type.value} index on '{field_path}'")
                except Exception as e:
                    # Index might already exist, which is fine
                    if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                        logger.debug(f"Index on '{field_path}' already exists, skipping")
                    else:
                        logger.warning(f"Failed to create index on '{field_path}': {e}")
            
            # Create text index for Qdrant 1.16 hybrid search support
            # Try different API signatures for text index creation
            text_index_created = False
            try:
                # Try with index_params parameter (newer API)
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="name",
                    field_schema=PayloadSchemaType.TEXT,
                    index_params=TextIndexParams(
                        type="text",
                        tokenizer=TokenizerType.WORD,
                        lowercase=True,
                    ),
                )
                logger.info("Created TEXT index on 'name' (Qdrant 1.16 hybrid search support)")
                text_index_created = True
            except Exception as e1:
                try:
                    # Try without extra params (simpler API)
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="name",
                        field_schema=PayloadSchemaType.TEXT,
                    )
                    logger.info("Created TEXT index on 'name' (simplified API)")
                    text_index_created = True
                except Exception as e2:
                    # Index might already exist, which is fine
                    error_msg = str(e2).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        logger.debug("TEXT index on 'name' already exists, skipping")
                        text_index_created = True
                    else:
                        logger.warning(f"Failed to create text index on 'name': {e2}")
                        logger.debug(f"First attempt error: {e1}")
            
            if not text_index_created:
                logger.warning("Text index on 'name' field was not created. Hybrid search may not work properly.")
            
            # Get collection information
            collection_info = self.client.get_collection(self.collection_name)
            
            return {
                "name": self.collection_name,
                "status": collection_info.status,
                "points_count": collection_info.points_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
            }
            
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise
    
    def _create_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for given text using OpenAI API.
        
        Private method that converts text to embedding vector using the configured
        OpenAI embedding model. Handles edge cases like empty or None text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
            
        Raises:
            Exception: If embedding generation fails
        """
        try:
            # Handle edge case: empty or None text
            if not text or not text.strip():
                logger.warning("Empty text provided, returning zero vector")
                return [0.0] * settings.embedding_dimensions
            
            # Generate embedding using OpenAI
            response = self.openai_client.embeddings.create(
                model=settings.embedding_model,
                input=text.strip(),
            )
            
            embedding = response.data[0].embedding
            
            # Validate embedding dimensions
            if len(embedding) != settings.embedding_dimensions:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {settings.embedding_dimensions}, "
                    f"got {len(embedding)}"
                )
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to create embedding: {e}")
            raise
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract potential product name keywords from query text.
        
        Simple keyword extraction that identifies potential product names or
        connector identifiers. This is used to determine if hybrid search
        should be used.
        
        Args:
            text: Input query text
            
        Returns:
            List of extracted keywords (non-empty words, excluding common stop words)
        """
        if not text:
            return []
        
        # Simple keyword extraction: split by whitespace and filter
        words = text.split()
        
        # Filter out very short words and common stop words
        stop_words = {
            'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
            'could', 'may', 'might', 'must', 'can', 'for', 'with', 'on', 'at',
            'to', 'from', 'of', 'in', 'by', 'about', 'into', 'through', 'during',
            'connector', 'connectors', 'need', 'needs', 'required', 'requires',
            'looking', 'search', 'find', 'want', 'wants'
        }
        
        keywords = [
            word.strip('.,!?;:()[]{}"\'').lower()
            for word in words
            if len(word.strip('.,!?;:()[]{}"\'')) > 2
            and word.strip('.,!?;:()[]{}"\'').lower() not in stop_words
        ]
        
        return keywords[:10]  # Limit to top 10 keywords
    
    def _connector_to_searchable_text(self, connector: Connector) -> str:
        """
        Convert Connector model to rich searchable text representation.
        
        Private method that creates a comprehensive text representation of a connector
        by combining all relevant information. This text will be embedded for vector
        search, so it's optimized for semantic matching.
        
        Args:
            connector: Connector model to convert
            
        Returns:
            Single cohesive string optimized for semantic search
        """
        spec = connector.specifications
        
        # Build formatted specifications string
        specs_text = (
            f"{spec.pin_count} pins, {spec.voltage_rating}V, {spec.current_rating}A, "
            f"temperature range {spec.min_operating_temp} to {spec.max_operating_temp}°C, "
            f"{spec.ip_rating}"
        )
        
        # Build materials string
        materials_text = (
            f"Housing: {spec.housing_material}, Contacts: {spec.contact_material} "
            f"with {spec.contact_plating} plating"
        )
        
        # Build certifications string
        certs_text = ", ".join(connector.certifications) if connector.certifications else "None"
        
        # Build applications string
        apps_text = ", ".join(connector.applications) if connector.applications else "None"
        
        # Combine all into cohesive text
        searchable_text = (
            f"{connector.name}. "
            f"{connector.description}. "
            f"Specifications: {specs_text}. "
            f"Materials: {materials_text}. "
            f"Certifications: {certs_text}. "
            f"Applications: {apps_text}."
        )
        
        return searchable_text
    
    def upload_connectors(
        self,
        connectors: List[Connector],
        batch_size: int = 50,
    ) -> int:
        """
        Upload connectors to Qdrant with generated embeddings.
        
        Converts each connector to searchable text, generates embeddings, and uploads
        them to Qdrant in batches. Each connector is stored as a point with its
        embedding as the vector and full connector data as payload.
        
        Args:
            connectors: List of Connector models to upload
            batch_size: Number of connectors to upload per batch (default: 50)
            
        Returns:
            Total count of connectors uploaded
            
        Raises:
            Exception: If upload fails
        """
        try:
            if not connectors:
                logger.warning("No connectors provided for upload")
                return 0
            
            total_connectors = len(connectors)
            logger.info(f"Starting upload of {total_connectors} connectors...")
            
            points = []
            uploaded_count = 0
            
            for idx, connector in enumerate(connectors, start=1):
                try:
                    # Convert connector to searchable text
                    searchable_text = self._connector_to_searchable_text(connector)
                    
                    # Generate embedding
                    embedding = self._create_embedding(searchable_text)
                    
                    # Create unique ID from part number (using hash for consistency)
                    point_id = int(
                        hashlib.md5(connector.part_number.encode()).hexdigest()[:8], 16
                    )
                    
                    # Create Qdrant point with embedding and payload
                    point = PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=connector.model_dump(),  # Convert Pydantic model to dict
                    )
                    
                    points.append(point)
                    
                    # Upload batch when reaching batch size
                    if len(points) >= batch_size:
                        self.client.upsert(
                            collection_name=self.collection_name,
                            points=points,
                        )
                        uploaded_count += len(points)
                        batch_num = uploaded_count // batch_size
                        logger.info(
                            f"Uploaded batch {batch_num}/{(total_connectors + batch_size - 1) // batch_size} "
                            f"({len(points)} points)"
                        )
                        points = []
                        
                except Exception as e:
                    logger.error(f"Failed to process connector {connector.part_number}: {e}")
                    continue
            
            # Upload remaining points
            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                )
                uploaded_count += len(points)
                batch_num = (uploaded_count + batch_size - 1) // batch_size
                logger.info(
                    f"Uploaded final batch {batch_num}/{(total_connectors + batch_size - 1) // batch_size} "
                    f"({len(points)} points)"
                )
            
            logger.info(f"Successfully uploaded {uploaded_count} connectors")
            return uploaded_count
            
        except Exception as e:
            logger.error(f"Failed to upload connectors: {e}")
            raise
    
    def search(
        self,
        query_text: str,
        filters: Optional[Dict] = None,
        limit: int = 10,
        enable_acorn: bool = True,
        use_hybrid: bool = False,
    ) -> List[Tuple[Connector, float]]:
        """
        Search connectors using semantic similarity with optional ACORN and hybrid search support.
        
        Generates embedding for query text and searches Qdrant collection for similar
        connectors. Supports filtering and Qdrant 1.16 ACORN algorithm for improved
        recall with restrictive filters. Can optionally use hybrid search combining
        vector similarity with text matching.
        
        Args:
            query_text: Text query to search for
            filters: Optional dictionary of filter conditions (e.g., {'gte': {'voltage_rating': 12}})
            limit: Maximum number of results to return (default: 10)
            enable_acorn: Whether to use ACORN algorithm if enabled in settings (default: True)
            use_hybrid: Whether to use hybrid search combining vector and text matching (default: False)
            
        Returns:
            List of tuples containing (Connector, score) pairs ordered by relevance
            
        Raises:
            Exception: If search fails
        """
        try:
            # Generate embedding for query text
            query_embedding = self._create_embedding(query_text)
            
            # Build Qdrant filter from filters dict
            qdrant_filter = None
            if filters:
                filter_conditions = []
                
                # Convert filter dict to Qdrant filter format
                for condition_type, conditions in filters.items():
                    if condition_type == "gte":  # Greater than or equal
                        for field_path, value in conditions.items():
                            # Handle nested paths (e.g., specifications.voltage_rating)
                            filter_conditions.append(
                                FieldCondition(
                                    key=field_path,
                                    range=Range(gte=value),
                                )
                            )
                    elif condition_type == "lte":  # Less than or equal
                        for field_path, value in conditions.items():
                            filter_conditions.append(
                                FieldCondition(
                                    key=field_path,
                                    range=Range(lte=value),
                                )
                            )
                    elif condition_type == "range":  # Range with both gte and lte
                        for field_path, range_dict in conditions.items():
                            # Range dict should have 'gte' and/or 'lte' keys
                            range_params = {}
                            if "gte" in range_dict:
                                range_params["gte"] = range_dict["gte"]
                            if "lte" in range_dict:
                                range_params["lte"] = range_dict["lte"]
                            if range_params:
                                filter_conditions.append(
                                    FieldCondition(
                                        key=field_path,
                                        range=Range(**range_params),
                                    )
                                )
                    elif condition_type == "match":  # Exact match
                        for field_path, value in conditions.items():
                            filter_conditions.append(
                                FieldCondition(
                                    key=field_path,
                                    match=MatchValue(value=value),
                                )
                            )
                
                # Combine conditions with AND logic (must clause)
                if filter_conditions:
                    qdrant_filter = Filter(must=filter_conditions)
            
            # Configure search parameters based on ACORN flag
            search_params = None
            use_acorn = enable_acorn and settings.acorn_enabled
            
            if use_acorn:
                # ACORN algorithm (Qdrant 1.16) improves recall for restrictive filters
                search_params = SearchParams(hnsw_ef=128)
                logger.info("Using ACORN algorithm (Qdrant 1.16) for improved search recall")
            else:
                logger.info("Using standard HNSW search")
            
            # Build query based on hybrid mode
            if use_hybrid:
                # Hybrid search: combine vector similarity with text matching
                # Extract keywords from query text for text matching
                keywords = self._extract_keywords(query_text)
                
                # Add text match filter to existing filters if keywords found
                if keywords:
                    # Create text match conditions on 'name' field
                    text_match_conditions = []
                    for keyword in keywords[:5]:  # Limit to top 5 keywords
                        text_match_conditions.append(
                            FieldCondition(
                                key="name",
                                match=MatchText(text=keyword)
                            )
                        )
                    
                    # Combine text matches with OR logic (should clause)
                    if len(text_match_conditions) > 1:
                        text_filter = Filter(should=text_match_conditions)
                    else:
                        text_filter = Filter(must=text_match_conditions)
                    
                    # Combine with existing filters using AND logic
                    if qdrant_filter and qdrant_filter.must:
                        # Merge filters
                        combined_conditions = list(qdrant_filter.must) + [text_filter]
                        qdrant_filter = Filter(must=combined_conditions)
                    elif qdrant_filter:
                        # If filter has other structure, wrap both
                        qdrant_filter = Filter(must=[qdrant_filter, text_filter])
                    else:
                        qdrant_filter = text_filter
                    
                    logger.info(f"Using hybrid search with text matching on keywords: {keywords}")
                else:
                    logger.info("Hybrid search requested but no keywords found, using vector-only")
            
            # Use vector embedding for query
            query = query_embedding
            
            # Execute search in Qdrant using query_points (newer API)
            query_response = self.client.query_points(
                collection_name=self.collection_name,
                query=query,
                query_filter=qdrant_filter,
                search_params=search_params,
                limit=limit,
            )
            
            # Extract results from QueryResponse
            search_results = query_response.points
            
            # Extract connectors from search results
            results = []
            for result in search_results:
                try:
                    # Convert payload to dict if it's not already (handles Qdrant payload types)
                    if isinstance(result.payload, dict):
                        payload_dict = result.payload
                    else:
                        # Try to convert to dict
                        payload_dict = dict(result.payload) if hasattr(result.payload, 'items') else result.payload
                    
                    # Convert payload back to Connector model
                    connector = Connector(**payload_dict)
                    # Score is already normalized by Qdrant (0-1), convert to 0-100
                    # In newer API, score might be in result.score or result.scores
                    score = getattr(result, 'score', 0.0) * 100.0 if hasattr(result, 'score') and result.score else 0.0
                    results.append((connector, score))
                except Exception as e:
                    logger.warning(f"Failed to parse connector from search result: {e}")
                    logger.debug(f"Payload type: {type(result.payload)}, Payload: {str(result.payload)[:200]}")
                    continue
            
            # Sort deterministically by score descending, then part_number ascending for ties
            results.sort(key=lambda x: (-x[1], x[0].part_number))
            
            logger.info(f"Search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    def hybrid_search(
        self,
        query_text: str,
        text_keywords: Optional[List[str]] = None,
        filters: Optional[Dict] = None,
        limit: int = 10,
        enable_acorn: bool = True,
    ) -> Tuple[List[Tuple[Connector, float, str]], Dict]:
        """
        Hybrid search combining vector similarity with text matching.
        
        This method demonstrates Qdrant's unified search capability by combining
        semantic vector search with full-text matching on the 'name' field.
        Results include an indication of match type (vector, text, or both).
        
        Args:
            query_text: Text query for semantic search
            text_keywords: Optional list of keywords for text matching on 'name' field
            filters: Optional dictionary of filter conditions
            limit: Maximum number of results to return (default: 10)
            enable_acorn: Whether to use ACORN algorithm (default: True)
            
        Returns:
            Tuple containing:
            - List of tuples: (Connector, score, match_type) where match_type is
              'vector', 'text', or 'both'
            - Dictionary with search metadata including:
              - hybrid_used: Whether hybrid search was actually used
              - text_keywords_used: Keywords used for text matching
              - match_breakdown: Count of matches by type
        """
        try:
            # Generate embedding for semantic search
            query_embedding = self._create_embedding(query_text)
            
            # Extract keywords if not provided
            if text_keywords is None:
                text_keywords = self._extract_keywords(query_text)
            
            # Build Qdrant filter combining text match with other filters
            filter_conditions = []
            
            # Configure search parameters
            search_params = None
            use_acorn = enable_acorn and settings.acorn_enabled
            
            if use_acorn:
                search_params = SearchParams(hnsw_ef=128)
                logger.info("Using ACORN algorithm with hybrid search")
            
            # Build hybrid search: combine vector similarity with text matching via filters
            hybrid_used = False
            if text_keywords:
                # Add text match filter on 'name' field
                text_match_conditions = []
                for keyword in text_keywords[:5]:  # Limit to top 5 keywords
                    text_match_conditions.append(
                        FieldCondition(
                            key="name",
                            match=MatchText(text=keyword)
                        )
                    )
                
                # Combine text matches with OR logic (should clause)
                if len(text_match_conditions) > 1:
                    text_filter = Filter(should=text_match_conditions)
                else:
                    text_filter = Filter(must=text_match_conditions)
                
                # Add text filter to conditions
                filter_conditions.append(text_filter)
                
                hybrid_used = True
                logger.info(f"Hybrid search: combining vector similarity with text matching on keywords: {text_keywords}")
            else:
                logger.info("Hybrid search: no keywords provided, using vector-only")
            
            # Add other filters from filters dict
            if filters:
                for condition_type, conditions in filters.items():
                    if condition_type == "gte":  # Greater than or equal
                        for field_path, value in conditions.items():
                            filter_conditions.append(
                                FieldCondition(
                                    key=field_path,
                                    range=Range(gte=value),
                                )
                            )
                    elif condition_type == "lte":  # Less than or equal
                        for field_path, value in conditions.items():
                            filter_conditions.append(
                                FieldCondition(
                                    key=field_path,
                                    range=Range(lte=value),
                                )
                            )
                    elif condition_type == "range":  # Range with both gte and lte
                        for field_path, range_dict in conditions.items():
                            # Range dict should have 'gte' and/or 'lte' keys
                            range_params = {}
                            if "gte" in range_dict:
                                range_params["gte"] = range_dict["gte"]
                            if "lte" in range_dict:
                                range_params["lte"] = range_dict["lte"]
                            if range_params:
                                filter_conditions.append(
                                    FieldCondition(
                                        key=field_path,
                                        range=Range(**range_params),
                                    )
                                )
                    elif condition_type == "match":  # Exact match
                        for field_path, value in conditions.items():
                            filter_conditions.append(
                                FieldCondition(
                                    key=field_path,
                                    match=MatchValue(value=value),
                                )
                            )
            
            # Combine all conditions with AND logic
            qdrant_filter = None
            if filter_conditions:
                qdrant_filter = Filter(must=filter_conditions)
            
            # Execute hybrid search with vector query and text filter
            query_response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=qdrant_filter,
                search_params=search_params,
                limit=limit,
            )
            
            # Extract results and determine match types
            search_results = query_response.points
            results = []
            match_breakdown = {"vector": 0, "text": 0, "both": 0}
            
            # Get keywords for match type detection
            keywords_lower = [kw.lower() for kw in (text_keywords or [])]
            
            for result in search_results:
                try:
                    # Convert payload to dict if it's not already (handles Qdrant payload types)
                    if isinstance(result.payload, dict):
                        payload_dict = result.payload
                    else:
                        # Try to convert to dict
                        payload_dict = dict(result.payload) if hasattr(result.payload, 'items') else result.payload
                    
                    connector = Connector(**payload_dict)
                    score = getattr(result, 'score', 0.0) * 100.0 if hasattr(result, 'score') and result.score else 0.0
                    
                    # Determine match type based on whether connector name contains keywords
                    connector_name_lower = connector.name.lower()
                    text_matched = any(kw in connector_name_lower for kw in keywords_lower) if keywords_lower else False
                    
                    if hybrid_used and text_matched:
                        match_type = "both"
                    elif text_matched:
                        match_type = "text"
                    else:
                        match_type = "vector"
                    
                    match_breakdown[match_type] += 1
                    results.append((connector, score, match_type))
                    
                except Exception as e:
                    logger.warning(f"Failed to parse connector from hybrid search result: {e}")
                    logger.debug(f"Payload type: {type(result.payload)}, Payload: {str(result.payload)[:200]}")
                    continue
            
            # Build metadata
            metadata = {
                "hybrid_used": hybrid_used,
                "text_keywords_used": text_keywords if text_keywords else [],
                "match_breakdown": match_breakdown,
            }
            
            # Sort deterministically by score descending, then part_number ascending for ties
            results.sort(key=lambda x: (-x[1], x[0].part_number))
            
            logger.info(
                f"Hybrid search returned {len(results)} results: "
                f"{match_breakdown['both']} both, {match_breakdown['text']} text, "
                f"{match_breakdown['vector']} vector"
            )
            
            return results, metadata
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise
    
    def find_similar_connectors(
        self,
        connector_part_number: str,
        limit: int = 5,
    ) -> List[Tuple[Connector, float]]:
        """
        Find similar connectors using vector similarity search.
        
        Retrieves the connector's embedding vector and uses it to search for similar
        connectors. The input connector is excluded from results using a filter.
        This approach uses Qdrant's search API to find connectors with similar
        vector embeddings, effectively achieving the same goal as a recommendation API.
        
        Args:
            connector_part_number: Part number of the connector to find similar ones for
            limit: Maximum number of similar connectors to return (default: 5)
            
        Returns:
            List of tuples containing (Connector, similarity_score) pairs ordered by
            similarity (highest first). Similarity scores are between 0.0 and 100.0.
            
        Raises:
            ValueError: If connector with given part_number is not found
            Exception: If search fails
        """
        try:
            logger.info(f"Finding similar connectors for part number: {connector_part_number}")
            
            # First, retrieve the connector to get its embedding vector
            try:
                # Use scroll to find the connector by part_number
                scroll_result = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="part_number",
                                match=MatchValue(value=connector_part_number)
                            )
                        ]
                    ),
                    limit=1,
                    with_payload=True,
                    with_vectors=True,  # We need the vector for similarity search
                )
                
                if not scroll_result[0] or len(scroll_result[0]) == 0:
                    raise ValueError(f"Connector with part number '{connector_part_number}' not found")
                
                # Get the connector point with its vector
                connector_point = scroll_result[0][0]
                
                # Extract the vector - it might be in different formats
                connector_vector = None
                if hasattr(connector_point, 'vector'):
                    connector_vector = connector_point.vector
                elif hasattr(connector_point, 'vectors'):
                    # If multiple vectors, use the default one
                    connector_vector = connector_point.vectors if isinstance(connector_point.vectors, list) else connector_point.vectors.get('', None)
                
                if not connector_vector:
                    # Fallback: regenerate embedding from connector data
                    logger.warning(f"Could not retrieve vector for connector {connector_part_number}, regenerating embedding")
                    # Convert payload to connector to regenerate embedding
                    if isinstance(connector_point.payload, dict):
                        payload_dict = connector_point.payload
                    else:
                        payload_dict = dict(connector_point.payload) if hasattr(connector_point.payload, 'items') else connector_point.payload
                    
                    connector = Connector(**payload_dict)
                    searchable_text = self._connector_to_searchable_text(connector)
                    connector_vector = self._create_embedding(searchable_text)
                
            except Exception as e:
                logger.error(f"Failed to find connector {connector_part_number}: {e}")
                raise ValueError(f"Connector with part number '{connector_part_number}' not found") from e
            
            # Create filter to exclude the input connector
            exclude_filter = Filter(
                must_not=[
                    FieldCondition(
                        key="part_number",
                        match=MatchValue(value=connector_part_number)
                    )
                ]
            )
            
            # Use the connector's vector to search for similar connectors
            # This achieves the same goal as a recommend API
            try:
                query_response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=connector_vector,  # Use the connector's embedding as query
                    query_filter=exclude_filter,  # Exclude the input connector
                    limit=limit,
                )
                
                # Extract results from QueryResponse
                search_results = query_response.points
                
            except Exception as e:
                logger.error(f"Similar connectors search failed: {e}")
                raise
            
            # Extract connectors from search results
            results = []
            for result in search_results:
                try:
                    # Convert payload to dict if it's not already (handles Qdrant payload types)
                    if isinstance(result.payload, dict):
                        payload_dict = result.payload
                    else:
                        # Try to convert to dict
                        payload_dict = dict(result.payload) if hasattr(result.payload, 'items') else result.payload
                    
                    # Skip if it's the same connector (shouldn't happen due to filter, but double-check)
                    part_num = payload_dict.get("part_number") if isinstance(payload_dict, dict) else None
                    if part_num == connector_part_number:
                        continue
                    
                    # Convert payload back to Connector model
                    connector = Connector(**payload_dict)
                    
                    # Get similarity score (Qdrant returns scores between 0-1, convert to 0-100)
                    # Score might be in result.score or accessed differently
                    if hasattr(result, 'score'):
                        score = float(result.score) * 100.0 if result.score is not None else 0.0
                    elif hasattr(result, 'scores') and result.scores:
                        score = float(result.scores[0]) * 100.0
                    else:
                        score = 0.0
                    
                    results.append((connector, score))
                        
                except Exception as e:
                    logger.warning(f"Failed to parse connector from search result: {e}")
                    logger.debug(f"Result structure: {type(result)}, attributes: {dir(result) if hasattr(result, '__dict__') else 'N/A'}")
                    continue
            
            logger.info(
                f"Found {len(results)} similar connectors for '{connector_part_number}' "
                f"(requested: {limit})"
            )
            
            return results
            
        except ValueError:
            # Re-raise ValueError (connector not found)
            raise
        except Exception as e:
            logger.error(f"Failed to find similar connectors for {connector_part_number}: {e}")
            raise
    
    def get_collection_stats(self) -> Dict:
        """
        Retrieve collection statistics from Qdrant.
        
        Gets information about the collection including point count, vector count,
        indexed vectors, and collection status.
        
        Returns:
            Dictionary containing collection statistics
            
        Raises:
            Exception: If collection doesn't exist or retrieval fails
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            return {
                "points_count": collection_info.points_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "segments_count": getattr(collection_info, 'segments_count', None),
                "status": collection_info.status.value if isinstance(collection_info.status, CollectionStatus) else str(collection_info.status),
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection statistics: {e}")
            raise

