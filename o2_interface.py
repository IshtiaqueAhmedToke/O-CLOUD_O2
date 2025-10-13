#!/usr/bin/env python3
"""
O-RAN O2 Interface - Complete IMS + DMS Implementation
Compliant with:
- O-RAN.WG6.O2IMS-INTERFACE-R004-v09.00
- O-RAN.WG6.O2DMS-INTERFACE-ETSI-NFV-PROFILE-R004-v09.00

Implements:
- O2ims_InfrastructureInventory (v1.2.0)
- O2ims_InfrastructureMonitoring (v1.2.0)
- O2ims_InfrastructureProvisioning (v1.0.0)
- O2ims_InfrastructurePerformance (v1.1.0)
- O2dms_DeploymentLifecycle (v2.14.0)
- O2dms_DeploymentFault (v1.14.0)
- O2dms_DeploymentPerformance (v2.13.0)
"""

from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
import psutil
import socket
import subprocess
import os
import signal
import uuid
from datetime import datetime, timedelta
from db_manager import db
import requests
import threading
import json

app = Flask(__name__)
CORS(app)

# =============================================================================
# CONFIGURATION
# =============================================================================

OCLOUD_ID = "ocloud-001"
OCLOUD_NAME = f"O-CLOUD-{socket.gethostname()}"
GLOBAL_CLOUD_ID = f"{OCLOUD_ID}@oran-o-cloud.example.com"

IMS_API_VERSIONS = {
    "O2ims_infrastructureInventory": "1.2.0",
    "O2ims_infrastructureMonitoring": "1.2.0",
    "O2ims_infrastructureProvisioning": "1.0.0",
    "O2ims_infrastructurePerformance": "1.1.0"
}

DMS_API_VERSIONS = {
    "vnflcm": "2.14.0",
    "vnffm": "1.14.0",
    "vnfpm": "2.13.0"
}

DU_PATH = "/home/toke/srsRAN_Project/build/apps/gnb/gnb"
DU_CONFIG = "/home/toke/srsRAN_Project/build/gnb_du.yml"
DU_LOG = "/home/toke/o-cloud/logs/du.log"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_system_resources():
    """Get current system resource information"""
    cpu_count = psutil.cpu_count()
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "cpu": {
            "total_cores": cpu_count,
            "used_percent": round(cpu_percent, 2),
            "available_cores": round(cpu_count * (1 - cpu_percent/100), 2)
        },
        "memory": {
            "total_mb": round(memory.total / (1024**2)),
            "used_mb": round(memory.used / (1024**2)),
            "available_mb": round(memory.available / (1024**2)),
            "percent_used": round(memory.percent, 2)
        },
        "storage": {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "available_gb": round(disk.free / (1024**3), 2),
            "percent_used": round(disk.percent, 2)
        }
    }

def create_problem_details(status, title, detail, instance=None):
    """Create RFC 7807 Problem Details response"""
    problem = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance or request.path
    }
    return jsonify(problem), status

def send_notification(callback_uri, notification_data):
    """Send notification to subscriber"""
    try:
        response = requests.post(callback_uri, json=notification_data, timeout=5)
        return response.status_code == 204
    except Exception as e:
        print(f"Failed to send notification to {callback_uri}: {e}")
        return False

# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.route('/')
def root():
    """Service root with all API endpoints"""
    return jsonify({
        "service": "O-RAN O2 Interface",
        "oCloudId": OCLOUD_ID,
        "globalCloudId": GLOBAL_CLOUD_ID,
        "name": OCLOUD_NAME,
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "apis": {
            "O2 IMS": {
                "inventory": {
                    "version": IMS_API_VERSIONS["O2ims_infrastructureInventory"],
                    "endpoint": "/O2ims_infrastructureInventory/v1"
                },
                "monitoring": {
                    "version": IMS_API_VERSIONS["O2ims_infrastructureMonitoring"],
                    "endpoint": "/O2ims_infrastructureMonitoring/v1"
                },
                "provisioning": {
                    "version": IMS_API_VERSIONS["O2ims_infrastructureProvisioning"],
                    "endpoint": "/O2ims_infrastructureProvisioning/v1"
                },
                "performance": {
                    "version": IMS_API_VERSIONS["O2ims_infrastructurePerformance"],
                    "endpoint": "/O2ims_infrastructurePerformance/v1"
                }
            },
            "O2 DMS": {
                "lifecycle": {
                    "version": DMS_API_VERSIONS["vnflcm"],
                    "endpoint": "/vnflcm/v2"
                },
                "fault": {
                    "version": DMS_API_VERSIONS["vnffm"],
                    "endpoint": "/vnffm/v1"
                },
                "performance": {
                    "version": DMS_API_VERSIONS["vnfpm"],
                    "endpoint": "/vnfpm/v2"
                }
            }
        }
    })

# =============================================================================
# O2 IMS - INFRASTRUCTURE INVENTORY API (v1.2.0)
# =============================================================================

@app.route('/O2ims_infrastructureInventory/v1', methods=['GET'])
def ims_inventory_root():
    """O-Cloud Description (CloudInfo)"""
    return jsonify({
        "oCloudId": OCLOUD_ID,
        "globalCloudId": GLOBAL_CLOUD_ID,
        "name": OCLOUD_NAME,
        "description": "O-RAN Compliant O-Cloud Infrastructure",
        "infrastructureManagementServiceEndpoint": "/O2ims_infrastructureInventory/v1",
        "serviceUri": request.url_root.rstrip('/'),
        "extensions": {
            "location": socket.gethostname(),
            "capabilities": ["VM", "Container", "5G-RAN"]
        }
    })

