#!/usr/bin/env python3
"""
O-CLOUD Alarm Configuration
Defines thresholds and rules for automatic alarm creation
"""

# Alarm Thresholds for Automatic Creation
ALARM_THRESHOLDS = {
    # CPU Usage Thresholds (percentage)
    "cpu_usage": {
        "critical": 95.0,    # Above this = CRITICAL alarm
        "major": 90.0,       # Above this = MAJOR alarm
        "minor": 80.0,       # Above this = MINOR alarm
        "clear": 75.0        # Below this = clear alarm
    },
    
    # Memory Usage Thresholds (percentage)
    "memory_usage": {
        "critical": 90.0,
        "major": 85.0,
        "minor": 75.0,
        "clear": 70.0
    },
    
    # Disk Usage Thresholds (percentage)
    "disk_usage": {
        "critical": 95.0,
        "major": 90.0,
        "minor": 85.0,
        "clear": 80.0
    },
    
    # gNB Process Specific
    "gnb_process_cpu": {
        "critical": 95.0,
        "major": 85.0,
        "minor": 75.0,
        "clear": 70.0
    },
    
    "gnb_process_memory": {
        "critical": 90.0,
        "major": 80.0,
        "minor": 70.0,
        "clear": 65.0
    }
}

# Alarm Type Mappings
ALARM_TYPE_MAP = {
    "cpu_usage": "ProcessingError",
    "memory_usage": "MemoryError", 
    "disk_usage": "StorageCapacityProblem",
    "gnb_process_cpu": "ProcessingError",
    "gnb_process_memory": "MemoryError",
    "process_not_found": "CommunicationsAlarm",
    "resource_state_change": "EquipmentAlarm"
}

# Probable Cause Templates
PROBABLE_CAUSE_TEMPLATES = {
    "cpu_usage": "System CPU usage {value:.1f}% exceeds {threshold}% threshold",
    "memory_usage": "System memory usage {value:.1f}% exceeds {threshold}% threshold",
    "disk_usage": "Disk usage {value:.1f}% exceeds {threshold}% threshold",
    "gnb_process_cpu": "gNB process CPU usage {value:.1f}% exceeds {threshold}% threshold",
    "gnb_process_memory": "gNB process memory usage {value:.1f}% exceeds {threshold}% threshold",
    "process_not_found": "gNB process not found or stopped",
    "resource_state_change": "Resource operational state changed to {state}"
}

# Feature Flags
ENABLE_AUTOMATIC_ALARMS = True           # Master switch for automatic alarms
ENABLE_MANUAL_ALARM_CREATION = True      # Allow POST /alarms (for testing)
ALARM_CHECK_INTERVAL = 60                # Check thresholds every N seconds
ALARM_DEDUPLICATION_WINDOW = 300         # Don't create duplicate alarms within N seconds

# Alarm Notification Settings
SEND_ALARM_NOTIFICATIONS = True          # Send notifications when alarms raised/cleared
ALARM_NOTIFICATION_RETRY = 3             # Number of retry attempts

# Logging
ALARM_LOGGING_ENABLED = True
ALARM_LOG_LEVEL = "INFO"                 # DEBUG, INFO, WARNING, ERROR
