-- Setup 10 test campaigns for sequential posting every 2 minutes
-- Each campaign has different categories, sales rank thresholds, and timings

-- Clean up existing campaigns and timings for fresh test
DELETE FROM campaign_timings WHERE campaign_id IN (SELECT id FROM campaigns WHERE name LIKE 'test_%');
DELETE FROM campaigns WHERE name LIKE 'test_%';

-- Campaign 1: Electronics (High quality, low sales rank)
INSERT INTO campaigns (name, status, params) VALUES (
    'test_electronics', 
    'running', 
    '{"channels": ["@test_electronics"], "categories": ["Electronics"], "browse_node_ids": ["1626160311"], "max_sales_rank": 5000, "language": "en"}'::jsonb
) RETURNING id;

-- Campaign 2: Home & Kitchen (Medium quality)  
INSERT INTO campaigns (name, status, params) VALUES (
    'test_home_kitchen', 
    'running', 
    '{"channels": ["@test_home"], "categories": ["Home & Kitchen"], "browse_node_ids": ["524015031"], "max_sales_rank": 10000, "language": "en"}'::jsonb
) RETURNING id;

-- Campaign 3: Fashion (Trending items)
INSERT INTO campaigns (name, status, params) VALUES (
    'test_fashion', 
    'running', 
    '{"channels": ["@test_fashion"], "categories": ["Fashion"], "browse_node_ids": ["1736683031"], "max_sales_rank": 7500, "language": "en"}'::jsonb
) RETURNING id;

-- Campaign 4: Sports & Outdoors
INSERT INTO campaigns (name, status, params) VALUES (
    'test_sports', 
    'running', 
    '{"channels": ["@test_sports"], "categories": ["Sports"], "browse_node_ids": ["524013031"], "max_sales_rank": 8000, "language": "en"}'::jsonb
) RETURNING id;

-- Campaign 5: Books (Higher sales rank threshold)
INSERT INTO campaigns (name, status, params) VALUES (
    'test_books', 
    'running', 
    '{"channels": ["@test_books"], "categories": ["Books"], "browse_node_ids": ["411663031"], "max_sales_rank": 12000, "language": "en"}'::jsonb
) RETURNING id;

-- Campaign 6: Toys & Games (Family products)
INSERT INTO campaigns (name, status, params) VALUES (
    'test_toys', 
    'running', 
    '{"channels": ["@test_toys"], "categories": ["ToysAndGames"], "browse_node_ids": ["632829031"], "max_sales_rank": 6000, "language": "en"}'::jsonb
) RETURNING id;

-- Campaign 7: Beauty & Personal Care
INSERT INTO campaigns (name, status, params) VALUES (
    'test_beauty', 
    'running', 
    '{"channels": ["@test_beauty"], "categories": ["Beauty"], "browse_node_ids": ["619808031"], "max_sales_rank": 9000, "language": "en"}'::jsonb
) RETURNING id;

-- Campaign 8: Automotive
INSERT INTO campaigns (name, status, params) VALUES (
    'test_automotive', 
    'running', 
    '{"channels": ["@test_auto"], "categories": ["Automotive"], "browse_node_ids": ["1571283031"], "max_sales_rank": 11000, "language": "en"}'::jsonb
) RETURNING id;

-- Campaign 9: Health & Household
INSERT INTO campaigns (name, status, params) VALUES (
    'test_health', 
    'running', 
    '{"channels": ["@test_health"], "categories": ["Health"], "browse_node_ids": ["1571286031"], "max_sales_rank": 13000, "language": "en"}'::jsonb
) RETURNING id;

-- Campaign 10: Garden & Outdoors
INSERT INTO campaigns (name, status, params) VALUES (
    'test_garden', 
    'running', 
    '{"channels": ["@test_garden"], "categories": ["Garden"], "browse_node_ids": ["1571288031"], "max_sales_rank": 14000, "language": "en"}'::jsonb
) RETURNING id;

-- Set sequential timings for immediate testing (current time + offset)
-- Current time is ~11:35 AM, campaigns will post every 2 minutes in sequence

-- Campaign 1: Electronics (starts immediately)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time) 
SELECT id, 0, '11:35:00'::time, '11:37:00'::time FROM campaigns WHERE name = 'test_electronics';

-- Campaign 2: Home & Kitchen (2 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time) 
SELECT id, 0, '11:37:00'::time, '11:39:00'::time FROM campaigns WHERE name = 'test_home_kitchen';

-- Campaign 3: Fashion (4 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time) 
SELECT id, 0, '11:39:00'::time, '11:41:00'::time FROM campaigns WHERE name = 'test_fashion';

-- Campaign 4: Sports (6 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time) 
SELECT id, 0, '11:41:00'::time, '11:43:00'::time FROM campaigns WHERE name = 'test_sports';

-- Campaign 5: Books (8 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time) 
SELECT id, 0, '11:43:00'::time, '11:45:00'::time FROM campaigns WHERE name = 'test_books';

-- Campaign 6: Toys (10 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time) 
SELECT id, 0, '11:45:00'::time, '11:47:00'::time FROM campaigns WHERE name = 'test_toys';

-- Campaign 7: Beauty (12 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time) 
SELECT id, 0, '11:47:00'::time, '11:49:00'::time FROM campaigns WHERE name = 'test_beauty';

-- Campaign 8: Automotive (14 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time) 
SELECT id, 0, '11:49:00'::time, '11:51:00'::time FROM campaigns WHERE name = 'test_automotive';

-- Campaign 9: Health (16 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time) 
SELECT id, 0, '11:51:00'::time, '11:53:00'::time FROM campaigns WHERE name = 'test_health';

-- Campaign 10: Garden (18 minutes later)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time) 
SELECT id, 0, '11:53:00'::time, '11:55:00'::time FROM campaigns WHERE name = 'test_garden';

-- Verification query
SELECT 
    c.id, 
    c.name, 
    c.status,
    ct.start_time, 
    ct.end_time,
    c.params->>'max_sales_rank' as sales_rank_threshold,
    c.params->>'categories' as categories,
    c.params->>'channels' as channels
FROM campaigns c 
JOIN campaign_timings ct ON c.id = ct.campaign_id 
WHERE c.name LIKE 'test_%'
ORDER BY ct.start_time;
