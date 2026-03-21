# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Lena's Homestead** agent backend — AI-powered parenting companion where children grow life skills through gamified quests guided by "Lena the Flower Nymph" mascot. This repo contains the **AWS AgentCore agents** that power the AI backend.

Core principle: "AI guides parents, never replaces them." The AI is a coaching engine — it suggests, breaks down challenges into guided steps, and helps parents teach. It never gives children answers directly.

## Architecture

### Agent Hierarchy

The **Lena AI Steward** is the central orchestrator agent deployed on AWS AgentCore. It does NOT perform domain tasks itself — it recognizes intent, plans workflows, and calls sub-agents via `agentsAsToolsCall`:

- **QuestGeneratorAgent** — generates daily quests across four pillars (Learning, Exercise, Responsibility, Life Habits) with Socratic parent guidance
- **PreferenceAnalyzerAgent** — analyzes child behavioral history and preference scores, returns 2-3 ranked suggestions
- **AdvisorAgent** — generates proactive parent notifications with actionable suggestions
- **MomentPlannerAgent** — plans family activities, calculates goal pacing (seeds/day to meet deadline)
- **PlaceDiscoveryAgent** — finds nearby real-world locations via Google Places API, filters by rating/distance/open status

### Data Flow

```
Frontend (Next.js) → Lena AI Steward (orchestrator)
    → Sub-agents (via agentsAsToolsCall)
    → OpenAI API (LLM)
    → Supabase Postgres (persistent memory)
```

### Database Design (Supabase Postgres)

The database is organized around `family_id` as the tenant boundary:
- **Identity/tenancy:** families, parents, children, parent_child_roles
- **Motivation/action:** goals, quests, quest_streaks
- **Personalization:** preference_categories, child_preferences
- **Planning/recommendation:** activities, calendar_events, advisor_messages, place_cache
- **Memory/audit:** event_logs, family_context_view (read-only AI context layer)

`family_context_view` is the primary AI entry point — agents read this first for a compact household snapshot, then do targeted reads from specific tables as needed.

### Agent Operating Rule

Every AI feature follows this sequence:
1. Read `family_context_view` for the household snapshot
2. Read only the extra tables needed for the specific decision
3. Make a bounded decision tied to one family + one child/event
4. Write the decision into a first-class table (quests, activities, advisor_messages)
5. Append an `event_logs` record for traceability

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Orchestrator | AWS AgentCore (Lena AI Steward) |
| LLM | OpenAI API (via API key) |
| Sub-Agent Communication | AgentCore `agentsAsToolsCall` |
| Database | Supabase Postgres |
| Voice | ElevenLabs API |
| Location | Google Places API |
| AWS Account | `aeonic-hackathon-lotushack` |

## MCP Server

The `bedrock-agentcore-mcp-server` is configured in `.mcp.json` for interacting with AWS AgentCore services (agent runtime, memory, gateway, docs).

## Key Design Constraints

- Quests must include parent guidance prompts (Socratic questions) — never reveal answers directly
- Always return 2-3 options for children (optimal decision count for kids)
- Preference scores update incrementally — no large jumps
- One quest per child per assigned_date — guard against duplicates
- Place discovery uses cache-first pattern to reduce API cost and latency
- Proximity verification is boolean only — no location history stored

## Reference Documents

- `docs/PRD-agent-backend.md` — full product requirements, agent I/O specs, DB schema, frontend communication protocol
- `docs/AI_AGENT_SYSTEM_DESIGN.md` — detailed table-by-table AI reasoning guide, agent responsibility matrix, end-to-end flow diagrams
