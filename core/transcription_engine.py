import os
import sys
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
                self.dg_connection.send(audio_data)
            except Exception as e:
                # Socket might not be fully established yet
                pass

    def run(self):
        if not self.api_key:
            print("Error: DEEPGRAM_API_KEY not found in .env")
            return

        try:
            deepgram = DeepgramClient(self.api_key)
            # Establish the Live WebSocket connection
            self.dg_connection = deepgram.listen.live.v("1")

            # Define Event Handlers - Catch 'self' in a closure to avoid shadowing
            engine_self = self
            
            def on_message(dg_client, result, **kwargs):
                if not result.channel or not result.channel.alternatives:
                    return
                transcript = result.channel.alternatives[0].transcript
                if not transcript:
                    return

                # Diarization logic for multi-channel audio
                try:
                    ch_idx = result.channel_index[0] if isinstance(result.channel_index, list) else result.channel_index
                except AttributeError:
                    try:
                        result_dict = result.to_dict()
                        ch_idx = result_dict.get("channel_index", [0])[0]
                    except:
                        ch_idx = 0
                
                # Use speech_final (if available) for better debouncing, fallback to is_final
                speech_final = getattr(result, "speech_final", False)
                is_final_attr = getattr(result, "is_final", False)
                
                # We emit both as our 'is_final' flag if it's truly the end of a thought
                # Since we configured utterance_end_ms, speech_final is the more reliable marker.
                true_final = speech_final or is_final_attr
                
                speaker_name = "You" if ch_idx == 0 else "Client"

                # Use the engine_self closure to reach the QThread signal
                engine_self.new_transcript.emit(speaker_name, transcript, bool(true_final))

            def safe_print(msg):
                try:
                    if sys.stdout is not None:
                        print(msg)
                except:
                    pass

            def on_error(dg_client, error, **kwargs):
                safe_print(f"Deepgram WebSocket Error: {error}")

            def on_close(dg_client, close, **kwargs):
                safe_print(f"Deepgram Connection Closed: {close}")

            # Bind events
            self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)
            self.dg_connection.on(LiveTranscriptionEvents.Close, on_close)

            # Deepgram options configured for dual-stream, low latency meeting settings
            options = LiveOptions(
                model="nova-2-meeting",
                language="en-US",
                multichannel=True, # Critical setting for Dual-Stream!
                channels=2,
                encoding="linear16", 
                sample_rate=44100, 
                interim_results=True,     # Stream word-by-word
                endpointing=100,          # Reduced from 200 to 100ms for even faster "Final" tags
                smart_format=True,
                utterance_end_ms=1000,    # Helps finalize silent blocks
                vad_events=True
            )

            # Connect
            if self.dg_connection.start(options) is False:
                print("Failed to start Deepgram connection")
                return

            print("Deepgram WebSocket Live Connection Established.")
            
            # Start the QThread event loop. This is critical for latency!
            # Using exec() instead of a while True loop allows this thread to 
            # process the 'feed_audio' signals as soon as they are emitted from the audio thread.
            self.exec()

            # Cleanup
            self.dg_connection.finish()

        except Exception as e:
            print(f"Transcription Engine Error: {e}")

    def stop(self):
        self._running = False
        self.quit() # Signals the exec() loop to exit
        self.wait(500)

