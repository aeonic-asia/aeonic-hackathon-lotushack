# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Lena's Homestead** agent backend — AI-powered parenting companion where children grow life skills through gamified quests guided by "Lena the Flower Nymph" mascot. This repo contains the **AWS AgentCore agents** that power the AI backend.

Core principle: "AI guides parents, never replaces them." The AI is a coaching engine — it suggests, breaks down challenges into guided steps, and helps parents teach. It never gives children answers directly.

## Architecture

### Single-Runtime Agent Design

All agents run in a **single AWS AgentCore runtime** (`agents/app.py`). The **Lena AI Steward** is the orchestrator — it recognizes intent, loads family context, and delegates to sub-agents. Sub-agents are Strands `Agent` instances exposed as `@tool` functions that the orchestrator calls in-process (no cross-runtime networking).

**Implemented agents:**
- **QuestGeneratorAgent** — generates daily quest *suggestions* across four pillars (Learning, Exercise, Responsibility, Life Habits) with Socratic parent guidance. **Read-only** — returns JSON suggestions for parent approval; does NOT write to the database.

**Planned agents (not yet implemented):**
- **PreferenceAnalyzerAgent** — analyzes child behavioral history and preference scores, returns 2-3 ranked suggestions
- **AdvisorAgent** — generates proactive parent notifications with actionable suggestions
- **MomentPlannerAgent** — plans family activities, calculates goal pacing (seeds/day to meet deadline)
- **PlaceDiscoveryAgent** — finds nearby real-world locations via Google Places API, filters by rating/distance/open status

### Data Flow

```
Frontend (Next.js) → POST /invocations → Lena AI Steward (orchestrator)
    → Sub-agents (in-process @tool functions)
    → OpenAI API (LLM via Strands OpenAIModel)
    → Supabase Postgres (read-only context assembly)
    → JSON suggestions returned to frontend
    → Parent approves → Frontend writes to Supabase
```

### Database Design (Supabase Postgres)

The database is organized around `family_id` as the tenant boundary:
- **Identity/tenancy:** families, parents, children, parent_child_roles
- **Motivation/action:** goals, quests, quest_streaks
- **Personalization:** preference_categories, child_preferences
- **Planning/recommendation:** activities, calendar_events, advisor_messages, place_cache
- **Memory/audit:** event_logs
- **AI context layer (planned):** family_context_view (read-only view — not yet created)

`family_context_view` is planned as the primary AI entry point. Until created, agents assemble household context via direct queries, encapsulated behind a shared service method (e.g. `FamilyContextService.getSnapshot(familyId)`) so the view can be swapped in later without refactoring agents.

### Agent Operating Rule

Agents are **read-only suggestion engines**. They do not write to the database directly. The flow is:
1. Read family context via `FamilyContextService.get_snapshot(family_id)` (encapsulates the planned `family_context_view`)
2. Read only the extra tables needed for the specific decision
3. Generate a bounded suggestion tied to one family + one child/event
4. Return structured JSON suggestions to the frontend
5. Parent approves/rejects in the frontend; only approved items are persisted by the NestJS API

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Orchestrator | AWS AgentCore (single runtime, Lena AI Steward) |
| Agent Framework | Strands Agents (`strands-agents` Python SDK) |
| LLM | OpenAI API (`gpt-4o` via `strands.models.openai.OpenAIModel`) |
| Sub-Agent Communication | In-process `@tool` functions (not cross-runtime) |
| Database | Supabase Postgres (`pg8000` pure-Python driver from agents) |
| Voice | ElevenLabs API |
| Location | Google Places API |
| AWS Account | `aeonic-hackathon-lotushack` |

## MCP Servers

Two MCP servers are configured in `.mcp.json`:

- **`bedrock-agentcore-mcp-server`** — interacts with AWS AgentCore services (agent runtime, memory, gateway, docs)
- **`postgres`** (`@modelcontextprotocol/server-postgres`) — **read-only** access to the Supabase Postgres database. Use `mcp__postgres__query` with SQL to explore schemas, inspect data, and debug during development. Connection string is in `.mcp.json`. All columns use camelCase (TypeORM convention) — quote identifiers in raw SQL (e.g. `"childId"`).

