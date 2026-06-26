import os
import json
import logging
from pathlib import Path
from core.utils import get_app_data_dir
from datetime import datetime

def _get_app_data_dir():
    """Return the persistent AppData directory for the application."""
    return get_app_data_dir()

class MeetingLogger:
    def __init__(self):
        # Use AppData directory — never os.getcwd()
        app_data = _get_app_data_dir()
        self.sessions_dir = str(app_data / "sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)
        
        # Create a unique directory for this session based on start time
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_dir = os.path.join(self.sessions_dir, f"Session_{self.timestamp}")
        os.makedirs(self.session_dir, exist_ok=True)
        
        self.log_file = os.path.join(self.session_dir, "meeting_events.jsonl")
        
        # Aggregation state
        self.current_speaker = None
        self.aggregated_text = []
        self.current_timestamp = None
        self.history = [] # In-memory history for RAG context
        
        logging.info(f"Logging conversation to {self.log_file}")

    def log_utterance(self, speaker: str, text: str):
        """
        Logs a final utterance. If the speaker is the same, it aggregates.
        """
        if not text.strip():
            return

        # If speaker changed, flush the previous block
        if self.current_speaker is not None and self.current_speaker != speaker:
            self.flush()

        # Start new block if needed
        if self.current_speaker is None:
            self.current_speaker = speaker
            self.current_timestamp = datetime.now().isoformat(timespec='seconds')

        self.aggregated_text.append(text.strip())
        # Also add to in-memory history for context retrieval
        self.history.append({"speaker": speaker, "text": text.strip(), "timestamp": datetime.now().isoformat()})

    def get_history(self):
        return self.history

    def get_clean_transcript(self, include_ai=False):
        """Returns a nicely formatted string of the conversation with grouped speakers."""
        if not self.history:
            return ""
            
        grouped_lines = []
        last_speaker = None
        current_block = []
        
        for entry in self.history:
            speaker = entry.get("speaker", "Unknown")
            text = entry.get("text", "").strip()
            
            if not text:
                continue
                
            # Filter for just the sales rep and client (and AI if requested)
            valid_speakers = ["You", "Client"]
            if include_ai:
                valid_speakers.append("AI Assistant")
                
            if speaker not in valid_speakers:
                continue
            
            display_speaker = "Sales Rep" if speaker == "You" else speaker
            
            if last_speaker == display_speaker:
                # Same speaker, same paragraph (add with a space)
                current_block.append(text)
            else:
                # Speaker changed, flush previous block
                if current_block:
                    grouped_lines.append(f"{last_speaker}:\n{' '.join(current_block)}\n")
                
                last_speaker = display_speaker
                current_block = [text]
                
        # Add the final block if it exists
        if current_block:
            grouped_lines.append(f"{last_speaker}:\n{' '.join(current_block)}\n")
            
        return "\n".join(grouped_lines)

    def get_recent_context_window(self, n=4) -> str:
        """Returns the last N utterances as a formatted string for LLM context."""
        recent = self.history[-n:]
        lines = []
        for entry in recent:
            if entry.get("speaker") in ["You", "Client"]:
                lines.append(f"{entry.get('speaker')}: {entry.get('text')}")
        return "\n".join(lines)

    def flush(self):
        """Writes the current buffered block to the file."""
        if not self.aggregated_text:
            return

        channel = "rep" if self.current_speaker == "You" else "client"
        full_text = " ".join(self.aggregated_text)

        log_entry = {
            "timestamp": self.current_timestamp,
            "channel": channel,
            "text": full_text
        }
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logging.error(f"File log error: {e}")

        # Reset buffer
        self.aggregated_text = []
        self.current_speaker = None
        self.current_timestamp = None

    def flush_if_stale(self, max_age_seconds: int = 30):
        """Safety flush: write the buffer if it's older than max_age_seconds to prevent data loss on crash."""
        if not self.current_timestamp or not self.aggregated_text:
            return
        try:
            ts = datetime.fromisoformat(self.current_timestamp)
            age = (datetime.now() - ts).total_seconds()
            if age >= max_age_seconds:
                logging.info("Safety flush triggered (stale buffer).")
                self.flush()
        except Exception as e:
            logging.error(f"flush_if_stale error: {e}")

    def log_rag_interaction(self, question: str, answer: str):
        """Logs an AI Q&A interaction."""
        # Add to history for transcript inclusion
        self.history.append({
            "speaker": "AI Assistant", 
            "text": f"Q: {question}\nA: {answer}", 
            "timestamp": datetime.now().isoformat()
        })
        
        log_entry = {
            "timestamp": datetime.now().isoformat(timespec='seconds'),
            "channel": "ai_assistant",
            "question": question,
            "answer": answer
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logging.error(f"File log error (RAG): {e}")

    def save_clean_transcript(self) -> str:
        """
        Saves the current history as a clean text file in the transcripts directory.
        Returns the path to the saved file.
        """
        self.flush() # Ensure everything is written to disk
        transcript = self.get_clean_transcript()
        if not transcript:
            return ""
            
        file_path = os.path.join(self.session_dir, "transcript.txt")
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(transcript)
            return file_path
        except Exception as e:
            logging.error(f"Error saving clean transcript: {e}")
            return ""

    def get_session_dir(self) -> str:
        return self.session_dir
