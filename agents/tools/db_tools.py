"""Strands @tool wrappers for database operations.

These tools are given to agents so they can read from and write to
the Supabase Postgres database. Each tool returns a JSON string.
"""

import json

from strands import tool

from db.connection import execute_query, execute_write
from db.family_context import FamilyContextService, _serialize
from db import queries


@tool
def get_family_context(family_id: str) -> str:
    """Get the complete household context for a family including parents, children, preferences, streaks, active quests, and goals.

    Args:
        family_id: UUID of the family
    """
    snapshot = FamilyContextService.get_snapshot(family_id)
    return json.dumps(snapshot, indent=2)


@tool
def get_child_context(child_id: str) -> str:
    """Get a single child's profile including coins, preferences, goals, active quests, and streak.

    Args:
        child_id: UUID of the child
    """
    child_rows = execute_query(queries.GET_CHILD_BY_ID, (child_id,))
    if not child_rows:
        return json.dumps({"error": f"Child {child_id} not found"})

    child = child_rows[0]

    streak_rows = execute_query(queries.GET_CHILD_STREAKS, (child_id,))
    streak = streak_rows[0] if streak_rows else {
        "currentStreak": 0,
        "longestStreak": 0,
        "lastCompletedDate": None,
    }

    preferences = execute_query(queries.GET_CHILD_PREFERENCES, (child_id,))
    active_quests = execute_query(queries.GET_ACTIVE_QUESTS, (child_id,))
    goals = execute_query(queries.GET_CHILD_GOALS, (child_id,))

    result = {
        "id": str(child["id"]),
        "name": child["name"],
        "coins": child["coins"],
        "family_id": str(child["familyId"]),
        "family_name": child["family_name"],
        "streak": _serialize(streak),
        "preferences": [_serialize(p) for p in preferences],
        "active_quests": [_serialize(q) for q in active_quests],
        "goals": [_serialize(g) for g in goals],
    }
    return json.dumps(result, indent=2)


@tool
def check_existing_quest(child_id: str, assigned_date: str) -> str:
    """Check if a quest already exists for a child on the given date.

    Args:
        child_id: UUID of the child
        assigned_date: Date in YYYY-MM-DD format
    """
    rows = execute_query(queries.CHECK_QUEST_EXISTS, (child_id, assigned_date))
    if rows:
        return json.dumps({"exists": True, "quest_id": str(rows[0]["id"])})
    return json.dumps({"exists": False})


@tool
def save_quest(
    child_id: str,
    title: str,
    description: str,
    category: str,
    reward: int,
    guiding_questions: str,
    assigned_date: str,
) -> str:
    """Save a new quest to the database.

    Args:
        child_id: UUID of the child
        title: Quest title (adventure-framed, not a chore)
        description: Short description of the quest
        category: One of: learning, exercise, responsibility, habit
        reward: Number of seeds (5-15)
        guiding_questions: JSON string of Socratic guidance steps, e.g. [{"step": 1, "prompt": "Ask..."}]
        assigned_date: Date in YYYY-MM-DD format
    """
    row = execute_write(
        queries.INSERT_QUEST,
        (child_id, title, description, category, reward, guiding_questions, assigned_date),
    )
    if row:
        return json.dumps({"success": True, "quest": _serialize(row)})
    return json.dumps({"success": False, "error": "Failed to insert quest"})


@tool
def log_event(family_id: str, child_id: str, event_type: str, metadata: str) -> str:
    """Log an event to the event_logs table for traceability.

    Args:
        family_id: UUID of the family
        child_id: UUID of the child
        event_type: Type of event, e.g. 'quest_generated', 'quest_completed'
        metadata: JSON string with event details
    """
    row = execute_write(
        queries.INSERT_EVENT_LOG,
        (family_id, child_id, event_type, metadata),
    )
    if row:
        return json.dumps({"success": True, "event_log_id": str(row["id"])})
    return json.dumps({"success": False, "error": "Failed to log event"})
