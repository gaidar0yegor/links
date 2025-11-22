-- Setup 2 test campaigns for sequential posting every 1 minute
-- Each campaign has different categories and browse nodes

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

-- RUSSIAN CHANNEL CAMPAIGNS (@deslwow)
-- Campaign 2: Toys & Games (Family products)
INSERT INTO campaigns (name, status, params) VALUES (
    'russian_toys',
    'running',
    '{"channels": ["@deslwow"], "categories": ["ToysAndGames"], "browse_node_ids": ["632829031"], "max_sales_rank": 6000, "language": "ru"}'::jsonb
) RETURNING id;

-- Set sequential timings for immediate testing (current time + offset)
-- Current time is ~15:32 PM, campaigns will post sequentially

-- Clear existing timings and set new ones starting immediately

DELETE FROM campaign_timings WHERE campaign_id IN (
    SELECT id FROM campaigns WHERE name LIKE 'italian_%' OR name LIKE 'russian_%'
);

-- Campaign 1: Italian Electronics (starts immediately - 15:33:00)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:33:00'::time, '15:34:00'::time FROM campaigns WHERE name = 'italian_electronics';

-- Campaign 2: Russian Toys (1 minute later - 15:34:00)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '15:34:00'::time, '15:35:00'::time FROM campaigns WHERE name = 'russian_toys';

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
