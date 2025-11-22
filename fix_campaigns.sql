-- Fix to make campaigns run every day instead of just Mondays
-- Run this to fix the scheduling issue

-- DELETE existing single-day timings (only Mondays were set up)
DELETE FROM campaign_timings WHERE day_of_week = 0;

-- Add daily schedules for ALL 7 days of the week for each campaign
-- This creates timing entries for Monday (0) through Sunday (6)
INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
SELECT
    c.id,
    days.day_of_week,
    CASE
        WHEN days.day_of_week = 0 THEN '15:08:00'::time  -- Monday start
        WHEN days.day_of_week = 1 THEN '03:08:00'::time  -- Tuesday start
        WHEN days.day_of_week = 2 THEN '03:08:00'::time  -- Wednesday start
        WHEN days.day_of_week = 3 THEN '03:08:00'::time  -- Thursday start
        WHEN days.day_of_week = 4 THEN '03:08:00'::time  -- Friday start
        WHEN days.day_of_week = 5 THEN '03:08:00'::time  -- Saturday start
        WHEN days.day_of_week = 6 THEN '03:08:00'::time  -- Sunday start
    END,
    CASE
        WHEN days.day_of_week = 0 THEN '15:10:00'::time  -- Monday end
        WHEN days.day_of_week = 1 THEN '03:10:00'::time  -- Tuesday end
        WHEN days.day_of_week = 2 THEN '03:10:00'::time  -- Wednesday end
        WHEN days.day_of_week = 3 THEN '03:10:00'::time  -- Thursday end
        WHEN days.day_of_week = 4 THEN '03:10:00'::time  -- Friday end
        WHEN days.day_of_week = 5 THEN '03:10:00'::time  -- Saturday end
        WHEN days.day_of_week = 6 THEN '03:10:00'::time  -- Sunday end
    END
FROM campaigns c
CROSS JOIN (VALUES (0), (1), (2), (3), (4), (5), (6)) AS days(day_of_week)
WHERE c.name LIKE 'italian_%' OR c.name LIKE 'russian_%';

-- Alternative: Simpler approach using the new code support for daily schedules
-- UPDATE campaign_timings SET day_of_week = -1 WHERE campaign_id IN (
--     SELECT id FROM campaigns WHERE name LIKE 'italian_%' OR name LIKE 'russian_%'
-- );
