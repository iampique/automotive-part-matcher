/**
 * API client for making HTTP requests to the backend.
 * 
 * Provides centralized API communication with type safety and comprehensive
 * error handling for network, server, and client errors.
 */

import axios, { AxiosError } from 'axios';
import type {
  Connector,
  CollectionStats,
  SearchResponse,
  WorkflowDiagram,
  SimilarConnectorsResponse,
  HealthResponse,
  ImpactAnalysisResponse,
  ConnectorComplianceResponse,
  SupplierRiskResponse,
  SpofResponse,
  DisruptionRequest,
  DisruptionResponse,
  PartSourcing,
} from './types';

/**
 * Axios instance configured for backend API communication.
 * 
 * Uses NEXT_PUBLIC_API_URL environment variable if set,
 * otherwise defaults to http://localhost:8000 for local development.
 */
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Format error message for UI display.
 * 
 * Extracts meaningful error messages from various error types
 * including network errors, server errors, and client errors.
 */
function formatError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string }>;
    
    // Server error with detail message
    if (axiosError.response?.data?.detail) {
      return axiosError.response.data.detail;
    }
    
    // HTTP status code errors
    if (axiosError.response) {
      const status = axiosError.response.status;
      const statusText = axiosError.response.statusText;
      
      if (status >= 500) {
        return `Server error: ${status} ${statusText}`;
      } else if (status >= 400) {
        return `Client error: ${status} ${statusText}`;
      }
    }
    
    // Network/timeout errors
    if (axiosError.code === 'ECONNABORTED') {
      return 'Request timeout: The server took too long to respond';
    }
    
    if (axiosError.code === 'ERR_NETWORK') {
      return 'Network error: Unable to connect to the server';
    }
    
    // Generic axios error
    return axiosError.message || 'An unexpected error occurred';
  }
  
  // Non-axios errors
  if (error instanceof Error) {
    return error.message;
  }
  
  return 'An unknown error occurred';
}

/**
 * Search for connectors matching the provided requirements.
 * 
 * Accepts either text input or a file (PDF/DOCX) containing requirements.
 * The backend will parse the requirements, search the vector database,
 * score matches, and return ranked results.
 * 
 * @param textInput - Optional free-form text describing connector requirements
 * @param file - Optional PDF or DOCX file with requirements
 * @param llmProvider - Optional LLM provider override ('claude' or 'openai')
 * @param topK - Number of top results to return (default: 10, max: 20)
 * @param enableAcorn - Whether to use ACORN algorithm (default: true)
 * @returns SearchResponse with matched connectors and execution metadata
 * @throws Error with formatted message if request fails
 * 
 * @example
 * ```typescript
 * const results = await searchConnectors({
 *   textInput: "12-pin automotive connector",
 *   topK: 5
 * });
 * ```
 */
export async function searchConnectors({
  textInput,
  file,
  llmProvider,
  topK = 10,
  enableAcorn = true,
}: {
  textInput?: string;
  file?: File;
  llmProvider?: string;
  topK?: number;
  enableAcorn?: boolean;
}): Promise<SearchResponse> {
  try {
    // Create FormData for multipart/form-data request
    const formData = new FormData();
    
    // Append parameters if provided
    if (textInput) {
      formData.append('text_input', textInput);
    }
    
    if (file) {
      formData.append('file', file);
    }
    
    if (llmProvider) {
      formData.append('llm_provider', llmProvider);
    }
    
    // Always append these parameters
    formData.append('top_k', topK.toString());
    formData.append('enable_acorn', enableAcorn.toString());
    
    // Make POST request
    const response = await apiClient.post<SearchResponse>('/api/search', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`Search failed: ${errorMessage}`);
  }
}

/**
 * Get Qdrant collection statistics.
 * 
 * Retrieves information about the connector collection including
 * total points, indexed vectors, and collection status.
 * 
 * @returns CollectionStats with collection information
 * @throws Error with formatted message if request fails
 * 
 * @example
 * ```typescript
 * const stats = await getStats();
 * console.log(`Total connectors: ${stats.points_count}`);
 * ```
 */
export async function getStats(): Promise<CollectionStats> {
  try {
    const response = await apiClient.get<CollectionStats>('/api/stats');
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`Failed to retrieve statistics: ${errorMessage}`);
  }
}

/**
 * Get detailed information for a specific connector by part number.
 * 
 * Searches the collection for a connector with the specified part number
 * and returns its complete information including specifications,
 * certifications, applications, and pricing.
 * 
 * @param partNumber - Part number of the connector to retrieve
 * @returns Connector object with complete information
 * @throws Error with formatted message if connector not found or request fails
 * 
 * @example
 * ```typescript
 * const connector = await getConnector('CONN-001');
 * console.log(connector.name);
 * ```
 */
