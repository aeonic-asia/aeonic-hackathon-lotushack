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
import time

from bedrock_agentcore.runtime import BedrockAgentCoreApp

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = BedrockAgentCoreApp()

# Lazy-init: AgentCore requires startup within 30s, so we defer heavy imports
# (Strands, OpenAI client, Orchestrator creation) to the first invocation.
_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        t0 = time.perf_counter()
        from orchestrator.agent import create_orchestrator
        _orchestrator = create_orchestrator()
        logger.info("[PERF] orchestrator_init=%.2fs", time.perf_counter() - t0)
    return _orchestrator


def _fetch_family_context(family_id: str, today: str) -> str:
    """Pre-fetch all children in a family from DB for RAG injection into the prompt.

    Loads every child's profile, age, preferences, streaks, goals, and
    existing quests so the LLM can generate suggestions for the whole family
    in a single call.
    """
    from db.connection import execute_query
    from db import queries

    t_db_start = time.perf_counter()

    t0 = time.perf_counter()
    family_rows = execute_query(queries.GET_FAMILY, (family_id,))
    logger.info("[PERF] db_get_family=%.3fs", time.perf_counter() - t0)
    if not family_rows:
        return f"Family {family_id} not found in database."

    family = family_rows[0]
    t0 = time.perf_counter()
    children_rows = execute_query(queries.GET_CHILDREN, (family_id,))
    logger.info("[PERF] db_get_children=%.3fs", time.perf_counter() - t0)
    if not children_rows:
        return f"No children found for family {family_id}."

    sections = [f"**Family:** {family['name']} (id: {family['id']})"]
    sections.append(f"**Number of children:** {len(children_rows)}")

    for child in children_rows:
        child_id = str(child["id"])
        age = child.get("childAge", "unknown")
        parts = [f"\n### {child['name']} (age {age}, coins: {child['coins']}, id: {child_id})"]

        t0 = time.perf_counter()
        prefs = execute_query(queries.GET_CHILD_PREFERENCES, (child_id,))
        logger.info("[PERF] db_preferences(%s)=%.3fs", child['name'], time.perf_counter() - t0)
        if prefs:
            pref_list = ", ".join(f"{p['category_name']} ({p['score']})" for p in prefs)
            parts.append(f"**Preferences/Interests:** {pref_list}")

        t0 = time.perf_counter()
        streaks = execute_query(queries.GET_CHILD_STREAKS, (child_id,))
        logger.info("[PERF] db_streaks(%s)=%.3fs", child['name'], time.perf_counter() - t0)
        if streaks:
            s = streaks[0]
            parts.append(f"**Streak:** current={s['currentStreak']}, longest={s['longestStreak']}")

        t0 = time.perf_counter()
        goals = execute_query(queries.GET_CHILD_GOALS, (child_id,))
        logger.info("[PERF] db_goals(%s)=%.3fs", child['name'], time.perf_counter() - t0)
        if goals:
            goal_list = ", ".join(f"{g['title']} (target: {g['target_coins']})" for g in goals)
            parts.append(f"**Goals:** {goal_list}")

        t0 = time.perf_counter()
        existing = execute_query(queries.CHECK_QUEST_EXISTS, (child_id, today))
        logger.info("[PERF] db_quest_exists(%s)=%.3fs", child['name'], time.perf_counter() - t0)
        if existing:
            parts.append(f"**Already has quest today:** Yes (quest_id: {existing[0]['id']})")
        else:
            parts.append("**Already has quest today:** No")

        t0 = time.perf_counter()
        active = execute_query(queries.GET_ACTIVE_QUESTS, (child_id,))
        logger.info("[PERF] db_active_quests(%s)=%.3fs", child['name'], time.perf_counter() - t0)
        if active:
            quest_list = ", ".join(f"{q['title']} ({q['status']})" for q in active[:5])
            parts.append(f"**Active quests:** {quest_list}")

        sections.append("\n".join(parts))

    logger.info("[PERF] db_total=%.2fs (children=%d)", time.perf_counter() - t_db_start, len(children_rows))
    return "\n\n".join(sections)


