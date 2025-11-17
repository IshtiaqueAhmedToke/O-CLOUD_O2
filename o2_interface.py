#!/usr/bin/env python3
"""
O-CLOUD O2 Interface Implementation
Implements O2 IMS (Infrastructure Management Service) and O2 DMS (Monitoring Service)

This is what the O-CLOUD exposes - NOT deployment management.
The SMO/orchestrator calls these APIs to:
- Discover infrastructure resources (IMS)
- Monitor infrastructure health and performance (DMS)
- Get notified of infrastructure changes (Subscriptions)
"""

from flask import Flask, jsonify, request, url_for
from flask_cors import CORS
import uuid
import socket
import psutil
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from ocloud_db import db
from discovery_layer import get_discovery
from notification_manager import notification_manager
from report_generator import report_generator
from alarm_monitor import alarm_monitor
from alarm_config import ENABLE_MANUAL_ALARM_CREATION

app = Flask(__name__)
CORS(app)

# O-Cloud Identity (should be configured, not hardcoded)
OCLOUD_ID = "ocloud-001"
OCLOUD_NAME = f"O-CLOUD-{socket.gethostname()}"
GLOBAL_CLOUD_ID = f"{OCLOUD_ID}@oran-ocloud.example.com"

# Initialize O-Cloud in database
db.init_ocloud(
    ocloud_id=OCLOUD_ID,
    global_cloud_id=GLOBAL_CLOUD_ID,
    name=OCLOUD_NAME,
    description="O-RAN Compliant O-Cloud Infrastructure",
    service_uri="http://localhost:5000"
)

# ============================================================================
# O2 IMS API - Infrastructure Inventory Management
# ============================================================================

@app.route('/O2ims_infrastructureInventory/v1', methods=['GET'])
def ims_api_root():
    """O2 IMS API root - provides O-Cloud information"""
    ocloud = db.get_ocloud(OCLOUD_ID)
    return jsonify({
        "oCloudId": ocloud['ocloud_id'],
        "globalCloudId": ocloud['global_cloud_id'],
        "name": ocloud['name'],
        "description": ocloud['description'],
        "serviceUri": request.url_root.rstrip('/'),
        "resourcePools": url_for('get_resource_pools', _external=True),
        "resources": url_for('get_resources', _external=True),
        "resourceTypes": url_for('get_resource_types', _external=True),
        "deploymentManagers": url_for('get_deployment_managers', _external=True)
    })

@app.route('/O2ims_infrastructureInventory/v1/resourcePools', methods=['GET'])
def get_resource_pools():
    """Get all resource pools in the O-Cloud"""
    pools = db.get_resource_pools(OCLOUD_ID)
    return jsonify(pools)

@app.route('/O2ims_infrastructureInventory/v1/resourcePools/<pool_id>', methods=['GET'])
def get_resource_pool(pool_id):
    """Get specific resource pool"""
    pool = db.get_resource_pool(pool_id)
    if not pool:
        return jsonify({"error": "Resource pool not found"}), 404
    return jsonify(pool)

@app.route('/O2ims_infrastructureInventory/v1/resourcePools/<pool_id>/resources', 
          methods=['GET'])
def get_pool_resources(pool_id):
    """Get all resources in a specific pool"""
    resources = db.get_resources(resource_pool_id=pool_id)
    return jsonify(resources)

@app.route('/O2ims_infrastructureInventory/v1/resourceTypes', methods=['GET'])
def get_resource_types():
    """Get all resource types"""
    types = db.get_resource_types()
    return jsonify(types)

@app.route('/O2ims_infrastructureInventory/v1/resourceTypes/<type_id>', methods=['GET'])
def get_resource_type(type_id):
    """Get specific resource type"""
    rtype = db.get_resource_type(type_id)
    if not rtype:
        return jsonify({"error": "Resource type not found"}), 404
    return jsonify(rtype)

@app.route('/O2ims_infrastructureInventory/v1/resources', methods=['GET'])
def get_resources():
    """Get all resources with optional filtering"""
    resource_pool_id = request.args.get('resourcePoolId')
    resource_type_id = request.args.get('resourceTypeId')
    
    resources = db.get_resources(
        resource_pool_id=resource_pool_id,
        resource_type_id=resource_type_id
    )
    return jsonify(resources)

@app.route('/O2ims_infrastructureInventory/v1/resources/<resource_id>', methods=['GET'])
def get_resource(resource_id):
    """Get specific resource"""
    resource = db.get_resource(resource_id)
    if not resource:
        return jsonify({"error": "Resource not found"}), 404
    return jsonify(resource)

@app.route('/O2ims_infrastructureInventory/v1/deploymentManagers', methods=['GET'])
def get_deployment_managers():
    """Get all deployment managers"""
    managers = db.get_deployment_managers(OCLOUD_ID)
    return jsonify(managers)

@app.route('/O2ims_infrastructureInventory/v1/deploymentManagers/<dm_id>', 
          methods=['GET'])