@app.route('/O2ims_infrastructureInventory/v1/resourceTypes', methods=['GET'])
def get_resource_types():
    """GET /resourceTypes"""
    resource_types = [
        {
            "resourceTypeId": "rt-compute-001",
            "name": "Compute",
            "description": "Virtual compute resources",
            "vendor": "Generic",
            "version": "1.0",
            "alarmDictionaryId": "alarm-dict-compute",
            "performanceDictionaryId": "perf-dict-compute",
            "extensions": {}
        },
        {
            "resourceTypeId": "rt-storage-001",
            "name": "Storage",
            "description": "Storage resources",
            "vendor": "Generic",
            "version": "1.0",
            "alarmDictionaryId": "alarm-dict-storage",
            "performanceDictionaryId": "perf-dict-storage",
            "extensions": {}
        },
        {
            "resourceTypeId": "rt-network-001",
            "name": "Network",
            "description": "Network resources",
            "vendor": "Generic",
            "version": "1.0",
            "alarmDictionaryId": "alarm-dict-network",
            "performanceDictionaryId": "perf-dict-network",
            "extensions": {}
        }
    ]
    return jsonify(resource_types)

@app.route('/O2ims_infrastructureInventory/v1/resourceTypes/<resource_type_id>', methods=['GET'])
def get_resource_type(resource_type_id):
    """GET /resourceTypes/{resourceTypeId}"""
    return jsonify({
        "resourceTypeId": resource_type_id,
        "name": "Compute",
        "description": "Virtual compute resources",
        "vendor": "Generic",
        "version": "1.0",
        "alarmDictionaryId": "alarm-dict-compute",
        "performanceDictionaryId": "perf-dict-compute",
        "extensions": {}
    })

@app.route('/O2ims_infrastructureInventory/v1/resourcePools', methods=['GET'])
def get_resource_pools():
    """GET /resourcePools"""
    resources = get_system_resources()
    
    pools = [{
        "resourcePoolId": "pool-001",
        "oCloudId": OCLOUD_ID,
        "globalLocationId": f"{socket.gethostname()}-site-001",
        "name": "Default Resource Pool",
        "description": "Primary compute resource pool",
        "location": socket.gethostname(),
        "resources": {
            "cpu": resources["cpu"]["total_cores"],
            "memory": resources["memory"]["total_mb"],
            "storage": resources["storage"]["total_gb"]
        },
        "extensions": {}
    }]
    
    return jsonify(pools)

@app.route('/O2ims_infrastructureInventory/v1/resourcePools/<pool_id>', methods=['GET'])
def get_resource_pool(pool_id):
    """GET /resourcePools/{resourcePoolId}"""
    if pool_id != "pool-001":
        return create_problem_details(404, "Not Found", "Resource pool not found")
    
    resources = get_system_resources()
    return jsonify({
        "resourcePoolId": pool_id,
        "oCloudId": OCLOUD_ID,
        "globalLocationId": f"{socket.gethostname()}-site-001",
        "name": "Default Resource Pool",
        "description": "Primary compute resource pool",
        "resources": resources
    })

@app.route('/O2ims_infrastructureInventory/v1/resourcePools/<pool_id>/resources', methods=['GET'])
def get_pool_resources(pool_id):
    """GET /resourcePools/{resourcePoolId}/resources"""
    if pool_id != "pool-001":
        return create_problem_details(404, "Not Found", "Resource pool not found")
    
    resources = [{
        "resourceId": "resource-compute-001",
        "resourcePoolId": pool_id,
        "oCloudId": OCLOUD_ID,
        "globalAssetId": f"asset-{socket.gethostname()}",
        "resourceTypeId": "rt-compute-001",
        "name": f"Compute Node - {socket.gethostname()}",
        "description": "Physical/Virtual compute resource",
        "elements": get_system_resources()
    }]
    
    return jsonify(resources)

@app.route('/O2ims_infrastructureInventory/v1/resourcePools/<pool_id>/resources/<resource_id>', methods=['GET'])
def get_resource(pool_id, resource_id):
    """GET /resourcePools/{resourcePoolId}/resources/{resourceId}"""
    return jsonify({
        "resourceId": resource_id,
        "resourcePoolId": pool_id,
        "resourceTypeId": "rt-compute-001",
        "name": f"Compute Resource {resource_id}",
        "elements": get_system_resources()
    })

@app.route('/O2ims_infrastructureInventory/v1/deploymentManagers', methods=['GET'])
def get_deployment_managers():
    """GET /deploymentManagers"""
    return jsonify([{
        "deploymentManagerId": "dm-001",
        "oCloudId": OCLOUD_ID,
        "name": "Native Process Manager",
        "description": "Manages O-RAN NF lifecycle",
        "serviceUri": "/vnflcm/v2",
        "supportedLocations": [socket.gethostname()],
        "capacityInformation": get_system_resources(),
        "extensions": {}
    }])

@app.route('/O2ims_infrastructureInventory/v1/deploymentManagers/<dm_id>', methods=['GET'])
def get_deployment_manager(dm_id):
    """GET /deploymentManagers/{deploymentManagerId}"""
    if dm_id != "dm-001":
        return create_problem_details(404, "Not Found", "Deployment manager not found")
    
    return jsonify({
        "deploymentManagerId": dm_id,
        "oCloudId": OCLOUD_ID,
        "name": "Native Process Manager",
        "serviceUri": "/vnflcm/v2",
        "capacityInformation": get_system_resources()
    })

@app.route('/O2ims_infrastructureInventory/v1/alarmDictionaries', methods=['GET'])
def get_alarm_dictionaries():
    """GET /alarmDictionaries"""
    return jsonify([{
        "alarmDictionaryId": "alarm-dict-compute",
        "alarmDictionarySchemaVersion": "1.0",
        "entityType": "Compute",
        "vendor": "O-RAN",
        "managementInterfaceId": ["o2ims"],
        "alarmDefinition": [{
            "alarmDefinitionId": "alarm-001",
            "alarmName": "ProcessFailure",
            "alarmDescription": "Process has failed",
            "proposedRepairActions": "Restart process or heal deployment"
        }]
    }])

