import pyaudiowpatch as pyaudio
import struct
import math
import sys

def get_rms(data):
    """Calculate the Root Mean Square (RMS) of the audio data to measure volume."""
    count = len(data) // 2
    if count == 0:
        return 0
    # Unpack 16-bit signed integers (paInt16 format)
    shorts = struct.unpack(f"<{count}h", data)
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count)

def main():
    p = pyaudio.PyAudio()

    # Look for the WASAPI host API by type
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        print("Error: WASAPI is not available on this system.")
        print("This script requires Windows and a PyAudio build with WASAPI support.")
        sys.exit(1)

    wasapi_index = wasapi_info["index"]
    loopback_device = None

    # Step 1: Iterate over devices to find the WASAPI Loopback device
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)
        
        if dev_info["hostApi"] == wasapi_index:
            # PyAudioWPatch provides the 'isLoopbackDevice' key
            if dev_info.get("isLoopbackDevice", False):
                loopback_device = dev_info
                break
            # Fallback string matching just in case
            if "loopback" in dev_info["name"].lower():
                loopback_device = dev_info
                break

    if not loopback_device:
        print("Error: Could not find a WASAPI Loopback device.")
        print("Note: The standard 'PyAudio' library does not support loopback devices out of the box.")
        print("Recommendation: Use 'pyaudiowpatch' which is a drop-in replacement.")
        print("Run: pip uninstall pyaudio && pip install pyaudiowpatch")
        p.terminate()
        sys.exit(1)

    print(f"Detected WASAPI Loopback Device: {loopback_device['name']}")

    # Setup the stream parameters using the device's default settings
    FORMAT = pyaudio.paInt16
    
    # Loopback devices sometimes show 0 input channels initially
    CHANNELS = int(loopback_device.get("maxInputChannels", 0))
    if CHANNELS == 0:
        CHANNELS = int(loopback_device.get("maxOutputChannels", 2))
        
    RATE = int(loopback_device["defaultSampleRate"])
    CHUNK = 1024

    print(f"Opening stream with {CHANNELS} channels at {RATE} Hz...")

    try:
        # Step 2: Open the input stream using the found loopback device
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=loopback_device["index"],
            frames_per_buffer=CHUNK
        )
    except IOError as e:
        print(f"Failed to open the audio stream. Error: {e}")
        p.terminate()
        sys.exit(1)

    print("\n--- Level Meter Started! ---")
    print("Play a YouTube video or some audio. Press Ctrl+C to stop.\n")

    # Step 3: Continuously read raw bytes and update the level meter
    try:
        while True:
            # Get a stream of raw bytes
            data = stream.read(CHUNK, exception_on_overflow=False)
            
            # Optional: Determine noise level using RMS
            rms = get_rms(data)
            
            # Simple Console Level Meter
            # Scale down the RMS value to fit nicely in 50 characters (max visual width)
            # Typically, 10000+ RMS is fairly loud, but you might need to adjust logic
            MAX_RMS_SCALE = 10000 
            level = int((rms / MAX_RMS_SCALE) * 50)
            level = min(max(level, 0), 50)  # Clamp between 0 and 50
            
            bar = "█" * level + "-" * (50 - level)
            
            if rms > 200:  # Threshold determining what constitutes "noise"
                sys.stdout.write(f"\r[NOISE DETECTED] |{bar}| {int(rms):05d}")
            else:
                sys.stdout.write(f"\r[  SILENCE...  ] |{bar}| {int(rms):05d}")
            
            sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n\nStopping script...")

    finally:
        # Cleanup properly to free the device
        if 'stream' in locals() and stream.is_active():
            stream.stop_stream()
            stream.close()
        p.terminate()

if __name__ == "__main__":
    main()
