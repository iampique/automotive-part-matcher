import logging
import os
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import Optional, Dict
from fastapi import UploadFile
import base64
import io

# Load .env from project root and backend/ so Qdrant/API keys are available
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, ".env"))
load_dotenv(os.path.join(_here, "backend", ".env"))

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
    from backend.app.models import SearchResponse
    
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

if __name__ == "__main__":
    server.run()
