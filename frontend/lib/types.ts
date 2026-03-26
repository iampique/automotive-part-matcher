/**
 * TypeScript interfaces matching backend Pydantic models.
 * 
 * These types ensure type-safe data handling throughout the frontend
 * and match the structure returned by the FastAPI backend.
 */

/**
 * Technical specifications for an automotive connector.
 * 
 * Represents electrical, environmental, and material properties
 * required for connector matching.
 */
export interface ConnectorSpecifications {
  /** Number of electrical pins/contacts in the connector */
  pin_count: number;
  
  /** Maximum voltage rating in volts */
  voltage_rating: number;
  
  /** Maximum current rating in amps */
  current_rating: number;
  
  /** Minimum operating temperature in degrees Celsius */
  min_operating_temp: number;
  
  /** Maximum operating temperature in degrees Celsius */
  max_operating_temp: number;
  
  /** IP (Ingress Protection) rating indicating protection level (e.g., IP67, IP68) */
  ip_rating: string;
  
  /** Material used for the connector housing (e.g., 'Nylon', 'Polyamide', 'Metal') */
  housing_material: string;
  
  /** Material used for the electrical contacts (e.g., 'Copper', 'Brass', 'Phosphor Bronze') */
  contact_material: string;
  
  /** Surface plating on contacts for corrosion resistance (e.g., 'Tin', 'Gold', 'Silver') */
  contact_plating: string;
}

/**
 * Pricing and availability information for a connector.
 * 
 * Represents commercial information including unit pricing
 * and lead time for procurement planning.
 */
export interface ConnectorPricing {
  /** Unit price in US dollars */
  unit_price_usd: number;
  
  /** Lead time for delivery in days */
  lead_time_days: number;
}

/**
 * Complete connector data model.
 * 
 * Represents an automotive connector with all its specifications,
 * certifications, applications, and pricing information.
 */
export interface Connector {
  /** Unique part number identifier for the connector */
  part_number: string;
  
  /** Human-readable name of the connector */
  name: string;
  
  /** Detailed description of the connector, its features, and use cases */
  description: string;
  
  /** Type or category of connector (e.g., 'Circular', 'Rectangular', 'Terminal Block') */
  connector_type: string;
  
  /** Complete technical specifications for the connector */
  specifications: ConnectorSpecifications;
  
  /** List of certifications and standards the connector meets (e.g., 'ISO 9001', 'UL', 'CE') */
  certifications: string[];
  
  /** List of automotive applications where this connector is commonly used */
  applications: string[];
  
  /** Pricing and availability information */
  pricing: ConnectorPricing;
}

/**
 * Search result for a matched connector.
 * 
 * Represents a single connector match with its relevance score and explanation.
 * Used in search responses to show why a connector was matched and how well
 * it fits the requirements.
 */
export interface MatchResult {
  /** Part number of the matched connector */
  part_number: string;
  
  /** Name of the matched connector */
  name: string;
  
  /** Relevance match score between 0.0 and 100.0, where higher scores indicate better matches */
  match_score: number;
  
  /** Human-readable explanation of why this connector was matched and how it meets the requirements */
  match_explanation: string;
  
  /** Complete connector object with all specifications and details */
  connector: Connector;
  
  /** Whether this match is a fallback result (did not pass hard requirements but shown due to semantic similarity) */
  is_fallback_match?: boolean;
}

/**
 * Execution step information for workflow visualization.
 * 
 * Tracks individual node execution in the LangGraph workflow,
 * including duration, output, and status for debugging and visualization.
 */
export interface ExecutionStep {
  /** Name of the workflow node (e.g., 'parse', 'search', 'score', 'rank') */
  node: string;
  
  /** Duration of this step in milliseconds */
  duration_ms: number;
  
  /** Output description of what this node produced */
  output: string;
  
  /** Execution status: 'success' or 'error' */
  status: 'success' | 'error';
  
  /** Optional flag indicating if ACORN was used (for search node) */
  acorn_used?: boolean;
}

/**
 * Response model for connector search operations.
 * 
 * Contains the search results along with metadata about the search execution,
 * including processing time, query summary, and execution trace for debugging
 * and workflow visualization.
 */
export interface SearchResponse {
  /** List of matched connectors ordered by relevance score (highest first) */
  matches: MatchResult[];
  
  /** Total processing time for the search operation in milliseconds */
  processing_time_ms: number;
  
  /** Summary of the parsed query and search strategy used */
  query_summary: string;
  
  /** Whether Qdrant 1.16 ACORN feature was used for this search */
  acorn_used: boolean;
  
  /** Optional execution trace for workflow visualization and debugging */
  execution_trace?: ExecutionStep[];
  
  /** Whether fallback matching was used (no connectors passed hard requirements, so semantic matches were returned) */
  fallback_used?: boolean;
  
  /** Number of matches that passed hard requirements (vs fallback matches) */
  matches_passed_hard_requirements?: number;
}

/**
 * Collection statistics from Qdrant.
 * 
 * Contains information about the connector collection including
 * point count, indexed vectors, and collection status.
 */
export interface CollectionStats {
  /** Total number of connectors (points) in the collection */
  points_count: number;
  
  /** Number of indexed vectors */
  indexed_vectors_count: number;
  
  /** Number of segments in the collection (optional) */
  segments_count?: number;
  
  /** Collection status (e.g., 'green', 'yellow', 'red') */
  status: string;
}

/**
 * Workflow diagram response.
 * 
 * Contains Mermaid diagram code and optionally PNG image data
 * for visualizing the LangGraph workflow.
 */
export interface WorkflowDiagram {
  /** Mermaid diagram code as string */
  mermaid_code: string;
  
  /** Optional base64-encoded PNG image of the diagram */
  png_base64?: string;
}

/**
 * Similar connector result with explanation.
 * 
 * Represents a connector similar to a reference connector,
 * including similarity score and explanation of why it's similar.
 */
export interface SimilarConnector {
  /** The similar connector object */
  connector: Connector;
  
  /** Similarity score between 0.0 and 100.0 */
  similarity_score: number;
  
  /** Explanation of why this connector is similar */
  explanation: string;
}

/**
 * Response for similar connectors endpoint.
 * 
 * Contains list of similar connectors, the base connector used
 * as reference, and overall explanation.
 */
export interface SimilarConnectorsResponse {
  /** List of similar connectors with scores and explanations */
  similar_connectors: SimilarConnector[];
  
  /** The connector that was used as the reference */
  base_connector: Connector;
  
  /** Overall explanation of the similarity results */
  explanation: string;
  
  /** Number of similar connectors found */
  count: number;
}
