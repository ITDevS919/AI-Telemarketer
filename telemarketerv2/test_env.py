import os
from dotenv import load_dotenv

print("Starting .env test")

# Try loading with explicit path
env_path = os.path.join(os.path.dirname(__file__), '.env')
print(f"Looking for .env at: {env_path}")
print(f"File exists: {os.path.exists(env_path)}")

# Load the environment variables
print("Calling load_dotenv()")
result = load_dotenv(dotenv_path=env_path)
print(f"load_dotenv result: {result}")

# Check if GROQ_API_KEY is in environment
groq_key = os.getenv("GROQ_API_KEY")
print(f"GROQ_API_KEY present: {groq_key is not None}")

# Check other variables as control
twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
print(f"TWILIO_ACCOUNT_SID present: {twilio_sid is not None}")

# Print all environment variables (keys only)
print("\nAll environment variables:")
for key in sorted(os.environ.keys()):
    print(f"  {key}") 