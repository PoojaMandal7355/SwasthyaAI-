"""
FastAPI application entry point for SwasthyaAI.

This module creates a LangGraph Supervisor orchestrating multiple clinical agents:
- diagnosis_agent
- rag_agent (LanceDB + embeddings)
- google_search_agent (SerpAPI / Google Custom Search)
- eval_agent
- clinical_rules_agent
- risk_scoring_agent
- differential_diagnosis_agent
- triage_decision_agent
- recommendation_agent
- report_formatting_agent

Endpoints:
- POST /analyze_transcript: Analyze patient transcript and generate clinical report
- POST /upload_pdf: Upload PDF documents for RAG knowledge base
- WebSocket /voice/ws/exotel/{stream_id}: Voice agent WebSocket endpoint
- POST /voice/exotel/inbound: Handle inbound call webhook
- POST /voice/exotel/outbound: Initiate outbound call
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket

from config import settings
from api import router
from api.voice_routes import voice_router, ws_exotel_endpoint, close_global_session


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown events."""
    # Startup: Global session will be created on first use
    yield
    # Shutdown: Close global aiohttp session
    await close_global_session()


# Initialize FastAPI app with lifespan management
app = FastAPI(
    title="SwasthyaAI - Supervisor Orchestrator",
    description="Clinical AI system for patient transcript analysis and diagnosis with voice agent capabilities",
    lifespan=lifespan
)

# Include API routes
app.include_router(router)
app.include_router(voice_router)

# WebSocket endpoint at root level (Exotel calls this directly)
@app.websocket("/ws/exotel/{stream_id}")
async def ws_exotel_root(stream_id: str, websocket: WebSocket):
    """WebSocket endpoint for Exotel - root level for external access."""
    await ws_exotel_endpoint(stream_id, websocket)
