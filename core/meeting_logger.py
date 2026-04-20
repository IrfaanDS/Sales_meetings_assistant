import os
import json
from datetime import datetime

class MeetingLogger:
    def __init__(self):
        # Ensure the logs directory exists
        self.logs_dir = os.path.join(os.getcwd(), "logs")
        self.transcripts_dir = os.path.join(os.getcwd(), "transcripts")
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.transcripts_dir, exist_ok=True)
        
        # Create a unique file for this session based on start time
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = os.path.join(self.logs_dir, f"meeting_{self.timestamp}.jsonl")
        
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
            print(f"File log error: {e}")

        # Reset buffer
        self.aggregated_text = []
        self.current_speaker = None
        self.current_timestamp = None

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
            print(f"File log error (RAG): {e}")

    def save_clean_transcript(self) -> str:
        """
        Saves the current history as a clean text file in the transcripts directory.
        Returns the path to the saved file.
        """
        self.flush() # Ensure everything is written to disk
        transcript = self.get_clean_transcript()
        if not transcript:
            return ""
            
        filename = f"transcript_{self.timestamp}.txt"
        file_path = os.path.join(self.transcripts_dir, filename)
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Meeting Transcript - {self.timestamp}\n")
                f.write("="*40 + "\n\n")
                f.write(transcript)
            return file_path
        except Exception as e:
            print(f"Error saving clean transcript: {e}")
            return ""

