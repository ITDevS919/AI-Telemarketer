import numpy as np
import sounddevice as sd
import time

# Generate a simple sine wave tone at 440 Hz (A4)
def generate_tone(frequency=440, duration=3, sample_rate=48000):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = 0.5 * np.sin(2 * np.pi * frequency * t)
    return tone.astype(np.float32)

# Print available devices
print("\n----- AVAILABLE AUDIO DEVICES -----")
devices = sd.query_devices()
output_devices = []

for i, dev in enumerate(devices):
    device_type = "INPUT" if dev['max_input_channels'] > 0 else ""
    device_type += " OUTPUT" if dev['max_output_channels'] > 0 else ""
    print(f"Device {i}: {dev['name']} - {device_type}")
    
    # Collect output device indices
    if dev['max_output_channels'] > 0:
        output_devices.append(i)

print(f"\nFound {len(output_devices)} output devices: {output_devices}")
print("----------------------------------\n")

# Generate test tone once
tone = generate_tone()

# Try to find any device with "NoMachine" in the name first
nomachine_devices = []
for i in output_devices:
    if "nomachine" in devices[i]['name'].lower():
        nomachine_devices.append(i)

if nomachine_devices:
    print(f"Found {len(nomachine_devices)} NoMachine output devices: {nomachine_devices}")
    
    # Try each NoMachine device
    for device_idx in nomachine_devices:
        try:
            print(f"\nPlaying 3-second test tone through {devices[device_idx]['name']} (device {device_idx})")
            sd.default.device = device_idx
            sd.play(tone, samplerate=48000, blocking=True)
            print(f"✓ Success playing through device {device_idx}")
        except Exception as e:
            print(f"✗ Error with device {device_idx}: {e}")
else:
    print("No NoMachine output devices found.")
    
# If still no success, try all output devices
print("\nTrying all output devices sequentially...")
for device_idx in output_devices:
    if device_idx in nomachine_devices:
        continue  # Skip NoMachine devices already tried
        
    try:
        print(f"\nPlaying 3-second test tone through {devices[device_idx]['name']} (device {device_idx})")
        sd.default.device = device_idx
        sd.play(tone, samplerate=48000, blocking=True)
        print(f"✓ Success playing through device {device_idx}")
    except Exception as e:
        print(f"✗ Error with device {device_idx}: {e}")

print("\nTest complete. Please let me know which device(s) produced audible sound.") 