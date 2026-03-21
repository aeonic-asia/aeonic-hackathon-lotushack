import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level up from agents/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL_ID = os.environ.get("OPENAI_MODEL_ID", "gpt-4o-mini")


def get_model():
    """Create an OpenAI model instance for Strands agents (free-form text)."""
    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={"api_key": OPENAI_API_KEY},
        model_id=OPENAI_MODEL_ID,
        params={
            "max_tokens": 2000,
            "temperature": 0.7,
        },
    )


# JSON Schema for quest generation structured output
QUEST_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "quest_suggestions",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "childId": {"type": "string"},
                            "childName": {"type": "string"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "category": {
                                "type": "string",
                                "enum": ["learning", "exercise", "responsibility", "life habits"],
                            },
                            "reward": {"type": "integer"},
                            "guidingQuestions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "step": {"type": "integer"},
                                        "type": {
                                            "type": "string",
                                            "enum": ["ask", "guide", "encourage"],
                                        },
                                        "prompt": {"type": "string"},
                                    },
                                    "required": ["step", "type", "prompt"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": [
                            "childId", "childName", "title", "description",
                            "category", "reward", "guidingQuestions",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["suggestions"],
            "additionalProperties": False,
        },
    },
}


def get_quest_model():
    """Create an OpenAI model with structured output for quest generation.

    Uses response_format with JSON Schema so the model output is guaranteed
    to match the quest suggestion schema — no regex extraction needed.
    """
    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={"api_key": OPENAI_API_KEY},
        model_id=OPENAI_MODEL_ID,
        params={
            "max_tokens": 2000,
            "temperature": 0.7,
            "response_format": QUEST_SCHEMA,
        },
    )


# JSON Schema for moment planning structured output
MOMENT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "moment_suggestions",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "suggestedDay": {"type": "string"},
                            "suggestedTimeWindow": {"type": "string"},
                            "durationMinutes": {"type": "integer"},
                            "childIds": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "childNames": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "mapsQuery": {"type": "string"},
                            "rationale": {"type": "string"},
                        },
                        "required": [
                            "title", "description", "suggestedDay",
                            "suggestedTimeWindow", "durationMinutes",
                            "childIds", "childNames", "mapsQuery", "rationale",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["suggestions"],
            "additionalProperties": False,
        },
    },
}


def get_moment_model():
    """Create an OpenAI model with structured output for moment planning.

    Uses response_format with JSON Schema so the model output is guaranteed
    to match the moment suggestion schema.
    """
    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={"api_key": OPENAI_API_KEY},
        model_id=OPENAI_MODEL_ID,
        params={
            "max_tokens": 2000,
            "temperature": 0.7,
            "response_format": MOMENT_SCHEMA,
        },
    )
