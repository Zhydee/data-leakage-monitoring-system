CREATE DATABASE dlms_db;
\c dlms_db

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE scan_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    data_type VARCHAR(50) NOT NULL,
    search_data TEXT NOT NULL,
    custom_regex VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    total_tools INTEGER DEFAULT 5,
    completed_tools INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
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

-- Create indexes for better performance
CREATE INDEX idx_scan_jobs_user_id ON scan_jobs(user_id);
CREATE INDEX idx_scan_jobs_status ON scan_jobs(status);
CREATE INDEX idx_scan_results_job_id ON scan_results(job_id);
CREATE INDEX idx_scan_results_tool_name ON scan_results(tool_name);
CREATE INDEX idx_tool_status_job_id ON tool_status(job_id);

-- Insert sample data (optional for testing)
INSERT INTO users (username, email, password_hash) VALUES 
('testuser', 'test@example.com', '$2b$12$dummy_hash_for_testing'),
('admin', 'admin@example.com', '$2b$12$dummy_hash_for_testing');

-- Display created tables
\dt