"""
FastAPI webhook receiver for call end events.

This endpoint receives webhook POST requests when calls end, containing:
- Transcript data
- Call metrics
- Usage metrics
- Latency metrics
- Call information
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
import json

# Initialize FastAPI app
app = FastAPI(
    title="Call Webhook Receiver",
    description="Receives webhook POST requests when calls end",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Call Webhook Receiver",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    Receive webhook POST request with call data.
    
    Expected payload structure:
    {
        "stream_id": str,
        "call_id": str,
        "call_info": {
            "from": str,
            "to": str,
            "direction": str,
            "status": str,
            "websocket_url": str
        },
        "transcript": {
            "full_text": str,
            "message_count": int,
            "messages": list
        },
        "metrics": dict,
        "usage_metrics": dict,
        "latency_metrics": dict,
        "timestamp": str
    }
    """
    try:
        # Parse JSON payload
        payload = await request.json()
        
        # Extract key information
        stream_id = payload.get("stream_id", "unknown")
        call_id = payload.get("call_id", "unknown")
        call_info = payload.get("call_info", {})
        transcript = payload.get("transcript", {})
        metrics = payload.get("metrics", {})
        usage_metrics = payload.get("usage_metrics", {})
        latency_metrics = payload.get("latency_metrics", {})
        timestamp = payload.get("timestamp", datetime.utcnow().isoformat() + "Z")
        
        # Log received webhook
        logger.info(f"Received webhook for call_id={call_id}, stream_id={stream_id}")
        logger.info(f"Call direction: {call_info.get('direction', 'unknown')}")
        logger.info(f"From: {call_info.get('from', 'unknown')} To: {call_info.get('to', 'unknown')}")
        logger.info(f"Transcript message count: {transcript.get('message_count', 0)}")
        
        # Log transcript (truncated for readability)
        full_text = transcript.get("full_text", "")
        if full_text:
            transcript_preview = full_text[:200] + "..." if len(full_text) > 200 else full_text
            logger.info(f"Transcript preview: {transcript_preview}")
        
        # Log metrics if available
        if metrics:
            logger.info(f"Metrics: {json.dumps(metrics, indent=2)}")
        if usage_metrics:
            logger.info(f"Usage metrics: {json.dumps(usage_metrics, indent=2)}")
        if latency_metrics:
            logger.info(f"Latency metrics: {json.dumps(latency_metrics, indent=2)}")
        
        # Here you can add your custom processing logic:
        # - Save to database
        # - Send to analytics service
        # - Trigger other workflows
        # - etc.
        
        # Return success response
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Webhook received successfully",
                "call_id": call_id,
                "stream_id": stream_id,
                "received_at": datetime.utcnow().isoformat() + "Z"
            }
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(e)}")
    except Exception as e:
        logger.exception(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/webhook/raw")
async def receive_webhook_raw(request: Request):
    """
    Receive webhook POST request and return raw payload (for debugging).
    """
    try:
        payload = await request.json()
        logger.info(f"Received raw webhook: {json.dumps(payload, indent=2)}")
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "received_payload": payload,
                "received_at": datetime.utcnow().isoformat() + "Z"
            }
        )
    except Exception as e:
        logger.exception(f"Error processing raw webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

