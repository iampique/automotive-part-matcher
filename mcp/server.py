import logging
import os
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import Optional, Dict
import base64
import io

# Load env from mcp/ then backend/ so Qdrant/API keys are available
_here = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(_here)
load_dotenv(os.path.join(_here, ".env"))
load_dotenv(os.path.join(_repo_root, "backend", ".env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

server = FastMCP("automotive-part-matcher")

@server.tool()
async def search_connectors(
    text_input: Optional[str] = None,
    file_content: Optional[str] = None,
    file_name: Optional[str] = None,
    llm_provider: Optional[str] = None,
    top_k: int = 10,
    enable_acorn: bool = True
) -> Dict:
    """
    Search for connectors matching the provided requirements.
    
    Args:
        text_input: Optional text description of requirements
        file_content: Optional base64 encoded file content
        file_name: Optional file name for the uploaded file
        llm_provider: Optional LLM provider override ('claude' or 'openai')
        top_k: Number of top results to return (1-20, default: 10)
        enable_acorn: Whether to use ACORN algorithm (default: True)
        
    Returns:
        Dictionary with matched connectors and metadata
    """
    from backend.app.api import search_connectors as api_search_connectors
    
    # Handle file upload if provided
    file_upload = None
    if file_content and file_name:
        try:
            # Decode base64 content
            file_bytes = base64.b64decode(file_content)
            # Create a proper UploadFile-like object
            from fastapi.datastructures import UploadFile as FastAPIUploadFile
            file_upload = FastAPIUploadFile(
                filename=file_name,
                file=io.BytesIO(file_bytes)
            )
        except Exception as e:
            logger.error(f"Failed to decode file content: {e}")
            return {"error": f"Failed to decode file content: {str(e)}"}
    
    try:
        # Call the original API function
        result = await api_search_connectors(
            text_input=text_input,
            file=file_upload,
            llm_provider=llm_provider,
            top_k=top_k,
            enable_acorn=enable_acorn
        )
        
        # Convert SearchResponse to dict for MCP
        if hasattr(result, 'dict'):
            return result.dict()
        else:
            return result
            
    except Exception as e:
        logger.error(f"Search connectors failed: {e}")
        return {"error": f"Search failed: {str(e)}"}

@server.tool()
async def get_similar_connectors(part_number: str, limit: int = 5) -> Dict:
    """
    Find similar connectors to the specified connector using Qdrant's recommendation API.
    
    Args:
        part_number: Part number of the connector to find similar ones for
        limit: Maximum number of similar connectors to return (default: 5, max: 20)
        
    Returns:
        Dictionary containing similar connectors with similarity scores
    """
    from backend.app.api import get_similar_connectors as api_get_similar_connectors
    
    try:
        # Call the original API function
        result = await api_get_similar_connectors(
            part_number=part_number,
            limit=limit
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Get similar connectors failed: {e}")
        return {"error": f"Get similar connectors failed: {str(e)}"}

@server.tool()
async def get_part_impact(part_number: str) -> Dict:
    """Impact analysis: vehicles and assemblies affected when a part is unavailable."""
    from backend.app.api import get_part_impact as api_get_part_impact
    try:
        result = await api_get_part_impact(part_number=part_number)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except Exception as e:
        logger.error(f"Get part impact failed: {e}")
        return {"error": str(e)}


@server.tool()
async def get_assembly_compliance(assembly_id: str) -> Dict:
    """Compliance inheritance for an assembly hierarchy."""
    from backend.app.api import get_assembly_compliance as api_get_assembly_compliance
    try:
        result = await api_get_assembly_compliance(assembly_id=assembly_id)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except Exception as e:
        logger.error(f"Get assembly compliance failed: {e}")
        return {"error": str(e)}


@server.tool()
async def get_supplier_risk() -> Dict:
    """Supplier concentration risk and sole-source analysis."""
    from backend.app.api import get_supplier_risk as api_get_supplier_risk
    try:
        result = await api_get_supplier_risk()
        return result.model_dump() if hasattr(result, "model_dump") else result
    except Exception as e:
        logger.error(f"Get supplier risk failed: {e}")
        return {"error": str(e)}


@server.tool()
async def get_part_sourcing(part_number: str) -> Dict:
    """Primary supplier and share for a specific connector part."""
    from backend.app.api import get_part_sourcing as api_get_part_sourcing
    try:
        result = await api_get_part_sourcing(part_number=part_number)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except Exception as e:
        logger.error(f"Get part sourcing failed: {e}")
        return {"error": str(e)}


@server.tool()
async def analyze_disruption(
    part_number: str,
    max_alternatives: int = 8,
    min_similarity: float = 55.0,
) -> Dict:
    """Full disruption mitigation workflow: impact, alternatives, compliance, supplier risk."""
    from backend.app.api import analyze_disruption as api_analyze_disruption
    from backend.app.models import DisruptionRequest

    try:
        result = await api_analyze_disruption(
            DisruptionRequest(
                part_number=part_number,
                max_alternatives=max_alternatives,
                min_similarity=min_similarity,
            )
        )
        return result.model_dump() if hasattr(result, "model_dump") else result
    except Exception as e:
        logger.error(f"Analyze disruption failed: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    server.run()
