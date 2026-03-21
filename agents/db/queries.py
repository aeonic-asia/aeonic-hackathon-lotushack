"""Parameterized SQL queries for Supabase Postgres.

All camelCase column names are quoted to match the TypeORM convention used in the schema.
"""

# --- Read queries ---

GET_FAMILY = """
    SELECT id, name FROM families WHERE id = %s;
"""

GET_PARENTS = """
    SELECT id, name, email
    FROM parents
    WHERE "familyId" = %s;
"""

GET_CHILDREN = """
    SELECT id, name, coins, "familyId"
    FROM children
    WHERE "familyId" = %s;
"""

GET_CHILD_BY_ID = """
    SELECT c.id, c.name, c.coins, c."familyId", f.name AS family_name
    FROM children c
    JOIN families f ON f.id = c."familyId"
    WHERE c.id = %s;
"""

GET_CHILD_PREFERENCES = """
    SELECT cp.score, pc.name AS category_name, pc.description AS category_description
    FROM child_preferences cp
    JOIN preference_categories pc ON pc.id = cp."categoryId"
    WHERE cp."childId" = %s
    ORDER BY cp.score DESC;
"""

GET_CHILD_STREAKS = """
    SELECT "currentStreak", "longestStreak", "lastCompletedDate"
    FROM quest_streaks
    WHERE "childId" = %s
    LIMIT 1;
"""

GET_ACTIVE_QUESTS = """
    SELECT id, title, status, reward, "assignedDate"
    FROM quests
    WHERE "childId" = %s AND status = 'pending'
    ORDER BY "assignedDate" DESC;
"""

GET_CHILD_GOALS = """
    SELECT id, title, target_coins, deadline
    FROM goals
    WHERE "childId" = %s
    ORDER BY deadline ASC NULLS LAST;
"""

CHECK_QUEST_EXISTS = """
    SELECT id FROM quests
    WHERE "childId" = %s AND "assignedDate" = %s
    LIMIT 1;
"""

# --- Write queries ---

INSERT_QUEST = """
    INSERT INTO quests (
        "childId", title, description, category, reward,
        "guidingQuestions", "assignedDate", status
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
    RETURNING id, title, category, reward, "assignedDate";
"""

INSERT_EVENT_LOG = """
    INSERT INTO event_logs (
        "familyId", "childId", "eventType", metadata
    ) VALUES (%s, %s, %s, %s::jsonb)
    RETURNING id;
"""
