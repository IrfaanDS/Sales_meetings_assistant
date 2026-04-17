import os
import time
import asyncio
import numpy as np
import faiss
import nest_asyncio
import google.generativeai as genai
from typing import List, Dict, Optional
from pypdf import PdfReader
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from langchain_groq import ChatGroq
from PyQt6.QtCore import QThread, pyqtSignal
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv()

# Configure LLM default system prompt
DEFAULT_SYSTEM_PROMPT = """
Role: You are the Sales Intelligence Co-Pilot. Your goal is to provide the sales representative with a direct "response script" to read aloud to the client in real-time.

Input Context:
Live Transcript: Speech from the client (often messy or accented).
Retrieved Context: Snippets from the project’s knowledge base.

Task Instructions:
1. Identify Intent: Detect the client's core question or technical concern.
2. Script Generation: Write a response that the rep can speak immediately. It must be conversational, authoritative, and brief (40-60 words).

CRITICAL CONSTRAINTS (The Golden Rules):
- NEVER ask a follow-up question. Your output is the ANSWER to the client's question.
- DO NOT engage in a dialogue with the sales rep.
- BE INVISIBLE: Never say "The document states" or "Here is a script." Start directly with the suggested response.
- FORMAT FOR SPEED
- ACCURACY: If the context doesn't contain the answer, say "I don't have information on that specific detail yet" as a script for the rep.
"""

class DocumentProcessor:
    def __init__(self, chunk_size=600, chunk_overlap=100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_directory(self, path: str) -> List[str]:
        chunks = []
        if not os.path.exists(path): return []
        for f in os.listdir(path):
            fpath = os.path.join(path, f)
            if f.endswith(".pdf"): chunks.extend(self.chunk_text(self.load_pdf(fpath)))
            elif f.endswith(".txt"): chunks.extend(self.chunk_text(open(fpath, encoding='utf-8').read()))
        return chunks

    def load_file(self, fpath: str) -> List[str]:
        if not os.path.exists(fpath): return []
        if fpath.endswith(".pdf"): return self.chunk_text(self.load_pdf(fpath))
        elif fpath.endswith(".txt"): return self.chunk_text(open(fpath, encoding='utf-8').read())
        return []

    def load_pdf(self, path: str) -> str:
        try: return "\n".join([p.extract_text() for p in PdfReader(path).pages])
        except Exception as e: return ""

    def chunk_text(self, text: str) -> List[str]:
        chunks, start = [], 0
        while start < len(text):
            end = start + self.chunk_size
            if end < len(text):
                break_idx = text.rfind('\n', start, end)
                if break_idx == -1 or break_idx < start + 200: break_idx = text.rfind(' ', start, end)
                if break_idx != -1: end = break_idx
            chunk = text[start:end].strip()
            if len(chunk) > 30: chunks.append(chunk)
            start = end - self.chunk_overlap
            if start >= end: start = end + 1
        return chunks

class HybridEngine:
    def __init__(self, chunks: List[str]):
        self.chunks, self.embed_model = chunks, SentenceTransformer('all-MiniLM-L6-v2')
        self.bm25, self.faiss_index = None, None
        self._build()

    def _build(self):
        if not self.chunks: return print("No chunks to index!")
        print(f"Indexing {len(self.chunks)} fragments...")
        self.bm25 = BM25Okapi([d.lower().split() for d in self.chunks])
        embs = self.embed_model.encode(self.chunks, show_progress_bar=False)
        self.faiss_index = faiss.IndexFlatL2(embs.shape[1])
        self.faiss_index.add(embs.astype('float32'))
        print("✅ Engine ready!")

    async def retrieve(self, query: str, k: int = 2):
        if not self.chunks:
            return []
        v_task = asyncio.to_thread(self._v_search, query, k*2)
        k_task = asyncio.to_thread(self._k_search, query, k*2)
        v_res, k_res = await asyncio.gather(v_task, k_task)
        ranks = {}
        for i, idx in enumerate(v_res): ranks[idx] = ranks.get(idx, 0) + 1.0/(60+i)
        for i, idx in enumerate(k_res): ranks[idx] = ranks.get(idx, 0) + 1.0/(60+i)
        top = sorted(ranks.keys(), key=ranks.get, reverse=True)[:k]
        return [self.chunks[i] for i in top if i != -1]

    def _v_search(self, q, k): 
        if self.faiss_index is None: return []
        return self.faiss_index.search(self.embed_model.encode([q]).astype('float32'), k)[1][0].tolist()
        
    def _k_search(self, q, k): 
        if self.bm25 is None: return []
        return np.argsort(self.bm25.get_scores(q.lower().split()))[-k:][::-1].tolist()

class SalesAssistant:
    def __init__(self, engine: HybridEngine, model="llama-3.3-70b-versatile", system_prompt: str = DEFAULT_SYSTEM_PROMPT):
        self.engine = engine
        self.model_name = model
        self.system_prompt = system_prompt

    async def stream_ask(self, query: str, emit_func):
        api_key = os.environ.get("GROQ_API_KEY")
        # Initialize Groq LLM (optimized for speed)
        llm = ChatGroq(
            model=self.model_name, 
            temperature=0,
            groq_api_key=api_key
        )
        
        ctx = "\n---\n".join(await self.engine.retrieve(query))
        prompt = f"{self.system_prompt}\n\nContext: {ctx}\n\nQuery: {query}\n\nSales Response:"
        
        try:
            async for chunk in llm.astream(prompt): 
                emit_func(chunk.content)
        except Exception as e:
            emit_func(f"\n[Model Error: {e}]\n")
            print(f"❌ Model error: {e}")


# --- PyQt6 QThreads for background execution ---


class RAGIndexThread(QThread):
    finished = pyqtSignal(object)  # Emits the SalesAssistant instance upon completion
    error = pyqtSignal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            processor = DocumentProcessor()
            if self.file_path:
                chunks = processor.load_file(self.file_path)
            else:
                chunks = []
                
            engine = HybridEngine(chunks)
            assistant = SalesAssistant(engine)
            self.finished.emit(assistant)
        except Exception as e:
            self.error.emit(str(e))


class RAGQueryThread(QThread):
    chunk_received = pyqtSignal(str)
    completed = pyqtSignal()

    def __init__(self, assistant: SalesAssistant, query: str):
        super().__init__()
        self.assistant = assistant
        self.query = query

    def run(self):
        if not self.assistant:
            self.chunk_received.emit("Assistant engine is not initialized.")
            self.completed.emit()
            return
            
        def emitter(chunk_text):
            self.chunk_received.emit(chunk_text)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.assistant.stream_ask(self.query, emitter))
        loop.close()
        self.completed.emit()

