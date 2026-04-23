import os
import sys
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer


def _get_model_path():
    """Return the SentenceTransformer model path, accounting for PyInstaller frozen bundles."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
        return os.path.join(base, 'sentence_transformers_cache', 'all-MiniLM-L6-v2')
    return 'all-MiniLM-L6-v2'


def _get_db_path():
    """Return a persistent Qdrant DB path inside AppData, never relative to cwd."""
    app_data = Path.home() / "AppData" / "Local" / "AI_Meetings_Assistant"
    db_path = app_data / "qdrant_db"
    db_path.mkdir(parents=True, exist_ok=True)
    return str(db_path)


class QdrantVectorStore:
    def __init__(self, collection_name: str = "meeting_docs", db_path: str = None):
        self.collection_name = collection_name
        self.db_path = db_path or _get_db_path()
        
        # Ensure directory exists for local qdrant
        os.makedirs(self.db_path, exist_ok=True)
        
        try:
            self.client = QdrantClient(path=self.db_path)
        except Exception as e:
            logging.critical(f"Failed to open Qdrant DB at {self.db_path}: {e}", exc_info=True)
            raise  # Let it propagate so RAGIndexThread.error signal fires

        self.embed_model = SentenceTransformer(_get_model_path())
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.client.get_collection(self.collection_name)
            logging.info(f"Collection {self.collection_name} exists.")
        except Exception:
            logging.info(f"Creating new collection {self.collection_name}...")
            vector_size = self.embed_model.get_sentence_embedding_dimension()
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size, 
                    distance=models.Distance.COSINE
                ),
            )

    def is_empty(self) -> bool:
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return collection_info.points_count == 0
        except:
            return True

    def list_documents(self) -> List[str]:
        """Returns a list of unique filenames currently indexed."""
        # A simple hack for local qdrant without complex grouping: 
        # scroll and collect unique filenames from metadata.
        # This is safe for typical use cases (a few dozen docs).
        filenames = set()
        try:
            records, next_page = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                with_payload=True,
                with_vectors=False
            )
            for record in records:
                if record.payload and "filename" in record.payload:
                    filenames.add(record.payload["filename"])
        except Exception as e:
            logging.error(f"Error listing documents: {e}")
        return list(filenames)

    def upsert_chunks(self, chunks: List[str], filename: str):
        if not chunks:
            return

        logging.info(f"Embedding {len(chunks)} chunks for {filename}...")
        embeddings = self.embed_model.encode(chunks, show_progress_bar=False)
        
        points = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=emb.tolist(),
                    payload={
                        "text": chunk,
                        "filename": filename,
                        "chunk_idx": i
                    }
                )
            )

        # Upsert in batches of 100 to avoid memory spikes
        batch_size = 100
        for i in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[i:i+batch_size]
            )
        logging.info(f"Upserted {filename} into Qdrant.")

    def close(self):
        if hasattr(self, 'client'):
            try:
                # QdrantClient doesn't always have an explicit close() 
                # but we can at least drop the reference.
                # In newer versions it might have .close()
                if hasattr(self.client, 'close'):
                    self.client.close()
                del self.client
                logging.info("Qdrant client closed.")
            except Exception as e:
                logging.error(f"Error closing Qdrant client: {e}")

    def __del__(self):
        self.close()

    def search(self, query: str, limit: int = 3, filter_docs: List[str] = None) -> List[Dict[str, Any]]:
        query_vector = self.embed_model.encode([query])[0].tolist()
        
        query_filter = None
        if filter_docs:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="filename",
                        match=models.MatchAny(any=filter_docs),
                    )
                ]
            )
        elif filter_docs is not None:
            # If an empty list specifically was passed, return no results
            return []

        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True
        )
        
        results = []
        for scored_point in search_result:
            if scored_point.payload:
                results.append({
                    "text": scored_point.payload.get("text", ""),
                    "filename": scored_point.payload.get("filename", "Unknown"),
                    "score": scored_point.score
                })
        return results

    def delete_document(self, filename: str):
        """Deletes all chunks associated with a specific filename."""
        logging.info(f"Deleting document: {filename} from Qdrant...")
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="filename",
                            match=models.MatchValue(value=filename),
                        ),
                    ]
                )
            ),
        )
        logging.info(f"Deleted {filename}.")

_global_instance = None

def get_vector_store():
    global _global_instance
    if _global_instance is None:
        _global_instance = QdrantVectorStore()
    return _global_instance

def close_vector_store():
    global _global_instance
    if _global_instance is not None:
        _global_instance.close()
        _global_instance = None
