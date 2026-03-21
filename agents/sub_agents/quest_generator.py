"""QuestGeneratorAgent — generates daily quest suggestions with Socratic parent guidance.

Now used as a Graph node (not a @tool wrapper). The agent is instantiated
directly in orchestrator/agent.py and receives its task from the graph's
conditional edge routing.
"""

# This module is kept for backwards compatibility and as the canonical
# location for quest generation logic. The actual Agent instance is
# created in orchestrator/agent.py using QUEST_GENERATOR_PROMPT and
# the DB tools (get_child_context, check_existing_quest).
