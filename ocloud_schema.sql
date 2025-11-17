-- O-CLOUD Database Schema (O2 Interface Compliant)
-- Focuses on Infrastructure Inventory (IMS) and Monitoring (DMS)

-- ============================================================================
-- O2 IMS (Infrastructure Management Service) Tables
-- ============================================================================

-- O-Cloud information
CREATE TABLE IF NOT EXISTS ocloud (
    ocloud_id TEXT PRIMARY KEY,
    global_cloud_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    service_uri TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resource Pools (groups of compute/storage/network resources)
CREATE TABLE IF NOT EXISTS resource_pools (
    resource_pool_id TEXT PRIMARY KEY,
    ocloud_id TEXT NOT NULL,
    global_location_id TEXT,
    name TEXT NOT NULL,
    description TEXT,
    location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ocloud_id) REFERENCES ocloud(ocloud_id)
);

-- Resource Types (CPU, Memory, Storage, etc.)
CREATE TABLE IF NOT EXISTS resource_types (
    resource_type_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    vendor TEXT,
    model TEXT,
    version TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Physical/Virtual Resources (actual infrastructure components)
CREATE TABLE IF NOT EXISTS resources (
    resource_id TEXT PRIMARY KEY,
    resource_type_id TEXT NOT NULL,
    resource_pool_id TEXT NOT NULL,
    global_asset_id TEXT,
    name TEXT NOT NULL,
    description TEXT,
    -- Resource state
    administrative_state TEXT DEFAULT 'unlocked', -- locked/unlocked
    operational_state TEXT DEFAULT 'enabled',     -- enabled/disabled
    availability_status TEXT DEFAULT 'available', -- available/allocated/reserved
    -- Physical properties
    parent_id TEXT,  -- For hierarchical resources
    -- Metadata (JSON)
    extensions TEXT, -- Additional properties as JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resource_type_id) REFERENCES resource_types(resource_type_id),
    FOREIGN KEY (resource_pool_id) REFERENCES resource_pools(resource_pool_id),
    FOREIGN KEY (parent_id) REFERENCES resources(resource_id)
);

-- Deployment Managers (entities that can deploy workloads)
CREATE TABLE IF NOT EXISTS deployment_managers (
    deployment_manager_id TEXT PRIMARY KEY,
    ocloud_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    deployment_manager_type TEXT, -- k8s, openstack, etc
    service_uri TEXT,
    support_profiles TEXT, -- JSON array of supported profiles
    capacity TEXT, -- JSON with capacity info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ocloud_id) REFERENCES ocloud(ocloud_id)
);

-- ============================================================================
-- O2 DMS (Infrastructure Monitoring Service) Tables  
-- ============================================================================

-- Performance Metric Definitions
CREATE TABLE IF NOT EXISTS metric_definitions (
    metric_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    unit TEXT,
    description TEXT,
    collection_type TEXT, -- gauge/counter/cumulative
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance Monitoring Jobs
CREATE TABLE IF NOT EXISTS performance_jobs (
    job_id TEXT PRIMARY KEY,
    object_type TEXT NOT NULL, -- 'resource', 'resource_pool', etc
    object_instance_ids TEXT NOT NULL, -- JSON array
    sub_object_instance_ids TEXT, -- JSON array for sub-resources
    criteria TEXT NOT NULL, -- JSON with performance metrics to collect
    callback_uri TEXT NOT NULL,
    reports_endpoint TEXT, -- Where reports are posted
    collection_interval INTEGER DEFAULT 60, -- seconds
    reporting_period INTEGER DEFAULT 300, -- seconds  
    state TEXT DEFAULT 'enabled', -- enabled/disabled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_report_time TIMESTAMP -- When last report was generated
);

-- Performance Data (time-series)
CREATE TABLE IF NOT EXISTS performance_data (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id TEXT NOT NULL,
    metric_id TEXT NOT NULL,
    value REAL NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (resource_id) REFERENCES resources(resource_id),
    FOREIGN KEY (metric_id) REFERENCES metric_definitions(metric_id)
);

-- Infrastructure Alarms
CREATE TABLE IF NOT EXISTS alarms (
    alarm_id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    alarm_raised_time TIMESTAMP NOT NULL,
    alarm_changed_time TIMESTAMP,
    alarm_cleared_time TIMESTAMP,
    perceived_severity TEXT NOT NULL, -- CRITICAL/MAJOR/MINOR/WARNING
    probable_cause TEXT NOT NULL,
    alarm_type TEXT, -- COMMUNICATIONS_ALARM, PROCESSING_ERROR_ALARM, etc
    is_root_cause BOOLEAN DEFAULT 0,
    correlated_alarm_ids TEXT, -- JSON array
    alarm_acknowledged BOOLEAN DEFAULT 0,
    alarm_acknowledged_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resource_id) REFERENCES resources(resource_id)
);

