"""
Configuration module for SwasthyaAI application.

Centralizes all configuration settings, environment variables, and constants.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Load environment variables
load_dotenv()


class Settings:
    """Application settings and configuration."""
    
    # API Keys
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    SERPAPI_KEY: Optional[str] = os.environ.get("SERPAPI_KEY")
    
    # Paths
    LANCEDB_PATH: str = os.environ.get("LANCEDB_PATH", "./lancedb_store")
    
    # Model Configuration
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4.1")
    EMBEDDING_MODEL_NAME: str = os.environ.get(
        "EMBEDDING_MODEL", 
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    
    # PDF Processing Defaults
    DEFAULT_CHUNK_SIZE: int = 1000
    DEFAULT_CHUNK_OVERLAP: int = 200
    MIN_PDF_TEXT_LENGTH: int = 50
    
    # RAG Configuration
    DEFAULT_TOP_K: int = 5
    EMBEDDING_BATCH_SIZE: int = 32
    LANCEDB_TABLE_NAME: str = "clinical_guidelines"
    
    # Search Configuration
    SEARCH_RESULTS_LIMIT: int = 5
    SEARCH_LANGUAGE: str = "hi"  # Hindi
    SEARCH_REGION: str = "in"  # India
    
    # Report Generation
    DEFAULT_LANGUAGE: str = "hi"
    DEFAULT_CONSENT_STATUS: str = "verified"
    TOKEN_CHAR_RATIO: int = 4  # Approximate: 1 token ≈ 4 characters
    
    # Voice Agent Configuration (Pipecat/Exotel)
    HOST: str = os.environ.get("HOST", "localhost")
    PORT: int = int(os.environ.get("PORT", 8000))
    EXOTEL_ACCOUNT_SID: Optional[str] = os.environ.get("EXOTEL_SID")
    EXOTEL_AUTH_TOKEN: Optional[str] = os.environ.get("EXOTEL_API_TOKEN")
    EXOTEL_API_KEY: Optional[str] = os.environ.get("EXOTEL_API_KEY")
    EXOTEL_API_BASE: str = os.environ.get("EXOTEL_API_BASE", "https://api.exotel.com/v1")
    DEEPGRAM_API_KEY: Optional[str] = os.environ.get("DEEPGRAM_API_KEY")
    SARVAM_API_KEY: Optional[str] = os.environ.get("SARVAM_API_KEY")
    SARVAM_VOICE_ID: str = os.environ.get("SARVAM_VOICE_ID", "default_voice")
    WEBHOOK_URL: Optional[str] = os.environ.get("WEBHOOK_URL")

    # Vobiz Configuration
    VOBIZ_AUTH_ID: Optional[str] = os.environ.get("VOBIZ_AUTH_ID")
    VOBIZ_AUTH_TOKEN: Optional[str] = os.environ.get("VOBIZ_AUTH_TOKEN")
    VOBIZ_PHONE_NUMBER: Optional[str] = os.environ.get("VOBIZ_PHONE_NUMBER")
    
    def __init__(self):
        """Validate required settings on initialization."""
        if not self.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY must be set")
    
    @property
    def embedding_model(self) -> SentenceTransformer:
        """Lazy load embedding model."""
        if not hasattr(self, "_embedding_model"):
            print(f"Loading embedding model: {self.EMBEDDING_MODEL_NAME}")
            self._embedding_model = SentenceTransformer(self.EMBEDDING_MODEL_NAME)
            print("Embedding model loaded successfully")
        return self._embedding_model


# Global settings instance
settings = Settings()