def _fetch_moment_context(family_id: str, today: str) -> str:
    """Pre-fetch family context plus calendar, activities, and advisor messages for moment planning.

    Reuses _fetch_family_context for the base household data, then appends
    calendar events, recent activities, and recent advisor messages.
    On weekdays the calendar horizon is today only (evening at home);
    on weekends it spans the full weekend.
    """
    from db.connection import execute_query
    from db import queries
    from datetime import date, timedelta

    t_db_start = time.perf_counter()

    # Reuse the base family context (children, preferences, streaks, goals)
    base_context = _fetch_family_context(family_id, today)

    today_date = date.fromisoformat(today)
    is_weekend = today_date.weekday() >= 5  # 5=Saturday, 6=Sunday

    # Calendar events: scope depends on weekday vs weekend
    if is_weekend:
        # Weekend: fetch through Sunday
        days_until_sunday = 6 - today_date.weekday()  # 0 if Sunday, 1 if Saturday
        horizon = (today_date + timedelta(days=days_until_sunday + 1)).isoformat()
        cal_label = "this weekend"
    else:
        # Weekday: only today (evening at home)
        horizon = (today_date + timedelta(days=1)).isoformat()
        cal_label = f"today ({today}, evening only)"

    t0 = time.perf_counter()
    calendar_rows = execute_query(queries.GET_CALENDAR_EVENTS, (family_id, today, horizon))
    logger.info("[PERF] db_calendar_events=%.3fs", time.perf_counter() - t0)

    if calendar_rows:
        cal_lines = []
        for ev in calendar_rows:
            cal_lines.append(
                f"- {ev['parent_name']}: {ev['title']} "
                f"({ev['startTime']} to {ev['endTime']})"
            )
        calendar_section = f"## Parent Calendar ({cal_label})\n" + "\n".join(cal_lines)
    else:
        calendar_section = f"## Parent Calendar ({cal_label})\nNo scheduled events found."

    # Recent activities
    t0 = time.perf_counter()
    activity_rows = execute_query(queries.GET_RECENT_ACTIVITIES, (family_id,))
    logger.info("[PERF] db_recent_activities=%.3fs", time.perf_counter() - t0)

    if activity_rows:
        act_lines = []
        for a in activity_rows:
            status = "completed" if a.get("completed") else "not completed"
            act_lines.append(
                f"- {a['activity']} (child: {a['child_name']}, "
                f"{status}, {a['createdAt']})"
            )
        activities_section = "## Recent Activities\n" + "\n".join(act_lines)
    else:
        activities_section = "## Recent Activities\nNo recent activities found."

    # Recent advisor messages
    t0 = time.perf_counter()
    advisor_rows = execute_query(queries.GET_RECENT_ADVISOR_MESSAGES, (family_id,))
    logger.info("[PERF] db_recent_advisor=%.3fs", time.perf_counter() - t0)

    if advisor_rows:
        adv_lines = []
        for m in advisor_rows:
            adv_lines.append(
                f"- {m.get('suggestedActivity', 'N/A')} "
                f"(child: {m['child_name']}, status: {m['status']}, {m['createdAt']})"
            )
        advisor_section = "## Recent Suggestions\n" + "\n".join(adv_lines)
    else:
        advisor_section = "## Recent Suggestions\nNo recent suggestions found."

    logger.info("[PERF] db_moment_total=%.2fs", time.perf_counter() - t_db_start)

    return f"{base_context}\n\n{calendar_section}\n\n{activities_section}\n\n{advisor_section}"


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
        today = date.today().isoformat()

        # RAG pattern: pre-fetch all children in the family
        family_context = _fetch_family_context(family_id, today)

        return (
            f"[INTENT:generateQuests] "
            f"Generate exactly 5 daily quest suggestions for today ({today}) "
            f"for the children in family {family_id}. "
            f"Distribute quests as equally as possible across all children. "
            f"Use each child's age, preferences/interests, and goals to personalise quests.\n\n"
            f"## Family Context (pre-loaded from database)\n"
            f"{family_context}\n\n"
            f"Using the context above, generate 5 quest suggestions distributed fairly "
            f"across all children. Each quest must include a \"childId\" field. "
            f"Return ONLY a JSON array of quest suggestions."
        )

    if intent == "planMoment":
        from datetime import date
        today_date = date.today()
        today = today_date.isoformat()
        day_name = today_date.strftime("%A")  # e.g. "Friday"
        is_weekend = today_date.weekday() >= 5  # 5=Saturday, 6=Sunday

        moment_context = _fetch_moment_context(family_id, today)

        if is_weekend:
            day_instruction = (
                f"Today is {day_name} {today} (WEEKEND). "
                f"Suggest 3 outside-the-home outing activities spread across "
                f"Saturday and Sunday. Use flexible time windows throughout the day "
                f"(morning, afternoon, or all-day), duration 60-120 minutes each. "
                f"Every suggestion MUST have a non-empty mapsQuery."
            )
        else:
            day_instruction = (
                f"Today is {day_name} {today} (WEEKDAY). "
                f"ALL 3 suggestions MUST be for TODAY {today}. "
                f"Do NOT suggest activities for any other date. "
                f"Suggestion 1: suggestedDay={today}. "
                f"Suggestion 2: suggestedDay={today}. "
                f"Suggestion 3: suggestedDay={today}. "
                f"All must be AT-HOME evening activities (after 5 PM, 30-60 min). "
                f"All must have mapsQuery=\"\"."
            )

        return (
            f"[INTENT:planMoment] "
            f"{day_instruction} "
            f"Use the children's preferences and avoid repeating recent activities.\n\n"
            f"## Family Context (pre-loaded from database)\n"
            f"{moment_context}\n\n"
            f"Generate exactly 3 moment suggestions following the rules above. "
            f"Return ONLY a JSON object with a 'suggestions' array."
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


def _extract_agent_text(result) -> str:
    """Extract text from a direct Strands Agent call result."""
    if hasattr(result, "message"):
        message = result.message
        if isinstance(message, dict):
            content = message.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "")
    return str(result)


