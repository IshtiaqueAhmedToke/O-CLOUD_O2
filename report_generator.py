#!/usr/bin/env python3
"""
O-CLOUD Performance Report Generator
Generates and delivers performance reports according to O2 DMS specification
"""

import threading
import time
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from ocloud_db import db
import json

class ReportGenerator:
    """
    Generates performance reports for active performance jobs.
    Runs in background, checks jobs, aggregates metrics, and delivers reports.
    """
    
    def __init__(self):
        self.running = False
        self.worker_thread = None
        self.check_interval = 10  # Check jobs every 10 seconds
        
    def start(self):
        """Start the report generator thread"""
        if self.running:
            return
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        print("Performance Report Generator started")
        
    def stop(self):
        """Stop the report generator thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        print("Performance Report Generator stopped")
        
    def _worker(self):
        """Background worker that checks performance jobs"""
        while self.running:
            try:
                self._check_jobs()
                time.sleep(self.check_interval)
            except Exception as e:
                print(f"Error in report generator: {e}")
                
    def _check_jobs(self):
        """Check all active performance jobs and generate reports if needed"""
        jobs = db.get_performance_jobs()
        
        for job in jobs:
            if self._should_generate_report(job):
                self._generate_and_deliver_report(job)
                
    def _should_generate_report(self, job: Dict) -> bool:
        """Check if it's time to generate a report for this job"""
        criteria = job.get('criteria', {})
        if isinstance(criteria, str):
            try:
                criteria = json.loads(criteria)
            except:
                criteria = {}
                
        reporting_period = criteria.get('reportingPeriod', 300)  # Default 5 minutes
        
        # Get last report time (stored in extensions or default to job creation)
        last_report_time_str = job.get('last_report_time')
        
        if not last_report_time_str:
            # First report - check if enough time has passed since job creation
            job_created = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            elapsed = (now - job_created).total_seconds()
            return elapsed >= reporting_period
        
        # Check if reporting period has elapsed since last report
        last_report_time = datetime.fromisoformat(last_report_time_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        elapsed = (now - last_report_time).total_seconds()
        
        return elapsed >= reporting_period
        
    def _generate_and_deliver_report(self, job: Dict):
        """Generate performance report and deliver to callback"""
        print(f"Generating report for job {job['job_id']}")
        
        # Parse criteria
        criteria = job.get('criteria', {})
        if isinstance(criteria, str):
            try:
                criteria = json.loads(criteria)
            except:
                criteria = {}
                
        # Parse object instance IDs
        object_instance_ids = job.get('object_instance_ids', [])
        if isinstance(object_instance_ids, str):
            try:
                object_instance_ids = json.loads(object_instance_ids)
            except:
                object_instance_ids = []
                
        # Get metrics for each object
        collection_period = criteria.get('collectionPeriod', 60)
        performance_metrics = criteria.get('performanceMetric', [])
        
        if isinstance(performance_metrics, str):
            performance_metrics = [performance_metrics]
            
        # Aggregate data
        report_data = []
        
        for object_id in object_instance_ids:
            object_data = {
                'objectType': job.get('object_type', 'Resource'),
                'objectInstanceId': object_id,
                'performanceMetrics': {}
            }
            
            # Get metrics for this object
            for metric_name in performance_metrics:
                # Get recent data points
                metric_values = self._get_metric_data(
                    object_id, 
                    metric_name, 
                    collection_period
                )
                
                if metric_values:
                    # Calculate aggregates
                    object_data['performanceMetrics'][metric_name] = {
                        'current': metric_values[-1] if metric_values else None,
                        'average': sum(metric_values) / len(metric_values) if metric_values else None,
                        'min': min(metric_values) if metric_values else None,
                        'max': max(metric_values) if metric_values else None,
                        'samples': len(metric_values)
                    }
                    
            report_data.append(object_data)
            
        # Build report payload
        report_payload = {
            'reportType': 'performanceReport',
            'jobId': job['job_id'],
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'reportingPeriod': criteria.get('reportingPeriod', 300),
            'collectionPeriod': collection_period,
            'data': report_data
        }
        
        # Deliver report
        callback_uri = job.get('callback_uri')
        if callback_uri:
            success = self._deliver_report(callback_uri, report_payload)
            
            if success:
                # Update last report time
                db.update_performance_job_last_report(
                    job['job_id'],
                    datetime.now(timezone.utc).isoformat()
                )
        else:
            print(f"No callback URI for job {job['job_id']}")
            
    def _get_metric_data(self, resource_id: str, metric_name: str, 
                        collection_period: int) -> List[float]:
        """Get metric data points for aggregation"""
        # Get data from the last collection period
        since = datetime.now(timezone.utc) - timedelta(seconds=collection_period)
        
        # Query performance data from database
        # This assumes we have a method to get performance data
        try:
            data_points = db.get_performance_data_since(
                resource_id, 
                metric_name, 
                since.isoformat()
            )
            
            return [point['value'] for point in data_points if point.get('value') is not None]
        except:
            # If method doesn't exist, return empty list
            # We'll add this method to ocloud_db.py
            return []
            
    def _deliver_report(self, callback_uri: str, report_payload: Dict) -> bool:
        """Deliver performance report to callback URI"""
        try:
            response = requests.post(
                callback_uri,
                json=report_payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code in [200, 201, 202, 204]:
                print(f"Performance report delivered to {callback_uri}")
                return True
            else:
                print(f"Report delivery failed: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"Report delivery timeout: {callback_uri}")
        except requests.exceptions.ConnectionError:
            print(f"Report delivery connection error: {callback_uri}")
        except Exception as e:
            print(f"Report delivery error: {e}")
            
        return False
        
    def generate_immediate_report(self, job_id: str) -> Optional[Dict]:
        """Generate a report immediately for a specific job (manual trigger)"""
        job = db.get_performance_job(job_id)
        if not job:
            return None
            
        self._generate_and_deliver_report(job)
        return {"status": "Report generation triggered"}

# Global instance
report_generator = ReportGenerator()
