-- ============================================================
-- Migration: Add missing columns to quests table
-- ============================================================
ALTER TABLE quests ADD COLUMN IF NOT EXISTS "description" TEXT;
ALTER TABLE quests ADD COLUMN IF NOT EXISTS "category" VARCHAR NOT NULL DEFAULT 'learning';
ALTER TABLE quests ADD COLUMN IF NOT EXISTS "guidingQuestions" JSONB;

-- ============================================================
-- Migration: Create child_preferences table if missing
-- ============================================================
CREATE TABLE IF NOT EXISTS child_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "childId" UUID NOT NULL REFERENCES children(id) ON DELETE CASCADE,
    "categoryId" UUID NOT NULL REFERENCES preference_categories(id) ON DELETE CASCADE,
    score INTEGER NOT NULL DEFAULT 0,
    "updatedAt" TIMESTAMP NOT NULL DEFAULT now()
);

-- ============================================================
-- Seed Data: One family with parents, children, preferences, goals
-- ============================================================

-- Family
INSERT INTO families (id, name) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'The Smith Family');

-- Parents
INSERT INTO parents (id, "familyId", name, email) VALUES
    ('b1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'Sarah Smith', 'sarah@example.com'),
    ('b1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000001', 'Tom Smith', 'tom@example.com');

-- Children
INSERT INTO children (id, "familyId", name, coins) VALUES
    ('c1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'Emma', 45),
    ('c1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000001', 'Liam', 20);

-- Parent-child roles
INSERT INTO parent_child_roles (id, "parentId", "childId", role) VALUES
    (gen_random_uuid(), 'b1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'mother'),
    (gen_random_uuid(), 'b1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000002', 'mother'),
    (gen_random_uuid(), 'b1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000001', 'father'),
    (gen_random_uuid(), 'b1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'father');

-- Preference categories
INSERT INTO preference_categories (id, name, description) VALUES
    ('d1000000-0000-0000-0000-000000000001', 'learning', 'Educational activities and knowledge building'),
    ('d1000000-0000-0000-0000-000000000002', 'exercise', 'Physical activities and sports'),
    ('d1000000-0000-0000-0000-000000000003', 'toys', 'Toy stores and play activities'),
    ('d1000000-0000-0000-0000-000000000004', 'fish', 'Aquariums and marine life'),
    ('d1000000-0000-0000-0000-000000000005', 'park', 'Outdoor parks and playgrounds'),
    ('d1000000-0000-0000-0000-000000000006', 'art', 'Drawing, painting, and crafts'),
    ('d1000000-0000-0000-0000-000000000007', 'music', 'Singing, instruments, and rhythm'),
    ('d1000000-0000-0000-0000-000000000008', 'dessert', 'Baking and sweet treats');

-- Child preferences (Emma: age 9, loves art and fish)
INSERT INTO child_preferences ("childId", "categoryId", score) VALUES
    ('c1000000-0000-0000-0000-000000000001', 'd1000000-0000-0000-0000-000000000001', 4),
    ('c1000000-0000-0000-0000-000000000001', 'd1000000-0000-0000-0000-000000000002', 3),
    ('c1000000-0000-0000-0000-000000000001', 'd1000000-0000-0000-0000-000000000004', 5),
    ('c1000000-0000-0000-0000-000000000001', 'd1000000-0000-0000-0000-000000000006', 5),
    ('c1000000-0000-0000-0000-000000000001', 'd1000000-0000-0000-0000-000000000007', 2);

-- Child preferences (Liam: age 6, loves toys and parks)
INSERT INTO child_preferences ("childId", "categoryId", score) VALUES
    ('c1000000-0000-0000-0000-000000000002', 'd1000000-0000-0000-0000-000000000001', 2),
    ('c1000000-0000-0000-0000-000000000002', 'd1000000-0000-0000-0000-000000000002', 4),
    ('c1000000-0000-0000-0000-000000000002', 'd1000000-0000-0000-0000-000000000003', 5),
    ('c1000000-0000-0000-0000-000000000002', 'd1000000-0000-0000-0000-000000000005', 5),
    ('c1000000-0000-0000-0000-000000000002', 'd1000000-0000-0000-0000-000000000008', 3);

-- Goals
INSERT INTO goals (id, "childId", title, target_coins, deadline) VALUES
    ('e1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'Art Supplies Set', 100, '2026-04-15'),
    ('e1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'New Toy Car', 60, '2026-04-01');

-- Quest streaks (initialised)
INSERT INTO quest_streaks ("childId", "currentStreak", "longestStreak", "lastCompletedDate") VALUES
    ('c1000000-0000-0000-0000-000000000001', 3, 7, '2026-03-20'),
    ('c1000000-0000-0000-0000-000000000002', 1, 4, '2026-03-20');
