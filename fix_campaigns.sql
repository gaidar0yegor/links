-- DELETE unnecessary campaigns - keep only 3 working campaigns
-- 1. russian_garden (new channel @GovnoIzJopizdeeez)
-- 2. italian_sports (has posted, working)
-- 3. italian_home_kitchen (good catalog)

-- First, find and delete undesired campaigns
DELETE FROM posts WHERE campaign_id IN (
    SELECT id FROM campaigns
    WHERE name NOT IN (
        'russian_garden',
        'italian_sports',
        'italian_home_kitchen'
    )
);

DELETE FROM campaign_posted_products WHERE campaign_id IN (
    SELECT id FROM campaigns
    WHERE name NOT IN (
        'russian_garden',
        'italian_sports',
        'italian_home_kitchen'
    )
);

DELETE FROM campaign_timings WHERE campaign_id IN (
    SELECT id FROM campaigns
    WHERE name NOT IN (
        'russian_garden',
        'italian_sports',
        'italian_home_kitchen'
    )
);

DELETE FROM campaigns WHERE name NOT IN (
    'russian_garden',
    'italian_sports',
    'italian_home_kitchen'
);

-- LOWER quality thresholds so posts happen immediately for testing
-- Drop max_sales_rank from 5000/8000/9000/etc to MUCH lower values
UPDATE campaigns
SET params = jsonb_set(
    CASE
        WHEN params->>'max_sales_rank' IS NOT NULL THEN params
        ELSE jsonb_set(params, '{max_sales_rank}', '"50000"')
    END,
    '{max_sales_rank}',
    '"50000"'
)
WHERE name IN ('russian_garden', 'italian_sports', 'italian_home_kitchen');

-- Reset posting history for italian_home_kitchen and italian_sports to force new posts
-- Keep russian_garden as is since it's new
DELETE FROM campaign_posted_products
WHERE campaign_id IN (
    SELECT id FROM campaigns WHERE name IN ('italian_sports', 'italian_home_kitchen')
);

-- Add better Timing Schedules - reduce waiting, post more frequently
UPDATE campaign_timings
SET start_time = CASE
    WHEN campaign_id = (SELECT id FROM campaigns WHERE name = 'russian_garden') THEN '10:00:00'::time
    WHEN campaign_id = (SELECT id FROM campaigns WHERE name = 'italian_sports') THEN '11:00:00'::time
    WHEN campaign_id = (SELECT id FROM campaigns WHERE name = 'italian_home_kitchen') THEN '12:00:00'::time
    ELSE start_time
END,
end_time = CASE
    WHEN campaign_id = (SELECT id FROM campaigns WHERE name = 'russian_garden') THEN '22:00:00'::time
    WHEN campaign_id = (SELECT id FROM campaigns WHERE name = 'italian_sports') THEN '22:00:00'::time
    WHEN campaign_id = (SELECT id FROM campaigns WHERE name = 'italian_home_kitchen') THEN '22:00:00'::time
    ELSE end_time
END
WHERE EXISTS (
    SELECT 1 FROM campaigns c
    WHERE c.id = campaign_timings.campaign_id
    AND c.name IN ('russian_garden', 'italian_sports', 'italian_home_kitchen')
);

-- Make timing truly daily for better testing (reduces waiting)
UPDATE campaign_timings
SET day_of_week = -1
WHERE campaign_id IN (
    SELECT id FROM campaigns WHERE name IN ('russian_garden', 'italian_sports', 'italian_home_kitchen')
);
