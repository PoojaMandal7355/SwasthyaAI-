"""Voice agent routes for Pipecat/Exotel integration."""

import os
import uuid
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

import aiohttp
import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.frames.frames import LLMRunFrame, StartInterruptionFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.serializers.exotel import ExotelFrameSerializer
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from pipecat.transcriptions.language import Language

# from pipecat.processors.observers.user_bot_latency import UserBotLatencyLogObserver
from pipecat.observers.loggers.user_bot_latency_log_observer import UserBotLatencyLogObserver

LATENCY_OBSERVER_AVAILABLE = True

from config import settings

# Try to import RAG components (optional, for endpoints only)


load_dotenv(override=True)

# Initialize router
voice_router = APIRouter(prefix="/voice", tags=["voice"])

# In-memory store for calls (demo only - consider using Redis in production)
CALLS: Dict[str, Dict[str, Any]] = {}

# Global aiohttp session with connection pooling for better performance
# This reduces connection overhead and improves latency
_global_session: Optional[aiohttp.ClientSession] = None


async def get_global_session() -> aiohttp.ClientSession:
    """Get or create global aiohttp session with optimized connection pooling."""
    global _global_session
    if _global_session is None or _global_session.closed:
        # Configure connector with connection pooling limits
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=30,  # Max connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            force_close=False,  # Reuse connections
            enable_cleanup_closed=True,  # Clean up closed connections
        )
        timeout = aiohttp.ClientTimeout(
            total=30,  # Total timeout
            connect=10,  # Connection timeout
            sock_read=10,  # Socket read timeout
        )
        _global_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": "SwasthyaAI-VoiceAgent/1.0"},
        )
        logger.info("Created global aiohttp session with connection pooling")
    return _global_session


async def close_global_session():
    """Close global aiohttp session (called on app shutdown)."""
    global _global_session
    if _global_session and not _global_session.closed:
        await _global_session.close()
        logger.info("Closed global aiohttp session")


