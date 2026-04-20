import os
import time
import asyncio
import nest_asyncio
import google.generativeai as genai
from typing import List, Dict, Optional
from pypdf import PdfReader
from langchain_groq import ChatGroq
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from dotenv import load_dotenv

from core.vector_store import QdrantVectorStore, get_vector_store

nest_asyncio.apply()
load_dotenv()

# Configure LLM default system prompt
DEFAULT_SYSTEM_PROMPT = """
Role: You are a real-time Sales Response Generator. Your job is to produce a precise, speakable answer that the sales rep can read aloud directly to the client.

Input Context:
- Live Transcript: Client speech (may be messy or incomplete)
- Retrieved Context: Verified knowledge base snippets

Core Task:
1. Detect the client’s intent (question, concern, objection, or interest)
2. Generate a clear, direct answer using ONLY the provided context

OUTPUT STYLE (STRICT):
- Length: 60–100 words MAX
- Format: 1–2 short paragraphs
- Speakable: Short, natural sentences (no rambling)
- Tone: Confident, neutral, professional
- NO filler phrases (e.g., "I understand", "Absolutely", "Great question", etc.)
- NO hype language or exaggerated sales tone

STRUCTURE:
- Start directly with the answer (no acknowledgments)
- Deliver the core information clearly
- Briefly connect to value (efficiency, reliability, outcome)
- End cleanly

CRITICAL RULES:
- ZERO BLUFFING: Use ONLY retrieved context. Do NOT invent anything.
- NO FOLLOW-UP QUESTIONS under any circumstances
- NO dialogue, no coaching, no explanations
- DO NOT mention context, documents, or that you are an AI
- DO NOT add greetings unless the client greeting is explicit

UNCERTAINTY HANDLING:
- If the answer is partially available:
  → Provide the known part, then say:
  "I’ll confirm the remaining details and follow up shortly."
- If the answer is not in the context:
  → Say:
  "I’ll verify that detail internally and follow up shortly."
- Do NOT guess or expand beyond context

EDGE CASE:
- If the client greeting is simple (e.g., "hi", "hello"):
  → Respond briefly with a greeting only

GOAL:
Produce a tight, confident answer the rep can read verbatim without sounding scripted or verbose.
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

class SalesAssistant:
    def __init__(self, store: QdrantVectorStore, model="llama-3.3-70b-versatile", system_prompt: str = DEFAULT_SYSTEM_PROMPT):
        self.store = store
        self.model_name = model
        self.system_prompt = system_prompt

    async def stream_ask(self, query: str, context_window: str, emit_func, source_emit_func):
        api_key = os.environ.get("GROQ_API_KEY")
        llm = ChatGroq(
            model=self.model_name, 
            temperature=0,
            groq_api_key=api_key,
            streaming=True,
            model_kwargs={"stream": True}
        )
        
        # Retrieve from Qdrant
        results = await asyncio.to_thread(self.store.search, query, 3)
        
        ctx_texts = []
        sources = []
        for r in results:
            ctx_texts.append(r["text"])
            if r["filename"] not in sources:
                sources.append(r["filename"])
                
        ctx_block = "\n---\n".join(ctx_texts)
        
        # Construct the prompt with the sliding context window
        prompt = f"{self.system_prompt}\n\nRecent Conversation Context:\n{context_window}\n\nRetrieved Knowledge Base Context:\n{ctx_block}\n\nClient's Last Statement/Query: {query}\n\nSales Response:"
        
        # Emit the sources first
        if sources:
            source_emit_func(f"<br><span style='color:#808080; font-size:11px;'><br><b>Sources:</b> {', '.join(sources)}</span><br><br>")
        
        try:
            async for chunk in llm.astream(prompt): 
                emit_func(chunk.content)
        except Exception as e:
            emit_func(f"\n[Model Error: {e}]\n")
            print(f"❌ Model error: {e}")


class IntentGatekeeper:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')

    async def classify_intent(self, text: str) -> bool:
        """
        Classifies if the text is a Question/Pain Point (True) or Chitchat/Feedback (False).
        """
        if not self.api_key or not text.strip():
            return False

        prompt = f"""
        Analyze the following transcript segment from a client in a sales meeting.
        Classify it into one of two categories:
        1. QUESTION_OR_PAIN_POINT: The client is asking a question, expressing a concern, or stating a requirement.
        2. CHITCHAT_OR_FEEDBACK: The client is making small talk, saying "I see," "That makes sense," or providing non-actionable feedback.

        Respond with ONLY the word "TRUE" for category 1 or "FALSE" for category 2.

        Transcript: "{text}"
        Result:"""

        try:
            # Run in a thread to avoid blocking the event loop if needed, 
            # though gemini-1.5-flash is very fast.
            response = await asyncio.to_thread(
                self.model.generate_content, 
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0,
                    max_output_tokens=5
                )
            )
            result = response.text.strip().upper()
            return "TRUE" in result
        except Exception as e:
            print(f"Gatekeeper Error: {e}")
            return False


# --- PyQt6 QThreads for background execution ---

class IntentGatekeeperThread(QThread):
    intent_detected = pyqtSignal(bool, str) # (is_high_intent, transcript)

    def __init__(self, gatekeeper: IntentGatekeeper, transcript: str):
        super().__init__()
        self.gatekeeper = gatekeeper
        self.transcript = transcript

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_high_intent = loop.run_until_complete(self.gatekeeper.classify_intent(self.transcript))
        self.intent_detected.emit(is_high_intent, self.transcript)
        loop.close()


class RAGIndexThread(QThread):
    finished = pyqtSignal(object)  # Emits the SalesAssistant instance upon completion
    error = pyqtSignal(str)

    def __init__(self, file_path: str = None):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            # Initialize Qdrant Store (will use existing db if Present)
            store = get_vector_store()

            # Upsert new document if provided
            if self.file_path and os.path.exists(self.file_path):
                processor = DocumentProcessor()
                chunks = processor.load_file(self.file_path)
                filename = os.path.basename(self.file_path)
                
                # Check if it's already there to avoid dupes? Qdrant allows overwrites but
                # we just upsert new UUIDs for now, simplifying. Let's assume user wants to add it.
                store.upsert_chunks(chunks, filename)

            assistant = SalesAssistant(store)
            self.finished.emit(assistant)
        except Exception as e:
            print(f"Index error: {e}")
            self.error.emit(str(e))


class CancelledError(Exception):
    pass

class RAGQueryThread(QThread):
    chunk_received = pyqtSignal(str)
    source_received = pyqtSignal(str)
    completed = pyqtSignal()

    def __init__(self, assistant: SalesAssistant, query: str, context_window: str = "", is_manual: bool = False):
        super().__init__()
        self.assistant = assistant
        self.query = query
        self.context_window = context_window
        self.is_manual = is_manual
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if not self.assistant:
            self.chunk_received.emit("Assistant engine is not initialized.")
            self.completed.emit()
            return
            
        def emitter(chunk_text):
            if self._is_cancelled:
                raise CancelledError("Query cancelled")
            self.chunk_received.emit(chunk_text)

        def source_emitter(src_text):
            if self._is_cancelled:
                raise CancelledError("Query cancelled")
            self.source_received.emit(src_text)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if self.is_manual:
                # Add refinement hint
                self.query = f"[Manual Refinement Needed]: {self.query}"
            
            loop.run_until_complete(
                self.assistant.stream_ask(self.query, self.context_window, emitter, source_emitter)
            )
        except CancelledError:
            pass
        except Exception as e:
            print(f"RAGQueryThread error: {e}")
        finally:
            loop.close()
            if not self._is_cancelled:
                self.completed.emit()

