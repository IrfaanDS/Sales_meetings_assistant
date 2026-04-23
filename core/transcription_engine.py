import os
import sys
import time
import logging
from dotenv import load_dotenv
from PyQt6.QtCore import QThread, pyqtSignal

from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions
)

load_dotenv()

MAX_RETRIES = 5

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
            logging.error("DEEPGRAM_API_KEY not found in .env")
            return

        for attempt in range(MAX_RETRIES):
            if not self._running:
                break
            try:
                logging.info(f"Deepgram connection attempt {attempt + 1}/{MAX_RETRIES}")
                self._connect()
                break  # Clean exit from _connect (i.e. exec() returned), don't retry
            except Exception as e:
                if not self._running:
                    break
                wait = 2 ** attempt
                logging.error(f"Deepgram attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
        else:
            logging.critical("Deepgram failed after all retries. Transcription unavailable.")

    def _connect(self):
        """Establish the Deepgram WebSocket connection and run the event loop."""
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

        def on_error(dg_client, error, **kwargs):
            # Only log errors if we are still supposed to be running
            if engine_self._running:
                logging.error(f"[Deepgram] WebSocket Error: {error}")

        def on_close(dg_client, close, **kwargs):
            logging.info(f"[Deepgram] Connection Closed: {close}")

        self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        self.dg_connection.on(LiveTranscriptionEvents.Close, on_close)

        options = LiveOptions(
            model="nova-3",
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
            raise ConnectionError("Failed to start Deepgram connection.")

        logging.info("Deepgram WebSocket Live Connection Established.")

        # Use QThread's event loop to handle signals
        self.exec()

        # Cleanup
        self.dg_connection.finish()
        self.dg_connection = None

    def stop(self):
        self._running = False
        self.quit() # Signals the exec() loop to exit
        self.wait(500)