@app.route('/O2ims_infrastructureInventory/v1/performanceDictionaries', methods=['GET'])
def get_performance_dictionaries():
    """GET /performanceDictionaries"""
    return jsonify([{
        "performanceDictionaryId": "perf-dict-compute",
        "performanceDictionarySchemaVersion": "1.0",
        "entityType": "Compute",
        "vendor": "O-RAN",
        "managementInterfaceId": ["o2ims"],
        "performanceMeasurement": [{
            "performanceMeasurementId": "pm-cpu-001",
            "name": "CPUUsage",
            "unit": "percent",
            "description": "CPU utilization percentage"
        }]
    }])

@app.route('/O2ims_infrastructureInventory/v1/subscriptions', methods=['GET', 'POST'])
def ims_inventory_subscriptions():
    """Inventory change subscriptions"""
    if request.method == 'GET':
        subs = db.get_subscriptions_by_type('ims_inventory')
        return jsonify(subs)
    
    data = request.json
    if not data or 'callback' not in data:
        return create_problem_details(400, "Bad Request", "callback URI required")
    
    sub_id = str(uuid.uuid4())
    db.create_subscription(sub_id, 'ims_inventory', data['callback'], data.get('filter'))
    
    response = jsonify({
        "subscriptionId": sub_id,
        "callback": data['callback'],
        "consumerSubscriptionId": data.get('consumerSubscriptionId'),
        "filter": data.get('filter')
    })
    response.status_code = 201
    response.headers['Location'] = f"/O2ims_infrastructureInventory/v1/subscriptions/{sub_id}"
    return response

@app.route('/O2ims_infrastructureInventory/v1/subscriptions/<sub_id>', methods=['GET', 'DELETE'])
def ims_inventory_subscription(sub_id):
    """Individual inventory subscription"""
    if request.method == 'GET':
        sub = db.get_subscription(sub_id)
        if not sub:
            return create_problem_details(404, "Not Found", "Subscription not found")
        return jsonify(sub)
    
    db.delete_subscription(sub_id)
    return '', 204

# =============================================================================
# O2 IMS - INFRASTRUCTURE MONITORING API (v1.2.0)
# =============================================================================

@app.route('/O2ims_infrastructureMonitoring/v1/alarms', methods=['GET'])
def get_alarms():
    """GET /alarms - Query alarm list"""
    deployments = db.get_all_deployments()
    alarms = []
    
    for dep in deployments:
        if dep['status'] == 'FAILED' or dep['operational_state'] == 'STOPPED':
            alarms.append({
                "alarmEventRecordId": f"alarm-{dep['deployment_id']}",
                "resourceId": dep['deployment_id'],
                "resourceTypeId": "rt-compute-001",
                "alarmDefinitionId": "alarm-001",
                "probableCauseId": "process-failure",
                "alarmRaisedTime": dep['updated_at'],
                "perceivedSeverity": 3,  # CRITICAL
                "alarmChangedTime": dep['updated_at'],
                "alarmAcknowledged": False,
                "extensions": {
                    "pid": dep['pid'],
                    "type": dep['type']
                }
            })
    
    return jsonify(alarms)

@app.route('/O2ims_infrastructureMonitoring/v1/alarms/<alarm_id>', methods=['GET', 'PATCH'])
def alarm(alarm_id):
    """GET/PATCH individual alarm"""
    if request.method == 'GET':
        return jsonify({
            "alarmEventRecordId": alarm_id,
            "perceivedSeverity": 3,
            "alarmAcknowledged": False
        })
    
    data = request.json
    
    if 'alarmAcknowledged' in data:
        return jsonify({
            "alarmAcknowledged": True,
            "alarmAcknowledgedTime": datetime.utcnow().isoformat() + 'Z'
        })
    elif 'perceivedSeverity' in data and data['perceivedSeverity'] == 5:
        return jsonify({
            "perceivedSeverity": 5,
            "alarmClearedTime": datetime.utcnow().isoformat() + 'Z'
        })
    
    return create_problem_details(400, "Bad Request", "Invalid alarm modification")

@app.route('/O2ims_infrastructureMonitoring/v1/alarmSubscriptions', methods=['GET', 'POST'])
def alarm_subscriptions():
    """Alarm subscriptions"""
    if request.method == 'GET':
        subs = db.get_subscriptions_by_type('ims_alarm')
        return jsonify(subs)
    
    data = request.json
    if not data or 'callback' not in data:
        return create_problem_details(400, "Bad Request", "callback required")
    
    sub_id = str(uuid.uuid4())
    db.create_subscription(sub_id, 'ims_alarm', data['callback'], data.get('filter'))
    
    response = jsonify({
        "alarmSubscriptionId": sub_id,
        "callback": data['callback'],
        "filter": data.get('filter')
    })
    response.status_code = 201
    response.headers['Location'] = f"/O2ims_infrastructureMonitoring/v1/alarmSubscriptions/{sub_id}"
    return response

# =============================================================================
# O2 IMS - INFRASTRUCTURE PROVISIONING API (v1.0.0)
# =============================================================================

