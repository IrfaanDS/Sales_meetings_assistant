import os
import time
import asyncio
import logging
import google.generativeai as genai
from typing import List, Dict, Optional
from pypdf import PdfReader
from langchain_groq import ChatGroq
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from dotenv import load_dotenv

from core.vector_store import QdrantVectorStore, get_vector_store
load_dotenv()

# Configure LLM default system prompt
DEFAULT_SYSTEM_PROMPT = """
# ROLE
You are an elite, high-energy Sales Engineer at an innovative tech startup. Your goal is to provide a confident, persuasive, and technically precise "response script" that the sales representative can read aloud to the client in real-time.

# CONTEXT PREVIEW
- **Live Transcript**: Speech from the client (often messy or accented).
- **Retrieved Context**: Snippets from the project’s knowledge base.

# OPERATIONAL INSTRUCTIONS
1. **Identify Intent**: Detect the client's core question, pain point, or technical concern.
2. **Script Generation**: Write a descriptive, comprehensive, and highly sales-oriented response. 
3. **Drafting Style**: Conversational, authoritative, and embodying a fast-paced, problem-solving startup tone.
4. **Length**: 80-100 words.

# OUTPUT STRUCTURE (MANDATORY)
Structure your response script for maximum readability and impact:
- **Direct Opening**: Address the concern immediately with a high-energy, confident statement.
- **Detailed Solution**: Provide a thorough, elaborate explanation based on the context. Use clear small paragraphs for different points and keep it structured.
- **Logical Flow**: Use transition words (e.g., "Essentially," "What this enables is," "From a technical standpoint") to keep the explanation fluid.
- **Confidence Closer**: End with a strong statement of value or professional reassurance.

# THE GOLDEN RULES (CRITICAL)
- **ZERO BLUFFING**: Base your response EXCLUSIVELY on the provided context. Do NOT invent features, metrics, or answers.
- **NO FOLLOW-UP QUESTIONS**: Your output is the detailed ANSWER. Never ask the client a question back.
- **BE INVISIBLE**: Start directly with the response. Do NOT say "Here is a script" or "Based on the documents."
- **NO DIALOGUE**: Do not talk to the sales rep; only provide the read-aloud script.
- **UNCERTAINTY PROTOCOL**: If context is insufficient, say: "I want to make sure I give you the exact technical details on that. Let me look into our internal documentation and follow up with you on that remaining point shortly."
- **GREETING HANDLING**: If the client says "hi" or "hello", respond with a simple "Hi" or "Hello" only.
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
    def __init__(self, store: QdrantVectorStore, model="llama-3.3-70b-versatile", system_prompt: str = DEFAULT_SYSTEM_PROMPT, selected_docs: List[str] = None):
        self.store = store
        self.model_name = model
        self.system_prompt = system_prompt
        self.selected_docs = selected_docs

    async def stream_ask(self, query: str, context_window: str, emit_func, source_emit_func):
        api_key = os.environ.get("GROQ_API_KEY")
        llm = ChatGroq(
            model=self.model_name, 
            temperature=0,
            groq_api_key=api_key,
            streaming=True,
            model_kwargs={"stream": True}
        )
        
        # Retrieve from Qdrant with filtering
        results = await asyncio.to_thread(self.store.search, query, 3, self.selected_docs)
        
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
            await asyncio.wait_for(
                self._do_stream(llm, prompt, emit_func),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            emit_func("\n[Response timed out after 30s]\n")
            logging.error("stream_ask timed out after 30 seconds.")
        except Exception as e:
            emit_func(f"\n[Model Error: {e}]\n")
            logging.error(f"Model error: {e}", exc_info=True)

    async def _do_stream(self, llm, prompt, emit_func):
        """Helper for stream_ask so asyncio.wait_for can wrap it."""
        async for chunk in llm.astream(prompt):
            emit_func(chunk.content)


class IntentGatekeeper:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')

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
            logging.error(f"Gatekeeper Error: {e}")
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
            logging.error(f"Index error: {e}", exc_info=True)
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
            logging.error(f"RAGQueryThread error: {e}", exc_info=True)
        finally:
            loop.close()
            if not self._is_cancelled:
                self.completed.emit()

