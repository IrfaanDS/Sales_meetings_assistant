import os
import asyncio
import logging
import google.generativeai as genai
from typing import List, Optional, Callable, Dict, Any
from pypdf import PdfReader
from langchain_groq import ChatGroq
from PyQt6.QtCore import QThread, pyqtSignal
from core.utils import load_env_file

from core.vector_store import QdrantVectorStore, get_vector_store

load_env_file()

# ---------------------------------------------------------------------------
# ARIA — Real-Time Sales Copilot System Prompt
# ---------------------------------------------------------------------------
DEFAULT_SYSTEM_PROMPT = """
# IDENTITY
You are ARIA -- a real-time Sales Copilot embedded invisibly in a live client meeting.
You generate a word-for-word speaking script for the Host (a senior product delivery manager) to narrate aloud to the client. You are their silent expert partner.

You are NOT a chatbot. You are NOT an assistant. You produce nothing except the narration-ready script.

---

# HOST PERSONA (Embody this voice always)
The Host speaks as a confident, composed senior delivery manager at an innovative tech company:
- Authoritative but human -- never robotic, never salesy
- Technically fluent, always translating specs into business outcomes
- Consultative: guides the client toward clarity, doesn't push
- Fast-moving but unhurried -- startup pace, enterprise polish

NEVER produce:
- Filler affirmations ("Absolutely!", "Great question!", "Of course!")
- Passive or hedging language ("might", "could potentially", "we believe")
- Brochure-speak or buzzword stacking
- Anything that sounds like a chatbot wrote it

---

# INPUTS YOU RECEIVE
- [HOST PROFILE]: Background on the Host (CV, experience, past projects). Use this ONLY to emulate their tone and "get in their skin". NEVER explain or summarize their past projects, background, or resume to the client unless explicitly answering a question about the Host's qualifications. You ARE the Host. Speak in the first person ("I", "we").
- [INTENT]: The classified intent category of the client's statement (Note: Manual queries may misclassify intent, so use your best judgment based on the context).
- [TRANSCRIPT]: Recent client-side dialogue.
- [CONTEXT]: PRIMARY SOURCE. Technical and product documentation. This is where the actual answers live.

---

# INTENT-BASED TONE CALIBRATION
Adapt delivery based on [INTENT] and the client's actual statement:

TECHNICAL          -> Lead with one precise term, immediately translate to business impact. Be explanatory but concise.
PRICING / BUDGET   -> Reframe as investment + ROI. Never apologize for cost. Anchor to risk reduced.
TIMELINE / DELIVERY-> Be specific, process-confident. Acknowledge constraint, then show the plan.
OBJECTION / CONCERN-> Validate in one sentence, pivot to evidence or precedent.
COMPETITION        -> Never attack. Redirect: "What we focus on is..." then differentiate.
RELATIONSHIP/TRUST -> Slow down. Be human. Less data, more empathy.
GREETING / CHITCHAT-> Be brief and conversational. e.g. "Hi, great to connect." Do NOT over-explain.

---

# OUTPUT FORMAT (MANDATORY -- render exactly as shown)
[The narration-ready script. First-person plural ("we", "our team") or singular ("I") as appropriate.
Conversational but authoritative. No bullet points. No headers. No emojis.
Flows naturally when read aloud. Keep it concise. Adapt length to the complexity of the query: short for greetings, detailed for technical questions.]

---

# THE GOLDEN RULES

1. PRIMARY CONTEXT -- Your primary focus is [CONTEXT]. Every technical claim, feature, and process detail must come from [CONTEXT]. [HOST PROFILE] is purely for stylistic grounding.
2. ZERO BLUFFING -- If [CONTEXT] is empty or insufficient, use the Knowledge Gap Protocol below.
3. BE INVISIBLE -- Begin output directly with the narration script. Never say "Here is a script" or address the Host.
4. SCRIPT ONLY -- Your output IS the client-facing narration. Nothing else.
5. NO PROFILE CONFUSION -- Never present Host background as a product feature. Never talk about the Host in the third person. Never randomly recite the Host's resume.
6. NO FABRICATION -- Never invent features, timelines, metrics, or case studies not present in [CONTEXT].

---

# KNOWLEDGE GAP PROTOCOL
If [CONTEXT] is empty, irrelevant, or insufficient to answer accurately,
replace the script with this narration:

"That's a precise question and it deserves a precise answer. I want to make sure I'm pulling from the exact technical documentation on that -- let me follow up with you before end of day so you have the full picture."

Do NOT speculate.
"""