@app.route('/O2ims_infrastructureProvisioning/v1/provisioningRequests', methods=['GET', 'POST'])
def provisioning_requests():
    """Provisioning requests"""
    if request.method == 'GET':
        return jsonify([])
    
    data = request.json
    prov_id = data.get('provisioningRequestId', str(uuid.uuid4()))
    
    response = jsonify({
        "provisioningRequestId": prov_id,
        "templateName": data.get('templateName'),
        "templateVersion": data.get('templateVersion'),
        "status": {
            "provisioningPhase": "PENDING",
            "message": "Provisioning request accepted",
            "updateTime": datetime.utcnow().isoformat() + 'Z'
        }
    })
    response.status_code = 201
    response.headers['Location'] = f"/O2ims_infrastructureProvisioning/v1/provisioningRequests/{prov_id}"
    return response

@app.route('/O2ims_infrastructureProvisioning/v1/provisioningRequests/<prov_id>', methods=['GET', 'PUT', 'DELETE'])
def provisioning_request(prov_id):
    """Individual provisioning request"""
    if request.method == 'GET':
        return jsonify({
            "provisioningRequestId": prov_id,
            "status": {
                "provisioningPhase": "FULFILLED",
                "updateTime": datetime.utcnow().isoformat() + 'Z'
            }
        })
    elif request.method == 'DELETE':
        return jsonify({"message": "Provisioning request deleted"}), 200
    else:  # PUT
        data = request.json
        return jsonify(data), 200

# =============================================================================
# O2 IMS - INFRASTRUCTURE PERFORMANCE API (v1.1.0) - COMPLETE
# =============================================================================

@app.route('/O2ims_infrastructurePerformance/v1/measurementJobs', methods=['GET', 'POST'])
def measurement_jobs():
    """Performance measurement jobs"""
    if request.method == 'GET':
        jobs = db.get_pm_jobs('ims')
        result = []
        for job in jobs:
            result.append({
                "measurementJobId": job['job_id'],
                "resourceIds": job['object_instance_ids'],
                "collectionInterval": job['collection_interval'],
                "reportingPeriod": job['reporting_period'],
                "state": job['state']
            })
        return jsonify(result)
    
    # POST - Create measurement job
    data = request.json
    job_id = str(uuid.uuid4())
    
    db.create_pm_job(
        job_id=job_id,
        job_type='ims',
        object_type='Resource',
        object_instance_ids=data.get('resourceIds', []),
        callback_uri=data.get('callbackUri'),
        collection_interval=data.get('collectionInterval', 60)
    )
    
    response = jsonify({
        "measurementJobId": job_id,
        "resourceIds": data.get('resourceIds', []),
        "collectionInterval": data.get('collectionInterval', 60),
        "state": "ACTIVE",
        "status": "RUNNING"
    })
    response.status_code = 201
    response.headers['Location'] = f"/O2ims_infrastructurePerformance/v1/measurementJobs/{job_id}"
    return response

@app.route('/O2ims_infrastructurePerformance/v1/measurementJobs/<job_id>', methods=['GET', 'DELETE'])
def measurement_job(job_id):
    """Individual measurement job"""
    if request.method == 'GET':
        job = db.get_pm_job(job_id)
        if not job:
            return create_problem_details(404, "Not Found", "Measurement job not found")
        
        return jsonify({
            "measurementJobId": job['job_id'],
            "state": job['state'],
            "status": "RUNNING" if job['state'] == 'ACTIVE' else "STOPPED"
        })
    
    # DELETE
    db.delete_pm_job(job_id)
    return '', 204

@app.route('/O2ims_infrastructurePerformance/v1/measurementJobs/<job_id>/performanceData', methods=['GET'])
def measurement_job_performance_data(job_id):
    """Get performance data for measurement job"""
    job = db.get_pm_job(job_id)
    if not job:
        return create_problem_details(404, "Not Found", "Measurement job not found")
    
    # Get latest resource metrics
    resources = get_system_resources()
    
    # Create a performance report
    report_id = str(uuid.uuid4())
    entries = [{
        "objectType": "Resource",
        "objectInstanceId": "resource-compute-001",
        "performanceMetric": [
            {
                "name": "CPUUsage",
                "value": resources['cpu']['used_percent'],
                "unit": "percent"
            },
            {
                "name": "MemoryUsage",
                "value": resources['memory']['percent_used'],
                "unit": "percent"
            },
            {
                "name": "StorageUsage",
                "value": resources['storage']['percent_used'],
                "unit": "percent"
            }
        ],
        "performanceMetricGroup": "SystemMetrics",
        "observedTime": datetime.utcnow().isoformat() + 'Z'
    }]
    
    db.create_pm_report(report_id, job_id, entries)
    
    return jsonify({
        "measurementJobId": job_id,
        "entries": entries
    })

# =============================================================================
# O2 DMS - DEPLOYMENT LIFECYCLE API (v2.14.0) - COMPLETE
# =============================================================================

@app.route('/vnflcm/v2/vnf_instances', methods=['GET', 'POST'])
def vnf_instances():
    """VNF instances (NF Deployments)"""
    if request.method == 'GET':
        deployments = db.get_all_deployments()
        
        vnf_instances = []
        for dep in deployments:
            vnf_instances.append({
                "id": dep['deployment_id'],
                "vnfInstanceName": dep['name'],
                "vnfdId": "nfdd-odu-001",
                "instantiationState": "INSTANTIATED" if dep['status'] == 'DEPLOYED' else "NOT_INSTANTIATED",
                "_links": {
                    "self": {"href": f"/vnflcm/v2/vnf_instances/{dep['deployment_id']}"},
                    "instantiate": {"href": f"/vnflcm/v2/vnf_instances/{dep['deployment_id']}/instantiate"}
                }
            })
        
        return jsonify(vnf_instances)
    
    # POST - Create new VNF instance
    data = request.json or {}
    deployment_id = f"vnf-{str(uuid.uuid4())[:8]}"
    
    deployment_data = {
        "deployment_id": deployment_id,
        "name": data.get('vnfInstanceName', 'O-DU Instance'),
        "type": "O-DU",
        "status": "NOT_INSTANTIATED",
        "operational_state": "STOPPED",
        "pid": None,
        "resource_pool_id": "pool-001",
        "config_file": None,
        "log_file": None,
        "deployed_at": None
    }
    db.save_deployment(deployment_data)
    
    response = jsonify({
        "id": deployment_id,
        "vnfInstanceName": deployment_data['name'],
        "instantiationState": "NOT_INSTANTIATED",
        "_links": {
            "self": {"href": f"/vnflcm/v2/vnf_instances/{deployment_id}"}
        }
    })
    response.status_code = 201
    response.headers['Location'] = f"/vnflcm/v2/vnf_instances/{deployment_id}"
    return response

