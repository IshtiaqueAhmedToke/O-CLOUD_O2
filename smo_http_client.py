#!/usr/bin/env python3
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import psutil
import socket
import uuid
import threading
import time
from datetime import datetime
from collections import deque
from db_manager import db

app = Flask(__name__)
CORS(app)

OCLOUD_ID = "ocloud-001"
OCLOUD_NAME = f"O-CLOUD-SMO-{socket.gethostname()}"
GLOBAL_CLOUD_ID = f"{OCLOUD_ID}@oran-o-cloud.example.com"

DU_METRICS_URL = "https://2760f6be0fad.ngrok-free.app"

du_metrics = {
    "cpu_usage": deque(maxlen=100),
    "memory_usage": deque(maxlen=100),
    "active_ues": deque(maxlen=100),
    "throughput_dl": deque(maxlen=100),
    "throughput_ul": deque(maxlen=100),
    "timestamps": deque(maxlen=100)
}

class DUHTTPClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 10
    
    def _get(self, endpoint):
        try:
            response = self.session.get(f"{self.base_url}{endpoint}")
            response.raise_for_status()
            return response.json(), None
        except Exception as e:
            return None, str(e)
    
    def _post(self, endpoint, data=None):
        try:
            response = self.session.post(f"{self.base_url}{endpoint}", json=data)
            response.raise_for_status()
            return response.json(), None
        except Exception as e:
            return None, str(e)
    
    def get_status(self):
        return self._get('/status')
    
    def get_metrics(self):
        return self._get('/metrics')
    
    def get_logs(self, lines=50):
        return self._get(f'/logs?lines={lines}')
    
    def get_config(self):
        return self._get('/config')
    
    def start_du(self):
        return self._post('/start')
    
    def stop_du(self):
        return self._post('/stop')
    
    def restart_du(self):
        return self._post('/restart')
    
    def check_connection(self):
        try:
            response = self.session.get(f"{self.base_url}/", timeout=5)
            return response.status_code == 200
        except:
            return False

du_client = DUHTTPClient(DU_METRICS_URL)

class MetricsCollector:
    def __init__(self):
        self.running = False
        self.thread = None
    
    def collect(self):
        while self.running:
            try:
                metrics_data, error = du_client.get_metrics()
                if metrics_data and not error:
                    timestamp = datetime.now().isoformat()
                    du_metrics["timestamps"].append(timestamp)
                    du_proc = metrics_data.get('du_process', {})
                    du_met = metrics_data.get('du_metrics', {})
                    du_metrics["cpu_usage"].append(du_proc.get('cpu_percent', 0))
                    du_metrics["memory_usage"].append(du_proc.get('memory_percent', 0))
                    du_metrics["active_ues"].append(du_met.get('active_ues', 0))
                    du_metrics["throughput_dl"].append(du_met.get('throughput_dl_mbps', 0))
                    du_metrics["throughput_ul"].append(du_met.get('throughput_ul_mbps', 0))
                    
                    status_data, _ = du_client.get_status()
                    if status_data:
                        deployments = db.get_all_deployments()
                        for dep in deployments:
                            if dep['type'] == 'O-DU':
                                status = 'DEPLOYED' if status_data.get('is_running') else 'NOT_INSTANTIATED'
                                state = 'RUNNING' if status_data.get('is_running') else 'STOPPED'
                                db.update_deployment_status(dep['deployment_id'], status, state, status_data.get('pid'))
            except Exception as e:
                print(f"[Metrics] Error: {e}")
            time.sleep(5)
    
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.collect, daemon=True)
            self.thread.start()
    
    def stop(self):
        self.running = False

metrics_collector = MetricsCollector()

@app.route('/')
def root():
    status_data, _ = du_client.get_status()
    is_running = status_data.get('is_running', False) if status_data else False
    return jsonify({
        "service": "O-RAN SMO with O2 Interface",
        "oCloudId": OCLOUD_ID,
        "globalCloudId": GLOBAL_CLOUD_ID,
        "name": OCLOUD_NAME,
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "managed_du": {
            "url": DU_METRICS_URL,
            "status": "running" if is_running else "stopped",
            "connection": "connected" if du_client.check_connection() else "disconnected"
        }
    })

@app.route('/du/status', methods=['GET'])
def get_du_status():
    data, error = du_client.get_status()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/du/start', methods=['POST'])
def start_du():
    data, error = du_client.start_du()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/du/stop', methods=['POST'])
def stop_du():
    data, error = du_client.stop_du()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/du/restart', methods=['POST'])
def restart_du():
    data, error = du_client.restart_du()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/du/logs', methods=['GET'])
def get_du_logs():
    lines = request.args.get('lines', 50, type=int)
    data, error = du_client.get_logs(lines)
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/du/metrics', methods=['GET'])
def get_du_metrics():
    return jsonify({
        "timestamps": list(du_metrics["timestamps"]),
        "cpu_usage": list(du_metrics["cpu_usage"]),
        "active_ues": list(du_metrics["active_ues"]),
        "throughput_dl": list(du_metrics["throughput_dl"]),
        "throughput_ul": list(du_metrics["throughput_ul"]),
        "memory_usage": list(du_metrics["memory_usage"])
    })

