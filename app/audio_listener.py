import pyaudiowpatch as pyaudio
import struct
import math
from PyQt6.QtCore import QThread, pyqtSignal

class AudioListenerThread(QThread):
    # Emits the raw RMS value and a scaled level for the UI
    audio_level = pyqtSignal(float, int)
    
    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        p = pyaudio.PyAudio()

        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
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
            p.terminate()
            return

        FORMAT = pyaudio.paInt16
        CHANNELS = int(loopback_device.get("maxInputChannels", 0))
        if CHANNELS == 0:
            CHANNELS = int(loopback_device.get("maxOutputChannels", 2))
            
        RATE = int(loopback_device["defaultSampleRate"])
        CHUNK = 1024

        try:
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=loopback_device["index"],
                frames_per_buffer=CHUNK
            )
        except IOError:
            p.terminate()
            return

        MAX_RMS_SCALE = 10000 

        while self._running:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                
                count = len(data) // 2
                if count > 0:
                    shorts = struct.unpack(f"<{count}h", data)
                    sum_squares = sum(s * s for s in shorts)
                    rms = math.sqrt(sum_squares / count)
                else:
                    rms = 0.0

                # Calculate scaled level for progress bar (0 to 20 chars max)
                level = int((rms / MAX_RMS_SCALE) * 20)
                level = min(max(level, 0), 20)
                
                self.audio_level.emit(rms, level)

            except Exception:
                pass

        if stream.is_active():
            stream.stop_stream()
            stream.close()
        p.terminate()

    def stop(self):
        self._running = False
        self.wait(100)
