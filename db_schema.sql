-- O-CLOUD Database Schema
-- Stores deployment state, jobs, and subscriptions

-- Deployments table
CREATE TABLE IF NOT EXISTS deployments (
    deployment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    operational_state TEXT NOT NULL,
    pid INTEGER,
    resource_pool_id TEXT,
    config_file TEXT,
    log_file TEXT,
    deployed_at TIMESTAMP,
    updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Jobs table (for async operations)
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    deployment_id TEXT,
    progress INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (deployment_id) REFERENCES deployments(deployment_id)
);

-- Subscriptions table (for event notifications)
CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id TEXT PRIMARY KEY,
    callback_uri TEXT NOT NULL,
    filter TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resource snapshots (optional - for historical tracking)
CREATE TABLE IF NOT EXISTS resource_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cpu_total_cores INTEGER,
    cpu_used_percent REAL,
    memory_total_mb INTEGER,
    memory_used_mb INTEGER,
    storage_total_gb REAL,
    storage_used_gb REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_deployment ON jobs(deployment_id);
