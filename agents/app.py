"""BedrockAgentCoreApp entrypoint — single runtime for all Lena's Homestead agents.

Uses a Strands Graph orchestrator with conditional edge routing:
  Router (entry) → Quest Agent | Coaching Agent

Locally: python app.py  (serves on PORT, default 8081)
Deploy: agentcore configure -e app.py && agentcore deploy
"""

import json
import logging
import os
import re

from bedrock_agentcore.runtime import BedrockAgentCoreApp

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = BedrockAgentCoreApp()

# Lazy-init: AgentCore requires startup within 30s, so we defer heavy imports
# (Strands, OpenAI client, Graph creation) to the first invocation.
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from orchestrator.agent import create_orchestrator
        _graph = create_orchestrator()
    return _graph


def _fetch_child_context(child_id: str, today: str) -> str:
    """Pre-fetch child context from DB for RAG injection into the prompt.

    This replaces tool-based context loading — the agent receives all data
    upfront and only needs a single LLM call to generate quests.
    """
    from db.connection import execute_query
    from db import queries
    from db.family_context import _serialize

    parts = []

    child_rows = execute_query(queries.GET_CHILD_BY_ID, (child_id,))
    if not child_rows:
        return f"Child {child_id} not found in database."

    child = child_rows[0]
    parts.append(f"**Child:** {child['name']} | Coins: {child['coins']} | Family: {child['family_name']}")

    # Preferences
    prefs = execute_query(queries.GET_CHILD_PREFERENCES, (child_id,))
    if prefs:
        pref_list = ", ".join(f"{p['category_name']} ({p['score']})" for p in prefs)
        parts.append(f"**Preferences:** {pref_list}")

    # Streak
    streaks = execute_query(queries.GET_CHILD_STREAKS, (child_id,))
    if streaks:
        s = streaks[0]
        parts.append(f"**Streak:** current={s['currentStreak']}, longest={s['longestStreak']}")

    # Active goals
    goals = execute_query(queries.GET_CHILD_GOALS, (child_id,))
    if goals:
        goal_list = ", ".join(f"{g['title']} (target: {g['target_coins']})" for g in goals)
        parts.append(f"**Goals:** {goal_list}")

    # Existing quests for today
    existing = execute_query(queries.CHECK_QUEST_EXISTS, (child_id, today))
    if existing:
        parts.append(f"**Already has quest today:** Yes (quest_id: {existing[0]['id']})")
    else:
        parts.append("**Already has quest today:** No")

    # Active (pending) quests
    active = execute_query(queries.GET_ACTIVE_QUESTS, (child_id,))
    if active:
        quest_list = ", ".join(f"{q['title']} ({q['status']})" for q in active[:5])
        parts.append(f"**Active quests:** {quest_list}")

    return "\n".join(parts)


def _build_task(payload: dict) -> str:
    """Build a task string with an embedded intent tag for graph routing.

    The [INTENT:xxx] tag is parsed by conditional edges in the graph
    to route to the correct sub-agent — no LLM routing overhead needed.
    """
    intent = payload.get("intent")
    child_id = payload.get("childId", "unknown")
    family_id = payload.get("familyId", "unknown")

    if intent == "generateQuests":
        from datetime import date
        child_age = payload.get("childAge", 8)
        focus_areas = payload.get("focusAreas", ["learning", "exercise", "responsibility"])
        if isinstance(focus_areas, list):
            focus_areas = ", ".join(focus_areas)
        today = date.today().isoformat()

        # RAG pattern: pre-fetch DB context so the agent needs zero tool calls
        child_context = _fetch_child_context(child_id, today)

        return (
            f"[INTENT:generateQuests] "
            f"Generate daily quest suggestions for today ({today}) for a {child_age}-year-old child "
            f"in family {family_id}. "
            f"Focus areas: {focus_areas}.\n\n"
            f"## Child Context (pre-loaded from database)\n"
            f"{child_context}\n\n"
            f"Using the context above, generate one quest per focus area that doesn't already "
            f"have a quest for today. Return ONLY a JSON array of quest suggestions."
        )

    if intent == "childWish":
        activity = payload.get("activity", "something fun")
        return (
            f"[INTENT:childWish] "
            f"Child {child_id} in family {family_id} wishes to: {activity}. "
            f"Help plan this."
        )

    if intent == "parentCoaching":
        question = payload.get("question", "")
        return (
            f"[INTENT:parentCoaching] "
            f"A parent in family {family_id} asks for coaching help: {question}"
        )

    # Free-form / no intent
    prompt = payload.get("prompt", "Hello! I'm here to help with your homestead.")
    return f"[INTENT:general] {prompt}"


def _extract_json_array(text: str) -> list | None:
    """Extract the first JSON array from LLM text that may contain markdown or narrative."""
    # Try the raw text first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    # Try markdown code blocks first (```json ... ```)
    code_block = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback: find the first JSON array (non-greedy to avoid spanning two arrays)
    match = re.search(r"\[[\s\S]*?\](?=\s*$|\s*```|\s*\n\n)", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # Last resort: greedy match
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _extract_text_from_graph_result(graph_result, target_node: str) -> str:
    """Extract the text output from a specific node in the graph result."""
    node_result = graph_result.results.get(target_node)
    if node_result is None:
        logger.warning("Node '%s' not found in graph results: %s", target_node, list(graph_result.results.keys()))
        return ""

    agent_results = node_result.get_agent_results()
    if not agent_results:
        return ""

    # Get the text from the last agent result's message
    result = agent_results[-1]
    message = result.message
    if isinstance(message, dict):
        content = message.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
    return str(result)


@app.entrypoint
def invoke(payload):
    """Main agent invocation handler — routes via Strands Graph."""
    intent = payload.get("intent")
    task = _build_task(payload)

    logger.info("Invoking graph with intent=%s", intent)
    graph_result = _get_graph()(task)
    logger.info(
        "Graph completed: status=%s, nodes=%s",
        graph_result.status,
        [n.node_id for n in graph_result.execution_order],
    )

    # For quest generation, extract structured JSON from the quest_generator node
    if intent == "generateQuests":
        raw_text = _extract_text_from_graph_result(graph_result, "quest_generator")
        logger.info("quest raw_text (first 300): %s", raw_text[:300])
        quests = _extract_json_array(raw_text)
        if quests is not None:
            return {"intent": intent, "suggestions": quests}
        logger.warning("Failed to extract JSON array from quest response")
        return {"intent": intent, "suggestions": [], "debug_raw": raw_text[:500]}

    # For other intents, return the coaching agent's response
    raw_text = _extract_text_from_graph_result(graph_result, "coaching")
    return {"result": {"role": "assistant", "content": [{"text": raw_text}]}}


if __name__ == "__main__":
    # AgentCore expects port 8080 (default). Override with PORT env var for local dev only.
    port = int(os.environ.get("PORT", 8080))
    app.run(port=port)