def get_deployment_manager(dm_id):
    """Get specific deployment manager"""
    dm = db.get_deployment_manager(dm_id)
    if not dm:
        return jsonify({"error": "Deployment manager not found"}), 404
    return jsonify(dm)

# ============================================================================
# O2 IMS Subscriptions - Infrastructure Change Notifications
# ============================================================================

@app.route('/O2ims_infrastructureInventory/v1/subscriptions', methods=['GET', 'POST'])
def ims_subscriptions():
    """Manage IMS subscriptions"""
    if request.method == 'GET':
        subs = db.get_subscriptions()
        ims_subs = [s for s in subs if s['subscription_type'].startswith('ims_')]
        return jsonify(ims_subs)
    
    # POST - Create subscription
    data = request.json
    subscription_id = str(uuid.uuid4())
    
    db.create_subscription(
        subscription_id=subscription_id,
        subscription_type=data.get('subscriptionType', 'ims_inventory_change'),
        callback_uri=data['callback'],
        filter_criteria=data.get('filter'),
        consumer_subscription_id=data.get('consumerSubscriptionId')
    )
    
    response = jsonify({
        "subscriptionId": subscription_id,
        "callback": data['callback'],
        "subscriptionType": data.get('subscriptionType', 'ims_inventory_change')
    })
    response.status_code = 201
    return response

@app.route('/O2ims_infrastructureInventory/v1/subscriptions/<sub_id>', 
          methods=['GET', 'DELETE'])
def ims_subscription(sub_id):
    """Get or delete IMS subscription"""
    if request.method == 'DELETE':
        db.delete_subscription(sub_id)
        return '', 204
    
    sub = db.get_subscription(sub_id)
    if not sub:
        return jsonify({"error": "Subscription not found"}), 404
    return jsonify(sub)

# ============================================================================
# O2 DMS API - Infrastructure Monitoring Service
# ============================================================================

@app.route('/O2dms_infrastructureMonitoring/v1', methods=['GET'])
def dms_api_root():
    """O2 DMS API root"""
    return jsonify({
        "oCloudId": OCLOUD_ID,
        "serviceUri": request.url_root.rstrip('/'),
        "performanceJobs": url_for('dms_performance_jobs', _external=True),
        "alarms": url_for('dms_alarms', _external=True),
        "subscriptions": url_for('dms_subscriptions', _external=True)
    })

# ============================================================================
# O2 DMS Performance Monitoring
# ============================================================================

@app.route('/O2dms_infrastructureMonitoring/v1/performanceJobs', 
          methods=['GET', 'POST'])
def dms_performance_jobs():
    """Manage performance monitoring jobs"""
    if request.method == 'GET':
        # Return all performance jobs
        # In production, you'd query from database
        return jsonify([])
    
    # POST - Create performance job
    data = request.json
    job_id = str(uuid.uuid4())
    
    db.create_performance_job(
        job_id=job_id,
        object_type=data['objectType'],
        object_instance_ids=data['objectInstanceIds'],
        criteria=data['criteria'],
        callback_uri=data['callbackUri'],
        collection_interval=data.get('collectionInterval', 60),
        reporting_period=data.get('reportingPeriod', 300)
    )
    
    response = jsonify({
        "id": job_id,
        "objectType": data['objectType'],
        "criteria": data['criteria'],
        "callbackUri": data['callbackUri']
    })
    response.status_code = 201
    return response

@app.route('/O2dms_infrastructureMonitoring/v1/performanceJobs/<job_id>', 
          methods=['GET', 'DELETE'])
def dms_performance_job(job_id):
    """Get or delete performance job"""
    if request.method == 'DELETE':
        # Delete job logic
        return '', 204
    
    job = db.get_performance_job(job_id)
    if not job:
        return jsonify({"error": "Performance job not found"}), 404
    return jsonify(job)

# ============================================================================
# O2 DMS Alarms
# ============================================================================

@app.route('/O2dms_infrastructureMonitoring/v1/alarms', methods=['GET', 'POST'])
def dms_alarms():
    """Get or create infrastructure alarms"""
    if request.method == 'POST':
        # Check if manual alarm creation is enabled
        if not ENABLE_MANUAL_ALARM_CREATION:
            return jsonify({
                "error": "Manual alarm creation is disabled",
                "message": "Alarms are created automatically by the system. Set ENABLE_MANUAL_ALARM_CREATION=True in alarm_config.py for testing."
            }), 403
        
        # Create new alarm (for testing/debugging)
        data = request.json
        alarm_id = str(uuid.uuid4())
        
        db.create_alarm(
            alarm_id=alarm_id,
            resource_id=data.get('resourceId'),
            perceived_severity=data.get('perceivedSeverity', 'WARNING'),
            probable_cause=data.get('probableCause', 'Unknown'),
            alarm_type=data.get('alarmType', 'Other'),
            is_root_cause=data.get('isRootCause', False)
        )
        
        # Trigger notification
        notification_manager.notify_alarm_raised(alarm_id)
        
        # Return created alarm
        alarm = db.get_alarm(alarm_id)
        return jsonify(alarm), 201
    
    # GET method
    resource_id = request.args.get('resourceId')
    severity = request.args.get('perceivedSeverity')
    active_only = request.args.get('activeOnly', 'true').lower() == 'true'
    
    alarms = db.get_alarms(
        resource_id=resource_id,
        severity=severity,
        active_only=active_only
    )
    return jsonify(alarms)

