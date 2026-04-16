import pyaudiowpatch as pyaudio
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

class DualAudioCaptureThread(QThread):
    """
    Captures audio from both the Sales Rep (Microphone) and the Client (WASAPI Loopback).
    Merges them into a single stereo stream where:
    - Left Channel = Sales Rep
    - Right Channel = Client
    """
    # Emits (sales_rep_rms, client_rms) to update UI safely
    audio_levels = pyqtSignal(float, float)
    
    # Broadcasts the raw batched stereo bytes for shipping to Deepgram
    audio_data = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        p = pyaudio.PyAudio()

        # 1. Get Client Device (Default WASAPI Loopback)
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            print("WASAPI not found. Ensure you are on Windows.")
            return

        wasapi_index = wasapi_info["index"]
        loopback_device = None

        for i in range(p.get_device_count()):
            dev_info = p.get_device_info_by_index(i)
            if dev_info["hostApi"] == wasapi_index:
                if dev_info.get("isLoopbackDevice", False) or "loopback" in dev_info["name"].lower():
                    loopback_device = dev_info
                    break

        if not loopback_device:
            print("WASAPI Loopback not found. Ensure speakers are enabled.")
            p.terminate()
            return

        # 2. Get Sales Rep Device (Default Microphone)
        try:
            mic_device = p.get_default_input_device_info()
        except IOError:
            print("No default microphone found.")
            p.terminate()
            return

        # Device metrics (Use Loopback sample rate as authority to avoid desyncs)
        RATE = int(loopback_device["defaultSampleRate"])
        CHUNK = 1024
        FORMAT = pyaudio.paInt16

        loop_channels = int(loopback_device.get("maxInputChannels", 2))
        if loop_channels == 0:
            loop_channels = int(loopback_device.get("maxOutputChannels", 2))
            
        mic_channels = int(mic_device.get("maxInputChannels", 1))

        # Open System Audio Stream
        try:
            loop_stream = p.open(
                format=FORMAT,
                channels=loop_channels,
                rate=RATE,
                input=True,
                input_device_index=loopback_device["index"],
                frames_per_buffer=CHUNK
            )
        except OSError as e:
            print(f"Failed to open loopback stream: {e}")
            p.terminate()
            return

        # Open Mic Stream
        try:
            mic_stream = p.open(
                format=FORMAT,
                channels=mic_channels,
                rate=RATE,
                input=True,
                input_device_index=mic_device["index"],
                frames_per_buffer=CHUNK
            )
        except OSError as e:
            print(f"Failed to open mic stream: {e}")
            loop_stream.close()
            p.terminate()
            return

        print("Capturing both Mic (Sales Rep) and System Audio (Client)...")
        MAX_RMS_SCALE = 10000

        while self._running:
            try:
                # 3. Read their data independently to prevent blocking on system silence
                # Mic always produces frames (even silent ones), so we pace the loop with it
                rep_raw = mic_stream.read(CHUNK, exception_on_overflow=False)
                
                # WASAPI loopback stops sending frames during total silence.
                # Check if frames are available before reading to prevent deadlocks.
                loop_avail = loop_stream.get_read_available()
                if loop_avail >= CHUNK:
                    client_raw = loop_stream.read(CHUNK, exception_on_overflow=False)
                else:
                    # Provide empty byte array of zeros matching the expected chunk size
                    client_raw = b'\x00' * (CHUNK * loop_channels * 2) # 2 bytes per int16 sample
                
                # 4. Process Client Data (Loopback)
                client_array = np.frombuffer(client_raw, dtype=np.int16)
                if loop_channels > 1:
                    # Mixdown to Mono: average the channels
                    client_array = client_array.reshape(-1, loop_channels)
                    client_mono = client_array.mean(axis=1).astype(np.int16)
                else:
                    client_mono = client_array

                # 5. Process Rep Data (Microphone)
                rep_array = np.frombuffer(rep_raw, dtype=np.int16)
                if mic_channels > 1:
                    rep_array = rep_array.reshape(-1, mic_channels)
                    rep_mono = rep_array.mean(axis=1).astype(np.int16)
                else:
                    rep_mono = rep_array

                # 6. "Merge" them into a single stereo signal 
                # Left (0) = Sales Rep (Mic)
                # Right (1) = Client (System Loopback)
                stereo_interleaved = np.column_stack((rep_mono, client_mono)).astype(np.int16)
                stereo_bytes = stereo_interleaved.tobytes()

                # Broadcast stereo chunks out to be consumed elsewhere (i.e. deeply coupled transcription sockets)
                self.audio_data.emit(stereo_bytes)

                # Calculate volume levels for the UI (RMS)
                client_rms = float(np.sqrt(np.mean(np.square(client_mono.astype(np.float32))))) if len(client_mono) > 0 else 0.0
                rep_rms = float(np.sqrt(np.mean(np.square(rep_mono.astype(np.float32))))) if len(rep_mono) > 0 else 0.0

                self.audio_levels.emit(rep_rms, client_rms)

            except Exception as e:
                # print(f"Audio read error: {e}")
                pass

        if loop_stream.is_active():
            loop_stream.stop_stream()
            loop_stream.close()
            
        if mic_stream.is_active():
            mic_stream.stop_stream()
            mic_stream.close()
            
        p.terminate()

    def stop(self):
        """Cleanly signals the loop to stop and waits up to 200ms."""
        self._running = False
        self.wait(200)
