import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level up from agents/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL_ID = os.environ.get("OPENAI_MODEL_ID", "gpt-4o")


def get_model():
    """Create an OpenAI model instance for Strands agents."""
    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={"api_key": OPENAI_API_KEY},
        model_id=OPENAI_MODEL_ID,
        params={
            "max_tokens": 2000,
            "temperature": 0.7,
        },
    )
