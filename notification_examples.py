#!/usr/bin/env python3
"""
Example: How to Trigger Notifications in O-CLOUD

This shows how to integrate notification_manager into your code
to send notifications when resources or alarms change.
"""

from notification_manager import notification_manager
from ocloud_db import db

# ============================================================================
# Example 1: Notify when resource is discovered
# ============================================================================

def example_resource_discovered():
    """When discovery finds a new resource, notify subscribers"""
    
    # Create resource in database (your existing code)
    resource_id = "gnb-12345"
    resource_data = {
        "resource_id": resource_id,
        "resource_type_id": "type-ran-gnb",
        "name": "gNB Process 12345",
        "operational_state": "enabled"
    }
    
    db.create_resource(
        resource_id=resource_id,
        resource_type_id="type-ran-gnb",
        resource_pool_id="pool-default",
        name="gNB Process 12345"
    )
    
    # Trigger notification (ADD THIS LINE)
    notification_manager.notify_resource_created(resource_id, resource_data)
    
    print(f"Resource {resource_id} created and notification queued")


# ============================================================================
# Example 2: Notify when resource state changes
# ============================================================================

def example_resource_state_changed():
    """When resource operational state changes, notify subscribers"""
    
    resource_id = "gnb-12345"
    
    # Update resource state (your existing code)
    db.update_resource_state(
        resource_id=resource_id,
        operational_state="disabled"  # gNB process stopped
    )
    
    # Get updated resource data
    resource = db.get_resource(resource_id)
    
    # Trigger notification (ADD THIS LINE)
    notification_manager.notify_resource_updated(resource_id, resource)
    
    print(f"Resource {resource_id} updated and notification queued")


# ============================================================================
# Example 3: Notify when alarm is raised
# ============================================================================

def example_alarm_raised():
    """When creating an alarm, notify subscribers"""
    
    # Create alarm (your existing code)
    alarm_id = db.create_alarm(
        resource_id="gnb-12345",
        alarm_type="ProcessingError",
        probable_cause="High CPU temperature",
        perceived_severity="CRITICAL"
    )
    
    # Trigger notification (ADD THIS LINE)
    notification_manager.notify_alarm_raised(alarm_id)
    
    print(f"Alarm {alarm_id} raised and notification queued")


# ============================================================================
# Example 4: Notify when alarm is cleared
# ============================================================================

def example_alarm_cleared():
    """When clearing an alarm, notify subscribers"""
    
    alarm_id = "alarm-123"
    
    # Clear alarm (your existing code)
    db.update_alarm(
        alarm_id=alarm_id,
        alarm_cleared=True
    )
    
    # Trigger notification (ADD THIS LINE)
    notification_manager.notify_alarm_cleared(alarm_id)
    
    print(f"Alarm {alarm_id} cleared and notification queued")


# ============================================================================
# Example 5: Integration into gnb_discovery.py
# ============================================================================

def integration_example_gnb_discovery():
    """
    How to integrate into gnb_discovery.py
    
    In gnb_discovery.py, modify the discover_gnb() method:
    """
    
    code_example = '''
    # In gnb_discovery.py - discover_gnb() method
    
    from notification_manager import notification_manager  # ADD THIS IMPORT
    
    def discover_gnb(self, pool_id: str) -> Optional[str]:
        gnb_proc = self.find_gnb_process()
        
        if not gnb_proc:
            # gNB not running - mark as disabled
            resources = db.get_resources(resource_type_id=self.gnb_resource_type)
            for resource in resources:
                if resource['operational_state'] != 'disabled':
                    db.update_resource_state(
                        resource_id=resource['resource_id'],
                        operational_state='disabled'
                    )
                    # ADD THIS: Notify that resource changed
                    notification_manager.notify_resource_updated(
                        resource['resource_id'],
                        db.get_resource(resource['resource_id'])
                    )
            return None
        
        # gNB is running
        resource_id = f"gnb-{gnb_proc['pid']}"
        existing = db.get_resource(resource_id)
        
        if existing:
            # Update existing
            db.update_resource_state(
                resource_id=resource_id,
                operational_state='enabled'
            )
            # ADD THIS: Notify update
            notification_manager.notify_resource_updated(
                resource_id,
                db.get_resource(resource_id)
            )
        else:
            # Create new
            db.create_resource(...)
            # ADD THIS: Notify creation
            notification_manager.notify_resource_created(
                resource_id,
                db.get_resource(resource_id)
            )
        
        return resource_id
    '''
    
    print(code_example)


# ============================================================================
# Example 6: Test with a Mock SMO
# ============================================================================

def create_test_smo_server():
    """
    Create a simple Flask server to receive notifications (for testing)
    Save this as test_smo.py and run it to receive notifications
    """
    
    test_server_code = '''
#!/usr/bin/env python3
"""Test SMO Server - Receives O-CLOUD Notifications"""

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/notify', methods=['POST'])
def receive_notification():
    """Receive notification from O-CLOUD"""
    notification = request.json
    print(f"\\nReceived Notification:")
    print(f"  Type: {notification.get('notificationEventType')}")
    print(f"  Object: {notification.get('objectRef')}")
    print(f"  Time: {notification.get('timestamp')}")
    print(f"  Data: {notification.get('data')}")
    return jsonify({"status": "received"}), 200

if __name__ == '__main__':
    print("Test SMO listening on http://localhost:8888")
    print("Create subscriptions with callback: http://localhost:8888/notify")
    app.run(host='0.0.0.0', port=8888)
    '''
    
    print("Save this as test_smo.py:\n")
    print(test_server_code)


# ============================================================================
# Example 7: Create a subscription and test
# ============================================================================

def example_test_workflow():
    """Complete workflow to test notifications"""
    
    workflow = '''
# Terminal 1: Start Test SMO
python3 test_smo.py

# Terminal 2: Start O-CLOUD (with notifications enabled)
cd ~/OCLOUD
python3 o2_interface.py

# Terminal 3: Create subscription
curl -X POST http://localhost:5000/O2ims_infrastructureInventory/v1/subscriptions \\
  -H "Content-Type: application/json" \\
  -d '{
    "callback": "http://localhost:8888/notify",
    "filter": {
      "resourceTypeId": "type-ran-gnb"
    }
  }'

# Terminal 4: Start gNB (will trigger notification)
cd ~/srsRAN_Project/build/apps/gnb
sudo ./gnb -c ~/gnb.yaml

# Watch Terminal 1 (test SMO) - you should see:
# Received Notification:
#   Type: resourceInfo.created
#   Object: /O2ims_infrastructureInventory/v1/resources/gnb-12345
#   ...

# Stop gNB (will trigger update notification)
# Ctrl+C in gNB terminal

# Watch Terminal 1 again - you should see:
# Received Notification:
#   Type: resourceInfo.updated
#   Object: /O2ims_infrastructureInventory/v1/resources/gnb-12345
#   ...
    '''
    
    print(workflow)


if __name__ == '__main__':
    print("="*70)
    print("  O-CLOUD Notification Examples")
    print("="*70)
    print("\nThese examples show how to integrate notifications.\n")
    
    print("\nExample 1: Resource Created")
    print("-" * 70)
    example_resource_discovered()
    
    print("\nExample 2: Resource Updated")
    print("-" * 70)
    example_resource_state_changed()
    
    print("\nExample 3: Alarm Raised")
    print("-" * 70)
    example_alarm_raised()
    
    print("\nExample 6: Test SMO Server Code")
    print("-" * 70)
    create_test_smo_server()
    
    print("\nExample 7: Complete Test Workflow")
    print("-" * 70)
    example_test_workflow()
