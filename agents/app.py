"""BedrockAgentCoreApp entrypoint — single runtime for all Lena's Homestead agents.

The orchestrator runs in-process and delegates to sub-agents via @tool functions.
Locally: python app.py  (serves on PORT, default 8081)
Deploy: agentcore configure -e app.py && agentcore deploy
"""

import json
import os
import re

from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

# Lazy-init: AgentCore requires startup within 30s, so we defer heavy imports
# (Strands, OpenAI client, Agent creation) to the first invocation.
_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from orchestrator.agent import create_orchestrator
        _orchestrator = create_orchestrator()
    return _orchestrator


def build_prompt_from_intent(payload: dict) -> str:
    """Convert a structured frontend intent payload into a natural language prompt.

    The orchestrator reasons better with natural language, so we translate
    the JSON intent format into a sentence it can act on.
    """
    intent = payload["intent"]
    child_id = payload.get("childId", "unknown")
    family_id = payload.get("familyId", "unknown")

    if intent == "generateQuests":
        child_age = payload.get("childAge", 8)
        focus_areas = payload.get("focusAreas", ["learning", "exercise", "responsibility"])
        if isinstance(focus_areas, list):
            focus_areas = ", ".join(focus_areas)
        return (
            f"Generate daily quests for child {child_id} (age {child_age}) "
            f"in family {family_id}. "
            f"Focus areas: {focus_areas}."
        )

    if intent == "childWish":
        activity = payload.get("activity", "something fun")
        return (
            f"Child {child_id} in family {family_id} wishes to: {activity}. "
            f"Help plan this."
        )

    if intent == "parentCoaching":
        question = payload.get("question", "")
        return (
            f"A parent in family {family_id} asks for coaching help: {question}"
        )

    # Generic fallback for intents not yet implemented
    return f"Handle intent '{intent}' for family {family_id}, child {child_id}. Payload: {payload}"


def _extract_json_array(text: str) -> list | None:
    """Extract the first JSON array from LLM text that may contain markdown or narrative."""
    # Try the raw text first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    # Try to find a JSON array in markdown code blocks or inline
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


@app.entrypoint
def invoke(payload):
    """Main agent invocation handler."""
    intent = payload.get("intent")
    if intent:
        prompt = build_prompt_from_intent(payload)
    else:
        prompt = payload.get("prompt", "Hello! I'm here to help with your homestead.")

    result = _get_orchestrator()(prompt)

    # For structured intents, extract clean JSON from the LLM response
    if intent == "generateQuests":
        raw_text = result.message.get("content", [{}])[0].get("text", "")
        quests = _extract_json_array(raw_text)
        if quests is not None:
            return {"intent": intent, "suggestions": quests}

    return {"result": result.message}


if __name__ == "__main__":
    # AgentCore expects port 8080 (default). Override with PORT env var for local dev only.
    port = int(os.environ.get("PORT", 8080))
    app.run(port=port)
