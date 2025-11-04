CREATE TABLE scan_jobs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR,
    data_type VARCHAR(50) NOT NULL,
    search_data TEXT NOT NULL,
    custom_regex VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    total_tools INTEGER DEFAULT 5,
    completed_tools INTEGER DEFAULT 0,
    scan_source VARCHAR(20) DEFAULT 'manual' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scan_results (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES scan_jobs(id),
    tool_name VARCHAR(50) NOT NULL,
    result_type VARCHAR(50) NOT NULL,
    result_data JSONB,
    severity VARCHAR(20),
    confidence_score FLOAT,
    source_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tool_status (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES scan_jobs(id),
    tool_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    results_count INTEGER DEFAULT 0
);

CREATE TABLE monitored_assets (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    data_type VARCHAR NOT NULL,
    search_data VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_scanned_at TIMESTAMP,
    previous_results_hash VARCHAR
);

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES monitored_assets(id) ON DELETE CASCADE,
    user_id VARCHAR NOT NULL,
    scan_id INTEGER REFERENCES scan_jobs(id) ON DELETE SET NULL,
    message VARCHAR NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_scan_jobs_status ON scan_jobs(status);
CREATE INDEX idx_scan_results_job_id ON scan_results(job_id);
CREATE INDEX idx_tool_status_job_id ON tool_status(job_id);
CREATE INDEX idx_alerts_asset_id ON alerts(asset_id);
