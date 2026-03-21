# Lena's Homestead - Agent Backend PRD

## Product Overview

**Lena's Homestead** is an AI-powered parenting companion that transforms daily family life into guided quests. Children grow life skills through gamified activities in a cozy magical homestead, guided by **Lena the Flower Nymph** mascot.

**Core Positioning:** "AI that helps parents guide their children — not replace them."

The AI acts as a **coaching engine** (not an automation engine): it suggests what to do, breaks down challenges into guided steps, and helps parents teach — never gives children answers directly.

---

## Core Product Loops

### Loop 1 — Quest Loop
```
AI generates quests → Parent approves → Child completes → Parent verifies → Seeds earned → Goal progress
```

### Loop 2 — Goal Economy Loop
```
Seeds accumulate → Progress toward meaningful goals (e.g., birthday gift) → Financial literacy lessons
```

### Loop 3 — Family Moments Loop
```
AI suggests shared activity → Proximity verification → Activity timer → Rewards for both parent and child
```

### Loop 4 — Advisor Loop (Proactive AI)
```
Child expresses wish → AI analyzes preferences → Agent discovers nearby places → Parent receives notification → Parent schedules activity
```

---

## Agent Backend Architecture

### AWS Account
- **Account:** `aeonic-hackathon-lotushack`
- **Services:** AWS AgentCore, Amazon Bedrock, (Supabase for DB)

### High-Level Architecture

```
Next.js Frontend
│
├─ Child Adventure Dashboard (dynamic, single-page)
├─ Parent Dashboard
├─ Advisor Notifications
│
↓
🌸 Lena AI Steward (Orchestrator Agent — AWS AgentCore)
│
│  agentsAsToolsCall
│
├─ QuestGeneratorAgent
├─ PreferenceAnalyzerAgent
├─ AdvisorAgent
├─ MomentPlannerAgent
└─ PlaceDiscoveryAgent
        │
        ▼
   External APIs (Google Places, ElevenLabs)
        │
        ▼
   Amazon Bedrock (LLM)
        │
        ▼
   Supabase Postgres (Persistent Memory)
```

### Lena AI Steward — Orchestrator Agent

The **Lena AI Steward** is the central orchestrator. It does NOT perform domain tasks itself. Instead, it:

1. **Recognizes user intent** from frontend requests
2. **Plans a workflow** (which sub-agents to call, in what order)
3. **Calls sub-agents as tools** via `agentsAsToolsCall`
4. **Synthesizes results** into a unified response

**Example orchestration flow** (child selects "See Fish"):
```
Frontend → Lena Steward
  1. calls PreferenceAnalyzerAgent (reads preference scores)
  2. calls MomentPlannerAgent (converts preference into activity)
  3. calls PlaceDiscoveryAgent (finds nearby open places with good reviews)
  4. calls AdvisorAgent (generates parent notification)
  → Returns unified recommendation to frontend
```

---

## Sub-Agent Definitions

### 1. QuestGeneratorAgent

**Purpose:** Generate daily quests across four pillars (Learning, Exercise, Responsibility, Life Habits).

**Input:**
```json
{
  "childAge": 8,
  "focusAreas": ["learning", "exercise", "responsibility"]
}
```

**Output:**
```json
[
  {"title": "Learn 3 new words", "category": "learning", "reward": 10},
  {"title": "Run for 5 minutes", "category": "exercise", "reward": 10},
  {"title": "Help wash dishes", "category": "responsibility", "reward": 10}
]
```

**AI Behavior:**
- Generate age-appropriate quests
- Include parent guidance prompts (Socratic questions) for each quest
- For learning quests: break down difficult problems into step-by-step guiding questions parents can ask
- Never reveal answers directly

**Socratic Guidance Example** (for a math quest):
```
Parent guidance for "What is 3/4 + 2/5?":
  Step 1: Ask — Do the fractions have the same denominator?
  Step 2: Ask — What number can both 4 and 5 divide into?
  Step 3: Guide — How can we convert 3/4 into twentieths?
  Step 4: Guide — Now can we add them?
```

---

### 2. PreferenceAnalyzerAgent

**Purpose:** Analyze child's behavioral history and preference scores to determine top interests.

**Input:**
```json
{
  "childId": "123",
  "preferences": {
    "toy_store": 5,
    "fish": 3,
    "park": 2,
    "dessert": 1
  }
}
```

**Output:**
```json
{
  "topPreferences": ["toy_store", "fish"],
  "suggestedActivities": [
    {"title": "Visit a Toy Store", "icon": "🧸", "mapQuery": "toy store kids"},
    {"title": "See Fish", "icon": "🐠", "mapQuery": "pet store aquarium"},
    {"title": "Park Walk", "icon": "🌳", "mapQuery": "park playground"}
  ]
}
```

