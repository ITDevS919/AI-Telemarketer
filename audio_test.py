import sounddevice as sd
import numpy as np
import time

TARGET_DEVICE_INDEX = 14 # Focus on the NoMachine device
TARGET_SAMPLE_RATE = 48000
TARGET_CHANNELS = 1
TEST_DURATION = 5 # Seconds

def audio_callback(indata, frames, time_info, status):
    # This function will be called by sounddevice when audio data is available
    if status:
        print(f"Callback Status Warning: {status}")
    volume_norm = np.linalg.norm(indata) * 10
    # Print frequently to show activity
    print(f"Callback called! Audio level: {volume_norm:.2f}") 

# --- Get device info --- 
try:
    device_info = sd.query_devices(TARGET_DEVICE_INDEX)
    print(f"Target Device {TARGET_DEVICE_INDEX}: {device_info['name']}")
    print(f"  Max Input Channels: {device_info['max_input_channels']}")
    print(f"  Default Sample Rate: {device_info['default_samplerate']}")
except Exception as e:
    print(f"Error querying device {TARGET_DEVICE_INDEX}: {e}")
    exit()

print(f"\nAttempting to open stream on device {TARGET_DEVICE_INDEX}...")
print(f"  Requested Sample Rate: {TARGET_SAMPLE_RATE} Hz")
print(f"  Requested Channels: {TARGET_CHANNELS}")

try:
    with sd.InputStream(device=TARGET_DEVICE_INDEX, 
                       channels=TARGET_CHANNELS,
                       callback=audio_callback, 
                       blocksize=1024, # Or another reasonable size 
                       samplerate=TARGET_SAMPLE_RATE):
        print(f"\nStream opened successfully! Listening for {TEST_DURATION} seconds...")
        print("Speak into your microphone!")
        # Keep the main thread alive while the callback runs in the background
        time.sleep(TEST_DURATION)
    print(f"\nFinished listening.")

except sd.PortAudioError as pae:
    print(f"\nERROR: PortAudioError opening stream: {pae}")
    print("Please check if the device supports the requested settings (Rate, Channels).")
except Exception as e:
    print(f"\nERROR: An unexpected error occurred: {e}")

print("\nAudio test script finished.")

# OLD code iterating through all devices - REMOVED
# # Get all devices with input channels
# devices = sd.query_devices()
# input_devices = [i for i, dev in enumerate(devices) if dev['max_input_channels'] > 0]
# 
# print(f"Found {len(input_devices)} input devices:")
# for i in input_devices:
#     dev = sd.query_devices(i)
#     print(f"Device {i}: {dev['name']} - {dev['max_input_channels'] input channels")
# 
# for device_idx in input_devices:
#     dev = sd.query_devices(device_idx)
#     print(f"\nTesting device {device_idx}: {dev['name']}")
#     default_sr = int(dev['default_samplerate'])
#     print(f"Default Sample Rate: {default_sr} Hz")
#     print(f"Channels: {dev['max_input_channels']}")
#     try:
#         with sd.InputStream(device=device_idx, 
#                            channels=min(dev['max_input_channels'], 2),
#                            callback=audio_callback, 
#                            blocksize=1024, 
#                            samplerate=default_sr):
#             print(f"Recording from {dev['name']} (at {default_sr} Hz) for 3 seconds...")
#             for i in range(3):
#                 time.sleep(1)
#                 print(f"Testing... {i+1}s")
#         print(f"Device {device_idx} test completed.")
#     except Exception as e:
#         print(f"Error testing device {device_idx}: {e}")
#     
# print("\nAll device tests completed.")
