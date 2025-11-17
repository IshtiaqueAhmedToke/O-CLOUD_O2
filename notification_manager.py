#!/usr/bin/env python3
"""
O-CLOUD Notification Manager
Handles delivery of notifications to subscribers for O2 IMS and O2 DMS
"""

import requests
import threading
import time
import queue
from datetime import datetime, timezone
from typing import Dict, List, Optional
from ocloud_db import db
import json

class NotificationManager:
    """
    Manages notification delivery for O2 IMS and O2 DMS subscriptions.
    Runs in background thread, processes notification queue, and delivers to callbacks.
    """
    
    def __init__(self):
        self.notification_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        self.delivery_timeout = 5  # seconds
        self.max_retries = 3
        
    def start(self):
        """Start the notification worker thread"""
        if self.running:
            return
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        print("Notification Manager started")
        
    def stop(self):
        """Stop the notification worker thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        print("Notification Manager stopped")
        
    def _worker(self):
        """Background worker that processes notification queue"""
        while self.running:
            try:
                # Get notification from queue (blocks for 1 second)
                notification = self.notification_queue.get(timeout=1)
                self._process_notification(notification)
                self.notification_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in notification worker: {e}")
                
    def _process_notification(self, notification: Dict):
        """Process a single notification"""
        notification_type = notification.get('type')
        
        if notification_type == 'ims':
            self._deliver_ims_notification(notification)
        elif notification_type == 'dms':
            self._deliver_dms_notification(notification)
        else:
            print(f"Unknown notification type: {notification_type}")
            
    def _deliver_ims_notification(self, notification: Dict):
        """Deliver O2 IMS notification to subscribers"""
        event_type = notification['event_type']
        resource_id = notification.get('resource_id')
        
        # Get matching subscriptions
        subscriptions = db.get_subscriptions()
        
        for sub in subscriptions:
            # Check if subscription matches this event
            if self._matches_ims_filter(sub, notification):
                payload = self._build_ims_notification_payload(sub, notification)
                self._send_notification(sub['callback_uri'], payload)
                
    def _deliver_dms_notification(self, notification: Dict):
        """Deliver O2 DMS notification to subscribers"""
        # Similar to IMS but for alarms/performance
        event_type = notification['event_type']
        
        if 'alarm' in event_type:
            self._deliver_alarm_notification(notification)
        elif 'performance' in event_type:
            self._deliver_performance_notification(notification)
            
    def _deliver_alarm_notification(self, notification: Dict):
        """Deliver alarm notification"""
        alarm_id = notification.get('alarm_id')
        
        # Get alarm details
        alarm = db.get_alarm(alarm_id)
        if not alarm:
            return
            
        # Get DMS subscriptions for alarms
        # For simplicity, we'll check IMS subscriptions with alarm filters
        subscriptions = db.get_subscriptions()
        
        for sub in subscriptions:
            # Check filter - if subscriber wants alarms for this resource
            filter_data = sub.get('filter', {})
            if isinstance(filter_data, str):
                try:
                    filter_data = json.loads(filter_data)
                except:
                    filter_data = {}
                    
            resource_id = alarm.get('resource_id')
            if filter_data.get('resourceId') == resource_id or not filter_data.get('resourceId'):
                payload = self._build_alarm_notification_payload(sub, alarm, notification)
                self._send_notification(sub['callback_uri'], payload)
                
    def _deliver_performance_notification(self, notification: Dict):
        """Deliver performance notification"""
        # This is called when performance data is collected
        # Check if any performance jobs need reports
        pass  # Handled by report generator
        
    def _matches_ims_filter(self, subscription: Dict, notification: Dict) -> bool:
        """Check if notification matches subscription filter"""
        filter_data = subscription.get('filter', {})
        
        # Parse filter if it's stored as JSON string
        if isinstance(filter_data, str):
            try:
                filter_data = json.loads(filter_data)
            except:
                filter_data = {}
                
        # If no filter, match all
        if not filter_data:
            return True
            
        # Check resource pool filter
        if 'resourcePoolId' in filter_data:
            resource = db.get_resource(notification.get('resource_id'))
            if resource and resource.get('resource_pool_id') != filter_data['resourcePoolId']:
                return False
                
        # Check resource type filter
        if 'resourceTypeId' in filter_data:
            resource = db.get_resource(notification.get('resource_id'))
            if resource and resource.get('resource_type_id') != filter_data['resourceTypeId']:
                return False
                
        return True
        
    def _build_ims_notification_payload(self, subscription: Dict, notification: Dict) -> Dict:
        """Build O2 IMS notification payload according to spec"""
        return {
            "notificationEventType": notification['event_type'],
            "objectRef": f"/O2ims_infrastructureInventory/v1/resources/{notification.get('resource_id')}",
            "objectType": "ResourceInfo",
            "notificationId": notification.get('notification_id', f"notif-{int(time.time())}"),
            "subscriptionId": subscription['subscription_id'],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": notification.get('data', {})
        }
        
    def _build_alarm_notification_payload(self, subscription: Dict, alarm: Dict, notification: Dict) -> Dict:
        """Build alarm notification payload"""
        return {
            "notificationEventType": notification['event_type'],
            "objectRef": f"/O2dms_infrastructureMonitoring/v1/alarms/{alarm['alarm_id']}",
            "objectType": "AlarmEventRecord",
            "notificationId": notification.get('notification_id', f"notif-{int(time.time())}"),
            "subscriptionId": subscription['subscription_id'],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alarmId": alarm['alarm_id'],
            "resourceId": alarm['resource_id'],
            "perceivedSeverity": alarm['perceived_severity'],
            "probableCause": alarm['probable_cause'],
            "alarmRaisedTime": alarm['alarm_raised_time']
        }
        
    def _send_notification(self, callback_uri: str, payload: Dict) -> bool:
        """Send notification to callback URI with retries"""
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    callback_uri,
                    json=payload,
                    timeout=self.delivery_timeout,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code in [200, 201, 202, 204]:
                    print(f"Notification delivered to {callback_uri}: {payload['notificationEventType']}")
                    return True
                else:
                    print(f"Notification failed (attempt {attempt+1}): {response.status_code}")
                    
            except requests.exceptions.Timeout:
                print(f"Notification timeout (attempt {attempt+1}): {callback_uri}")
            except requests.exceptions.ConnectionError:
                print(f"Notification connection error (attempt {attempt+1}): {callback_uri}")
            except Exception as e:
                print(f"Notification error (attempt {attempt+1}): {e}")
                
            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                
        print(f"Notification delivery failed after {self.max_retries} attempts: {callback_uri}")
        return False
        
    # ========================================================================
    # Public methods to queue notifications
    # ========================================================================
    
    def notify_resource_created(self, resource_id: str, resource_data: Dict):
        """Queue notification for resource creation"""
        self.notification_queue.put({
            'type': 'ims',
            'event_type': 'resourceInfo.created',
            'resource_id': resource_id,
            'data': resource_data,
            'notification_id': f"notif-res-created-{int(time.time())}"
        })
        
    def notify_resource_updated(self, resource_id: str, resource_data: Dict):
        """Queue notification for resource update"""
        self.notification_queue.put({
            'type': 'ims',
            'event_type': 'resourceInfo.updated',
            'resource_id': resource_id,
            'data': resource_data,
            'notification_id': f"notif-res-updated-{int(time.time())}"
        })
        
    def notify_resource_deleted(self, resource_id: str):
        """Queue notification for resource deletion"""
        self.notification_queue.put({
            'type': 'ims',
            'event_type': 'resourceInfo.deleted',
            'resource_id': resource_id,
            'data': {},
            'notification_id': f"notif-res-deleted-{int(time.time())}"
        })
        
    def notify_alarm_raised(self, alarm_id: str):
        """Queue notification for alarm raised"""
        self.notification_queue.put({
            'type': 'dms',
            'event_type': 'alarm.raised',
            'alarm_id': alarm_id,
            'notification_id': f"notif-alarm-raised-{int(time.time())}"
        })
        
    def notify_alarm_changed(self, alarm_id: str):
        """Queue notification for alarm changed"""
        self.notification_queue.put({
            'type': 'dms',
            'event_type': 'alarm.changed',
            'alarm_id': alarm_id,
            'notification_id': f"notif-alarm-changed-{int(time.time())}"
        })
        
    def notify_alarm_cleared(self, alarm_id: str):
        """Queue notification for alarm cleared"""
        self.notification_queue.put({
            'type': 'dms',
            'event_type': 'alarm.cleared',
            'alarm_id': alarm_id,
            'notification_id': f"notif-alarm-cleared-{int(time.time())}"
        })

# Global instance
notification_manager = NotificationManager()