@app.entrypoint
def invoke(payload):
    """Main agent invocation handler.

    Structured intents (generateQuests, etc.) call agents directly — single
    LLM call, no router overhead. Free-form prompts go through the graph
    (router → coaching agent).
    """
    t_total = time.perf_counter()
    intent = payload.get("intent")

    t0 = time.perf_counter()
    task = _build_task(payload)
    logger.info("[PERF] build_task=%.2fs (intent=%s)", time.perf_counter() - t0, intent)

    t0 = time.perf_counter()
    orch = _get_orchestrator()
    logger.info("[PERF] get_orchestrator=%.2fs", time.perf_counter() - t0)

    # --- Direct agent calls for structured intents (skip router) ---

    if intent == "generateQuests":
        t0 = time.perf_counter()
        result = orch.quest_agent(task)
        logger.info("[PERF] quest_agent_llm=%.2fs", time.perf_counter() - t0)

        t0 = time.perf_counter()
        raw_text = _extract_agent_text(result)
        # Structured output: model returns {"suggestions": [...]} directly
        try:
            parsed = json.loads(raw_text)
            quests = parsed.get("suggestions", [])
        except (json.JSONDecodeError, TypeError):
            # Fallback to regex extraction if structured output somehow fails
            quests = _extract_json_array(raw_text)
        logger.info("[PERF] json_parse=%.3fs", time.perf_counter() - t0)
        logger.info("[PERF] TOTAL=%.2fs (direct call, structured output)", time.perf_counter() - t_total)

        if quests is not None:
            return {"intent": intent, "suggestions": quests}
        logger.warning("Failed to parse quest response")
        logger.info("quest raw_text (first 300): %s", raw_text[:300])
        return {"intent": intent, "suggestions": [], "debug_raw": raw_text[:500]}

    if intent == "planMoment":
        t0 = time.perf_counter()
        result = orch.moment_agent(task)
        logger.info("[PERF] moment_agent_llm=%.2fs", time.perf_counter() - t0)

        t0 = time.perf_counter()
        raw_text = _extract_agent_text(result)
        # Structured output: model returns {"suggestions": [...]} directly
        try:
            parsed = json.loads(raw_text)
            moments = parsed.get("suggestions", [])
        except (json.JSONDecodeError, TypeError):
            moments = _extract_json_array(raw_text)
        logger.info("[PERF] json_parse=%.3fs", time.perf_counter() - t0)
        logger.info("[PERF] TOTAL=%.2fs (direct call, structured output)", time.perf_counter() - t_total)

        if moments is not None:
            return {"intent": intent, "suggestions": moments}
        logger.warning("Failed to parse moment response")
        logger.info("moment raw_text (first 300): %s", raw_text[:300])
        return {"intent": intent, "suggestions": [], "debug_raw": raw_text[:500]}

    if intent in ("childWish", "parentCoaching"):
        t0 = time.perf_counter()
        result = orch.coaching_agent(task)
        logger.info("[PERF] coaching_agent_llm=%.2fs", time.perf_counter() - t0)
        raw_text = _extract_agent_text(result)
        logger.info("[PERF] TOTAL=%.2fs (direct call, no router)", time.perf_counter() - t_total)
        return {"result": {"role": "assistant", "content": [{"text": raw_text}]}}

    # --- Free-form prompts go through the graph (router → coaching) ---

    t0 = time.perf_counter()
    graph_result = orch.graph(task)
    graph_elapsed = time.perf_counter() - t0
    logger.info(
        "[PERF] graph_execution=%.2fs, status=%s, nodes=%s",
        graph_elapsed,
        graph_result.status,
        [n.node_id for n in graph_result.execution_order],
    )

    raw_text = _extract_text_from_graph_result(graph_result, "coaching")
    logger.info("[PERF] TOTAL=%.2fs (graph path)", time.perf_counter() - t_total)
    return {"result": {"role": "assistant", "content": [{"text": raw_text}]}}


if __name__ == "__main__":
    # AgentCore expects port 8080 (default). Override with PORT env var for local dev only.
    port = int(os.environ.get("PORT", 8080))
    app.run(port=port)