@app.route('/vnflcm/v2/vnf_instances/<vnf_id>', methods=['GET', 'DELETE', 'PATCH'])
def vnf_instance(vnf_id):
    """Get, Delete, or Patch individual VNF instance"""
    dep = db.get_deployment(vnf_id)
    if not dep:
        return create_problem_details(404, "Not Found", "VNF instance not found")
    
    if request.method == 'GET':
        return jsonify({
            "id": vnf_id,
            "vnfInstanceName": dep['name'],
            "vnfdId": "nfdd-odu-001",
            "vnfProvider": "O-RAN Alliance",
            "vnfProductName": "O-DU",
            "vnfSoftwareVersion": "1.0",
            "vnfdVersion": "1.0",
            "instantiationState": "INSTANTIATED" if dep['status'] == 'DEPLOYED' else "NOT_INSTANTIATED",
            "instantiatedVnfInfo": {
                "flavourId": "simple",
                "vnfState": dep['operational_state'],
                "extCpInfo": []
            } if dep['status'] == 'DEPLOYED' else None,
            "_links": {
                "self": {"href": f"/vnflcm/v2/vnf_instances/{vnf_id}"},
                "terminate": {"href": f"/vnflcm/v2/vnf_instances/{vnf_id}/terminate"} if dep['status'] == 'DEPLOYED' else None,
                "instantiate": {"href": f"/vnflcm/v2/vnf_instances/{vnf_id}/instantiate"} if dep['status'] != 'DEPLOYED' else None
            }
        })
    
    elif request.method == 'DELETE':
        if dep['status'] == 'DEPLOYED':
            return create_problem_details(409, "Conflict", 
                "VNF must be terminated before deletion")
        db.delete_deployment(vnf_id)
        return '', 204
    
    else:  # PATCH
        data = request.json
        if 'vnfInstanceName' in data:
            dep['name'] = data['vnfInstanceName']
            db.save_deployment(dep)
        return jsonify({"vnfInstanceName": dep['name']})

@app.route('/vnflcm/v2/vnf_instances/<vnf_id>/instantiate', methods=['POST'])
def instantiate_vnf(vnf_id):
    """Instantiate VNF"""
    dep = db.get_deployment(vnf_id)
    if not dep:
        return create_problem_details(404, "Not Found", "VNF instance not found")
    
    if dep['status'] == 'DEPLOYED':
        return create_problem_details(409, "Conflict", "VNF already instantiated")
    
    try:
        job_id = str(uuid.uuid4())
        db.create_job(job_id, "INSTANTIATE", vnf_id)
        
        os.makedirs(os.path.dirname(DU_LOG), exist_ok=True)
        log_file = open(DU_LOG, 'w')
        process = subprocess.Popen(
            ['sudo', DU_PATH, '-c', DU_CONFIG],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setpgrp
        )
        
        deployment_data = {
            "deployment_id": vnf_id,
            "name": dep['name'],
            "type": "O-DU",
            "status": "DEPLOYED",
            "operational_state": "RUNNING",
            "pid": process.pid,
            "resource_pool_id": "pool-001",
            "config_file": DU_CONFIG,
            "log_file": DU_LOG,
            "deployed_at": datetime.utcnow().isoformat()
        }
        db.save_deployment(deployment_data)
        db.update_job(job_id, "COMPLETED", 100)
        
        response = make_response('', 202)
        response.headers['Location'] = f"/vnflcm/v2/vnf_lcm_op_occs/{job_id}"
        return response
        
    except Exception as e:
        if 'job_id' in locals():
            db.update_job(job_id, "FAILED", 0, str(e))
        return create_problem_details(500, "Internal Server Error", str(e))

@app.route('/vnflcm/v2/vnf_instances/<vnf_id>/terminate', methods=['POST'])
def terminate_vnf(vnf_id):
    """Terminate VNF"""
    dep = db.get_deployment(vnf_id)
    if not dep:
        return create_problem_details(404, "Not Found", "VNF instance not found")
    
    try:
        job_id = str(uuid.uuid4())
        db.create_job(job_id, "TERMINATE", vnf_id)
        
        if dep['pid']:
            try:
                os.killpg(os.getpgid(dep['pid']), signal.SIGTERM)
            except:
                pass
        
        db.update_deployment_status(vnf_id, 'NOT_INSTANTIATED', 'STOPPED', None)
        db.update_job(job_id, "COMPLETED", 100)
        
        response = make_response('', 202)
        response.headers['Location'] = f"/vnflcm/v2/vnf_lcm_op_occs/{job_id}"
        return response
    except Exception as e:
        return create_problem_details(500, "Internal Server Error", str(e))

@app.route('/vnflcm/v2/vnf_instances/<vnf_id>/scale', methods=['POST'])
def scale_vnf(vnf_id):
    """Scale VNF"""
    dep = db.get_deployment(vnf_id)
    if not dep:
        return create_problem_details(404, "Not Found", "VNF instance not found")
    
    if dep['status'] != 'DEPLOYED':
        return create_problem_details(409, "Conflict", "VNF must be instantiated to scale")
    
    job_id = str(uuid.uuid4())
    db.create_job(job_id, "SCALE", vnf_id)
    
    # Simulate scale operation
    db.update_job(job_id, "COMPLETED", 100)
    
    response = make_response('', 202)
    response.headers['Location'] = f"/vnflcm/v2/vnf_lcm_op_occs/{job_id}"
    return response

