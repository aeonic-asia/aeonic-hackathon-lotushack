"""Orchestrator — Strands Graph-based router for Lena AI Steward.

For structured intents (generateQuests, etc.), agents are called directly —
no router overhead. The Graph is only used for free-form prompts where
the router acknowledges and the coaching agent handles the request.

    Direct call:  intent → Agent (single LLM call)
    Graph path:   free-form → Router → CoachingAgent (two LLM calls)
"""

from strands import Agent
from strands.multiagent.graph import GraphBuilder, Graph

from config import get_model, get_quest_model
from orchestrator.prompts import (
    ROUTER_PROMPT,
    QUEST_GENERATOR_PROMPT,
    COACHING_PROMPT,
)
from tools.db_tools import get_family_context


class Orchestrator:
    """Holds both standalone agents and the fallback graph."""

    def __init__(self):
        model = get_model()

        # Quest agent uses structured output model (guaranteed JSON schema)
        self.quest_agent = Agent(
            model=get_quest_model(),
            system_prompt=QUEST_GENERATOR_PROMPT,
            tools=[],
            name="quest_generator",
        )

        self.coaching_agent = Agent(
            model=model,
            system_prompt=COACHING_PROMPT,
            tools=[get_family_context],
            name="coaching",
        )

        # Graph for free-form prompts (router → coaching)
        router = Agent(
            model=model,
            system_prompt=ROUTER_PROMPT,
            tools=[],
            name="router",
        )

        builder = GraphBuilder()
        builder.add_node(router, node_id="router")
        builder.add_node(self.coaching_agent, node_id="coaching")
        builder.set_entry_point("router")
        builder.add_edge("router", "coaching")
        builder.set_execution_timeout(120)
        builder.set_node_timeout(60)
        self.graph = builder.build()


def create_orchestrator() -> Orchestrator:
    """Build the orchestrator with standalone agents and fallback graph."""
    return Orchestrator()
