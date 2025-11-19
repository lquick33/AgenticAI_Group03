from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", None)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", None)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", None)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", None)


required_env_vars = [
    "GOOGLE_API_KEY"
]

for var in required_env_vars:
    if not var:
        raise ValueError(f"Missing required environment variable: {var}")