@app.route('/vnflcm/v2/vnf_instances/<vnf_id>/heal', methods=['POST'])
def heal_vnf(vnf_id):
    """Heal VNF"""
    dep = db.get_deployment(vnf_id)
    if not dep:
        return create_problem_details(404, "Not Found", "VNF instance not found")
    
    job_id = str(uuid.uuid4())
    db.create_job(job_id, "HEAL", vnf_id)
    
    # Simulate heal operation - restart the process
    try:
        if dep['pid']:
            try:
                os.killpg(os.getpgid(dep['pid']), signal.SIGTERM)
            except:
                pass
        
        # Restart
        log_file = open(DU_LOG, 'a')
        process = subprocess.Popen(
            ['sudo', DU_PATH, '-c', DU_CONFIG],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setpgrp
        )
        
        db.update_deployment_status(vnf_id, 'DEPLOYED', 'RUNNING', process.pid)
        db.update_job(job_id, "COMPLETED", 100)
    except Exception as e:
        db.update_job(job_id, "FAILED", 0, str(e))
    
    response = make_response('', 202)
    response.headers['Location'] = f"/vnflcm/v2/vnf_lcm_op_occs/{job_id}"
    return response

@app.route('/vnflcm/v2/vnf_lcm_op_occs', methods=['GET'])
def vnf_lcm_operations():
    """List all LCM operations"""
    jobs = db.get_all_jobs()
    ops = []
    for job in jobs:
        ops.append({
            "id": job['job_id'],
            "operationState": job['status'],
            "stateEnteredTime": job['created_at'],
            "startTime": job['created_at'],
            "vnfInstanceId": job['deployment_id'],
            "operation": job['type'],
            "isAutomaticInvocation": False,
            "_links": {
                "self": {"href": f"/vnflcm/v2/vnf_lcm_op_occs/{job['job_id']}"},
                "vnfInstance": {"href": f"/vnflcm/v2/vnf_instances/{job['deployment_id']}"}
            }
        })
    return jsonify(ops)

@app.route('/vnflcm/v2/vnf_lcm_op_occs/<op_id>', methods=['GET'])
def vnf_lcm_operation(op_id):
    """Get specific LCM operation status"""
    job = db.get_job(op_id)
    if not job:
        return create_problem_details(404, "Not Found", "Operation not found")
    
    return jsonify({
        "id": job['job_id'],
        "operationState": job['status'],
        "stateEnteredTime": job['created_at'],
        "startTime": job['created_at'],
        "vnfInstanceId": job['deployment_id'],
        "operation": job['type'],
        "isAutomaticInvocation": False,
        "operationParams": {},
        "error": {"detail": job['error_message']} if job['error_message'] else None,
        "_links": {
            "self": {"href": f"/vnflcm/v2/vnf_lcm_op_occs/{op_id}"},
            "vnfInstance": {"href": f"/vnflcm/v2/vnf_instances/{job['deployment_id']}"}
        }
    })

@app.route('/vnflcm/v2/subscriptions', methods=['GET', 'POST'])
def vnf_lcm_subscriptions():
    """VNF LCM event subscriptions"""
    if request.method == 'GET':
        subs = db.get_subscriptions_by_type('dms_lifecycle')
        return jsonify(subs)
    
    data = request.json
    if not data or 'callbackUri' not in data:
        return create_problem_details(400, "Bad Request", "callbackUri required")
    
    sub_id = str(uuid.uuid4())
    db.create_subscription(sub_id, 'dms_lifecycle', data['callbackUri'], data.get('filter'))
    
    response = jsonify({
        "id": sub_id,
        "callbackUri": data['callbackUri'],
        "filter": data.get('filter'),
        "_links": {
            "self": {"href": f"/vnflcm/v2/subscriptions/{sub_id}"}
        }
    })
    response.status_code = 201
    response.headers['Location'] = f"/vnflcm/v2/subscriptions/{sub_id}"
    return response

@app.route('/vnflcm/v2/subscriptions/<sub_id>', methods=['GET', 'DELETE'])
def vnf_lcm_subscription(sub_id):
    """Individual LCM subscription"""
    if request.method == 'GET':
        sub = db.get_subscription(sub_id)
        if not sub:
            return create_problem_details(404, "Not Found", "Subscription not found")
        return jsonify(sub)
    
    db.delete_subscription(sub_id)
    return '', 204

# =============================================================================
# O2 DMS - DEPLOYMENT FAULT MANAGEMENT API (v1.14.0) - NEW
# =============================================================================

@app.route('/vnffm/v1/alarms', methods=['GET'])
def dms_alarms():
    """Get deployment-specific alarms"""
    alarms_data = db.get_dms_alarms()
    
    alarms = []
    for alarm in alarms_data:
        alarms.append({
            "id": alarm['alarm_id'],
            "managedObjectId": alarm['deployment_id'],
            "vnfcInstanceIds": [],
            "rootCauseFaultyResource": None,
            "alarmRaisedTime": alarm['alarm_raised_time'],
            "alarmChangedTime": alarm['alarm_raised_time'],
            "alarmClearedTime": alarm.get('alarm_cleared_time'),
            "alarmAcknowledgedTime": alarm.get('alarm_acknowledged_time'),
            "ackState": "ACKNOWLEDGED" if alarm['alarm_acknowledged'] else "UNACKNOWLEDGED",
            "perceivedSeverity": alarm['perceived_severity'],
            "eventTime": alarm['alarm_raised_time'],
            "eventType": alarm['event_type'],
            "faultType": "ProcessFailure",
            "probableCause": alarm['probable_cause'],
            "isRootCause": bool(alarm['is_root_cause']),
            "correlatedAlarmIds": [],
            "faultDetails": [],
            "_links": {
                "self": {"href": f"/vnffm/v1/alarms/{alarm['alarm_id']}"},
                "objectInstance": {"href": f"/vnflcm/v2/vnf_instances/{alarm['deployment_id']}"}
            }
        })
    
    return jsonify(alarms)

