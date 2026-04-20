import os
import json
from datetime import datetime

class MeetingLogger:
    def __init__(self):
        # Ensure the logs directory exists
        self.logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Create a unique file for this session based on start time
        start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = os.path.join(self.logs_dir, f"meeting_{start_time}.jsonl")
        
        # Aggregation state
        self.current_speaker = None
        self.aggregated_text = []
        self.current_timestamp = None
        self.history = [] # In-memory history for RAG context
        
        print(f"Logging conversation to {self.log_file}")

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
        """Returns a nicely formatted string of the conversation."""
        lines = []
        for entry in self.history:
            speaker = entry.get("speaker", "Unknown")
            text = entry.get("text", "")
            # Filter for just the sales rep and client
            if speaker in ["You", "Client"]:
                # Clarify the labels
                display_speaker = "Sales Rep" if speaker == "You" else "Client"
                lines.append(f"{display_speaker}:\n{text}\n")
        return "\n".join(lines)

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
            print(f"File log error: {e}")

        # Reset buffer
        self.aggregated_text = []
        self.current_speaker = None
        self.current_timestamp = None

    def log_rag_interaction(self, question: str, answer: str):
        """Logs an AI Q&A interaction."""
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
            print(f"File log error (RAG): {e}")

