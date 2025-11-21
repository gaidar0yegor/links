-- Setup 10 test campaigns for sequential posting every 2 minutes
-- Each campaign has different categories, sales rank thresholds, and timings

-- Clean up existing campaigns and timings for fresh test
DELETE FROM campaign_timings WHERE campaign_id IN (SELECT id FROM campaigns WHERE name LIKE 'test_%');
DELETE FROM campaigns WHERE name LIKE 'test_%';

-- Add missing columns for enhanced functionality (if not exists)
DO $$ BEGIN
    -- Add created_by_user_id column for admin notifications
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='campaigns' AND column_name='created_by_user_id') THEN
        ALTER TABLE campaigns ADD COLUMN created_by_user_id BIGINT;
    END IF;

    -- Add review filter columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='campaigns' AND column_name='min_review_count') THEN
        ALTER TABLE campaigns ADD COLUMN min_review_count INTEGER DEFAULT 0;
    END IF;

    -- Add posting frequency column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='campaigns' AND column_name='posting_frequency') THEN
        ALTER TABLE campaigns ADD COLUMN posting_frequency INTEGER DEFAULT 0; -- 0 = continuous
    END IF;

    -- Add track_id column for campaign-specific tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='campaigns' AND column_name='track_id') THEN
        ALTER TABLE campaigns ADD COLUMN track_id VARCHAR(100);
    END IF;
END $$;

-- ITALIAN CHANNEL CAMPAIGNS (@CheapAmazon3332234)
-- Campaign 1: Electronics (High quality, low sales rank)
INSERT INTO campaigns (name, status, params) VALUES (
    'italian_electronics',
    'running',
    '{"channels": ["@CheapAmazon3332234"], "categories": ["Electronics"], "browse_node_ids": ["1626160311"], "max_sales_rank": 5000, "language": "it"}'::jsonb
) RETURNING id;

-- Campaign 2: Home & Kitchen (Medium quality)
INSERT INTO campaigns (name, status, params) VALUES (
    'italian_home_kitchen',
    'running',
    '{"channels": ["@CheapAmazon3332234"], "categories": ["Home & Kitchen"], "browse_node_ids": ["524015031"], "max_sales_rank": 10000, "language": "it"}'::jsonb
) RETURNING id;

-- Campaign 3: Fashion (Trending items)
INSERT INTO campaigns (name, status, params) VALUES (
    'italian_fashion',
    'running',
    '{"channels": ["@CheapAmazon3332234"], "categories": ["Fashion"], "browse_node_ids": ["1736683031"], "max_sales_rank": 7500, "language": "it"}'::jsonb
) RETURNING id;

-- Campaign 4: Sports & Outdoors
INSERT INTO campaigns (name, status, params) VALUES (
    'italian_sports',
    'running',
    '{"channels": ["@CheapAmazon3332234"], "categories": ["Sports"], "browse_node_ids": ["524013031"], "max_sales_rank": 8000, "language": "it"}'::jsonb
) RETURNING id;

-- Campaign 5: Books (Higher sales rank threshold)
INSERT INTO campaigns (name, status, params) VALUES (
    'italian_books',
    'running',
    '{"channels": ["@CheapAmazon3332234"], "categories": ["Books"], "browse_node_ids": ["411663031"], "max_sales_rank": 12000, "language": "it"}'::jsonb
) RETURNING id;

-- RUSSIAN CHANNEL CAMPAIGNS (@deslwow)
-- Campaign 6: Toys & Games (Family products)
INSERT INTO campaigns (name, status, params) VALUES (
    'russian_toys',
    'running',
    '{"channels": ["@deslwow"], "categories": ["ToysAndGames"], "browse_node_ids": ["632829031"], "max_sales_rank": 6000, "language": "ru"}'::jsonb
) RETURNING id;

-- Campaign 7: Beauty & Personal Care
INSERT INTO campaigns (name, status, params) VALUES (
    'russian_beauty',
    'running',
    '{"channels": ["@deslwow"], "categories": ["Beauty"], "browse_node_ids": ["619808031"], "max_sales_rank": 9000, "language": "ru"}'::jsonb
) RETURNING id;

-- Campaign 8: Automotive
INSERT INTO campaigns (name, status, params) VALUES (
    'russian_automotive',
    'running',
    '{"channels": ["@deslwow"], "categories": ["Automotive"], "browse_node_ids": ["1571283031"], "max_sales_rank": 11000, "language": "ru"}'::jsonb
) RETURNING id;

-- Campaign 9: Health & Household
INSERT INTO campaigns (name, status, params) VALUES (
    'russian_health',
    'running',
    '{"channels": ["@deslwow"], "categories": ["Health"], "browse_node_ids": ["1571286031"], "max_sales_rank": 13000, "language": "ru"}'::jsonb
) RETURNING id;

-- Campaign 10: Garden & Outdoors
INSERT INTO campaigns (name, status, params) VALUES (
    'russian_garden',
    'running',
    '{"channels": ["@deslwow"], "categories": ["Garden"], "browse_node_ids": ["1571288031"], "max_sales_rank": 14000, "language": "ru"}'::jsonb
) RETURNING id;

-- Set sequential timings for immediate testing (current time + offset)
-- Current time is ~11:35 AM, campaigns will post every 2 minutes in sequence

-- Update timings for immediate posting (current time ~15:07 PM)
-- Clear existing timings and set new ones starting immediately

DELETE FROM campaign_timings WHERE campaign_id IN (
    SELECT id FROM campaigns WHERE name LIKE 'italian_%' OR name LIKE 'russian_%'
);

-- Campaign 1: Italian Electronics (starts in 1 minute)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:08:00'::time, '15:10:00'::time FROM campaigns WHERE name = 'italian_electronics';

-- Campaign 2: Italian Home & Kitchen (3 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:10:00'::time, '15:12:00'::time FROM campaigns WHERE name = 'italian_home_kitchen';

-- Campaign 3: Italian Fashion (5 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:12:00'::time, '15:14:00'::time FROM campaigns WHERE name = 'italian_fashion';

-- Campaign 4: Italian Sports (7 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:14:00'::time, '15:16:00'::time FROM campaigns WHERE name = 'italian_sports';

-- Campaign 5: Italian Books (9 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:16:00'::time, '15:18:00'::time FROM campaigns WHERE name = 'italian_books';

-- Campaign 6: Russian Toys (11 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:18:00'::time, '15:20:00'::time FROM campaigns WHERE name = 'russian_toys';

-- Campaign 7: Russian Beauty (13 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:20:00'::time, '15:22:00'::time FROM campaigns WHERE name = 'russian_beauty';

-- Campaign 8: Russian Automotive (15 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:22:00'::time, '15:24:00'::time FROM campaigns WHERE name = 'russian_automotive';

-- Campaign 9: Russian Health (17 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:24:00'::time, '15:26:00'::time FROM campaigns WHERE name = 'russian_health';

-- Campaign 10: Russian Garden (19 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:26:00'::time, '15:28:00'::time FROM campaigns WHERE name = 'russian_garden';

-- Verification query
SELECT
    c.id,
    c.name,
    c.status,
    ct.start_time,
    ct.end_time,
    c.params->>'max_sales_rank' as sales_rank_threshold,
    c.params->>'categories' as categories,
    c.params->>'language' as language,
    c.params->>'channels' as channels
FROM campaigns c
JOIN campaign_timings ct ON c.id = ct.campaign_id
WHERE c.name LIKE 'italian_%' OR c.name LIKE 'russian_%'
ORDER BY ct.start_time;