@app.route('/du/config', methods=['GET'])
def get_du_config():
    data, error = du_client.get_config()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(data)

@app.route('/O2ims_infrastructureInventory/v1', methods=['GET'])
def ims_inventory_root():
    return jsonify({
        "oCloudId": OCLOUD_ID,
        "globalCloudId": GLOBAL_CLOUD_ID,
        "name": OCLOUD_NAME,
        "description": "O-RAN SMO managing remote DU via HTTP",
        "serviceUri": request.url_root.rstrip('/')
    })

@app.route('/O2ims_infrastructureInventory/v1/resourcePools', methods=['GET'])
def get_resource_pools():
    return jsonify([{
        "resourcePoolId": "pool-001",
        "oCloudId": OCLOUD_ID,
        "name": "Remote DU Pool",
        "description": "DU compute resources"
    }])

@app.route('/vnflcm/v2/vnf_instances', methods=['GET', 'POST'])
def vnf_instances():
    if request.method == 'GET':
        deployments = db.get_all_deployments()
        instances = []
        for dep in deployments:
            instances.append({
                "id": dep['deployment_id'],
                "vnfInstanceName": dep['name'],
                "vnfdId": "nfdd-odu-001",
                "instantiationState": "INSTANTIATED" if dep['status'] == 'DEPLOYED' else "NOT_INSTANTIATED"
            })
        return jsonify(instances)
    
    data = request.json or {}
    deployment_id = "du-remote-001"
    deployment_data = {
        "deployment_id": deployment_id,
        "name": data.get('vnfInstanceName', 'Remote O-DU'),
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
        "instantiationState": "NOT_INSTANTIATED"
    })
    response.status_code = 201
    return response

@app.route('/vnflcm/v2/vnf_instances/<vnf_id>/instantiate', methods=['POST'])
def instantiate_vnf(vnf_id):
    return start_du()

@app.route('/vnflcm/v2/vnf_instances/<vnf_id>/terminate', methods=['POST'])
def terminate_vnf(vnf_id):
    return stop_du()

@app.route('/vnflcm/v2/vnf_instances/<vnf_id>', methods=['GET'])
def vnf_instance(vnf_id):
    dep = db.get_deployment(vnf_id)
    if not dep:
        return jsonify({"error": "VNF not found"}), 404
    return jsonify({
        "id": vnf_id,
        "vnfInstanceName": dep['name'],
        "instantiationState": "INSTANTIATED" if dep['status'] == 'DEPLOYED' else "NOT_INSTANTIATED",
        "vnfState": dep['operational_state']
    })

@app.route('/health', methods=['GET'])
def health():
    du_connected = du_client.check_connection()
    status_data, _ = du_client.get_status()
    du_running = status_data.get('is_running', False) if status_data else False
    return jsonify({
        "status": "healthy" if du_connected else "degraded",
        "oCloudId": OCLOUD_ID,
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "du_connection": "connected" if du_connected else "disconnected",
        "du_status": "running" if du_running else "stopped"
    })

@app.route('/status', methods=['GET'])
def status():
    deployments = db.get_all_deployments()
    status_data, _ = du_client.get_status()
    return jsonify({
        "oCloudId": OCLOUD_ID,
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "smo_host": socket.gethostname(),
        "du_metrics_url": DU_METRICS_URL,
        "du_connected": du_client.check_connection(),
        "du_running": status_data.get('is_running', False) if status_data else False,
        "deployments": {
            "total": len(deployments),
            "running": len([d for d in deployments if d['status'] == 'DEPLOYED']),
            "stopped": len([d for d in deployments if d['status'] == 'NOT_INSTANTIATED'])
        }
    })

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  O-RAN SMO WITH HTTP-BASED DU MANAGEMENT")
    print("="*70)
    print(f"\n  SMO Host:     {socket.gethostname()}")
    print(f"  DU URL:       {DU_METRICS_URL}")
    print(f"  Server:       http://0.0.0.0:5001")
    print(f"  Dashboard:    http://localhost:5001/smo_dashboard.html")
    print("\n" + "="*70 + "\n")
    
    print("Testing DU connection...")
    if du_client.check_connection():
        print(f"✓ Connected to DU")
        status_data, _ = du_client.get_status()
        if status_data:
            print(f"✓ DU Status: {'RUNNING' if status_data.get('is_running') else 'STOPPED'}")
    else:
        print(f"✗ Cannot connect to DU")
    
    print("\nStarting metrics collector...")
    metrics_collector.start()
    print("✓ Metrics collector started\n")
    print("="*70 + "\n")
    
    try:
        app.run(host='0.0.0.0', port=5001, debug=False)
    finally:
        metrics_collector.stop()
