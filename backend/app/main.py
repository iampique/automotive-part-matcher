"""
Main application entry point for the automotive part matcher backend.

This module serves as the entry point to start the FastAPI server using uvicorn.
Run this file directly to start the development server.
"""

import uvicorn

from app.api import app

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
