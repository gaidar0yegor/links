CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'timingless',
    params JSONB,
    created_by_user_id BIGINT,
    min_review_count INTEGER DEFAULT 0,
    posting_frequency REAL DEFAULT 0,
    track_id VARCHAR(100),
    last_post_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE campaign_timings (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    UNIQUE(campaign_id, day_of_week, start_time)
);

CREATE TABLE product_queue (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    asin VARCHAR(20) NOT NULL,
    title TEXT,
    price REAL,
    currency VARCHAR(10),
    rating REAL,
    review_count INTEGER,
    sales_rank INTEGER,
    image_urls TEXT[], -- Changed from image_url TEXT
    affiliate_link TEXT,
    browse_node_ids TEXT[],
    quality_score REAL,
    features TEXT[],
    status VARCHAR(50) NOT NULL DEFAULT 'queued', -- queued, posted, rejected
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    posted_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE statistics_log (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    channel_name VARCHAR(255),
    asin VARCHAR(20),
    final_link TEXT,
    post_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Function to update 'updated_at' timestamp automatically
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for 'campaigns' table
CREATE TRIGGER set_timestamp_campaigns
BEFORE UPDATE ON campaigns
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

-- Trigger for 'product_queue' table
CREATE TRIGGER set_timestamp_product_queue
BEFORE UPDATE ON product_queue
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();