export async function getConnector(partNumber: string): Promise<Connector> {
  try {
    const response = await apiClient.get<Connector>(`/api/connector/${partNumber}`);
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    
    // Check if it's a 404 (not found)
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      throw new Error(`Connector '${partNumber}' not found`);
    }
    
    throw new Error(`Failed to retrieve connector: ${errorMessage}`);
  }
}

/**
 * Get workflow diagram in Mermaid format for visualization.
 * 
 * Retrieves the LangGraph workflow as Mermaid diagram code that can be
 * rendered in documentation or visualization tools. Optionally includes
 * PNG image data if available.
 * 
 * @returns WorkflowDiagram with Mermaid code and optional PNG
 * @throws Error with formatted message if request fails
 * 
 * @example
 * ```typescript
 * const diagram = await getWorkflowDiagram();
 * // Use diagram.mermaid_code to render workflow visualization
 * ```
 */
export async function getWorkflowDiagram(): Promise<WorkflowDiagram> {
  try {
    const response = await apiClient.get<WorkflowDiagram>('/api/workflow-diagram');
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`Failed to retrieve workflow diagram: ${errorMessage}`);
  }
}

/**
 * Find similar connectors to a specified connector using Qdrant's recommendation API.
 * 
 * Uses Qdrant's recommend method to discover alternative connectors with similar
 * specifications, applications, and characteristics. This helps users discover
 * alternatives when exploring connector options.
 * 
 * @param partNumber - Part number of the connector to find similar ones for
 * @param limit - Maximum number of similar connectors to return (default: 5, max: 20)
 * @returns SimilarConnectorsResponse with similar connectors, base connector, and explanations
 * @throws Error with formatted message if connector not found or request fails
 * 
 * @example
 * ```typescript
 * const similar = await findSimilarConnectors('CONN-001', 5);
 * console.log(`Found ${similar.count} similar connectors`);
 * ```
 */
export async function findSimilarConnectors(
  partNumber: string,
  limit: number = 5,
  validateGraph: boolean = false
): Promise<SimilarConnectorsResponse> {
  try {
    // Validate limit
    if (limit < 1 || limit > 20) {
      throw new Error('Limit must be between 1 and 20');
    }
    
    const response = await apiClient.get<SimilarConnectorsResponse>(
      `/api/connector/${encodeURIComponent(partNumber)}/similar`,
      {
        params: { limit, validate_graph: validateGraph },
      }
    );
    
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    
    // Check if it's a 404 (not found)
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      throw new Error(`Connector '${partNumber}' not found`);
    }
    
    throw new Error(`Failed to find similar connectors: ${errorMessage}`);
  }
}

export async function getHealth(): Promise<HealthResponse> {
  try {
    const response = await apiClient.get<HealthResponse>('/health');
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`Health check failed: ${errorMessage}`);
  }
}

export async function getPartImpact(partNumber: string): Promise<ImpactAnalysisResponse> {
  try {
    const response = await apiClient.get<ImpactAnalysisResponse>(
      `/api/graph/impact/${encodeURIComponent(partNumber)}`
    );
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`Impact analysis failed: ${errorMessage}`);
  }
}

export async function getConnectorCompliance(
  partNumber: string
): Promise<ConnectorComplianceResponse> {
  try {
    const response = await apiClient.get<ConnectorComplianceResponse>(
      `/api/graph/compliance/connector/${encodeURIComponent(partNumber)}`
    );
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`Compliance lookup failed: ${errorMessage}`);
  }
}

export async function getPartSourcing(partNumber: string): Promise<PartSourcing> {
  try {
    const response = await apiClient.get<PartSourcing>(
      `/api/graph/sourcing/${encodeURIComponent(partNumber)}`
    );
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`Part sourcing lookup failed: ${errorMessage}`);
  }
}

export async function getSupplierRisk(): Promise<SupplierRiskResponse> {
  try {
    const response = await apiClient.get<SupplierRiskResponse>('/api/graph/suppliers/risk');
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`Supplier risk query failed: ${errorMessage}`);
  }
}

export async function getSupplierSpof(): Promise<SpofResponse> {
  try {
    const response = await apiClient.get<SpofResponse>('/api/graph/suppliers/spof');
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`SPOF query failed: ${errorMessage}`);
  }
}

export async function analyzeDisruption(
  request: DisruptionRequest
): Promise<DisruptionResponse> {
  try {
    const response = await apiClient.post<DisruptionResponse>(
      '/api/disruption/analyze',
      request
    );
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`Disruption analysis failed: ${errorMessage}`);
  }
}

export async function getDisruptionWorkflowDiagram(): Promise<{ mermaid: string; description: string }> {
  try {
    const response = await apiClient.get<{ mermaid: string; description: string }>(
      '/api/disruption/workflow-diagram'
    );
    return response.data;
  } catch (error) {
    const errorMessage = formatError(error);
    throw new Error(`Failed to load disruption workflow diagram: ${errorMessage}`);
  }
}