**Behavior:**
- Always return 2-3 options (optimal for children's decision-making)
- Use preference scores to rank suggestions
- Increment preference score when child selects an activity
- Stored in Supabase for persistence across sessions

---

### 3. AdvisorAgent

**Purpose:** Generate proactive parent notifications with actionable suggestions.

**Input:**
```json
{
  "childWish": "toy_store",
  "parentFreeTime": "18:30",
  "places": [{"name": "Kids Toy World", "rating": 4.6, "distance": "1.2 km"}]
}
```

**Output:**
```json
{
  "message": "Emma would enjoy visiting a toy store today. Kids Toy World (4.6★, 1.2 km away) is open now.",
  "timeSuggestion": "6:30 PM",
  "actions": ["schedule_moment", "view_nearby", "dismiss"]
}
```

**Notification Types:**
- Child wish fulfillment: "Your child wants to visit a toy store today. Shall I slot that into your available timeframe of ...?"
- Location discovery: "I found a coffee shop with a fish tank nearby matching your child's interests. Would you like to schedule time there?"
- Quest reminders and goal progress updates
- Family moment suggestions based on schedule availability

---

### 4. MomentPlannerAgent

**Purpose:** Plan family activities and calculate goal pacing.

**Features:**
- Convert child preferences into concrete activities
- Calculate savings pace for goals (seeds needed per day to meet deadline)
- Suggest family moment activities themed to the homestead

**Input:**
```json
{
  "goal": {"title": "Birthday Gift", "target": 120, "current": 30, "deadline": "2026-04-15"},
  "preferences": ["fish", "toys"]
}
```

**Output:**
```json
{
  "activity": "Board Game Night",
  "duration": "20 minutes",
  "goalPacing": {
    "remaining": 90,
    "daysLeft": 25,
    "seedsPerDay": 4,
    "onTrack": true
  }
}
```

---

### 5. PlaceDiscoveryAgent

**Purpose:** Find and evaluate nearby real-world locations matching child preferences.

**Why agent-side (not frontend):** The agent can reason about reviews, open hours, and suitability — the frontend cannot.

**Input:**
```json
{
  "activityType": "toy_store",
  "location": {"lat": 10.7626, "lng": 106.6602},
  "radius": 2000
}
```

**Process:**
1. Call Google Places API (Text Search or Nearby Search)
2. Filter: `open_now == true`, `rating > 4.0`, `review_count > 50`
3. Rank by: rating, distance, review count
4. Return top 2-3 places

**Output:**
```json
{
  "suggestedPlaces": [
    {
      "name": "Kids Toy World",
      "rating": 4.6,
      "reviewCount": 320,
      "distance": "1.2 km",
      "address": "District 1",
      "openNow": true,
      "mapsLink": "https://www.google.com/maps/dir/?api=1&destination=Kids+Toy+World"
    }
  ]
}
```

**Google Places API integration:**
- Endpoint: `https://maps.googleapis.com/maps/api/place/textsearch/json`
- Or Nearby Search: `https://maps.googleapis.com/maps/api/place/nearbysearch/json`
- Parameters: `location`, `radius`, `keyword`, `type`

---

## Database Schema (Supabase Postgres)

### Tables

```sql
-- Family unit
CREATE TABLE families (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Users (parents and children)
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id UUID REFERENCES families(id),
  name TEXT NOT NULL,
  role TEXT CHECK (role IN ('parent', 'child')),
  age INT,
  coins INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Goals children save toward
CREATE TABLE goals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  title TEXT NOT NULL,
  target_coins INT NOT NULL,
  deadline DATE,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- AI-generated quests
CREATE TABLE quests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  child_id UUID REFERENCES users(id),
  title TEXT NOT NULL,
  description TEXT,
  category TEXT CHECK (category IN ('learning', 'exercise', 'responsibility', 'habit')),
  reward INT NOT NULL,
  guiding_questions JSONB,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'completed', 'verified', 'rejected')),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Child preference scores (for AI suggestions)
CREATE TABLE preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  child_id UUID REFERENCES users(id) UNIQUE,
  scores JSONB DEFAULT '{}',
  updated_at TIMESTAMPTZ DEFAULT now()
);
-- Example scores: {"toy_store": 5, "fish": 3, "park": 2}

-- AI advisor messages for parents
CREATE TABLE advisor_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  child_id UUID REFERENCES users(id),
  message TEXT NOT NULL,
  type TEXT CHECK (type IN ('wish', 'location', 'goal', 'moment', 'reminder')),
  metadata JSONB,
  status TEXT DEFAULT 'unread' CHECK (status IN ('unread', 'read', 'actioned', 'dismissed')),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Family shared activities
CREATE TABLE activities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id UUID REFERENCES families(id),
  activity TEXT NOT NULL,
  duration INT,
  proximity_verified BOOLEAN DEFAULT false,
  completed BOOLEAN DEFAULT false,
  reward_seeds INT DEFAULT 5,
  reward_tokens INT DEFAULT 3,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Wallet transaction history
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  type TEXT CHECK (type IN ('quest_reward', 'moment_reward', 'redeem', 'loan', 'repayment')),
  amount INT NOT NULL,
  reference_id UUID,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### Agent Memory Layers

| Layer | Storage | Purpose |
|-------|---------|---------|
| Persistent structured data | Supabase Postgres | Profiles, quests, goals, preferences, transactions |
| Preference memory | Supabase `preferences.scores` JSONB | Behavioral learning for suggestion engine |
| Session/context memory | AgentCore internal | Last suggestion, conversation state (prevents repetition) |

---

## Freemium / Token Incentive System

### How It Works
- **Base Free Tier:** 5 AI questions/interactions per day
- **Family Moment Bonus:** Completing a verified family moment unlocks +3 AI tokens
- **Premium Tier:** Unlimited AI guidance, Google Calendar integration, advanced goal planning

### Incentive Alignment
- **Parents:** Get more AI coaching tokens by spending time with their child
- **Children:** Earn seeds (coins) for completing quests AND for participating in family moments (+5 seeds)
- **Both rewarded** for engaging with the app's guidelines together

### Family Moments Verification
- **Proximity Check:** Both devices briefly share GPS location; Haversine distance < 50m confirms co-location
- **No tracking stored** — only a boolean `proximity_verified: true`
- **Privacy-safe:** No location history, no continuous tracking

---

## Proximity Check Implementation

```
Parent taps "Start Moment"
    ↓
Child confirms "Join Moment"
    ↓
Both devices: navigator.geolocation.getCurrentPosition()
    ↓
Haversine distance calculated
    ↓
If distance < 50m → "Homestead connection confirmed"
    ↓
Activity timer starts (e.g., 20 minutes)
    ↓
On completion → rewards distributed
```

Distance formula (Haversine):
```javascript
function calculateDistance(lat1, lon1, lat2, lon2) {
  const R = 6371e3; // Earth radius in meters
  const φ1 = lat1 * Math.PI / 180;
  const φ2 = lat2 * Math.PI / 180;
  const Δφ = (lat2 - lat1) * Math.PI / 180;
  const Δλ = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(Δφ/2)**2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ/2)**2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c; // meters
}
```

---

## Mascot Voice System

**Lena the Flower Nymph** — "Friendly Adventure Guide" archetype.

**Personality:** Curious, encouraging, playful, supportive. Never authoritative or preachy.

**Voice:** Generated via ElevenLabs API. Warm, calm, slightly playful tone.

**Trigger Points (voice plays on):**
- App open: "Welcome back to the homestead!"
- Quest completed: "Wonderful job! You're closer to your goal!"
- Goal milestone: "Only 20 seeds left for the birthday gift!"
- Family moment: "The homestead grows when families spend time together."

**Design Rules:**
- Voice triggers only at key moments (not constantly)
- Never punish or shame
- Frame tasks as adventures, not obligations
- AI must never directly give answers to children

---

## Frontend → Agent Communication

The frontend sends simple intent-based requests:

```json
// Quest generation
{ "intent": "generateQuests", "childId": "123", "childAge": 8 }

