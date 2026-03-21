"""Orchestrator — Strands Graph-based router for Lena AI Steward.

Uses a directed graph with conditional edges for intent-based routing:

    Router (entry point, lightweight LLM)
      → edge(intent == generateQuests) → QuestAgent
      → edge(fallback)                 → CoachingAgent

The router node is intentionally minimal — it acknowledges the request
while the conditional edges do deterministic routing based on the task
string (which contains the intent). This mirrors the LangGraph supervisor
pattern from the omn-ai project but uses Strands' native Graph API.
"""

from strands import Agent
from strands.multiagent.graph import GraphBuilder, Graph

from config import get_model
from orchestrator.prompts import (
    ROUTER_PROMPT,
    QUEST_GENERATOR_PROMPT,
    COACHING_PROMPT,
)
from tools.db_tools import get_family_context


def create_orchestrator() -> Graph:
    """Build the Strands Graph orchestrator with intent-based routing."""
    model = get_model()

    # --- Nodes ---

    # Router: lightweight entry point. Its only job is to acknowledge;
    # actual routing happens via conditional edges on state.task.
    router = Agent(
        model=model,
        system_prompt=ROUTER_PROMPT,
        tools=[],
        name="router",
    )

    # Quest generator: no tools needed — context is pre-loaded via RAG pattern
    quest_agent = Agent(
        model=model,
        system_prompt=QUEST_GENERATOR_PROMPT,
        tools=[],
        name="quest_generator",
    )

    # Coaching / general-purpose: has family context for free-form coaching
    coaching_agent = Agent(
        model=model,
        system_prompt=COACHING_PROMPT,
        tools=[get_family_context],
        name="coaching",
    )

    # --- Graph assembly ---

    builder = GraphBuilder()
    builder.add_node(router, node_id="router")
    builder.add_node(quest_agent, node_id="quest_generator")
    builder.add_node(coaching_agent, node_id="coaching")

    builder.set_entry_point("router")

    # Conditional edges: route based on intent keyword in the task string
    builder.add_edge(
        "router",
        "quest_generator",
        condition=lambda state: "[INTENT:generateQuests]" in str(state.task),
    )
    builder.add_edge(
        "router",
        "coaching",
        condition=lambda state: "[INTENT:generateQuests]" not in str(state.task),
    )

    builder.set_execution_timeout(120)
    builder.set_node_timeout(60)

    return builder.build()
