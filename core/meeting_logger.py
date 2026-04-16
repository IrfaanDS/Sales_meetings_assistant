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
        print(f"Logging conversation to {self.log_file}")

    def log_utterance(self, speaker: str, text: str):
        """
        Logs a final utterance to the JSON Lines payload.
        speaker is 'You' or 'Client'.
        """
        if not text.strip():
            return
            
        timestamp = datetime.now().isoformat(timespec='seconds')
        
        # Map frontend speaker display names to generic backend tags requested by user
        channel = "rep" if speaker == "You" else "client"
        
        log_entry = {
            "timestamp": timestamp,
            "channel": channel,
            "text": text.strip()
        }
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"File log error: {e}")
