"""LanceDB vector database service."""

from typing import Dict, List, Any

import lancedb
import pandas as pd

from config import settings


class LanceDBService:
    """Service for LanceDB vector database operations."""
    
    def __init__(self, db_path: str = None):
        """
        Initialize LanceDB service.
        
        Args:
            db_path: Path to LanceDB database (defaults to settings.LANCEDB_PATH)
        """
        self.db_path = db_path or settings.LANCEDB_PATH
        self._db = None
    
    @property
    def db(self):
        """Lazy load database connection."""
        if self._db is None:
            self._db = lancedb.connect(self.db_path)
        return self._db
    
    def store_embeddings(
        self, 
        data: List[Dict[str, Any]], 
        table_name: str = None
    ) -> int:
        """
        Store embeddings and text in LanceDB.
        
        Args:
            data: List of dictionaries with embeddings and metadata
            table_name: Name of the table to store data in
            
        Returns:
            Number of records stored
        """
        table_name = table_name or settings.LANCEDB_TABLE_NAME
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(data)
        
        # Check if table exists
        try:
            table = self.db.open_table(table_name)
            # Append to existing table
            table.add(df)
        except Exception:
            # Create new table if it doesn't exist
            # LanceDB will automatically detect the vector column
            table = self.db.create_table(table_name, df, mode="overwrite")
        
        return len(data)
    
    def search(
        self, 
        query_embedding: List[float], 
        top_k: int = None,
        table_name: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search LanceDB vector store for similar embeddings.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            table_name: Name of the table to search
            
        Returns:
            List of search results with metadata
        """
        top_k = top_k or settings.DEFAULT_TOP_K
        table_name = table_name or settings.LANCEDB_TABLE_NAME
        
        try:
            table = self.db.open_table(table_name)
        except Exception as e:
            raise ValueError(f"LanceDB table '{table_name}' not found: {str(e)}")
        
        # Search using the vector column (LanceDB auto-detects "vector" column)
        results = table.search(query_embedding).limit(top_k).to_pandas()
        
        hits = []
        for _, row in results.iterrows():
            hits.append({
                "id": row.get("id", ""),
                "score": row.get("_distance", None),
                "text": row.get("text", ""),
                "source": row.get("source", "")
            })
        
        return hits

