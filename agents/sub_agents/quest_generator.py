"""QuestGeneratorAgent — generates daily quest suggestions with Socratic parent guidance.

This module defines the quest generator as a Strands Agent with its own system
prompt and read-only DB tools. It returns structured JSON suggestions — the
parent approves them in the frontend before they are persisted.
"""

from datetime import date

from strands import Agent, tool

from config import get_model
from orchestrator.prompts import QUEST_GENERATOR_PROMPT
from tools.db_tools import check_existing_quest, get_child_context

# The quest generator agent instance — created once, reused across invocations
_quest_agent = None


def _get_quest_agent() -> Agent:
    """Lazy-init the quest generator agent."""
    global _quest_agent
    if _quest_agent is None:
        _quest_agent = Agent(
            model=get_model(),
            system_prompt=QUEST_GENERATOR_PROMPT,
            tools=[get_child_context, check_existing_quest],
        )
    return _quest_agent


@tool
def generate_quests(
    family_id: str,
    child_id: str,
    child_age: int,
    focus_areas: str,
) -> str:
    """Generate daily quest suggestions for a child. Returns JSON quest suggestions for parent review — does NOT write to the database.

    Args:
        family_id: UUID of the family
        child_id: UUID of the child
        child_age: Age of the child in years
        focus_areas: Comma-separated list of quest categories: learning,exercise,responsibility,habit
    """
    today = date.today().isoformat()
    areas_list = [a.strip() for a in focus_areas.split(",")]

    prompt = (
        f"Generate daily quest suggestions for today ({today}) for a {child_age}-year-old child "
        f"(child_id: {child_id}, family_id: {family_id}).\n"
        f"Focus areas: {', '.join(areas_list)}.\n"
        f"First, get the child's context. Then check if quests already exist for today. "
        f"Generate one quest suggestion per focus area that doesn't already have a quest for today. "
        f"Return ONLY a JSON array of quest suggestions."
    )

    agent = _get_quest_agent()
    result = agent(prompt)
    return result.message