-- Performance Thresholds
CREATE TABLE IF NOT EXISTS performance_thresholds (
    threshold_id TEXT PRIMARY KEY,
    object_type TEXT NOT NULL,
    object_instance_id TEXT NOT NULL,
    sub_object_instance_ids TEXT, -- JSON array
    criteria TEXT NOT NULL, -- JSON with threshold criteria
    callback_uri TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Subscription Tables (for both IMS and DMS)
-- ============================================================================

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id TEXT PRIMARY KEY,
    -- Subscription type: 
    --   IMS: 'inventory_change', 'resource_change'
    --   DMS: 'alarm_event', 'alarm_event_record', 'performance_info'
    subscription_type TEXT NOT NULL,
    callback_uri TEXT NOT NULL,
    -- Filter criteria (JSON)
    filter TEXT,
    -- Consumer info
    consumer_subscription_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- Subscription Events (audit trail)
CREATE TABLE IF NOT EXISTS subscription_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    object_id TEXT,
    notification_sent BOOLEAN DEFAULT 0,
    notification_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id)
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_resources_pool ON resources(resource_pool_id);
CREATE INDEX IF NOT EXISTS idx_resources_type ON resources(resource_type_id);
CREATE INDEX IF NOT EXISTS idx_resources_parent ON resources(parent_id);
CREATE INDEX IF NOT EXISTS idx_resources_state ON resources(operational_state, administrative_state);

CREATE INDEX IF NOT EXISTS idx_perf_data_resource ON performance_data(resource_id);
CREATE INDEX IF NOT EXISTS idx_perf_data_metric ON performance_data(metric_id);
CREATE INDEX IF NOT EXISTS idx_perf_data_timestamp ON performance_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_perf_data_resource_time ON performance_data(resource_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_alarms_resource ON alarms(resource_id);
CREATE INDEX IF NOT EXISTS idx_alarms_severity ON alarms(perceived_severity);
CREATE INDEX IF NOT EXISTS idx_alarms_cleared ON alarms(alarm_cleared_time);
CREATE INDEX IF NOT EXISTS idx_alarms_raised ON alarms(alarm_raised_time);

CREATE INDEX IF NOT EXISTS idx_subscriptions_type ON subscriptions(subscription_type);

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Insert default metric definitions
INSERT OR IGNORE INTO metric_definitions (metric_id, name, unit, description, collection_type) VALUES
('cpu_usage', 'CPU Usage', 'percent', 'CPU utilization percentage', 'gauge'),
('memory_usage', 'Memory Usage', 'percent', 'Memory utilization percentage', 'gauge'),
('disk_usage', 'Disk Usage', 'percent', 'Disk utilization percentage', 'gauge'),
('network_rx', 'Network RX', 'bytes/sec', 'Network receive throughput', 'counter'),
('network_tx', 'Network TX', 'bytes/sec', 'Network transmit throughput', 'counter'),
('disk_read', 'Disk Read', 'bytes/sec', 'Disk read throughput', 'counter'),
('disk_write', 'Disk Write', 'bytes/sec', 'Disk write throughput', 'counter');
