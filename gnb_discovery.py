#!/usr/bin/env python3
"""
gNB Discovery Module for O-CLOUD
Discovers srsRAN gNB process and reports it as an infrastructure resource
"""

import psutil
import re
from datetime import datetime, timezone
from typing import Optional, Dict
from ocloud_db import db

class GNBDiscovery:
    """Discovers and monitors srsRAN gNB process"""
    
    def __init__(self, ocloud_id: str):
        self.ocloud_id = ocloud_id
        self.gnb_resource_type = "type-ran-gnb"
        self._ensure_resource_type()
    
    def _ensure_resource_type(self):
        """Ensure gNB resource type exists"""
        try:
            existing = db.get_resource_type(self.gnb_resource_type)
            if not existing:
                db.create_resource_type(
                    type_id=self.gnb_resource_type,
                    name="RAN gNodeB",
                    vendor="srsRAN",
                    model="gNB",
                    version="1.0",
                    description="O-RAN gNodeB function"
                )
                print(f"  ✓ Created resource type: {self.gnb_resource_type}")
        except:
            pass
    
    def find_gnb_process(self) -> Optional[Dict]:
        """Find srsRAN gNB process"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent']):
            try:
                # Look for gnb process
                if proc.info['name'] and 'gnb' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    
                    # Try to extract config file
                    config_file = None
                    if '-c' in cmdline:
                        match = re.search(r'-c\s+(\S+)', cmdline)
                        if match:
                            config_file = match.group(1)
                    
                    # Get E2 node ID from cmdline or use default
                    e2_node_id = None
                    if 'e2_node_id' in cmdline:
                        match = re.search(r'e2_node_id[=\s]+(\S+)', cmdline)
                        if match:
                            e2_node_id = match.group(1)
                    
                    return {
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': cmdline,
                        'config_file': config_file,
                        'e2_node_id': e2_node_id,
                        'cpu_percent': proc.cpu_percent(interval=0.1),
                        'memory_percent': proc.memory_percent(),
                        'memory_mb': proc.memory_info().rss / (1024 * 1024)
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return None
    
    def discover_gnb(self, pool_id: str) -> Optional[str]:
        """
        Discover gNB and register as infrastructure resource
        Returns resource_id if found, None otherwise
        """
        gnb_proc = self.find_gnb_process()
        
        if not gnb_proc:
            # gNB not running - check if we have a resource to mark as disabled
            resources = db.get_resources(resource_type_id=self.gnb_resource_type)
            for resource in resources:
                if resource['operational_state'] != 'disabled':
                    db.update_resource_state(
                        resource_id=resource['resource_id'],
                        operational_state='disabled'
                    )
                    print(f"  ⚠ gNB process not found - marked {resource['resource_id']} as disabled")
            return None
        
        # gNB is running
        resource_id = f"gnb-{gnb_proc['pid']}"
        
        # Check if resource already exists
        existing = db.get_resource(resource_id)
        
        extensions = {
            "ran_function": {
                "type": "gNB",
                "vendor": "srsRAN",
                "e2_node_id": gnb_proc['e2_node_id'] or "unknown",
                "e2_enabled": gnb_proc['e2_node_id'] is not None
            },
            "process": {
                "pid": gnb_proc['pid'],
                "name": gnb_proc['name'],
                "cmdline": gnb_proc['cmdline'],
                "config_file": gnb_proc['config_file']
            },
            "resources": {
                "cpu_percent": gnb_proc['cpu_percent'],
                "memory_percent": gnb_proc['memory_percent'],
                "memory_mb": gnb_proc['memory_mb']
            }
        }
        
        if existing:
            # Update existing resource
            db.update_resource_state(
                resource_id=resource_id,
                operational_state='enabled'
            )
            print(f"  ✓ Updated gNB resource: {resource_id} (PID: {gnb_proc['pid']})")
        else:
            # Create new resource
            db.create_resource(
                resource_id=resource_id,
                resource_type_id=self.gnb_resource_type,
                resource_pool_id=pool_id,
                name=f"srsRAN gNB - PID {gnb_proc['pid']}",
                description="O-RAN gNodeB function",
                extensions=extensions
            )
            print(f"  ✓ Discovered new gNB: {resource_id} (PID: {gnb_proc['pid']})")
        
        # Record performance metrics
        self._record_gnb_metrics(resource_id, gnb_proc)
        
        return resource_id
    
    def _record_gnb_metrics(self, resource_id: str, gnb_proc: Dict):
        """Record gNB process metrics"""
        try:
            timestamp = datetime.now(timezone.utc)
            
            # CPU usage
            db.record_performance_data(
                resource_id, "cpu_usage", 
                gnb_proc['cpu_percent'], timestamp
            )
            
            # Memory usage
            db.record_performance_data(
                resource_id, "memory_usage",
                gnb_proc['memory_percent'], timestamp
            )
            
        except Exception as e:
            print(f"  ✗ Error recording gNB metrics: {e}")
    
    def get_gnb_info(self) -> Optional[Dict]:
        """Get current gNB information"""
        gnb_proc = self.find_gnb_process()
        if not gnb_proc:
            return None
        
        return {
            "running": True,
            "pid": gnb_proc['pid'],
            "e2_node_id": gnb_proc['e2_node_id'],
            "config_file": gnb_proc['config_file'],
            "cpu_percent": gnb_proc['cpu_percent'],
            "memory_percent": gnb_proc['memory_percent'],
            "memory_mb": round(gnb_proc['memory_mb'], 2)
        }