// Child wish (triggers advisor flow)
{ "intent": "childWish", "childId": "123", "activity": "see fish" }

// Find nearby places
{ "intent": "findActivityLocation", "activity": "toy_store", "location": {"lat": 10.76, "lng": 106.66} }

// Suggest family moment
{ "intent": "suggestFamilyMoment", "preferences": ["fish", "dessert"] }

// Parent coaching
{ "intent": "parentCoaching", "question": "My child is stuck on fractions" }
```

The Steward agent routes each intent to the appropriate sub-agent(s).

---

## Implementation Priority (Hackathon MVP)

### Must Have (Core Demo)
1. **Lena AI Steward** orchestrator agent on AWS AgentCore
2. **QuestGeneratorAgent** — AI quest generation with Socratic guidance
3. **PreferenceAnalyzerAgent** — 2-3 preference-based suggestions for child
4. **Supabase DB** — children, quests, preferences, goals tables
5. **Frontend integration** — dynamic child dashboard + parent dashboard

### Should Have (Demo Enhancement)
6. **AdvisorAgent** — proactive parent notifications
7. **PlaceDiscoveryAgent** — Google Places integration for location suggestions
8. **ElevenLabs voice** — Lena mascot voice on key interactions
9. **Proximity verification** — GPS-based family moment confirmation

### Nice to Have (If Time Allows)
10. Family moment timer with reward distribution
11. Goal pacing calculator
12. Micro-loan/parent-support system
13. Google Calendar integration (premium feature)

---

## Tech Stack Summary

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js + TailwindCSS |
| AI Orchestrator | AWS AgentCore (Lena AI Steward) |
| LLM | Amazon Bedrock (Claude) |
| Sub-Agents | AgentCore agentsAsToolsCall |
| Database | Supabase Postgres |
| Voice | ElevenLabs API |
| Location | Google Places API |
| Maps Links | Google Maps URL scheme (no API key needed for links) |
| State | React Context / Zustand (frontend) |

---

## Key Design Principles

1. **AI guides parents, never replaces them** — The AI is a coaching engine, not an automation engine
2. **Parents approve everything** — AI suggests, humans confirm
3. **No empty screens** — AI pre-generates content so parents just approve
4. **Seeds, not coins** — Themed currency matching the homestead aesthetic
5. **Quests, not tasks** — Children respond to adventure framing
6. **2-3 choices max for children** — Optimal decision count for kids
7. **The system is the authority** — Parents say "the app suggested this" instead of "I told you to do this"
8. **Privacy-safe location** — Proximity check only, no tracking, no history stored
