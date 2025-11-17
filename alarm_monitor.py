#!/usr/bin/env python3
"""
Automatic Alarm Monitor
Monitors system metrics and creates alarms based on thresholds
"""

import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from ocloud_db import db
from alarm_config import (
    ALARM_THRESHOLDS, 
    ALARM_TYPE_MAP,
    PROBABLE_CAUSE_TEMPLATES,
    ENABLE_AUTOMATIC_ALARMS,
    ALARM_CHECK_INTERVAL,
    ALARM_DEDUPLICATION_WINDOW,
    SEND_ALARM_NOTIFICATIONS
)

class AlarmMonitor:
    """
    Monitors metrics and automatically creates/clears alarms based on thresholds
    """
    
    def __init__(self):
        self.running = False
        self.worker_thread = None
        self.active_alarms = {}  # Track active alarms by (resource_id, metric_type)
        
    def start(self):
        """Start the alarm monitoring thread"""
        if not ENABLE_AUTOMATIC_ALARMS:
            print("Automatic alarm creation is disabled in config")
            return
            
        if self.running:
            return
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        print("Automatic Alarm Monitor started")
        
    def stop(self):
        """Stop the alarm monitoring thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        print("Automatic Alarm Monitor stopped")
        
    def _worker(self):
        """Background worker that checks thresholds"""
        while self.running:
            try:
                self._check_all_resources()
                time.sleep(ALARM_CHECK_INTERVAL)
            except Exception as e:
                print(f"Error in alarm monitor: {e}")
                
    def _check_all_resources(self):
        """Check all resources for alarm conditions"""
        resources = db.get_resources()
        
        for resource in resources:
            resource_id = resource['resource_id']
            
            # Check system-level metrics
            self._check_system_metrics(resource_id)
            
            # Check gNB-specific metrics if this is a gNB
            if resource.get('resource_type_id') == 'type-ran-gnb':
                self._check_gnb_metrics(resource_id, resource)
                
    def _check_system_metrics(self, resource_id: str):
        """Check system-level metrics (CPU, memory, disk)"""
        # Get recent performance data
        try:
            recent_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
            
            # Check CPU
            cpu_data = db.get_performance_data_since(resource_id, "cpu_usage", recent_time)
            if cpu_data:
                latest_cpu = cpu_data[-1]['value']
                self._check_threshold(
                    resource_id, 
                    "cpu_usage", 
                    latest_cpu, 
                    ALARM_THRESHOLDS.get("cpu_usage", {})
                )
            
            # Check Memory
            mem_data = db.get_performance_data_since(resource_id, "memory_usage", recent_time)
            if mem_data:
                latest_mem = mem_data[-1]['value']
                self._check_threshold(
                    resource_id,
                    "memory_usage",
                    latest_mem,
                    ALARM_THRESHOLDS.get("memory_usage", {})
                )
                
        except Exception as e:
            # Method might not exist yet, skip silently
            pass
            
    def _check_gnb_metrics(self, resource_id: str, resource: Dict):
        """Check gNB-specific metrics"""
        # Check if gNB process is running (from extensions)
        extensions = resource.get('extensions', {})
        if isinstance(extensions, str):
            import json
            try:
                extensions = json.loads(extensions)
            except:
                extensions = {}
                
        process_info = extensions.get('process', {})
        resources_info = extensions.get('resources', {})
        
        # Check if process exists
        if not process_info or not process_info.get('pid'):
            # gNB process not found - this is an alarm condition
            self._create_or_update_alarm(
                resource_id,
                "process_not_found",
                None,
                "CRITICAL",
                "gNB process not running or not discovered"
            )
        else:
            # Clear process not found alarm if it exists
            self._clear_alarm_if_exists(resource_id, "process_not_found")
            
            # Check gNB process CPU
            gnb_cpu = resources_info.get('cpu_percent')
            if gnb_cpu is not None:
                self._check_threshold(
                    resource_id,
                    "gnb_process_cpu",
                    gnb_cpu,
                    ALARM_THRESHOLDS.get("gnb_process_cpu", {})
                )
            
            # Check gNB process memory
            gnb_mem = resources_info.get('memory_percent')
            if gnb_mem is not None:
                self._check_threshold(
                    resource_id,
                    "gnb_process_memory",
                    gnb_mem,
                    ALARM_THRESHOLDS.get("gnb_process_memory", {})
                )
        
        # Check operational state changes
        if resource.get('operational_state') == 'disabled':
            self._create_or_update_alarm(
                resource_id,
                "resource_state_change",
                None,
                "MAJOR",
                f"Resource operational state is disabled"
            )
        else:
            self._clear_alarm_if_exists(resource_id, "resource_state_change")
            
    def _check_threshold(self, resource_id: str, metric_type: str, 
                        value: float, thresholds: Dict):
        """Check a metric value against thresholds and create/clear alarms"""
        if not thresholds:
            return
            
        critical = thresholds.get('critical', 100)
        major = thresholds.get('major', 90)
        minor = thresholds.get('minor', 80)
        clear_threshold = thresholds.get('clear', 70)
        
        # Determine severity
        severity = None
        threshold_name = None
        
        if value >= critical:
            severity = "CRITICAL"
            threshold_name = "critical"
        elif value >= major:
            severity = "MAJOR"
            threshold_name = "major"
        elif value >= minor:
            severity = "MINOR"
            threshold_name = "minor"
        
        if severity:
            # Create or update alarm
            probable_cause = PROBABLE_CAUSE_TEMPLATES.get(metric_type, "Threshold exceeded").format(
                value=value,
                threshold=thresholds.get(threshold_name, value)
            )
            self._create_or_update_alarm(
                resource_id,
                metric_type,
                value,
                severity,
                probable_cause
            )
        elif value < clear_threshold:
            # Clear alarm if exists
            self._clear_alarm_if_exists(resource_id, metric_type)
            
    def _create_or_update_alarm(self, resource_id: str, metric_type: str,
                               value: Optional[float], severity: str,
                               probable_cause: str):
        """Create a new alarm or update existing one"""
        alarm_key = (resource_id, metric_type)
        
        # Check if alarm already exists and is recent
        if alarm_key in self.active_alarms:
            existing_alarm_id = self.active_alarms[alarm_key]
            existing_alarm = db.get_alarm(existing_alarm_id)
            
            if existing_alarm and not existing_alarm.get('alarm_cleared'):
                # Alarm already exists and is active
                # Update severity if changed
                if existing_alarm.get('perceived_severity') != severity:
                    db.update_alarm(existing_alarm_id, perceived_severity=severity)
                    
                    # Send notification for severity change
                    if SEND_ALARM_NOTIFICATIONS:
                        from notification_manager import notification_manager
                        notification_manager.notify_alarm_changed(existing_alarm_id)
                        
                return existing_alarm_id
        
        # Create new alarm
        alarm_id = str(uuid.uuid4())
        alarm_type = ALARM_TYPE_MAP.get(metric_type, "Other")
        
        db.create_alarm(
            alarm_id=alarm_id,
            resource_id=resource_id,
            perceived_severity=severity,
            probable_cause=probable_cause,
            alarm_type=alarm_type,
            is_root_cause=False
        )
        
        # Track active alarm
        self.active_alarms[alarm_key] = alarm_id
        
        # Send notification
        if SEND_ALARM_NOTIFICATIONS:
            from notification_manager import notification_manager
            notification_manager.notify_alarm_raised(alarm_id)
        
        print(f"Auto-created alarm: {alarm_type} - {severity} - {probable_cause}")
        return alarm_id
        
    def _clear_alarm_if_exists(self, resource_id: str, metric_type: str):
        """Clear an alarm if it exists"""
        alarm_key = (resource_id, metric_type)
        
        if alarm_key in self.active_alarms:
            alarm_id = self.active_alarms[alarm_key]
            alarm = db.get_alarm(alarm_id)
            
            if alarm and not alarm.get('alarm_cleared'):
                db.clear_alarm(alarm_id)
                
                # Send notification
                if SEND_ALARM_NOTIFICATIONS:
                    from notification_manager import notification_manager
                    notification_manager.notify_alarm_cleared(alarm_id)
                
                print(f"Auto-cleared alarm: {alarm_id}")
            
            # Remove from tracking
            del self.active_alarms[alarm_key]

# Global instance
alarm_monitor = AlarmMonitor()