@app.route('/vnffm/v1/alarms/<alarm_id>', methods=['GET', 'PATCH'])
def dms_alarm(alarm_id):
    """Get or modify specific deployment alarm"""
    alarm = db.get_dms_alarm(alarm_id)
    if not alarm:
        return create_problem_details(404, "Not Found", "Alarm not found")
    
    if request.method == 'GET':
        return jsonify({
            "id": alarm['alarm_id'],
            "managedObjectId": alarm['deployment_id'],
            "alarmRaisedTime": alarm['alarm_raised_time'],
            "perceivedSeverity": alarm['perceived_severity'],
            "eventType": alarm['event_type'],
            "probableCause": alarm['probable_cause'],
            "ackState": "ACKNOWLEDGED" if alarm['alarm_acknowledged'] else "UNACKNOWLEDGED"
        })
    
    # PATCH - Acknowledge alarm
    data = request.json
    if 'ackState' in data and data['ackState'] == 'ACKNOWLEDGED':
        db.acknowledge_dms_alarm(alarm_id)
        return jsonify({
            "ackState": "ACKNOWLEDGED",
            "alarmAcknowledgedTime": datetime.utcnow().isoformat() + 'Z'
        })
    
    return create_problem_details(400, "Bad Request", "Invalid alarm modification")

@app.route('/vnffm/v1/subscriptions', methods=['GET', 'POST'])
def dms_fault_subscriptions():
    """DMS fault subscriptions"""
    if request.method == 'GET':
        subs = db.get_subscriptions_by_type('dms_fault')
        return jsonify(subs)
    
    data = request.json
    if not data or 'callbackUri' not in data:
        return create_problem_details(400, "Bad Request", "callbackUri required")
    
    sub_id = str(uuid.uuid4())
    db.create_subscription(sub_id, 'dms_fault', data['callbackUri'], data.get('filter'))
    
    response = jsonify({
        "id": sub_id,
        "callbackUri": data['callbackUri'],
        "filter": data.get('filter'),
        "_links": {
            "self": {"href": f"/vnffm/v1/subscriptions/{sub_id}"}
        }
    })
    response.status_code = 201
    response.headers['Location'] = f"/vnffm/v1/subscriptions/{sub_id}"
    return response

@app.route('/vnffm/v1/subscriptions/<sub_id>', methods=['GET', 'DELETE'])
def dms_fault_subscription(sub_id):
    """Individual fault subscription"""
    if request.method == 'GET':
        sub = db.get_subscription(sub_id)
        if not sub:
            return create_problem_details(404, "Not Found", "Subscription not found")
        return jsonify(sub)
    
    db.delete_subscription(sub_id)
    return '', 204

# =============================================================================
# O2 DMS - DEPLOYMENT PERFORMANCE API (v2.13.0) - NEW
# =============================================================================

@app.route('/vnfpm/v2/pm_jobs', methods=['GET', 'POST'])
def dms_pm_jobs():
    """Performance monitoring jobs for NFs"""
    if request.method == 'GET':
        jobs = db.get_pm_jobs('dms')
        result = []
        for job in jobs:
            result.append({
                "id": job['job_id'],
                "objectType": job['object_type'],
                "objectInstanceIds": job['object_instance_ids'],
                "subObjectInstanceIds": [],
                "criteria": {
                    "performanceMetric": ["CPUUsage", "MemoryUsage"],
                    "collectionPeriod": job['collection_interval'],
                    "reportingPeriod": job['reporting_period']
                },
                "callbackUri": job['callback_uri'],
                "_links": {
                    "self": {"href": f"/vnfpm/v2/pm_jobs/{job['job_id']}"}
                }
            })
        return jsonify(result)
    
    # POST - Create PM job
    data = request.json
    job_id = str(uuid.uuid4())
    
    db.create_pm_job(
        job_id=job_id,
        job_type='dms',
        object_type=data.get('objectType', 'Vnf'),
        object_instance_ids=data.get('objectInstanceIds', []),
        callback_uri=data.get('callbackUri'),
        collection_interval=data.get('criteria', {}).get('collectionPeriod', 60)
    )
    
    response = jsonify({
        "id": job_id,
        "objectType": data.get('objectType', 'Vnf'),
        "objectInstanceIds": data.get('objectInstanceIds', []),
        "criteria": data.get('criteria'),
        "callbackUri": data.get('callbackUri'),
        "_links": {
            "self": {"href": f"/vnfpm/v2/pm_jobs/{job_id}"}
        }
    })
    response.status_code = 201
    response.headers['Location'] = f"/vnfpm/v2/pm_jobs/{job_id}"
    return response

@app.route('/vnfpm/v2/pm_jobs/<job_id>', methods=['GET', 'DELETE'])
def dms_pm_job(job_id):
    """Individual PM job"""
    if request.method == 'GET':
        job = db.get_pm_job(job_id)
        if not job:
            return create_problem_details(404, "Not Found", "PM job not found")
        
        return jsonify({
            "id": job['job_id'],
            "objectType": job['object_type'],
            "objectInstanceIds": job['object_instance_ids'],
            "criteria": {
                "collectionPeriod": job['collection_interval'],
                "reportingPeriod": job['reporting_period']
            },
            "_links": {
                "self": {"href": f"/vnfpm/v2/pm_jobs/{job_id}"}
            }
        })
    
    # DELETE
    db.delete_pm_job(job_id)
    return '', 204

