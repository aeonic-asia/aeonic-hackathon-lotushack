"""Orchestrator Agent — Lena AI Steward.

Central hub that recognises intent, loads family context, and delegates
to the appropriate sub-agent tool.
"""

from strands import Agent

from config import get_model
from orchestrator.prompts import ORCHESTRATOR_PROMPT
from tools.db_tools import get_family_context
from sub_agents.quest_generator import generate_quests


def create_orchestrator() -> Agent:
    """Create and return the orchestrator agent with all registered tools."""
    return Agent(
        model=get_model(),
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=[get_family_context, generate_quests],
    )
