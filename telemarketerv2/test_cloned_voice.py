"""
Quick test script for cloned voice (ElevenLabs).
Run from backend: python test_cloned_voice.py
Requires ELEVENLABS_API_KEY in .env and at least one voice cloned via POST /api/voices/clone.
Output: tmp_output/test_cloned_voice_<VOICE_NAME>.wav
"""
import os
import sys
import wave
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

_backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_backend_dir))

from app.voice_cloning_handler import VoiceCloningHandler

VOICES_DIR = _backend_dir / "data" / "voices"
VOICE_NAME = os.getenv("TEST_VOICE_NAME", "company_voice")
TEST_TEXT = "Hello, this is a test of my cloned voice."
OUTPUT_DIR = _backend_dir / "tmp_output"
OUTPUT_WAV = OUTPUT_DIR / f"test_cloned_voice_{VOICE_NAME.replace(' ', '_')}.wav"
SAMPLE_RATE = 22050


def main():
    if not os.getenv("ELEVENLABS_API_KEY"):
        print("ERROR: Set ELEVENLABS_API_KEY in .env")
        sys.exit(1)

    print(f"Voices dir: {VOICES_DIR}")
    print(f"Voice name: {VOICE_NAME}")
    print(f"Synthesizing: '{TEST_TEXT}'")

    handler = VoiceCloningHandler(voices_dir=str(VOICES_DIR))
    if not handler.voice_exists(VOICE_NAME):
        print(f"ERROR: Voice '{VOICE_NAME}' not found. Clone a voice first via POST /api/voices/clone")
        sys.exit(1)

    pcm_data = handler.synthesize(
        text=TEST_TEXT,
        voice_name=VOICE_NAME,
        language="en",
        output_sample_rate=SAMPLE_RATE,
    )

    if not pcm_data:
        print("ERROR: Synthesis returned no audio.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUTPUT_WAV), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm_data)

    print(f"Done. Output saved to: {OUTPUT_WAV}")


if __name__ == "__main__":
    main()