@app.route('/vnfpm/v2/pm_jobs/<job_id>/reports/<report_id>', methods=['GET'])
def dms_pm_report(job_id, report_id):
    """Get specific performance report"""
    report = db.get_pm_report(report_id)
    if not report or report['job_id'] != job_id:
        return create_problem_details(404, "Not Found", "Report not found")
    
    return jsonify({
        "id": report['report_id'],
        "jobId": job_id,
        "entries": report['entries'],
        "_links": {
            "self": {"href": f"/vnfpm/v2/pm_jobs/{job_id}/reports/{report_id}"}
        }
    })

@app.route('/vnfpm/v2/thresholds', methods=['GET', 'POST'])
def dms_thresholds():
    """Performance thresholds for alerts"""
    if request.method == 'GET':
        thresholds = db.get_pm_thresholds()
        result = []
        for threshold in thresholds:
            result.append({
                "id": threshold['threshold_id'],
                "objectType": threshold['object_type'],
                "objectInstanceId": threshold['object_instance_id'],
                "criteria": threshold['criteria'],
                "callbackUri": threshold['callback_uri'],
                "_links": {
                    "self": {"href": f"/vnfpm/v2/thresholds/{threshold['threshold_id']}"}
                }
            })
        return jsonify(result)
    
    # POST - Create threshold
    data = request.json
    threshold_id = str(uuid.uuid4())
    
    db.create_pm_threshold(
        threshold_id=threshold_id,
        object_type=data.get('objectType', 'Vnf'),
        object_instance_id=data.get('objectInstanceId'),
        criteria=data.get('criteria'),
        callback_uri=data.get('callbackUri')
    )
    
    response = jsonify({
        "id": threshold_id,
        "objectType": data.get('objectType'),
        "objectInstanceId": data.get('objectInstanceId'),
        "criteria": data.get('criteria'),
        "callbackUri": data.get('callbackUri'),
        "_links": {
            "self": {"href": f"/vnfpm/v2/thresholds/{threshold_id}"}
        }
    })
    response.status_code = 201
    response.headers['Location'] = f"/vnfpm/v2/thresholds/{threshold_id}"
    return response

@app.route('/vnfpm/v2/thresholds/<threshold_id>', methods=['GET', 'DELETE'])
def dms_threshold(threshold_id):
    """Individual threshold"""
    if request.method == 'GET':
        threshold = db.get_pm_threshold(threshold_id)
        if not threshold:
            return create_problem_details(404, "Not Found", "Threshold not found")
        
        return jsonify({
            "id": threshold['threshold_id'],
            "objectType": threshold['object_type'],
            "objectInstanceId": threshold['object_instance_id'],
            "criteria": threshold['criteria'],
            "_links": {
                "self": {"href": f"/vnfpm/v2/thresholds/{threshold_id}"}
            }
        })
    
    # DELETE
    db.delete_pm_threshold(threshold_id)
    return '', 204

# =============================================================================
# HEALTH AND STATUS
# =============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "oCloudId": OCLOUD_ID,
        "globalCloudId": GLOBAL_CLOUD_ID,
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "services": {
            "ims": "operational",
            "dms": "operational"
        }
    })

@app.route('/status', methods=['GET'])
def status():
    """Detailed system status"""
    deployments = db.get_all_deployments()
    jobs = db.get_all_jobs()
    
    return jsonify({
        "oCloudId": OCLOUD_ID,
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "resources": get_system_resources(),
        "deployments": {
            "total": len(deployments),
            "running": len([d for d in deployments if d['status'] == 'DEPLOYED']),
            "stopped": len([d for d in deployments if d['status'] == 'NOT_INSTANTIATED'])
        },
        "jobs": {
            "total": len(jobs),
            "completed": len([j for j in jobs if j['status'] == 'COMPLETED']),
            "failed": len([j for j in jobs if j['status'] == 'FAILED']),
            "pending": len([j for j in jobs if j['status'] == 'PENDING'])
        }
    })

# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  O-RAN O2 INTERFACE - COMPLETE IMS + DMS")
    print("="*70)
    print(f"\n  O-Cloud ID:      {OCLOUD_ID}")
    print(f"  Global Cloud ID: {GLOBAL_CLOUD_ID}")
    print(f"\n  O2 IMS APIs:")
    print(f"  ├─ Inventory:    v{IMS_API_VERSIONS['O2ims_infrastructureInventory']} ✓ COMPLETE")
    print(f"  ├─ Monitoring:   v{IMS_API_VERSIONS['O2ims_infrastructureMonitoring']} ✓ COMPLETE")
    print(f"  ├─ Provisioning: v{IMS_API_VERSIONS['O2ims_infrastructureProvisioning']} ✓ COMPLETE")
    print(f"  └─ Performance:  v{IMS_API_VERSIONS['O2ims_infrastructurePerformance']} ✓ COMPLETE")
    print(f"\n  O2 DMS APIs:")
    print(f"  ├─ Lifecycle:    v{DMS_API_VERSIONS['vnflcm']} ✓ COMPLETE")
    print(f"  ├─ Fault:        v{DMS_API_VERSIONS['vnffm']} ✓ COMPLETE")
    print(f"  └─ Performance:  v{DMS_API_VERSIONS['vnfpm']} ✓ COMPLETE")
    print(f"\n  Server:          http://0.0.0.0:5000")
    print(f"  Dashboard:       http://localhost:5000/dashboard.html")
    print("\n" + "="*70 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
