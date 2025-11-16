"""API route handlers."""

import json
import random
import re
import string
import uuid
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from langchain_core.messages import HumanMessage

from config import settings
from models import TranscriptRequest, PDFUploadResponse
from services.pdf_service import PDFService
from services.lancedb_service import LanceDBService
from agents import create_supervisor_workflow

# Initialize router
router = APIRouter()

# Initialize services
pdf_service = PDFService()
lancedb_service = LanceDBService()

# Initialize supervisor workflow (lazy)
_supervisor_app = None


def get_supervisor_app():
    """Lazy initialization of supervisor workflow."""
    global _supervisor_app
    if _supervisor_app is None:
        _supervisor_app = create_supervisor_workflow()
    return _supervisor_app


@router.post("/analyze_transcript")
async def analyze_transcript(req: TranscriptRequest) -> Dict[str, Any]:
    """
    Analyze a patient transcript using the supervisor workflow.
    
    The supervisor will coordinate all clinical agents to generate a comprehensive report.
    Returns a structured JSON report matching the specified format.
    """
    transcript = req.transcript
    userid = req.userid
    location = req.location or ""

    # Construct the user message for the supervisor
    user_message = f"""
Analyze this patient transcript in Hindi and provide a comprehensive medical report following the exact JSON structure.

Patient Transcript (Hindi):
{transcript}

IMPORTANT: 
- Coordinate all agents to extract detailed information
- Ensure report_formatting_agent receives the original transcript for input_summary
- Generate the final report in the exact JSON structure with all required fields
- Preserve Hindi text in symptoms, triage explanations, differential diagnosis, and patient recommendations
"""
    if location:
        user_message += f"\nPatient Location: {location}"

    try:
        # Invoke the supervisor workflow
        supervisor_app = get_supervisor_app()
        result = supervisor_app.invoke({
            "messages": [HumanMessage(content=user_message)]
        })

        # Extract the final message from the supervisor
        messages = result.get("messages", [])
        final_message = messages[-1] if messages else None
        
        if not final_message:
            raise HTTPException(
                status_code=500,
                detail="No response from supervisor workflow"
            )
        
        # Extract content from the final message
        content = final_message.content if hasattr(final_message, 'content') else str(final_message)
        
        # Try to extract JSON from the response (handle markdown code blocks if present)
        try:
            # Remove markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
            
            parsed_response = json.loads(content)
            
            # Ensure required fields are set
            _enrich_response(parsed_response, userid, transcript)
            
            return parsed_response
            
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse supervisor response as JSON: {str(e)}. Response: {content[:500]}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Supervisor workflow failed: {str(e)}"
        )


def _enrich_response(response: Dict[str, Any], userid: str, transcript: str) -> None:
    """
    Enrich response with required metadata fields.
    
    Args:
        response: Response dictionary to enrich
        userid: User ID
        transcript: Original transcript text
    """
    # Ensure patient_id is set from userid
    if "patient_id" not in response or not response.get("patient_id"):
        response["patient_id"] = userid
    
    # Ensure pseudo_id is generated if not present
    if "pseudo_id" not in response or not response.get("pseudo_id"):
        pseudo_id = "anon_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        response["pseudo_id"] = pseudo_id
    
    # Ensure language is set
    response["language"] = settings.DEFAULT_LANGUAGE
    
    # Ensure consent_status is set
    if "consent_status" not in response:
        response["consent_status"] = settings.DEFAULT_CONSENT_STATUS
    
    # Ensure input_summary has transcript_excerpt
    if "input_summary" not in response:
        response["input_summary"] = {}
    
    if "transcript_excerpt" not in response["input_summary"]:
        # Extract key excerpt (first 200 characters or so)
        excerpt = transcript[:200] + "..." if len(transcript) > 200 else transcript
        response["input_summary"]["transcript_excerpt"] = excerpt
    
    if "call_date" not in response["input_summary"]:
        # Set current timestamp with IST timezone
        response["input_summary"]["call_date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30")
    
    if "transcript_tokens" not in response["input_summary"]:
        # Approximate token count
        response["input_summary"]["transcript_tokens"] = len(transcript) // settings.TOKEN_CHAR_RATIO
    
    # Ensure report_meta is set
    if "report_meta" not in response:
        response["report_meta"] = {}
    
    if "created_at" not in response["report_meta"]:
        response["report_meta"]["created_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30")
    
    if "generated_by" not in response["report_meta"]:
        response["report_meta"]["generated_by"] = "supervisor-agent-v1.2"
    
    if "audit_log_id" not in response["report_meta"]:
        audit_id = "audit_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        response["report_meta"]["audit_log_id"] = audit_id


@router.post("/upload_pdf", response_model=PDFUploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    source: str = Form(default="uploaded_pdf"),
    chunk_size: int = Form(default=None),
    overlap: int = Form(default=None)
) -> PDFUploadResponse:
    """
    Upload a PDF file for RAG (Retrieval Augmented Generation).
    
    The PDF will be processed, chunked, embedded, and stored in LanceDB.
    
    Parameters:
    - file: PDF file to upload
    - source: Source identifier for the document (default: "uploaded_pdf")
    - chunk_size: Number of words per chunk (default: from settings)
    - overlap: Number of overlapping words between chunks (default: from settings)
    
    Returns:
    - success: Whether the upload was successful
    - message: Status message
    - document_id: Unique identifier for the document
    - chunks_added: Number of chunks added to the database
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    try:
        # Read PDF file
        pdf_bytes = await file.read()
        
        # Extract text from PDF
        text = pdf_service.extract_text_from_pdf(pdf_bytes)
        
        if not text or len(text.strip()) < settings.MIN_PDF_TEXT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail="PDF appears to be empty or contains no extractable text"
            )
        
        # Chunk the text
        chunks = pdf_service.chunk_text(
            text, 
            chunk_size=chunk_size or settings.DEFAULT_CHUNK_SIZE,
            overlap=overlap or settings.DEFAULT_CHUNK_OVERLAP
        )
        
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Failed to create text chunks from PDF"
            )
        
        # Create embeddings and prepare data
        data = pdf_service.create_embeddings_for_chunks(chunks, source=source)
        
        # Store in LanceDB
        chunks_added = lancedb_service.store_embeddings(data)
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        return PDFUploadResponse(
            success=True,
            message=f"Successfully processed PDF: {file.filename}. Added {chunks_added} chunks to RAG database.",
            document_id=document_id,
            chunks_added=chunks_added
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {str(e)}"
        )

