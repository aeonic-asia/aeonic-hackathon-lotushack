"""FamilyContextService — assembles a household snapshot for AI agent reasoning.

This is the single abstraction that encapsulates context assembly. When
family_context_view is created in the database, only this file needs to change.
"""

from db.connection import execute_query
from db import queries


class FamilyContextService:
    @staticmethod
    def get_snapshot(family_id: str) -> dict:
        """Assemble a complete household context from direct table queries.

        Returns a dict with structure:
        {
            "family": {"id", "name"},
            "parents": [{"id", "name", "email"}],
            "children": [{
                "id", "name", "coins",
                "streak": {"currentStreak", "longestStreak", "lastCompletedDate"},
                "preferences": [{"category_name", "score"}],
                "active_quests": [{"id", "title", "status", "reward", "assignedDate"}],
                "goals": [{"id", "title", "target_coins", "deadline"}]
            }]
        }
        """
        family_rows = execute_query(queries.GET_FAMILY, (family_id,))
        if not family_rows:
            return {"error": f"Family {family_id} not found"}

        family = family_rows[0]
        parents = execute_query(queries.GET_PARENTS, (family_id,))
        children_rows = execute_query(queries.GET_CHILDREN, (family_id,))

        children = []
        for child in children_rows:
            child_id = str(child["id"])

            streak_rows = execute_query(queries.GET_CHILD_STREAKS, (child_id,))
            streak = streak_rows[0] if streak_rows else {
                "currentStreak": 0,
                "longestStreak": 0,
                "lastCompletedDate": None,
            }

            preferences = execute_query(queries.GET_CHILD_PREFERENCES, (child_id,))
            active_quests = execute_query(queries.GET_ACTIVE_QUESTS, (child_id,))
            goals = execute_query(queries.GET_CHILD_GOALS, (child_id,))

            children.append({
                "id": child_id,
                "name": child["name"],
                "coins": child["coins"],
                "streak": _serialize(streak),
                "preferences": [_serialize(p) for p in preferences],
                "active_quests": [_serialize(q) for q in active_quests],
                "goals": [_serialize(g) for g in goals],
            })

        return {
            "family": _serialize(family),
            "parents": [_serialize(p) for p in parents],
            "children": children,
        }


def _serialize(row: dict) -> dict:
    """Convert non-JSON-serializable values (dates, UUIDs) to strings."""
    return {k: str(v) if v is not None else None for k, v in row.items()}
