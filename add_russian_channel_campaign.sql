-- Add new Russian campaign for @GovnoIzJopizdeeez channel
-- Will target Russian Home & Garden products

-- First, update the existing russian_garden campaign to post to the new channel
UPDATE campaigns
SET params = jsonb_set(params, '{channels}', '["@GovnoIzJopizdeeez"]'::jsonb)
WHERE name = 'russian_garden';

-- Alternatively, create a new campaign if you prefer to keep both channels active
/*
INSERT INTO campaigns (name, status, params, created_by_user_id) VALUES (
    'russian_garden_second',
    'running',
    '{"channels": ["@GovnoIzJopizdeeez"], "categories": ["Garden"], "browse_node_ids": ["1571288031"], "max_sales_rank": 14000, "language": "ru"}'::jsonb,
    1451953302
) RETURNING id;

-- Add daily timing for the new campaign
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT id, 0, '16:08:00'::time, '16:10:00'::time FROM campaigns WHERE name = 'russian_garden_second'
UNION ALL
SELECT id, 1, '04:08:00'::time, '04:10:00'::time FROM campaigns WHERE name = 'russian_garden_second'
UNION ALL
SELECT id, 2, '04:08:00'::time, '04:10:00'::time FROM campaigns WHERE name = 'russian_garden_second'
UNION ALL
SELECT id, 3, '04:08:00'::time, '04:10:00'::time FROM campaigns WHERE name = 'russian_garden_second'
UNION ALL
SELECT id, 4, '04:08:00'::time, '04:10:00'::time FROM campaigns WHERE name = 'russian_garden_second'
UNION ALL
SELECT id, 5, '03:08:00'::time, '03:10:00'::time FROM campaigns WHERE name = 'russian_garden_second'
UNION ALL
SELECT id, 6, '03:08:00'::time, '03:10:00'::time FROM campaigns WHERE name = 'russian_garden_second';
*/

-- Verify the updated campaign
SELECT
    c.name,
    c.status,
    c.params->>'channels' as channels,
    c.params->>'categories' as categories,
    c.params->>'language' as language
FROM campaigns c
WHERE c.name = 'russian_garden';

-- Check campaign count
SELECT COUNT(*) as total_campaigns FROM campaigns WHERE status = 'running';
