# Lena's Homestead - AI Agent System Design

## Purpose

This document explains how the current database structure supports AI-agent behavior in Lena's Homestead. It is based on the active schema in `src/migrations/2026-03-21-mvp-final-schema.sql` and the registered TypeORM entities under `src/**`.

The core design idea is simple:

- `families` is the tenant and reasoning boundary.
- Operational tables hold the current household state.
- Behavioral tables hold memory of what happened.
- `family_context_view` composes the minimum AI-readable household snapshot.
- AI agents should read from stable context first, then write back to explicit operational records rather than inventing hidden state.

## Current Active Schema

The active database model contains 14 tables and 1 AI-facing view:

1. `families`
2. `parents`
3. `children`
4. `parent_child_roles`
5. `goals`
6. `quests`
7. `quest_streaks`
8. `preference_categories`
9. `child_preferences`
10. `activities`
11. `advisor_messages`
12. `calendar_events`
13. `event_logs`
14. `place_cache`
15. `family_context_view`

## AI-Oriented Architecture

```text
Parent / Child App
        |
        v
NestJS API
        |
        +--> Transactional tables
        |     families
        |     parents
        |     children
        |     parent_child_roles
        |     goals
        |     quests
        |     quest_streaks
        |     preference_categories
        |     child_preferences
        |     activities
        |     advisor_messages
        |     calendar_events
        |     event_logs
        |     place_cache
        |
        +--> family_context_view
                 |
                 v
        Lena AI Steward / Orchestrator
                 |
                 +--> Quest Generator
                 +--> Preference Learner
                 +--> Moment Planner
                 +--> Advisor Agent
                 +--> Place Discovery Agent
```

## Design Principles For Agent Usage

### 1. Family-scoped reasoning

Every meaningful AI decision should begin with `family_id`. This prevents cross-family leakage and gives the orchestrator a clean tenant boundary for memory, scheduling, and recommendation logic.

### 2. Explicit state over hidden memory

The agent should not rely on prompt-only memory. If a recommendation matters later, it should be persisted in a table such as `advisor_messages`, `activities`, `quests`, or `event_logs`.

### 3. Separate current state from historical evidence

- Current state lives in tables like `children`, `quests`, `quest_streaks`, `child_preferences`, and `calendar_events`.
- Historical evidence lives in `event_logs` and older `activities` / `advisor_messages`.

This separation makes agent reasoning easier:

- "What is true now?" uses operational tables.
- "Why do we believe this?" uses event history.

### 4. Read-optimized context assembly

`family_context_view` exists so the agent can fetch one family snapshot without reconstructing the household from many joins every time.

## Table-by-Table Reasoning

| Table | Role In The System | Why The AI Needs It | Main Relations | Typical Agent Behavior |
|---|---|---|---|---|
| `families` | Household root record | Defines the tenant boundary and shared context | Parent of `parents`, `children`, `activities`, `advisor_messages`, `calendar_events`, `event_logs` | Orchestrator starts here and scopes every workflow by family |
| `parents` | Guardian identities | Determines who receives suggestions and whose availability matters | Belongs to `families`; parent of `calendar_events`, `advisor_messages`, `parent_child_roles` | Advisor and planner use parents as delivery and scheduling targets |
| `children` | Child profiles and coin balance | Represents the main subject of questing, learning, and personalization | Belongs to `families`; parent of `goals`, `quests`, `quest_streaks`, `child_preferences`, `activities`, `advisor_messages`, `event_logs`, `parent_child_roles` | Most agents reason primarily per child inside a family |
| `parent_child_roles` | Parent-child bridge with semantics | Adds relational meaning such as mother, father, guardian | Bridge from `parents` to `children` | Lets agents explain or filter actions by guardian relationship |
| `goals` | Savings targets | Gives purpose to coin rewards and lets the AI align quests with motivation | Belongs to `children` | Quest generator can tune rewards or quest themes toward active goals |
| `quests` | Daily task state | Stores the actionable work the child is expected to complete | Belongs to `children` | Quest generator writes, dashboard reads, completion flow updates status |
| `quest_streaks` | Habit summary | Encodes momentum for gamification and encouragement | Belongs to `children` | Completion logic updates streak counters; advisor references streak health |
| `preference_categories` | Controlled vocabulary for interests | Prevents hardcoded columns and keeps preferences extensible | Parent of `child_preferences` | Preference learner maps evidence into reusable category labels |
| `child_preferences` | Numeric preference memory | Stores per-child affinity scores that make recommendations personalized | Bridge from `children` to `preference_categories` | Learner updates scores; quest, advisor, and planner read top interests |
| `activities` | Real-world or family moments | Captures what the family actually did and whether it was completed | Belongs to `families` and `children` | Planner proposes or records moments; learner uses them as evidence |
| `advisor_messages` | AI-to-parent recommendation log | Persists what the AI suggested, to whom, and whether it was seen | Belongs to `families`, `parents`, and `children` | Advisor writes suggestions; notification flow updates delivery/read status |
| `calendar_events` | Parent availability | Provides scheduling constraints for recommendations | Belongs to `parents` and `families` | Moment planner finds open windows before proposing activities |
| `event_logs` | Behavioral audit trail | Preserves why state changed and what the AI observed | Belongs to `families` and `children` | All agents should append evidence-worthy events here |
| `place_cache` | External search cache | Reduces repeated place lookups and stabilizes recommendation latency | Standalone | Place discovery reads cache first, then writes cached results |
| `family_context_view` | Read-only AI context layer | Produces a compact household snapshot for prompting and planning | Derived from family, parent, child, streak, preference, quest, activity tables | Orchestrator reads this first before deeper queries |