# ---------------------------------------------------------------------------
# Document Processor
# ---------------------------------------------------------------------------
class DocumentProcessor:
    """Loads and chunks documents for ingestion into the vector store."""

    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_directory(self, path: str) -> List[str]:
        chunks = []
        if not os.path.exists(path):
            return chunks
        for fname in os.listdir(path):
            fpath = os.path.join(path, fname)
            chunks.extend(self.load_file(fpath))
        return chunks

    def load_file(self, fpath: str) -> List[str]:
        if not os.path.exists(fpath):
            return []
        if fpath.endswith(".pdf"):
            return self.chunk_text(self._load_pdf(fpath))
        if fpath.endswith(".txt"):
            try:
                return self.chunk_text(open(fpath, encoding="utf-8").read())
            except Exception as e:
                logging.error(f"Failed to read {fpath}: {e}")
                return []
        return []

    def _load_pdf(self, path: str) -> str:
        try:
            return "\n".join(
                page.extract_text() or "" for page in PdfReader(path).pages
            )
        except Exception as e:
            logging.error(f"PDF read error for {path}: {e}")
            return ""

    def chunk_text(self, text: str) -> List[str]:
        """Splits text into overlapping chunks with soft boundary detection."""
        chunks, start = [], 0
        while start < len(text):
            end = start + self.chunk_size
            if end < len(text):
                # Prefer breaking on newlines, fall back to whitespace
                break_idx = text.rfind("\n", start, end)
                if break_idx == -1 or break_idx < start + 200:
                    break_idx = text.rfind(" ", start, end)
                if break_idx != -1:
                    end = break_idx
            chunk = text[start:end].strip()
            if len(chunk) > 30:
                chunks.append(chunk)
            start = end - self.chunk_overlap
            if start >= end:
                start = end + 1
        return chunks


# ---------------------------------------------------------------------------
# ARIA Sales Assistant (RAG Core)
# ---------------------------------------------------------------------------
class SalesAssistant:
    """
    Core RAG engine. Retrieves context from Qdrant, then streams a
    narration-ready script via the ARIA system prompt.
    """

    def __init__(
        self,
        store: QdrantVectorStore,
        model: str = "llama-3.3-70b-versatile",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        selected_docs: Optional[List[str]] = None,
        top_k: int = 3,
    ):
        self.store = store
        self.model_name = model
        self.system_prompt = system_prompt
        self.selected_docs = selected_docs
        self.top_k = top_k

    def _build_prompt(
        self,
        query: str,
        context_window: str,
        ctx_block: str,
        profile_block: str,
        intent_label: str,
        is_manual: bool,
    ) -> str:
        """
        Assembles the full prompt injected into the LLM.
        Separates ARIA's static identity from runtime inputs.
        """
        manual_hint = (
            "\n⚠️  [Manual Override — Host has flagged this for a more refined response]\n"
            if is_manual
            else ""
        )
        return (
            f"{self.system_prompt}"
            f"{manual_hint}"
            f"\n\n---\n"
            f"[HOST PROFILE]:\n{profile_block}\n\n"
            f"[INTENT]: {intent_label}\n\n"
            f"[TRANSCRIPT]:\n{context_window}\n\n"
            f"[CONTEXT]:\n{ctx_block}\n\n"
            f"Client's Last Statement: {query}\n"
        )

    async def stream_ask(
        self,
        query: str,
        context_window: str,
        emit_func: Callable[[str], None],
        source_emit_func: Callable[[str], None],
        intent_label: str = "TECHNICAL",
        is_manual: bool = False,
    ) -> None:
        """
        Retrieves context from Qdrant and streams the ARIA response token by token.
        """
        llm = ChatGroq(
            model=self.model_name,
            temperature=0,
            groq_api_key=os.environ.get("GROQ_API_KEY"),
            streaming=True,
        )

        # --- RAG Retrieval ---
        # 1. Product Knowledge (from selected docs)
        product_results = []
        if self.selected_docs:
            product_results = await asyncio.to_thread(
                self.store.search, query, self.top_k, self.selected_docs,
                filter_metadata={"source_type": "product"}
            )

        # 2. Host Profile Knowledge (global for the host)
        profile_results = await asyncio.to_thread(
            self.store.search, query, 1,
            filter_metadata={"source_type": "host_profile"}
        )

        ctx_texts, sources = [], []
        for r in product_results:
            ctx_texts.append(r["text"])
            if r["filename"] not in sources:
                sources.append(r["filename"])

        ctx_block = "\n---\n".join(ctx_texts) if ctx_texts else ""
        
        profile_texts = [r["text"] for r in profile_results]
        profile_block = "\n---\n".join(profile_texts) if profile_texts else "No host profile provided."

        # Emit sources to the UI before streaming the script
        if sources:
            source_emit_func(
                f"<br><span style='color:#808080; font-size:11px;'>"
                f"<b>Sources:</b> {', '.join(sources)}</span><br><br>"
            )

        prompt = self._build_prompt(
            query, context_window, ctx_block, profile_block, intent_label, is_manual
        )

        try:
            await asyncio.wait_for(
                self._stream_response(llm, prompt, emit_func),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            emit_func("\n[Response timed out — please retry]\n")
            logging.error("stream_ask timed out after 30 seconds.")
        except Exception as e:
            emit_func(f"\n[Model error: {e}]\n")
            logging.error(f"Model error in stream_ask: {e}", exc_info=True)

    async def _stream_response(
        self, llm: ChatGroq, prompt: str, emit_func: Callable[[str], None]
    ) -> None:
        async for chunk in llm.astream(prompt):
            emit_func(chunk.content)


# ---------------------------------------------------------------------------
# Intent Gatekeeper — Binary Classifier (Original Logic)
# ---------------------------------------------------------------------------
class IntentGatekeeper:
    """
    Classifies if the text is a Question/Pain Point (True) or Chitchat/Feedback (False).
    """

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self._model = None
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            logging.warning("GOOGLE_API_KEY not set — IntentGatekeeper disabled.")

    async def classify_intent(self, text: str) -> bool:
        """
        Returns True for high-intent questions/concerns, False for chitchat.
        """
        if not self._model or not text.strip():
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
            response = await asyncio.to_thread(
                self._model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0,
                    max_output_tokens=5,
                ),
            )
            result = response.text.strip().upper()
            return "TRUE" in result

        except Exception as e:
            logging.error(f"IntentGatekeeper error: {e}")
            return False