## Agent Implementation

### Project Structure

```
agents/
  app.py                    # BedrockAgentCoreApp entrypoint (single runtime)
  config.py                 # OpenAI model factory, env config
  requirements.txt          # Python dependencies (needs Python 3.10+)
  db/
    connection.py            # pg8000 DB connection to Supabase (pure Python, no C extensions)
    queries.py               # Parameterized SQL (camelCase-quoted)
    family_context.py        # FamilyContextService — key abstraction for household context
  tools/
    db_tools.py              # @tool wrappers for DB operations
  sub_agents/
    quest_generator.py       # QuestGeneratorAgent + @tool wrapper
  orchestrator/
    agent.py                 # Orchestrator Agent assembly
    prompts.py               # System prompts for all agents
  tests/
    seed_data.sql            # DB migration + seed data
```

### Running Locally

```bash
cd agents/
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PORT=8090 python app.py    # Default port is 8080 (AgentCore convention); override for local dev
```

### Testing

```bash
# Quest generation (returns 5 suggestions across all children, no DB writes)
curl -X POST http://localhost:8090/invocations \
  -H "Content-Type: application/json" \
  -d '{"intent":"generateQuests","familyId":"<uuid>"}'
```

### Deploying to AWS AgentCore

Prerequisites: AWS SSO login and `bedrock-agentcore-starter-toolkit` installed.

```bash
# 1. Login to AWS
aws sso login --profile aeonic-hackathon-lotushack

# 2. Install deployment CLI (once)
pip install bedrock-agentcore-starter-toolkit

# 3. Configure the agent (once, or after structural changes)
cd agents/
AWS_PROFILE=aeonic-hackathon-lotushack agentcore configure --entrypoint app.py --non-interactive --disable-memory

# 4. Deploy with environment variables
AWS_PROFILE=aeonic-hackathon-lotushack agentcore deploy \
  --env "OPENAI_API_KEY=<key>" \
  --env "SUPABASE_DB_URL=<connection-string>"

# 5. Verify deployment
AWS_PROFILE=aeonic-hackathon-lotushack agentcore status
AWS_PROFILE=aeonic-hackathon-lotushack agentcore invoke '{"prompt": "Hello"}'
```

**Deployment gotchas:**
- **Port must be 8080** — AgentCore health check expects this. Use `PORT` env var only for local dev.
- **No C extensions** — use `pg8000` (pure Python) instead of `psycopg2-binary`. Cross-compilation for ARM64 is unreliable.
- **Lazy-init heavy imports** — orchestrator/strands/OpenAI are imported on first invocation, not at module level. AgentCore's container init timeout is 30s.
- **Package size matters** — keep `requirements.txt` lean. Don't include `strands-agents-tools` unless actually used.
- **`--disable-memory`** — we use Supabase for persistence, not AgentCore's built-in memory service.

### Adding a New Sub-Agent

1. Create `agents/sub_agents/<name>.py` with a Strands `Agent` + `@tool` wrapper
2. Add the system prompt to `agents/orchestrator/prompts.py`
3. Register the `@tool` in `orchestrator/agent.py`'s `create_orchestrator()`
4. No infrastructure changes — same single runtime, just redeploy

## Hackathon Credentials (DELETE AFTER HACKATHON)

An IAM user `lena-agent-invoker` was created with long-lived access keys for the Next.js frontend to invoke AgentCore. These credentials are **scoped to `InvokeAgentRuntime` only** on the agent ARN.

- **Access Key ID:** `***REMOVED***`
- **Used in:** Next.js `.env.local` for the `/api/agent` route handler

**Cleanup after hackathon:**
```bash
AWS_PROFILE=aeonic-hackathon-lotushack aws iam delete-access-key --user-name lena-agent-invoker --access-key-id ***REMOVED***
AWS_PROFILE=aeonic-hackathon-lotushack aws iam delete-user-policy --user-name lena-agent-invoker --policy-name InvokeAgentOnly
AWS_PROFILE=aeonic-hackathon-lotushack aws iam delete-user --user-name lena-agent-invoker
```

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
