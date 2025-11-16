"""
Pydantic models for request/response schemas.
"""

from typing import Optional
from pydantic import BaseModel


class TranscriptRequest(BaseModel):
    """Request model for transcript analysis."""
    userid: str
    transcript: str
    location: Optional[str] = None  # Optional, useful for local outbreak search/filters


class PDFUploadResponse(BaseModel):
    """Response model for PDF upload endpoint."""
    success: bool
    message: str
    document_id: Optional[str] = None
    chunks_added: Optional[int] = None