# ---------------------------------------------------------------------------
# PyQt6 Worker Threads
# ---------------------------------------------------------------------------

class CancelledError(Exception):
    """Raised inside emit callbacks to abort an in-progress stream."""


class IntentGatekeeperThread(QThread):
    """
    Runs binary intent classification off the main thread.
    Emits (is_high_intent, original_transcript).
    """
    intent_detected = pyqtSignal(bool, str)

    def __init__(self, gatekeeper: IntentGatekeeper, transcript: str):
        super().__init__()
        self.gatekeeper = gatekeeper
        self.transcript = transcript

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            is_high_intent = loop.run_until_complete(
                self.gatekeeper.classify_intent(self.transcript)
            )
            self.intent_detected.emit(is_high_intent, self.transcript)
        finally:
            loop.close()


class RAGIndexThread(QThread):
    """
    Indexes a new document into Qdrant on a background thread.
    Emits the initialised SalesAssistant on success.
    """
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, file_path: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.file_path = file_path
        self.metadata = metadata or {"source_type": "product"}

    def run(self):
        try:
            store = get_vector_store()

            if self.file_path and os.path.exists(self.file_path):
                processor = DocumentProcessor()
                chunks = processor.load_file(self.file_path)
                filename = os.path.basename(self.file_path)
                store.upsert_chunks(chunks, filename, metadata=self.metadata)
                logging.info(f"Indexed {len(chunks)} chunks from '{filename}' as {self.metadata.get('source_type')}.")

            assistant = SalesAssistant(store)
            self.finished.emit(assistant)

        except Exception as e:
            logging.error(f"RAGIndexThread error: {e}", exc_info=True)
            self.error.emit(str(e))


class RAGQueryThread(QThread):
    """
    Runs a full RAG query + ARIA script generation on a background thread.
    Streams tokens back to the UI via Qt signals.
    """
    chunk_received = pyqtSignal(str)
    source_received = pyqtSignal(str)
    completed = pyqtSignal()

    def __init__(
        self,
        assistant: SalesAssistant,
        query: str,
        context_window: str = "",
        intent_label: str = "TECHNICAL",
        is_manual: bool = False,
    ):
        super().__init__()
        self.assistant = assistant
        self.query = query
        self.context_window = context_window
        self.intent_label = intent_label
        self.is_manual = is_manual
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _emit(self, text: str) -> None:
        if self._cancelled:
            raise CancelledError()
        self.chunk_received.emit(text)

    def _emit_source(self, text: str) -> None:
        if self._cancelled:
            raise CancelledError()
        self.source_received.emit(text)

    def run(self):
        if not self.assistant:
            self.chunk_received.emit("⚠️ Assistant engine is not initialised.")
            self.completed.emit()
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.assistant.stream_ask(
                    query=self.query,
                    context_window=self.context_window,
                    emit_func=self._emit,
                    source_emit_func=self._emit_source,
                    intent_label=self.intent_label,
                    is_manual=self.is_manual,
                )
            )
        except CancelledError:
            logging.info("RAGQueryThread: stream cancelled by user.")
        except Exception as e:
            logging.error(f"RAGQueryThread error: {e}", exc_info=True)
        finally:
            loop.close()
            if not self._cancelled:
                self.completed.emit()
