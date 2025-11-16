# SwasthyaAI Code Documentation

## Table of Contents

- [File Structure](#file-structure)
- [Core Modules](#core-modules)
- [API Endpoints](#api-endpoints)
- [Agent System](#agent-system)
- [Tools](#tools)
- [Services](#services)
- [Prompts System](#prompts-system)
- [RAG Implementation](#rag-implementation)
- [Voice Agent](#voice-agent)
- [Data Models](#data-models)

## File Structure

```
core/
├── app.py                          # Main FastAPI application entry point (45 lines)
├── config.py                       # Configuration and settings management
├── models.py                       # Pydantic request/response models
├── tools.py                        # LangChain tools for agents
├── agents.py                       # Agent creation and supervisor workflow
├── pyproject.toml                  # Project dependencies
├── api/                            # API routes directory
│   ├── __init__.py                # Router exports
│   ├── routes.py                  # Supervisor orchestrator endpoints
│   └── voice_routes.py            # Voice agent endpoints (Pipecat/Exotel)
├── services/                       # Business logic services
│   ├── __init__.py                # Service exports
│   ├── pdf_service.py             # PDF processing service
│   ├── lancedb_service.py         # LanceDB vector database service
│   └── search_service.py         # Health news search service
├── prompts/                        # Prompt templates directory
│   ├── __init__.py                # Prompt exports
│   ├── supervisor.py              # Supervisor coordination prompt
│   ├── diagnose_transcript.py     # Diagnosis tool prompt
│   ├── evaluate_patient_report.py # Evaluation tool prompt
│   ├── apply_clinical_rules.py    # Clinical rules tool prompt
│   ├── compute_risk_scores.py     # Risk scoring tool prompt
│   ├── differential_diagnosis.py  # Differential diagnosis tool prompt
│   ├── assign_triage_level.py     # Triage tool prompt
│   ├── generate_recommendations.py # Recommendations tool prompt
│   ├── format_clinical_report.py  # Report formatting tool prompt
│   ├── agent_diagnosis.py         # Diagnosis agent prompt
│   ├── agent_rag.py              # RAG agent prompt
│   ├── agent_search.py           # Search agent prompt
│   ├── agent_eval.py             # Evaluation agent prompt
│   ├── agent_clinical_rules.py    # Clinical rules agent prompt
│   ├── agent_risk_scoring.py     # Risk scoring agent prompt
│   ├── agent_differential_diagnosis.py # Differential diagnosis agent prompt
│   ├── agent_triage_decision.py  # Triage agent prompt
│   ├── agent_recommendation.py   # Recommendation agent prompt
│   └── agent_report_formatting.py # Report formatting agent prompt
├── lancedb_store/                  # LanceDB data directory (created at runtime)
└── README.md                       # Main documentation
```

## Core Modules

### app.py

The main application entry point (45 lines) - clean and focused:

```python
from fastapi import FastAPI
from config import settings
from api import router
from api.voice_routes import voice_router, ws_exotel_endpoint

app = FastAPI(...)
app.include_router(router)  # Supervisor orchestrator routes
app.include_router(voice_router)  # Voice agent routes

# WebSocket at root level for Exotel
@app.websocket("/ws/exotel/{stream_id}")
async def ws_exotel_root(...):
    await ws_exotel_endpoint(...)
```

**Responsibilities:**
- FastAPI app initialization
- Router registration
- WebSocket endpoint registration

### config.py

Centralized configuration management using a `Settings` class:

```python
class Settings:
    # API Keys
    OPENAI_API_KEY: str
    SERPAPI_KEY: Optional[str]
    
    # Model Configuration
    OPENAI_MODEL: str
    EMBEDDING_MODEL_NAME: str
    
    # Service Configuration
    LANCEDB_PATH: str
    DEFAULT_CHUNK_SIZE: int
    DEFAULT_CHUNK_OVERLAP: int
    
    # Voice Agent Configuration
    HOST: str
    PORT: int
    EXOTEL_ACCOUNT_SID: Optional[str]
    SARVAM_API_KEY: Optional[str]
    
    @property
    def embedding_model(self) -> SentenceTransformer:
        # Lazy-loaded embedding model
```

**Key Features:**
- Environment variable loading
- Type-safe configuration
- Validation at startup
- Lazy-loaded resources

### models.py

Pydantic models for request/response validation:

**TranscriptRequest:**
```python
class TranscriptRequest(BaseModel):
    userid: str                    # Patient/user identifier
    transcript: str                # Hindi patient transcript
    location: Optional[str] = None # Optional location for context
```

**PDFUploadResponse:**
```python
class PDFUploadResponse(BaseModel):
    success: bool                  # Upload success status
    message: str                   # Status message
    document_id: Optional[str]     # Generated document ID
    chunks_added: Optional[int]    # Number of chunks added
```

### tools.py

All LangChain tools organized in one module:

**Helper Functions:**
- `_call_openai()`: Wrapper for OpenAI API calls
- `_parse_json_input()`: Safe JSON parsing with defaults
- `_get_search_service()`: Lazy initialization of search service

**Tool Functions:**
All tools are decorated with `@tool` from `langchain_core.tools`:

1. **Core Analysis Tools:**
   - `diagnose_transcript()`: Analyzes Hindi transcripts
   - `query_clinical_guidelines()`: RAG queries
   - `search_health_news()`: Google Search integration
   - `evaluate_patient_report()`: Synthesizes results

2. **Clinical Decision Tools:**
   - `apply_clinical_rules()`: Red flag detection
   - `compute_risk_scores()`: Risk calculations
   - `differential_diagnosis()`: Diagnosis proposals
   - `assign_triage_level()`: Triage assignment

3. **Output Generation Tools:**
   - `generate_recommendations()`: Actionable recommendations
   - `format_clinical_report()`: Final report compilation

### agents.py

Agent creation and supervisor workflow:

```python
def create_all_agents():
    """Create all specialized agents."""
    return {
        "diagnosis_agent": create_react_agent(...),
        "rag_agent": create_react_agent(...),
        # ... all agents
    }

def create_supervisor_workflow():
    """Create and compile supervisor workflow."""
    agents = create_all_agents()
    workflow = create_supervisor(agents, model, prompt)
    return workflow.compile()
```

**Agent List:**
1. `diagnosis_agent` - Uses `diagnose_transcript` tool
2. `rag_agent` - Uses `query_clinical_guidelines` tool
3. `search_agent` - Uses `search_health_news` tool
4. `eval_agent` - Uses `evaluate_patient_report` tool
5. `clinical_rules_agent` - Uses `apply_clinical_rules` tool
6. `risk_scoring_agent` - Uses `compute_risk_scores` tool
7. `differential_diagnosis_agent` - Uses `differential_diagnosis` and `query_clinical_guidelines` tools
8. `triage_decision_agent` - Uses `assign_triage_level` tool
9. `recommendation_agent` - Uses `generate_recommendations` tool
10. `report_formatting_agent` - Uses `format_clinical_report` tool

## Services

### PDF Service (`services/pdf_service.py`)

**Methods:**
- `extract_text_from_pdf(pdf_file: bytes) -> str`: Extract text from PDF
- `chunk_text(text: str, chunk_size: int, overlap: int) -> List[Dict]`: Split text into chunks
- `create_embeddings_for_chunks(chunks: List[Dict], source: str) -> List[Dict]`: Generate embeddings

**Usage:**
```python
from services.pdf_service import PDFService

pdf_service = PDFService()
text = pdf_service.extract_text_from_pdf(pdf_bytes)
chunks = pdf_service.chunk_text(text)
embeddings = pdf_service.create_embeddings_for_chunks(chunks, source)
```

### LanceDB Service (`services/lancedb_service.py`)

**Methods:**
- `store_embeddings(data: List[Dict], table_name: str) -> int`: Store embeddings
- `search(query_embedding: List[float], top_k: int, table_name: str) -> List[Dict]`: Search vectors

**Usage:**
```python
from services.lancedb_service import LanceDBService

lancedb_service = LanceDBService()
count = lancedb_service.store_embeddings(data)
results = lancedb_service.search(query_embedding, top_k=5)
```

### Search Service (`services/search_service.py`)

**Methods:**
- `search_health_news(query: str, location: str, limit: int) -> List[Dict]`: Search health news

**Usage:**
```python
from services.search_service import SearchService

search_service = SearchService()
results = search_service.search_health_news("fever outbreak", location="Mumbai")
```

## API Endpoints

### Supervisor Orchestrator Endpoints (`api/routes.py`)

#### POST /analyze_transcript

**Function:** `analyze_transcript(req: TranscriptRequest)`

**Process Flow:**
1. Extract transcript, userid, location from request
2. Construct user message for supervisor
3. Invoke supervisor workflow with HumanMessage
4. Extract final message from workflow result
5. Parse JSON from response (handles markdown code blocks)
6. Validate and enrich response with required fields
7. Return structured JSON report

**Response Enrichment:**
- Sets `patient_id` from userid
- Generates `pseudo_id` if missing
- Sets `language` to "hi"
- Sets `consent_status` to "verified"
- Populates `input_summary` with transcript excerpt, call date, token count
- Populates `report_meta` with timestamps, audit log ID

**Error Handling:**
- JSON parsing errors → 500 with error details
- Missing response → 500 with error message
- Workflow failures → 500 with exception details

#### POST /upload_pdf

**Function:** `upload_pdf(file: UploadFile, source: str, chunk_size: int, overlap: int)`

**Process Flow:**
1. Validate file type (must be PDF)
2. Read PDF file bytes
3. Extract text using PDFService
4. Validate extracted text (minimum 50 characters)
5. Chunk text with specified size and overlap
6. Generate embeddings for chunks
7. Store in LanceDB using LanceDBService
8. Return success response with metadata

**Error Handling:**
- Invalid file type → 400 Bad Request
- Empty PDF → 400 Bad Request
- Processing errors → 500 Internal Server Error

### Voice Agent Endpoints (`api/voice_routes.py`)

#### WebSocket /ws/exotel/{stream_id}

**Function:** `ws_exotel_endpoint(stream_id: str, websocket: WebSocket)`

**Process:**
- Accepts WebSocket connection from Exotel
- Routes to inbound or outbound pipeline based on call direction
- Manages call lifecycle and cleanup

#### POST /voice/exotel/inbound

**Function:** `exotel_inbound(request: Request)`

**Process:**
- Receives inbound call webhook from Exotel
- Creates call metadata
- Returns WebSocket URL for connection

#### POST /voice/exotel/outbound

**Function:** `exotel_outbound(payload: Dict[str, Any])`

**Process:**
- Initiates outbound call via Exotel API
- Creates call metadata
- Returns call information and WebSocket URL

#### GET /voice/calls

**Function:** `get_calls()`

**Returns:** List of active/initiated calls for debugging

#### POST /voice/rag/upload-pdf

**Function:** `upload_pdf_rag(file: UploadFile, metadata: Optional[str])`

**Process:** Upload PDF to RAG knowledge base (voice agent specific)

#### POST /voice/rag/add-text

**Function:** `add_text_document(text: str, source: str, metadata: Optional[str])`

**Process:** Add text document to RAG knowledge base

#### GET /voice/rag/search

**Function:** `search_rag(query: str, top_k: int)`

**Process:** Search RAG knowledge base

## Agent System

### Agent Architecture

Each agent follows the ReAct (Reasoning + Acting) pattern:

1. **Receive task** from supervisor
2. **Reason** about what tool to use
3. **Act** by calling appropriate tool
4. **Observe** tool output
5. **Repeat** until task complete

### Agent Communication

Agents communicate through the supervisor's shared state:

```python
# Supervisor maintains state with:
- messages: List of conversation messages
- agent_outputs: Dictionary of agent outputs
- current_task: Current task being executed
```

### Tool Execution

Tools are executed synchronously within agents:

```python
@tool
def tool_function(param: str) -> str:
    # Tool implementation
    # Returns JSON string
    return json.dumps(result)
```

Agents parse tool outputs and use them for reasoning.

## Tools

### Tool Signature Pattern

All tools follow this pattern:

```python
@tool
def tool_name(input_json: str, ...) -> str:
    """
    Tool description.
    Inputs are JSON strings. Returns JSON string.
    """
    # Parse JSON inputs using _parse_json_input()
    # Call OpenAI API using _call_openai()
    # Return JSON string response
```

### Tool Categories

#### 1. Analysis Tools

**diagnose_transcript(transcript: str) -> str**
- **Input:** Hindi transcript string
- **Output:** JSON with symptoms, vitals, medical history, red flags
- **Uses:** OpenAI GPT-4 with `get_diagnose_transcript_prompt()`

**query_clinical_guidelines(keywords: str, top_k: int = 5) -> str**
- **Input:** Medical keywords (semicolon-separated)
- **Output:** JSON array of guideline hits
- **Uses:** Sentence Transformers + LanceDBService

**search_health_news(query: str, location: str = "") -> str**
- **Input:** Search query, optional location
- **Output:** JSON array of news articles
- **Uses:** SearchService (SerpAPI/Google Search)

#### 2. Clinical Decision Tools

**apply_clinical_rules(diagnosis_json: str, symptoms_json: str) -> str**
- **Input:** Diagnosis and symptoms JSON strings
- **Output:** Red flags JSON with escalation status
- **Uses:** OpenAI GPT-4

**compute_risk_scores(diagnosis_json: str, symptoms_json: str, ...) -> str**
- **Input:** Diagnosis, symptoms, age, comorbidities
- **Output:** Risk scores JSON
- **Uses:** OpenAI GPT-4

**differential_diagnosis(symptoms_json: str, rag_hits_json: str, ...) -> str**
- **Input:** Symptoms, RAG hits, clinical context
- **Output:** Differential diagnoses JSON
- **Uses:** OpenAI GPT-4

**assign_triage_level(red_flags_json: str, risk_scores_json: str, ...) -> str**
- **Input:** Red flags, risk scores, differential diagnosis
- **Output:** Triage decision JSON
- **Uses:** OpenAI GPT-4

#### 3. Output Generation Tools

**generate_recommendations(diagnosis_json: str, triage_json: str, ...) -> str**
- **Input:** Diagnosis, triage, differential, risk scores
- **Output:** Recommendations JSON
- **Uses:** OpenAI GPT-4

**format_clinical_report(diagnosis_json: str, triage_json: str, ...) -> str**
- **Input:** All previous outputs + transcript
- **Output:** Structured report JSON
- **Uses:** OpenAI GPT-4

## Voice Agent

### Architecture

The voice agent uses Pipecat for real-time voice interactions:

**Pipeline Components:**
1. **Transport**: FastAPI WebSocket transport with Exotel serializer
2. **STT**: Sarvam Speech-to-Text service (Hindi support)
3. **RAG Processor**: Adds context from knowledge base (optional)
4. **LLM**: OpenAI LLM service for response generation
5. **TTS**: Sarvam Text-to-Speech service (Hindi support)

**Pipeline Flow:**
```
Audio Input → STT → RAG Processor → LLM → TTS → Audio Output
```

### Configuration

Voice agent settings in `config.py`:
- `SARVAM_API_KEY`: Sarvam AI API key
- `SARVAM_VOICE_ID`: Voice ID for TTS
- `EXOTEL_ACCOUNT_SID`: Exotel account identifier
- `EXOTEL_AUTH_TOKEN`: Exotel authentication token
- `HOST`: WebSocket host for Exotel connections
- `PORT`: Application port

### Pipeline Types

**Inbound Pipeline:**
- Uses `inbound_prompt.md` for system prompt
- Greeting: "Hello! Thank you for calling. How can I assist you today?"

**Outbound Pipeline:**
- Uses `outbound_prompt.md` for system prompt
- Greeting: "Hello! This is an important call. Is this a good time to talk?"

## Prompts System

### Prompt Organization

Prompts are organized in the `prompts/` directory:

1. **Tool Prompts:** Function prompts for each tool
2. **Agent Prompts:** Behavior prompts for each agent
3. **Supervisor Prompt:** Coordination prompt

### Prompt Structure

**Tool Prompts:**
```python
def get_prompt(param1: type, param2: type) -> str:
    """
    Generate prompt for tool.
    Returns formatted prompt string.
    """
    return f"""
    Prompt template with {param1} and {param2}
    ...
    """
```

**Agent Prompts:**
```python
AGENT_PROMPT = """
Agent behavior description.
Role, responsibilities, and instructions.
"""
```

### Prompt Usage

Prompts are imported and used in modules:

```python
from prompts import (
    get_diagnose_transcript_prompt,
    AGENT_DIAGNOSIS_PROMPT,
    SUPERVISOR_PROMPT
)

# In tool function:
prompt = get_diagnose_transcript_prompt(transcript)

# In agent creation:
agent = create_react_agent(..., prompt=AGENT_DIAGNOSIS_PROMPT)
```

## RAG Implementation

### Embedding Generation

**Model:** Sentence Transformers (configurable via `EMBEDDING_MODEL`)

**Process:**
1. Text chunks converted to embeddings
2. Batch processing for efficiency (batch_size=32)
3. NumPy arrays converted to lists for storage

**Code:**
```python
embeddings = settings.embedding_model.encode(
    texts,
    convert_to_numpy=True,
    show_progress_bar=False,
    batch_size=settings.EMBEDDING_BATCH_SIZE
)
```

### Vector Storage

**Database:** LanceDB

**Schema:**
- `id`: Unique document ID (UUID)
- `vector`: Embedding vector (list of floats)
- `text`: Original text chunk
- `source`: Document source identifier
- `chunk_index`: Chunk position in document

**Storage:**
```python
lancedb_service = LanceDBService()
count = lancedb_service.store_embeddings(data, table_name="clinical_guidelines")
```

### Query Process

**Query Embedding:**
```python
query_embedding = settings.embedding_model.encode(
    keywords,
    convert_to_numpy=True
).tolist()
```

**Search:**
```python
results = lancedb_service.search(query_embedding, top_k=5)
```

**Results:**
- Returns top-k most similar chunks
- Includes distance scores
- Preserves metadata (source, text, etc.)

## Data Models

### Request Models

**TranscriptRequest:**
```python
{
    "userid": str,
    "transcript": str,
    "location": str | None
}
```

**PDF Upload (Form Data):**
```python
{
    "file": UploadFile,
    "source": str,
    "chunk_size": int,
    "overlap": int
}
```

### Response Models

**PDFUploadResponse:**
```python
{
    "success": bool,
    "message": str,
    "document_id": str | None,
    "chunks_added": int | None
}
```

**Clinical Report (Structured JSON):**
See [Response Format](#response-format) in README.md for complete structure.

### Internal Data Structures

**Chunk Dictionary:**
```python
{
    "text": str,
    "chunk_index": int
}
```

**Embedding Data:**
```python
{
    "id": str,
    "vector": List[float],
    "text": str,
    "source": str,
    "chunk_index": int
}
```

**RAG Hit:**
```python
{
    "id": str,
    "score": float,
    "text": str,
    "source": str
}
```

## Error Handling

### API Level

- **Validation Errors:** Pydantic validation at request level
- **HTTP Exceptions:** FastAPI HTTPException for errors
- **Status Codes:** 400 (Bad Request), 500 (Internal Server Error), 503 (Service Unavailable)

### Tool Level

- **JSON Parsing:** Try-except blocks with error messages using `_parse_json_input()`
- **API Failures:** Error messages in JSON responses
- **Missing Data:** Default values and null handling

### Agent Level

- **Tool Failures:** Agents handle tool errors gracefully
- **Supervisor:** Can retry or use alternative agents
- **Partial Results:** System continues with available data

### Service Level

- **Service Initialization:** Graceful handling of missing optional services
- **Resource Errors:** Clear error messages for missing resources
- **External API Failures:** Fallback behavior where possible

## Performance Considerations

### Embedding Generation

- **Batch Processing:** 32 chunks per batch (configurable)
- **Local Processing:** No API calls for embeddings
- **Model Loading:** Model loaded once at startup (lazy-loaded)

### LLM Calls

- **Sequential Execution:** Agents execute one at a time
- **Token Usage:** GPT-4 for all LLM interactions
- **Caching:** Not currently implemented (future enhancement)

### Database Operations

- **Vector Search:** Efficient similarity search in LanceDB
- **Append Operations:** Fast append for new documents
- **Table Creation:** One-time setup for new tables

### Voice Agent

- **Real-time Processing:** Low-latency pipeline for voice interactions
- **Audio Sample Rate:** 8000 Hz for telephony
- **Interruptions:** Supports voice activity detection and interruptions

## Testing

### Manual Testing

**Test Transcript Analysis:**
```bash
curl -X POST "http://localhost:8000/analyze_transcript" \
  -H "Content-Type: application/json" \
  -d '{"userid": "test", "transcript": "मुझे बुखार है"}'
```

**Test PDF Upload:**
```bash
curl -X POST "http://localhost:8000/upload_pdf" \
  -F "file=@test.pdf"
```

**Test Voice Agent RAG Search:**
```bash
curl -X GET "http://localhost:8000/voice/rag/search?query=fever&top_k=3"
```

### Unit Testing (Future)

- Tool function unit tests
- Service class unit tests
- Prompt validation tests
- Agent behavior tests
- Integration tests for workflows
- Voice agent pipeline tests

## Future Enhancements

1. **Async Agents:** Parallel agent execution
2. **Caching:** Cache RAG queries and LLM responses
3. **Database:** Persistent storage for reports
4. **Monitoring:** Metrics and observability
5. **GPU Support:** GPU acceleration for embeddings
6. **Streaming:** Streaming responses for long operations
7. **Multi-language:** Support for additional languages beyond Hindi
8. **Voice Agent Enhancements:** Better interruption handling, emotion detection