@app.route('/O2dms_infrastructureMonitoring/v1/alarms/<alarm_id>', methods=['GET', 'PATCH'])
def dms_alarm(alarm_id):
    """Get or update alarm"""
    if request.method == 'PATCH':
        data = request.json
        if data.get('alarmAcknowledged'):
            db.acknowledge_alarm(alarm_id)
        if data.get('alarmCleared'):
            db.clear_alarm(alarm_id)
        return '', 204
    
    alarm = db.get_alarm(alarm_id)
    if not alarm:
        return jsonify({"error": "Alarm not found"}), 404
    return jsonify(alarm)

# ============================================================================
# O2 DMS Subscriptions - Alarm and Performance Notifications
# ============================================================================

@app.route('/O2dms_infrastructureMonitoring/v1/subscriptions', methods=['GET', 'POST'])
def dms_subscriptions():
    """Manage DMS subscriptions"""
    if request.method == 'GET':
        subs = db.get_subscriptions()
        dms_subs = [s for s in subs if s['subscription_type'].startswith('dms_')]
        return jsonify(dms_subs)
    
    # POST - Create subscription
    data = request.json
    subscription_id = str(uuid.uuid4())
    
    db.create_subscription(
        subscription_id=subscription_id,
        subscription_type=data.get('subscriptionType', 'dms_alarm_event'),
        callback_uri=data['callback'],
        filter_criteria=data.get('filter'),
        consumer_subscription_id=data.get('consumerSubscriptionId')
    )
    
    response = jsonify({
        "subscriptionId": subscription_id,
        "callback": data['callback'],
        "subscriptionType": data.get('subscriptionType')
    })
    response.status_code = 201
    return response

@app.route('/O2dms_infrastructureMonitoring/v1/subscriptions/<sub_id>', 
          methods=['GET', 'DELETE'])
def dms_subscription(sub_id):
    """Get or delete DMS subscription"""
    if request.method == 'DELETE':
        db.delete_subscription(sub_id)
        return '', 204
    
    sub = db.get_subscription(sub_id)
    if not sub:
        return jsonify({"error": "Subscription not found"}), 404
    return jsonify(sub)

# ============================================================================
# Health and Status Endpoints
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "oCloudId": OCLOUD_ID,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route('/status', methods=['GET'])
def status():
    """Detailed O-Cloud status"""
    ocloud = db.get_ocloud(OCLOUD_ID)
    pools = db.get_resource_pools(OCLOUD_ID)
    resources = db.get_resources()
    alarms = db.get_alarms(active_only=True)
    
    # Get system metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return jsonify({
        "oCloud": ocloud,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "infrastructure": {
            "resourcePools": len(pools),
            "totalResources": len(resources),
            "activeAlarms": len(alarms)
        },
        "systemMetrics": {
            "cpuUsage": cpu_percent,
            "memoryUsage": memory.percent,
            "diskUsage": disk.percent
        }
    })

# ============================================================================
# Infrastructure Discovery Integration
# ============================================================================

def initialize_infrastructure():
    """Initialize infrastructure discovery"""
    print("Initializing infrastructure discovery...")
    
    # Get discovery instance
    discovery = get_discovery(OCLOUD_ID)
    
    # Run initial discovery
    print("Running initial discovery...")
    discovery.discover_all()
    
    # Start continuous discovery (every 60 seconds)
    discovery.start_continuous_discovery(interval=60)
    
    return discovery

# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  O-RAN O-CLOUD - O2 INTERFACE")
    print("="*70)
    print(f"\n  O-Cloud ID:        {OCLOUD_ID}")
    print(f"  Global Cloud ID:   {GLOBAL_CLOUD_ID}")
    print(f"  Name:              {OCLOUD_NAME}")
    print(f"  Server:            http://0.0.0.0:5000")
    print(f"\n  O2 IMS API:        http://localhost:5000/O2ims_infrastructureInventory/v1")
    print(f"  O2 DMS API:        http://localhost:5000/O2dms_infrastructureMonitoring/v1")
    print("\n" + "="*70 + "\n")
    
    print("Initializing infrastructure discovery...")
    discovery = initialize_infrastructure()
    print("✓ Infrastructure discovery initialized\n")
    
    print("Starting notification manager...")
    notification_manager.start()
    print("✓ Notification manager started\n")
    
    print("Starting performance report generator...")
    report_generator.start()
    print("✓ Report generator started\n")
    
    print("Starting automatic alarm monitor...")
    alarm_monitor.start()
    print("✓ Alarm monitor started\n")
    
    print("="*70 + "\n")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        # Clean shutdown
        discovery.stop_continuous_discovery()
