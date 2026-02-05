"""
Quick test script for cloned voice (XTTS).
Run from telemarketerv2: python test_cloned_voice.py
Output: test_cloned_voice_output.wav
"""
import sys
import wave
from pathlib import Path

# Ensure we can import app when run from telemarketerv2
_telemarketerv2_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_telemarketerv2_dir))

from app.voice_cloning_handler import VoiceCloningHandler

VOICES_DIR = _telemarketerv2_dir / "data" / "voices"
VOICE_NAME = "New Voice sample"
TEST_TEXT = "Hello, this is a test of my cloned voice. I am Steven Jobs."
OUTPUT_WAV = _telemarketerv2_dir / "tmp_output" / f"test_cloned_voice_{VOICE_NAME}.wav"
SAMPLE_RATE = 22050

def main():
    print(f"Voices dir: {VOICES_DIR}")
    print(f"Voice name: {VOICE_NAME}")
    print(f"Synthesizing: '{TEST_TEXT}'")
    print("Loading handler and model (first run may take a moment)...")

    handler = VoiceCloningHandler(voices_dir=str(VOICES_DIR))
    pcm_data = handler.synthesize(
        text=TEST_TEXT,
        voice_name=VOICE_NAME,
        language="en",
        output_sample_rate=SAMPLE_RATE,
    )

    if not pcm_data:
        print("ERROR: Synthesis returned no audio.")
        sys.exit(1)

    with wave.open(str(OUTPUT_WAV), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm_data)

    print(f"Done. Output saved to: {OUTPUT_WAV}")
    print("Play the file to hear your cloned voice.")


if __name__ == "__main__":
    main()