## Relational Interaction Model

### Household ownership

```text
families
  -> parents
  -> children
  -> activities
  -> advisor_messages
  -> calendar_events
  -> event_logs
```

This means a family is the natural top-level aggregate. If a family is deleted, related operational and behavioral records are also removed through cascade rules.

### Parent-child semantic bridge

```text
parents -> parent_child_roles -> children
```

This bridge matters because a parent is not just any adult in the family. The role gives the AI relational context for messaging, permissions, and future policy decisions.

### Child-centric personalization branch

```text
children
  -> goals
  -> quests
  -> quest_streaks
  -> child_preferences -> preference_categories
```

This is the most important branch for AI personalization. It combines motivation, current tasks, habit continuity, and learned interests.

### Recommendation branch

```text
calendar_events -> scheduling constraints
activities -> real-world evidence
place_cache -> external place knowledge
advisor_messages -> outbound parent communication
event_logs -> long-term memory and traceability
```

This branch turns raw household context into explainable recommendations.

## End-To-End Agent Flows

### 1. Family Context Load Flow

Used when the orchestrator needs to understand one household before deciding anything.

```text
Input: family_id
   |
   v
Read family_context_view
   |
   +--> parents summary
   +--> children summary
   +--> streak summary
   +--> top preferences
   +--> active quests
   +--> recent activities
   |
   v
Optional deep reads from goals, calendar_events, event_logs, advisor_messages
   |
   v
Agent reasoning and decision
```

Why this flow is correct:

- It minimizes prompt assembly cost.
- It keeps the first read deterministic.
- It avoids the agent making decisions from partial joins or missing context.

### 2. Daily Quest Generation Flow

Used by a `QuestGeneratorAgent`.

```text
family_context_view
   + goals
   + recent event_logs
   |
   v
Select child needing a daily quest
   |
   v
Check existing quest by child_id + assigned_date
   |
   +--> if exists: do not duplicate
   +--> if missing: create new quest
   |
   v
Write quests row
   |
   v
Write event_logs row with generation metadata
```

Tables involved:

- Read: `family_context_view`, `goals`, `quests`, `event_logs`
- Write: `quests`, `event_logs`

Why the tables work together:

- `child_preferences` helps choose content the child is likely to enjoy.
- `goals` helps choose reward intensity or narrative framing.
- `quests` holds the actionable task.
- `event_logs` records why that task was chosen.

### 3. Quest Completion And Streak Update Flow

Used when a child completes a quest.

```text
Quest marked completed
   |
   v
Update quests.status and quests.completed_at
   |
   v
Increment children.coins
   |
   v
Read and update quest_streaks
   |
   v
Write event_logs with before/after streak metadata
```

Tables involved:

- Read: `quests`, `quest_streaks`, `children`
- Write: `quests`, `children`, `quest_streaks`, `event_logs`

Why this matters for AI:

- The quest itself is transactional truth.
- Coins are the visible reward state.
- Streaks are a compressed habit signal.
- Event logs preserve the full explanation trail for later coaching.

### 4. Preference Learning Flow

Used by a `PreferenceLearnerAgent`.

```text
Activities completed
Advisor messages accepted
Quest outcomes observed
   |
   v
Convert evidence into category signals
   |
   v
Upsert child_preferences scores
   |
   v
Append event_logs describing the score change rationale
```

Tables involved:

- Read: `activities`, `advisor_messages`, `quests`, `event_logs`, `preference_categories`
- Write: `child_preferences`, `event_logs`

Why this model is strong:

- Categories are extensible.
- Scores stay child-specific.
- Evidence can come from multiple experiences, not one isolated event.

### 5. Family Moment Planning Flow

Used by a `MomentPlannerAgent`.

```text
Read family_context_view
   + calendar_events
   + child_preferences
   + recent activities
   |
   v
Infer best time and activity type
   |
   v
Optional place lookup through place_cache
   |
   v
Create advisor_messages recommendation
   |
   v
Optional create activities record if pre-booking a family moment
   |
   v
Log event in event_logs
```

Tables involved:

- Read: `family_context_view`, `calendar_events`, `activities`, `child_preferences`, `place_cache`
- Write: `advisor_messages`, optionally `activities`, `event_logs`, optionally `place_cache`

Why the data split matters:

- `calendar_events` answers "when can they go?"
- `child_preferences` answers "what will the child likely enjoy?"
- `activities` answers "what have they already done recently?"
- `advisor_messages` answers "what has already been suggested?"

### 6. Place Discovery Flow

Used by a `PlaceDiscoveryAgent`.

```text
Receive search intent
   |
   v
Check place_cache by query
   |
   +--> hit: return cached places
   +--> miss: call external provider, then cache results
   |
   v
Return location options to planner / advisor
```

Tables involved:

- Read: `place_cache`
- Write: `place_cache`

Why this table is intentionally isolated:

- It is infrastructure support, not family truth.
- Cache entries can be reused across families if the query is the same.
- It lowers latency and external API cost.

### 7. Parent Advice Delivery Flow

Used by an `AdvisorAgent`.

```text
Agent decides recommendation
   |
   v
Create advisor_messages row
   |
   v
Delivery system marks status from pending -> sent -> read
   |
   v
event_logs captures suggestion lifecycle if needed
```

Tables involved:

- Read: `parents`, `children`, `advisor_messages`
- Write: `advisor_messages`, optionally `event_logs`

Why this matters:

- The suggestion becomes auditable.
- The product can avoid repeating ignored advice too often.
- The AI can learn what kinds of recommendations parents actually engage with.

## Why Each Table Exists In The AI Memory Model

### Identity and tenancy

- `families`, `parents`, `children`, `parent_child_roles`
- These define who the AI is helping and the boundaries for safe reasoning.

### Motivation and action

- `goals`, `quests`, `quest_streaks`
- These define what the child is trying to achieve, what work is active, and whether habits are forming.

### Personalization

- `preference_categories`, `child_preferences`
- These let the AI convert experience into reusable preference signals.

### Planning and recommendation

- `activities`, `calendar_events`, `advisor_messages`, `place_cache`
- These support discovery, scheduling, suggestion generation, and delivery tracking.

### Memory and explainability

- `event_logs`, `family_context_view`
- `event_logs` is durable history.
- `family_context_view` is a read model for fast reasoning, not the system of record.

## Recommended Agent Responsibilities

| Agent | Primary Reads | Primary Writes | Notes |
|---|---|---|---|
| Orchestrator | `family_context_view` | none directly if possible | Should delegate specialized writes to domain agents/services |
| Quest Generator | `family_context_view`, `goals`, `quests` | `quests`, `event_logs` | Must respect one quest per child per assigned date |
| Preference Learner | `activities`, `quests`, `advisor_messages`, `event_logs` | `child_preferences`, `event_logs` | Should update scores gradually, not with large jumps |
| Moment Planner | `family_context_view`, `calendar_events`, `activities`, `place_cache` | `advisor_messages`, optionally `activities`, `event_logs` | Should avoid recommending overly repetitive moments |
| Advisor Agent | `parents`, `children`, `advisor_messages` | `advisor_messages`, `event_logs` | Tracks suggestion lifecycle |
| Place Discovery Agent | `place_cache` | `place_cache` | Should be reusable infrastructure for planners/advisors |

## Current-State Observations From The Schema

These are not blockers for the document, but they matter when turning the design into production agent logic.

1. `quest_streaks` does not currently enforce a unique `child_id` at the database level.
   This means application code should treat it as one logical streak record per child and guard against duplicates.

2. `activities` is family-scoped and child-linked, but each row points to one `child_id`.
   If one activity truly involves multiple children, the current schema models that as multiple rows or as one primary child with family context.

3. `advisor_messages` is both family-scoped and child-specific.
   That is useful for personalized advice, but broader family-wide recommendations may need one row per target child or a later schema extension.

4. `family_context_view` is a convenience read model, not a full memory model.
   It summarizes top preferences, pending quests, and recent activities, but deep reasoning may still need direct reads from `goals`, `calendar_events`, `advisor_messages`, and `event_logs`.

5. Empty legacy placeholders exist in `src/advisor/advisor.entity.ts` and `src/preferences/preference.entity.ts`.
   They do not appear to be part of the active AI data model described by the migration and registered modules.

## Recommended Operating Rule For The AI Layer

Use this sequence for every AI feature:

1. Read `family_context_view` for the fast household snapshot.
2. Read only the extra operational tables needed for the specific decision.
3. Make a bounded decision tied to one family and one child or household event.
4. Write the decision into a first-class table such as `quests`, `activities`, or `advisor_messages`.
5. Append an `event_logs` record so the system keeps a trace of why the decision happened.

This pattern keeps the AI explainable, testable, and compatible with future analytics.

## Summary

The current database is already shaped well for AI-agent usage because it separates:

- household identity,
- child personalization,
- actionable tasks,
- recommendation delivery,
- and behavioral memory.

The most important relational idea is that `families` defines the reasoning boundary, `children` defines the personalization focus, and `event_logs` preserves decision evidence. `family_context_view` then acts as the AI-ready read model that turns those normalized tables into a usable prompt context.