def load_prompt_from_file(filepath: str) -> str:
    """Load prompt content from a markdown file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning(f"Prompt file {filepath} not found, using default prompt")
        return "You are a helpful voice assistant responding via phone call. Speak concisely."
    except Exception as e:
        logger.error(f"Error loading prompt from {filepath}: {e}")
        return "You are a helpful voice assistant responding via phone call. Speak concisely."


def make_ws_url(stream_id: str, call_id: Optional[str] = None) -> str:
    """Construct the WebSocket URL that Exotel (or dev) should connect to."""
    query = f"?call_id={call_id}" if call_id else ""
    return f"wss://{settings.HOST}/ws/exotel/{stream_id}{query}"


async def send_call_webhook(
    stream_id: str,
    call_id: str,
    context: Optional[OpenAILLMContext] = None,
    task: Optional[PipelineTask] = None,
    call_info: Optional[Dict[str, Any]] = None,
    latency_observer: Optional[UserBotLatencyLogObserver] = None
):
    """Send call transcript, metrics, and related information to webhook."""
    if not settings.WEBHOOK_URL:
        logger.debug("Webhook URL not configured, skipping webhook call")
        return
    
    try:
        # Collect transcript from context
        transcript_messages = []
        full_transcript = ""
        if context and hasattr(context, 'messages'):
            transcript_messages = context.messages
            # Format transcript as readable text
            transcript_parts = []
            for msg in transcript_messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role == "user":
                    transcript_parts.append(f"User: {content}")
                elif role == "assistant":
                    transcript_parts.append(f"Assistant: {content}")
                elif role == "system":
                    # Skip system messages in transcript
                    continue
            full_transcript = "\n".join(transcript_parts)
        
        # Collect metrics from task
        metrics = {}
        usage_metrics = {}
        if task:
            # Try to get metrics from task
            if hasattr(task, 'metrics'):
                metrics = task.metrics or {}
            if hasattr(task, 'usage_metrics'):
                usage_metrics = task.usage_metrics or {}
            # Also check if metrics are stored elsewhere
            if hasattr(task, '_metrics'):
                metrics = task._metrics or {}
            # Try to get metrics from runner if available
            if hasattr(task, 'runner') and task.runner:
                if hasattr(task.runner, 'metrics'):
                    metrics = {**metrics, **(task.runner.metrics or {})}
        
        # Collect latency metrics from observer if available
        latency_metrics = {}
        if latency_observer:
            try:
                # Try to get latency data from observer
                if hasattr(latency_observer, 'latencies'):
                    latency_metrics = {"latencies": latency_observer.latencies}
                if hasattr(latency_observer, 'get_metrics'):
                    latency_metrics = {**latency_metrics, **latency_observer.get_metrics()}
            except Exception as e:
                logger.debug(f"Could not extract latency metrics: {e}")
        
        # Get call information
        call_data = call_info or {}
        
        # Prepare webhook payload
        payload = {
            "stream_id": stream_id,
            "call_id": call_id,
            "call_info": {
                "from": call_data.get("from", "unknown"),
                "to": call_data.get("to", "unknown"),
                "direction": call_data.get("direction", "unknown"),
                "status": call_data.get("status", "ended"),
                "websocket_url": call_data.get("websocket_url"),
            },
            "transcript": {
                "full_text": full_transcript,
                "message_count": len(transcript_messages),
                "messages": transcript_messages,
            },
            "metrics": metrics,
            "usage_metrics": usage_metrics,
            "latency_metrics": latency_metrics,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        
        # Send to webhook
        session = await get_global_session()
        async with session.post(
            settings.WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as response:
            if response.status >= 200 and response.status < 300:
                logger.info(f"Successfully sent webhook for call {call_id}")
            else:
                error_text = await response.text()
                logger.warning(
                    f"Webhook returned status {response.status} for call {call_id}: {error_text}"
                )
    except Exception as e:
        # Don't fail the call cleanup if webhook fails
        logger.exception(f"Error sending webhook for call {call_id}: {e}")


async def run_inbound_pipeline(websocket: WebSocket, stream_id: str, call_id: str):
    """Run the Pipecat pipeline for inbound calls with optimized real-time performance."""
    logger.info(f"Starting INBOUND pipeline for stream_id={stream_id}, call_id={call_id}")
    
    # Use global session for connection pooling
    session = await get_global_session()

    # Load inbound prompt
    inbound_prompt = load_prompt_from_file("inbound_prompt.md")

    # Initialize services
    llm_service = OpenAILLMService(api_key=settings.OPENAI_API_KEY)
    stt_service = SarvamSTTService(
        api_key=settings.SARVAM_API_KEY,
        model="saarika:v2.5",
        # params=SarvamSTTService.InputParams(language=Language.HI)

    )
    tts_service = SarvamTTSService(
        api_key=settings.SARVAM_API_KEY,
        voice_id=settings.SARVAM_VOICE_ID,
        model="bulbul:v2",
        aiohttp_session=session,
        sample_rate=8000,
        params=SarvamTTSService.InputParams(language=Language.HI,output_audio_codec="linear16",enable_preprocessing=True)
    )

    # Set up context with inbound prompt
    initial_system_message = {
        "role": "system",
        "content": inbound_prompt
    }
    context = OpenAILLMContext(messages=[initial_system_message])
    context_aggregator = llm_service.create_context_aggregator(context)

    # Serializer for Exotel
    serializer = ExotelFrameSerializer(stream_sid=stream_id, call_sid=call_id)

    # Transport layer with optimized VAD and Smart Turn Detection
    # VAD Parameters:
    # - start_secs=0.1: Lower threshold for faster detection of short utterances (e.g., "OK", "Yes")
    # - stop_secs=0.2: Optimized for Smart Turn Detection (recommended 0.2s when using Smart Turn)
    vad_params = VADParams(
        start_secs=0.1,  # Lower for better short utterance detection
        stop_secs=0.2,   # Optimized for Smart Turn Detection
    )
    vad_analyzer = SileroVADAnalyzer(params=vad_params)
    
    # Smart Turn Detection: Uses ML model to detect when user finishes speaking
    # Better than basic VAD as it recognizes conversational cues (intonation, linguistic signals)
    # LocalSmartTurnAnalyzerV3 runs on-device, supports 23 languages, efficient on CPU
    turn_analyzer = LocalSmartTurnAnalyzerV3()
    
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=vad_analyzer,
            turn_analyzer=turn_analyzer,  # Smart Turn Detection for better turn-taking
            serializer=serializer,
        ),
    )

    # Initialize processors
    processors = [
        transport.input(),
        stt_service,
    ]
    
    processors.extend([
        context_aggregator.user(),
        llm_service,
        tts_service,
        transport.output(),
        context_aggregator.assistant(),
    ])
    
    # Build pipeline
    pipeline = Pipeline(processors)

    # Create observers for monitoring and optimization
    observers = []
    latency_observer = None
    if LATENCY_OBSERVER_AVAILABLE:
        latency_observer = UserBotLatencyLogObserver()
        observers.append(latency_observer)
        logger.info(f"Latency monitoring enabled for stream {stream_id}")

    task = PipelineTask(
        pipeline=pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
            enable_usage_metrics=True,
            allow_interruptions=True,
        ),
        observers=observers if observers else None,
    )

    # Event hooks
    @transport.event_handler("on_client_connected")
    async def _on_connect(trans, client):
        logger.info(f"Inbound client connected on stream {stream_id}")
        inbound_welcome = "Swasthya AI में आपका स्वागत है! कॉल करने के लिए धन्यवाद। मैं आज आपकी किस प्रकार सहायता कर सकता/सकती हूँ?"
        await task.queue_frames([TTSSpeakFrame(inbound_welcome)])

    @transport.event_handler("on_client_disconnected")
    async def _on_disconnect(trans, client):
        logger.info(f"Inbound client disconnected stream {stream_id}")
        await task.cancel()

    runner = PipelineRunner()
    try:
        await runner.run(task)
    except asyncio.CancelledError:
        logger.info(f"Inbound pipeline cancelled for stream {stream_id}")
    except Exception as e:
        logger.exception(f"Inbound pipeline error for stream {stream_id}: {e}")
        # Re-raise to ensure proper cleanup
        raise
    finally:
        logger.info(f"Cleaning up inbound pipeline for stream {stream_id}")
        try:
            # Send interruption frame to stop any ongoing TTS
            await task.queue_frames([StartInterruptionFrame()])
        except Exception as e:
            logger.warning(f"Error sending interruption frame: {e}")
        
        # Get call info before removing from CALLS
        call_info = CALLS.get(stream_id, {}).copy()
        CALLS.pop(stream_id, None)
        
        # Send webhook with transcript, metrics, and call info
        try:
            await send_call_webhook(
                stream_id=stream_id,
                call_id=call_id,
                context=context,
                task=task,
                call_info=call_info,
                latency_observer=latency_observer
            )
        except Exception as e:
            logger.warning(f"Error sending webhook (non-fatal): {e}")
        
        # Close websocket gracefully
        try:
            await websocket.close()
        except Exception as e:
            # WebSocket may already be closed, which is fine
            logger.debug(f"Error closing websocket (may already be closed): {e}")
        
        # Note: We don't close the global session here as it's shared
        logger.info(f"Inbound pipeline closed for stream {stream_id}")


async def run_outbound_pipeline(websocket: WebSocket, stream_id: str, call_id: str):
    """Run the Pipecat pipeline for outbound calls with optimized real-time performance."""
    logger.info(f"Starting OUTBOUND pipeline for stream_id={stream_id}, call_id={call_id}")
    
    # Use global session for connection pooling
    session = await get_global_session()

    # Load outbound prompt
    outbound_prompt = load_prompt_from_file("outbound_prompt.md")

    # Initialize services
    llm_service = OpenAILLMService(api_key=settings.OPENAI_API_KEY)
    stt_service = SarvamSTTService(
        api_key=settings.SARVAM_API_KEY,
        model="saarika:v2.5",
        # params=SarvamSTTService.InputParams(language=language.HI)  # Fixed: Use Language.HI consistently
    )
    tts_service = SarvamTTSService(
        api_key=settings.SARVAM_API_KEY,
        voice_id=settings.SARVAM_VOICE_ID,
        model="bulbul:v2",
        aiohttp_session=session,
        sample_rate=8000,
        params=SarvamTTSService.InputParams(language=Language.HI, output_audio_codec="linear16")  # Fixed: Use Language.HI consistently
    )

    # Set up context with outbound prompt
    initial_system_message = {
        "role": "system",
        "content": outbound_prompt
    }
    context = OpenAILLMContext(messages=[initial_system_message])
    context_aggregator = llm_service.create_context_aggregator(context)

    # Serializer for Exotel
    serializer = ExotelFrameSerializer(stream_sid=stream_id, call_sid=call_id)

    # Transport layer with optimized VAD and Smart Turn Detection
    # VAD Parameters:
    # - start_secs=0.1: Lower threshold for faster detection of short utterances (e.g., "OK", "Yes")
    # - stop_secs=0.2: Optimized for Smart Turn Detection (recommended 0.2s when using Smart Turn)
    vad_params = VADParams(
        start_secs=0.1,  # Lower for better short utterance detection
        stop_secs=0.2,   # Optimized for Smart Turn Detection
    )
    vad_analyzer = SileroVADAnalyzer(params=vad_params)
    
    # Smart Turn Detection: Uses ML model to detect when user finishes speaking
    # Better than basic VAD as it recognizes conversational cues (intonation, linguistic signals)
    # LocalSmartTurnAnalyzerV3 runs on-device, supports 23 languages, efficient on CPU
    turn_analyzer = LocalSmartTurnAnalyzerV3()
    
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=vad_analyzer,
            turn_analyzer=turn_analyzer,  # Smart Turn Detection for better turn-taking
            serializer=serializer,
        ),
    )

    # Initialize processors
    processors = [
        transport.input(),
        stt_service,
    ]
    
    processors.extend([
        context_aggregator.user(),
        llm_service,
        tts_service,
        transport.output(),
        context_aggregator.assistant(),
    ])
    
    # Build pipeline
    pipeline = Pipeline(processors)

    # Create observers for monitoring and optimization
    observers = []
    latency_observer = None
    if LATENCY_OBSERVER_AVAILABLE:
        latency_observer = UserBotLatencyLogObserver()
        observers.append(latency_observer)
        logger.info(f"Latency monitoring enabled for stream {stream_id}")

    task = PipelineTask(
        pipeline=pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
            enable_usage_metrics=True,
            allow_interruptions=True,
        ),
        observers=observers if observers else None,
    )

    # Event hooks
    @transport.event_handler("on_client_connected")
    async def _on_connect(trans, client):
        logger.info(f"Outbound client connected on stream {stream_id}")
        outbound_welcome = "Swasthya AI में आपका स्वागत है! कॉल करने के लिए धन्यवाद। मैं आज आपकी किस प्रकार सहायता कर सकता/सकती हूँ?"
        await task.queue_frames([TTSSpeakFrame(outbound_welcome)])

    @transport.event_handler("on_client_disconnected")
    async def _on_disconnect(trans, client):
        logger.info(f"Outbound client disconnected stream {stream_id}")
        await task.cancel()

    runner = PipelineRunner()
    try:
        await runner.run(task)
    except asyncio.CancelledError:
        logger.info(f"Outbound pipeline cancelled for stream {stream_id}")
    except Exception as e:
        logger.exception(f"Outbound pipeline error for stream {stream_id}: {e}")
        # Re-raise to ensure proper cleanup
        raise
    finally:
        logger.info(f"Cleaning up outbound pipeline for stream {stream_id}")
        try:
            # Send interruption frame to stop any ongoing TTS
            await task.queue_frames([StartInterruptionFrame()])
        except Exception as e:
            logger.warning(f"Error sending interruption frame: {e}")
        
        # Get call info before removing from CALLS
        call_info = CALLS.get(stream_id, {}).copy()
        CALLS.pop(stream_id, None)
        
        # Send webhook with transcript, metrics, and call info
        try:
            await send_call_webhook(
                stream_id=stream_id,
                call_id=call_id,
                context=context,
                task=task,
                call_info=call_info,
                latency_observer=latency_observer
            )
        except Exception as e:
            logger.warning(f"Error sending webhook (non-fatal): {e}")
        
        # Close websocket gracefully
        try:
            await websocket.close()
        except Exception as e:
            # WebSocket may already be closed, which is fine
            logger.debug(f"Error closing websocket (may already be closed): {e}")
        
        # Note: We don't close the global session here as it's shared
        logger.info(f"Outbound pipeline closed for stream {stream_id}")


async def ws_exotel_endpoint(stream_id: str, websocket: WebSocket):
    """WebSocket endpoint handler for Exotel/dev testing."""
    await websocket.accept()
    query_params = websocket.query_params
    call_id = query_params.get("call_id", "")
    logger.info(f"WebSocket connection received stream_id={stream_id}, call_id={call_id}")

    # Determine call direction from stored call metadata
    call_info = CALLS.get(stream_id, {})
    direction = call_info.get("direction", "inbound")
    
    # Store call meta
    CALLS[stream_id] = {**call_info, "call_id": call_id, "status": "active"}

    try:
        # Route to appropriate pipeline based on direction
        if direction == "outbound":
            await run_outbound_pipeline(websocket, stream_id=stream_id, call_id=call_id)
        else:
            await run_inbound_pipeline(websocket, stream_id=stream_id, call_id=call_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for stream {stream_id}")
    except Exception as e:
        logger.exception(f"WebSocket handling error for stream {stream_id}: {e}")
    finally:
        CALLS.pop(stream_id, None)


@voice_router.post("/exotel/inbound")
async def exotel_inbound(request: Request):
    """Handle inbound call webhook from Exotel."""
    payload = await request.json()
    logger.info(f"Incoming inbound webhook: {payload}")
    
    from_number = payload.get("From") or payload.get("from") or "unknown"
    to_number = payload.get("To") or payload.get("to") or "unknown"
    call_id = payload.get("CallSid") or payload.get("call_id") or str(uuid.uuid4())

    stream_id = str(uuid.uuid4())
    ws_url = make_ws_url(stream_id, call_id)

    # Store meta
    CALLS[stream_id] = {
        "call_id": call_id,
        "from": from_number,
        "to": to_number,
        "direction": "inbound",
        "websocket_url": ws_url,
        "status": "pending"
    }

    logger.info(f"Inbound call created: stream_id={stream_id}, websocket_url={ws_url}")
    return JSONResponse({
        "stream_id": stream_id,
        "call_id": call_id,
        "websocket_url": ws_url
    })


@voice_router.post("/exotel/outbound")
async def exotel_outbound(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """Handle outbound call request."""
    logger.info(f"Outbound request payload: {payload}")
    if not settings.EXOTEL_ACCOUNT_SID or not settings.EXOTEL_AUTH_TOKEN:
        raise HTTPException(status_code=500, detail="Exotel credentials not configured")

    to_number = payload.get("to")
    from_number = payload.get("from")
    if not to_number or not from_number:
        raise HTTPException(status_code=400, detail="Both `to` and `from` are required")

    call_id = str(uuid.uuid4())
    stream_id = str(uuid.uuid4())
    ws_url = make_ws_url(stream_id, call_id)

    # Exotel REST call payload
    exotel_payload = {
        "From": from_number,
        "To": to_number,
        "StreamSid": stream_id,
        "WebsocketUrl": ws_url,
    }

    auth = (settings.EXOTEL_ACCOUNT_SID, settings.EXOTEL_AUTH_TOKEN)
    exotel_call_url = f"{settings.EXOTEL_API_BASE}/Calls"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(exotel_call_url, data=exotel_payload, auth=auth)
        if resp.status_code >= 400:
            logger.error(f"Exotel outbound call failed: {resp.status_code} {resp.text}")
            raise HTTPException(status_code=502, detail=f"Exotel API error: {resp.text}")

    result = resp.json()
    CALLS[stream_id] = {
        "call_id": call_id,
        "from": from_number,
        "to": to_number,
        "direction": "outbound",
        "websocket_url": ws_url,
        "exotel_response": result,
        "status": "initiated"
    }

    logger.info(f"Outbound call initiated: stream_id={stream_id}, ws_url={ws_url}")
    return JSONResponse({
        "stream_id": stream_id,
        "call_id": call_id,
        "websocket_url": ws_url,
        "exotel_response": result
    })


@voice_router.get("/calls")
async def get_calls():
    """List active/initiated calls for debugging."""
    return CALLS


@voice_router.post("/rag/upload-pdf")
async def upload_pdf_rag(
    file: UploadFile = File(...),
    metadata: Optional[str] = None
):
    """Upload a PDF file to the RAG knowledge base."""
    if not RAG_AVAILABLE:
        raise HTTPException(status_code=503, detail="RAG service not available")
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        pdf_bytes = await file.read()
        
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning(f"Invalid metadata JSON, ignoring: {metadata}")
        
        rag_service = get_rag_service()
        doc_id = rag_service.add_pdf(
            pdf_bytes=pdf_bytes,
            filename=file.filename,
            metadata=metadata_dict
        )
        
        logger.info(f"Successfully uploaded PDF: {file.filename} (doc_id: {doc_id})")
        
        return JSONResponse({
            "status": "success",
            "doc_id": doc_id,
            "filename": file.filename,
            "message": f"PDF '{file.filename}' has been added to the knowledge base"
        })
        
    except Exception as e:
        logger.exception(f"Error uploading PDF {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@voice_router.post("/rag/add-text")
async def add_text_document(
    text: str,
    source: str,
    metadata: Optional[str] = None
):
    """Add a text document to the RAG knowledge base."""
    if not RAG_AVAILABLE:
        raise HTTPException(status_code=503, detail="RAG service not available")
    
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text content cannot be empty")
    
    try:
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning(f"Invalid metadata JSON, ignoring: {metadata}")
        
        rag_service = get_rag_service()
        doc_id = rag_service.add_document(
            text=text,
            source=source,
            metadata=metadata_dict
        )
        
        logger.info(f"Successfully added text document: {source} (doc_id: {doc_id})")
        
        return JSONResponse({
            "status": "success",
            "doc_id": doc_id,
            "source": source,
            "message": f"Document '{source}' has been added to the knowledge base"
        })
        
    except Exception as e:
        logger.exception(f"Error adding text document {source}: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@voice_router.get("/rag/search")
async def search_rag(query: str, top_k: int = 3):
    """Search the RAG knowledge base."""
    if not RAG_AVAILABLE:
        raise HTTPException(status_code=503, detail="RAG service not available")
    
    try:
        rag_service = get_rag_service()
        results = rag_service.search(query, top_k=top_k)
        
        return JSONResponse({
            "query": query,
            "results": results,
            "count": len(results)
        })
        
    except Exception as e:
        logger.exception(f"Error searching RAG: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching: {str(e)}")

