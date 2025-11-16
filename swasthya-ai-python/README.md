# SwasthyaAI - Clinical Transcript Analysis System

A comprehensive multi-agent AI system for analyzing Hindi patient transcripts and generating structured clinical reports. Built with FastAPI, LangGraph Supervisor, and OpenAI GPT-4.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Agent System](#agent-system)
- [RAG System](#rag-system)
- [Response Format](#response-format)
- [Development](#development)

## Overview

SwasthyaAI is a sophisticated clinical decision support system that:

- **Analyzes Hindi patient transcripts** using natural language processing
- **Extracts symptoms, vitals, and medical history** with detailed metadata
- **Queries clinical guidelines** using RAG (Retrieval Augmented Generation)
- **Applies clinical rules** to detect red flags and escalation triggers
- **Computes risk scores** for various conditions (sepsis, cardiac, etc.)
- **Generates differential diagnoses** with confidence scores and citations
- **Assigns triage levels** based on clinical protocols
- **Provides recommendations** in both Hindi (for patients) and English (for doctors)
- **Generates structured reports** in JSON format matching FHIR-compatible standards

## Architecture

The system uses a **hierarchical multi-agent architecture** orchestrated by a LangGraph Supervisor:

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
│                  (REST API Endpoints)                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              LangGraph Supervisor Agent                      │
│         (Orchestrates all specialized agents)                │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Core Agents  │ │ Clinical     │ │ Output       │
│              │ │ Decision     │ │ Generation   │
│              │ │ Agents       │ │ Agents       │
└──────────────┘ └──────────────┘ └──────────────┘
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed architecture diagrams.

## Features

### 1. Multi-Agent Orchestration
- **10 specialized agents** working in coordination
- **Supervisor pattern** for intelligent task delegation
- **Sequential workflow** ensuring comprehensive analysis

### 2. Hindi Language Support
- Native support for Hindi (Devanagari script) transcripts
- Preserves Hindi text in patient-facing outputs
- Translates to English medical terminology for consistency

### 3. RAG (Retrieval Augmented Generation)
- **LanceDB** vector database for clinical guidelines
- **Sentence Transformers** for local embedding generation
- **PDF upload** endpoint for adding new guidelines
- Semantic search for relevant clinical information

### 4. Clinical Decision Support
- **Red flag detection** using deterministic rules
- **Risk scoring** for sepsis, cardiac events, diabetes, etc.
- **Differential diagnosis** with confidence scores
- **Triage assignment** following standard protocols (ESI, CTAS, Manchester)

### 5. Structured Output
- **JSON/FHIR-compatible** report format
- **Comprehensive metadata** including timestamps, confidence scores, audit logs
- **Bilingual recommendations** (Hindi for patients, English for doctors)

## Installation

### Prerequisites

- Python 3.11 or higher
- `uv` package manager (recommended) or `pip`

### Steps

1. **Clone the repository** (if applicable) or navigate to the project directory

2. **Install dependencies using uv:**
```bash
uv pip install -r requirements.txt
# Or if using pyproject.toml:
uv sync
```

3. **Set up environment variables:**
Create a `.env` file in the project root:
```env
OPENAI_API_KEY=your_openai_api_key_here
SERPAPI_KEY=your_serpapi_key_here
LANCEDB_PATH=./lancedb_store
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

4. **Run the application:**
```bash
uvicorn app:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 | Yes | - |
| `SERPAPI_KEY` | SerpAPI key for Google Search | No | - |
| `LANCEDB_PATH` | Path to LanceDB storage directory | No | `./lancedb_store` |
| `EMBEDDING_MODEL` | Sentence Transformer model name | No | `all-MiniLM-L6-v2` |

### Embedding Models

The system supports different Sentence Transformer models:

- **`all-MiniLM-L6-v2`** (default): Fast, English-only, good for medical content
- **`paraphrase-multilingual-MiniLM-L12-v2`**: Multilingual support, larger model
- **Custom models**: Any compatible Sentence Transformer model

## API Endpoints

### 1. Analyze Transcript

**POST** `/analyze_transcript`

Analyzes a Hindi patient transcript and returns a comprehensive clinical report.

**Request Body:**
```json
{
  "userid": "patient_123",
  "transcript": "मुझे पिछले तीन दिनों से बुखार हो रहा है...",
  "location": "Delhi, India"  // Optional
}
```

**Response:**
Returns a structured JSON report (see [Response Format](#response-format) section).

**Example:**
```bash
curl -X POST "http://localhost:8000/analyze_transcript" \
  -H "Content-Type: application/json" \
  -d '{
    "userid": "patient_123",
    "transcript": "मुझे पिछले तीन दिनों से बुखार हो रहा है। हल्की खांसी है और शरीर में दर्द हो रहा है।"
  }'
```

### 2. Upload PDF for RAG

**POST** `/upload_pdf`

Uploads a PDF document to be processed and added to the RAG knowledge base.

**Request:**
- `file`: PDF file (multipart/form-data)
- `source`: Source identifier (optional, default: "uploaded_pdf")
- `chunk_size`: Words per chunk (optional, default: 1000)
- `overlap`: Overlapping words between chunks (optional, default: 200)

**Response:**
```json
{
  "success": true,
  "message": "Successfully processed PDF: guidelines.pdf. Added 45 chunks to RAG database.",
  "document_id": "uuid-here",
  "chunks_added": 45
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/upload_pdf" \
  -F "file=@clinical_guidelines.pdf" \
  -F "source=ICMR_2023" \
  -F "chunk_size=1000" \
  -F "overlap=200"
```

## Agent System

The system consists of **10 specialized agents** organized into three categories:

### Core Analysis Agents

1. **Diagnosis Agent** (`diagnosis_agent`)
   - Analyzes Hindi patient transcripts
   - Extracts symptoms with detailed metadata (duration, severity in Hindi)
   - Identifies red flags and probable conditions
   - Extracts vitals and past medical history

2. **RAG Agent** (`rag_agent`)
   - Queries clinical guidelines database using semantic search
   - Uses Sentence Transformers for embedding-based retrieval
   - Returns relevant guideline snippets with citations

3. **Search Agent** (`search_agent`)
   - Searches for recent health news and outbreaks
   - Uses SerpAPI/Google Search
   - Supports Hindi and English queries

4. **Evaluation Agent** (`eval_agent`)
   - Synthesizes diagnosis, RAG hits, and news
   - Creates comprehensive patient reports
   - Provides confidence scores

### Clinical Decision Agents

5. **Clinical Rules Agent** (`clinical_rules_agent`)
   - Applies deterministic red-flag rules
   - Detects immediate escalation triggers
   - Returns red flags in Hindi

6. **Risk Scoring Agent** (`risk_scoring_agent`)
   - Computes disease-specific risk scores
   - Calculates sepsis, cardiac, diabetes risk scores
   - Flags elevated risks

7. **Differential Diagnosis Agent** (`differential_diagnosis_agent`)
   - Proposes possible diagnoses with confidence
   - Uses LLM + RAG for evidence-based suggestions
   - Includes citations from clinical guidelines

8. **Triage Decision Agent** (`triage_decision_agent`)
   - Assigns triage level (Emergent, Urgent, Routine)
   - Follows standard protocols (ESI, CTAS, Manchester)
   - Provides Hindi explanations

### Output Generation Agents

9. **Recommendation Agent** (`recommendation_agent`)
   - Generates doctor actionables (English)
   - Creates patient instructions (Hindi)
   - Suggests tests and referrals

10. **Report Formatting Agent** (`report_formatting_agent`)
    - Compiles all outputs into structured JSON
    - Ensures FHIR-compatible format
    - Adds metadata and audit logs

### Agent Workflow

The supervisor coordinates agents in this sequence:

```
1. diagnosis_agent → Extract symptoms/conditions
2. rag_agent → Query clinical guidelines
3. clinical_rules_agent → Check for red flags
4. risk_scoring_agent → Compute risk scores
5. differential_diagnosis_agent → Propose diagnoses
6. triage_decision_agent → Assign triage level
7. recommendation_agent → Generate actionables
8. report_formatting_agent → Compile final report
```

## RAG System

### Overview

The RAG (Retrieval Augmented Generation) system uses:

- **LanceDB**: Vector database for storing clinical guidelines
- **Sentence Transformers**: Local embedding model (no API costs)
- **Semantic Search**: Vector similarity search for relevant content

### Adding Documents

Use the `/upload_pdf` endpoint to add clinical guidelines:

1. Upload PDF files containing clinical protocols
2. System extracts text, chunks it, and generates embeddings
3. Documents are stored in LanceDB for retrieval

### Query Process

1. User query is converted to embedding using Sentence Transformers
2. Vector similarity search finds relevant chunks
3. Top-k results are returned with scores and citations

## Response Format

The `/analyze_transcript` endpoint returns a structured JSON report:

```json
{
  "patient_id": "p123_demo",
  "pseudo_id": "anon_00981",
  "language": "hi",
  "consent_status": "verified",
  "input_summary": {
    "transcript_excerpt": "मुझे पिछले तीन दिनों से बुखार हो रहा है...",
    "call_date": "2025-11-15T13:12:08+05:30",
    "transcript_tokens": 384
  },
  "symptoms": [
    {
      "name": "बुखार",
      "duration_days": 3,
      "onset_description": "3 दिन पहले",
      "severity": "मध्यम",
      "source": "utt_3"
    }
  ],
  "past_medical_history": {
    "reported_by_patient": {
      "diabetes": false,
      "hypertension": false,
      "medications": [],
      "allergies": [],
      "prior_infections": []
    },
    "retrieved_from_api": {
      "record_found": false,
      "lookup_time": "2025-11-15T13:12:15+05:30"
    }
  },
  "vitals_reported": {
    "temperature_f": 101.0,
    "spo2_percent": null,
    "heart_rate": null
  },
  "risk_scores": {
    "sepsis_risk_score": 0.14,
    "cardiac_flag": false,
    "dehydration_risk": "low"
  },
  "red_flags": [],
  "triage": {
    "level": "Urgent",
    "explanation": "बुखार 3+ दिन से है...",
    "recommended_action_window": "48 घंटे",
    "override_reason": null,
    "source_guidelines": [...]
  },
  "differential_diagnosis": [
    {
      "condition": "वायरल ज्वर (Common viral infection)",
      "confidence": 0.72,
      "rationale": "तीन दिन पुराना बुखार...",
      "citations": [...]
    }
  ],
  "recommendations": {
    "for_patient_hi": "आपको वायरल बुखार हो सकता है...",
    "tests_suggested": ["CBC", "Typhidot", "Platelet Count"],
    "referral_suggestion": {
      "urgency": "within 48 hours",
      "recommended_center": "नजदीकी प्राथमिक स्वास्थ्य केंद्र (PHC)"
    }
  },
  "doctor_summary_note": {
    "summary": "3-day febrile illness with dry cough...",
    "actionables": [
      "Advise paracetamol + rest",
      "Refer to PHC if symptoms persist >48h"
    ]
  },
  "report_meta": {
    "created_at": "2025-11-15T13:14:58+05:30",
    "generated_by": "supervisor-agent-v1.2",
    "confidence": 0.89,
    "human_review_required": false,
    "audit_log_id": "audit_5f8b9"
  }
}
```

## Development

### Project Structure

```
core/
├── app.py                 # Main FastAPI application
├── pyproject.toml         # Dependencies and project config
├── prompts/               # Prompt templates
│   ├── __init__.py
│   ├── supervisor.py      # Supervisor prompt
│   ├── diagnose_transcript.py
│   ├── format_clinical_report.py
│   ├── agent_*.py         # Agent prompts
│   └── ...                # Other tool prompts
├── lancedb_store/         # LanceDB data directory
└── README.md
```

### Key Dependencies

- **FastAPI**: Web framework for REST API
- **LangGraph**: Agent orchestration framework
- **LangChain**: LLM integration and tool definitions
- **OpenAI**: GPT-4 for LLM interactions
- **LanceDB**: Vector database for RAG
- **Sentence Transformers**: Local embedding generation
- **PDFPlumber**: PDF text extraction
- **SerpAPI**: Google Search integration

### Adding New Agents

1. Create a tool function with `@tool` decorator
2. Create agent prompt in `prompts/agent_*.py`
3. Create tool prompt in `prompts/*.py`
4. Add agent to supervisor workflow in `app.py`
5. Update supervisor prompt with agent description

### Testing

```bash
# Test the analyze endpoint
curl -X POST "http://localhost:8000/analyze_transcript" \
  -H "Content-Type: application/json" \
  -d '{"userid": "test", "transcript": "मुझे बुखार है"}'

# Test PDF upload
curl -X POST "http://localhost:8000/upload_pdf" \
  -F "file=@test.pdf"
```

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

For issues and questions, please [create an issue](link-to-issues) or contact [support email].

