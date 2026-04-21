import os
import sys
import time
from dotenv import load_dotenv
from PyQt6.QtCore import QThread, pyqtSignal

from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions
)

load_dotenv()

class TranscriptionEngine(QThread):
    # Emits (speaker_name, text, is_final)
    new_transcript = pyqtSignal(str, str, bool)

    def __init__(self):
        super().__init__()
        self._running = True
        self.dg_connection = None
        self.api_key = os.getenv("DEEPGRAM_API_KEY")

    def feed_audio(self, audio_data: bytes):
        """Pass the byte stream straight to Deepgram via the open websocket."""
        if self.dg_connection and self._running:
            try:
                # Use the internal send directly
                self.dg_connection.send(audio_data)
            except Exception:
                # We expect some failures during connection transitions, 
                # we suppress them to avoid console noise.
                pass

    def run(self):
        if not self.api_key:
            print("Error: DEEPGRAM_API_KEY not found in .env")
            return

        while self._running:
            try:
                deepgram = DeepgramClient(self.api_key)
                # Establish the Live WebSocket connection
                self.dg_connection = deepgram.listen.live.v("1")

                engine_self = self
                
                def on_message(dg_client, result, **kwargs):
                    if not result.channel or not result.channel.alternatives:
                        return
                    transcript = result.channel.alternatives[0].transcript
                    if not transcript:
                        return

                    try:
                        ch_idx = result.channel_index[0] if isinstance(result.channel_index, list) else result.channel_index
                    except:
                        ch_idx = 0
                    
                    speech_final = getattr(result, "speech_final", False)
                    is_final_attr = getattr(result, "is_final", False)
                    true_final = speech_final or is_final_attr
                    
                    speaker_name = "You" if ch_idx == 0 else "Client"
                    engine_self.new_transcript.emit(speaker_name, transcript, bool(true_final))

                def safe_print(msg):
                    try:
                        if sys.stdout is not None:
                            print(f"[Deepgram] {msg}")
                    except: pass

                def on_error(dg_client, error, **kwargs):
                    # Only log errors if we are still supposed to be running
                    if engine_self._running:
                        safe_print(f"WebSocket Error: {error}")

                def on_close(dg_client, close, **kwargs):
                    safe_print(f"Connection Closed: {close}")

                self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
                self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)
                self.dg_connection.on(LiveTranscriptionEvents.Close, on_close)

                options = LiveOptions(
                    model="nova-2-meeting",
                    language="en-US",
                    multichannel=True,
                    channels=2,
                    encoding="linear16", 
                    sample_rate=44100, 
                    interim_results=True,
                    endpointing=100,
                    smart_format=True,
                    utterance_end_ms=1000,
                    vad_events=True
                )

                if self.dg_connection.start(options) is False:
                    print("Failed to start Deepgram connection. Retrying...")
                    time.sleep(2)
                    continue

                print("Deepgram WebSocket Live Connection Established.")
                
                # Use QThread's event loop to handle signals
                self.exec()

                # Cleanup
                self.dg_connection.finish()
                self.dg_connection = None

            except Exception as e:
                if self._running:
                    print(f"Transcription Engine Error: {e}. Reconnecting in 3s...")
                    time.sleep(3)
                else:
                    break

    def stop(self):
        self._running = False
        self.quit() # Signals the exec() loop to exit
        self.wait(500)
