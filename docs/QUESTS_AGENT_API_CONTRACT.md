# Lena AI Agent — API Contract

## Endpoint

```
POST /api/agent
Content-Type: application/json
```

The Next.js route handler (`app/api/agent/route.ts`) proxies requests to the AWS AgentCore runtime. The frontend calls `/api/agent` — never the AWS endpoint directly.

---

## Request Formats

The agent accepts two request styles: **intent-based** (structured) and **prompt-based** (free-form).

### Intent-Based Request

```json
{
  "intent": "<intent-name>",
  "familyId": "<uuid>",
  "childId": "<uuid>",
  ...intent-specific fields
}
```

### Prompt-Based Request

```json
{
  "prompt": "<free-form text>"
}
```

---

## Intents

### `generateQuests`

Generate daily quest suggestions for a child. Returns structured JSON for parent approval — **no database writes**.

**Request:**

```json
{
  "intent": "generateQuests",
  "familyId": "a1000000-0000-0000-0000-000000000001",
  "childId": "c1000000-0000-0000-0000-000000000001",
  "childAge": 9,
  "focusAreas": ["learning", "exercise", "responsibility"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `intent` | `string` | yes | Must be `"generateQuests"` |
| `familyId` | `string (uuid)` | yes | Family ID — used to load household context |
| `childId` | `string (uuid)` | yes | Child to generate quests for |
| `childAge` | `number` | yes | Age of the child (affects difficulty/rewards) |
| `focusAreas` | `string[]` | no | Subset of: `"learning"`, `"exercise"`, `"responsibility"`, `"habit"`. Defaults to `["learning", "exercise", "responsibility"]` |

**Response:**

```json
{
  "intent": "generateQuests",
  "suggestions": [
    {
      "title": "Marine Life Explorer",
      "description": "Discover fascinating facts about five different marine creatures.",
      "category": "learning",
      "reward": 10,
      "guidingQuestions": [
        { "step": 1, "type": "ask", "prompt": "What marine creature interests you?" },
        { "step": 2, "type": "guide", "prompt": "What environment does it live in?" },
        { "step": 3, "type": "encourage", "prompt": "Great job! What else can you find?" }
      ]
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `intent` | `string` | Echo of the request intent |
| `suggestions` | `Quest[]` | Array of quest suggestions (one per focus area) |
| `suggestions[].title` | `string` | Adventure-framed quest name |
| `suggestions[].description` | `string` | One-sentence description |
| `suggestions[].category` | `string` | One of: `"learning"`, `"exercise"`, `"responsibility"`, `"habit"` |
| `suggestions[].reward` | `number` | Seeds reward (5–15, scaled by age/difficulty) |
| `suggestions[].guidingQuestions` | `GuidingQuestion[]` | Socratic parent guidance steps |
| `suggestions[].guidingQuestions[].step` | `number` | Step number |
| `suggestions[].guidingQuestions[].type` | `string` | One of: `"ask"`, `"guide"`, `"encourage"` |
| `suggestions[].guidingQuestions[].prompt` | `string` | Question/prompt for the parent to use |

---

### `childWish` *(planned — not yet implemented)*

Child expresses a wish for an activity.

**Request:**

```json
{
  "intent": "childWish",
  "familyId": "a1000000-0000-0000-0000-000000000001",
  "childId": "c1000000-0000-0000-0000-000000000001",
  "activity": "see fish"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `intent` | `string` | yes | Must be `"childWish"` |
| `familyId` | `string (uuid)` | yes | Family ID |
| `childId` | `string (uuid)` | yes | Child who made the wish |
| `activity` | `string` | yes | What the child wants to do |

**Response:** Free-form text (not yet structured).

---

### `parentCoaching`

Parent asks for guidance on helping their child.

**Request:**

```json
{
  "intent": "parentCoaching",
  "familyId": "a1000000-0000-0000-0000-000000000001",
  "question": "My child is stuck on fractions, how can I help?"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `intent` | `string` | yes | Must be `"parentCoaching"` |
| `familyId` | `string (uuid)` | yes | Family ID — loads context for personalized advice |
| `question` | `string` | yes | Parent's coaching question |

**Response:** Free-form text with Socratic guidance.

---

### Free-Form Prompt

For general conversation with Lena.

**Request:**

```json
{
  "prompt": "What activities are good for a 6-year-old who loves parks?"
}
```

**Response:**

```json
{
  "result": {
    "role": "assistant",
    "content": [
      {
        "text": "Great question! Here are some park adventures..."
      }
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `result.role` | `string` | Always `"assistant"` |
| `result.content[].text` | `string` | Lena's response text |

---

## Response Formats Summary

| Request Type | Response Shape |
|-------------|---------------|
| `generateQuests` | `{ intent, suggestions: Quest[] }` |
| `childWish` | `{ result: { role, content: [{ text }] } }` |
| `parentCoaching` | `{ result: { role, content: [{ text }] } }` |
| Free-form `prompt` | `{ result: { role, content: [{ text }] } }` |
| Error | `{ error: "message" }` with HTTP 500 |

---

## Test Data

Seed data UUIDs for development:

| Entity | UUID | Details |
|--------|------|---------|
| Family | `a1000000-0000-0000-0000-000000000001` | The Smith Family |
| Parent (Sarah) | `b1000000-0000-0000-0000-000000000001` | mother |
| Parent (Tom) | `b1000000-0000-0000-0000-000000000002` | father |
| Child (Emma) | `c1000000-0000-0000-0000-000000000001` | age 9, loves art & fish |
| Child (Liam) | `c1000000-0000-0000-0000-000000000002` | age 6, loves toys & parks |
