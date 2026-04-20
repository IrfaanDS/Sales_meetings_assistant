import os
import uuid
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

class QdrantVectorStore:
    def __init__(self, collection_name: str = "meeting_docs", db_path: str = "./qdrant_db"):
        self.collection_name = collection_name
        self.db_path = db_path
        
        # Ensure directory exists for local qdrant
        os.makedirs(self.db_path, exist_ok=True)
        
        self.client = QdrantClient(path=self.db_path)
        self.embed_model = SentenceTransformer('all-MiniLM-L6-v2')
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.client.get_collection(self.collection_name)
            print(f"Collection {self.collection_name} exists.")
        except Exception:
            print(f"Creating new collection {self.collection_name}...")
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
                limit=10000,
                with_payload=True,
                with_vectors=False
            )
            for record in records:
                if record.payload and "filename" in record.payload:
                    filenames.add(record.payload["filename"])
        except Exception as e:
            print(f"Error listing documents: {e}")
        return list(filenames)

    def upsert_chunks(self, chunks: List[str], filename: str):
        if not chunks:
            return

        print(f"Embedding {len(chunks)} chunks for {filename}...")
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
        print(f"✅ Upserted {filename} into Qdrant.")

    def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        query_vector = self.embed_model.encode([query])[0].tolist()
        
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
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
        print(f"Deleting document: {filename} from Qdrant...")
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
        print(f"✅ Deleted {filename}.")

_global_instance = None

def get_vector_store():
    global _global_instance
    if _global_instance is None:
        _global_instance = QdrantVectorStore()
    return _global_instance
