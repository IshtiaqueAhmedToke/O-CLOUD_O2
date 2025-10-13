-- O-CLOUD Database Schema
-- Stores deployment state, jobs, subscriptions, alarms, and performance data

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
    subscription_type TEXT NOT NULL,  -- NEW: 'ims_inventory', 'ims_alarm', 'dms_lifecycle', 'dms_fault', 'dms_performance'
    callback_uri TEXT NOT NULL,
    filter TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resource snapshots (for historical tracking)
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

-- NEW: DMS Alarms table
CREATE TABLE IF NOT EXISTS dms_alarms (
    alarm_id TEXT PRIMARY KEY,
    deployment_id TEXT NOT NULL,
    alarm_raised_time TIMESTAMP NOT NULL,
    perceived_severity TEXT NOT NULL,
    event_type TEXT NOT NULL,
    probable_cause TEXT,
    is_root_cause INTEGER DEFAULT 1,
    alarm_acknowledged INTEGER DEFAULT 0,
    alarm_acknowledged_time TIMESTAMP,
    alarm_cleared_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deployment_id) REFERENCES deployments(deployment_id)
);

-- NEW: Performance measurement jobs table
CREATE TABLE IF NOT EXISTS pm_jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,  -- 'ims' or 'dms'
    object_type TEXT,  -- 'Vnf', 'Resource', etc.
    object_instance_ids TEXT,  -- JSON array
    callback_uri TEXT,
    collection_interval INTEGER DEFAULT 60,
    reporting_period INTEGER DEFAULT 300,
    state TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NEW: Performance reports table
CREATE TABLE IF NOT EXISTS pm_reports (
    report_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    entries TEXT NOT NULL,  -- JSON array of performance data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES pm_jobs(job_id)
);

-- NEW: Performance thresholds table
CREATE TABLE IF NOT EXISTS pm_thresholds (
    threshold_id TEXT PRIMARY KEY,
    object_type TEXT NOT NULL,
    object_instance_id TEXT NOT NULL,
    criteria TEXT NOT NULL,  -- JSON with performance metric and threshold
    callback_uri TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_deployment ON jobs(deployment_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_type ON subscriptions(subscription_type);
CREATE INDEX IF NOT EXISTS idx_dms_alarms_deployment ON dms_alarms(deployment_id);
CREATE INDEX IF NOT EXISTS idx_pm_jobs_type ON pm_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_pm_reports_job ON pm_reports(job_id);
