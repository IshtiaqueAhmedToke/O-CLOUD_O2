#!/usr/bin/env python3
"""
Database Manager for O-CLOUD O2 Interface
Handles all database operations with SQLite
"""

import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

DATABASE_PATH = '/home/toke/O-CLOUD_O2/ocloud.db'

class DatabaseManager:
    """Manages SQLite database operations for O-CLOUD"""
    
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database with schema"""
        with open('db_schema.sql', 'r') as f:
            schema = f.read()
        
        with self.get_connection() as conn:
            conn.executescript(schema)
    
    # =========================================================================
    # DEPLOYMENT OPERATIONS
    # =========================================================================
    
    def save_deployment(self, deployment_data):
        """Save or update a deployment"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO deployments 
                (deployment_id, name, type, status, operational_state, pid, 
                 resource_pool_id, config_file, log_file, deployed_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                deployment_data['deployment_id'],
                deployment_data['name'],
                deployment_data['type'],
                deployment_data['status'],
                deployment_data['operational_state'],
                deployment_data.get('pid'),
                deployment_data.get('resource_pool_id'),
                deployment_data.get('config_file'),
                deployment_data.get('log_file'),
                deployment_data.get('deployed_at'),
                datetime.now().isoformat()
            ))
    
    def get_deployment(self, deployment_id):
        """Get a specific deployment by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM deployments WHERE deployment_id = ?',
                (deployment_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_deployments(self):
        """Get all deployments"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM deployments ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_deployment(self, deployment_id):
        """Delete a deployment"""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM deployments WHERE deployment_id = ?', (deployment_id,))
    
    def update_deployment_status(self, deployment_id, status, operational_state=None, pid=None):
        """Update deployment status"""
        with self.get_connection() as conn:
            if operational_state and pid:
                conn.execute('''
                    UPDATE deployments 
                    SET status = ?, operational_state = ?, pid = ?, updated_at = ?
                    WHERE deployment_id = ?
                ''', (status, operational_state, pid, datetime.now().isoformat(), deployment_id))
            else:
                conn.execute('''
                    UPDATE deployments 
                    SET status = ?, updated_at = ?
                    WHERE deployment_id = ?
                ''', (status, datetime.now().isoformat(), deployment_id))
    
    # =========================================================================
    # JOB OPERATIONS
    # =========================================================================
    
    def create_job(self, job_id, job_type, deployment_id=None):
        """Create a new job"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO jobs (job_id, type, status, deployment_id, progress)
                VALUES (?, ?, ?, ?, ?)
            ''', (job_id, job_type, 'PENDING', deployment_id, 0))
    
    def update_job(self, job_id, status, progress=None, error_message=None):
        """Update job status"""
        with self.get_connection() as conn:
            if status in ['COMPLETED', 'FAILED']:
                conn.execute('''
                    UPDATE jobs 
                    SET status = ?, progress = ?, error_message = ?, 
                        updated_at = ?, completed_at = ?
                    WHERE job_id = ?
                ''', (status, progress or 100, error_message, 
                      datetime.now().isoformat(), datetime.now().isoformat(), job_id))
            else:
                conn.execute('''
                    UPDATE jobs 
                    SET status = ?, progress = ?, error_message = ?, updated_at = ?
                    WHERE job_id = ?
                ''', (status, progress, error_message, datetime.now().isoformat(), job_id))
    
    def get_job(self, job_id):
        """Get a specific job"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_jobs(self):
        """Get all jobs"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM jobs ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    # =========================================================================
    # RESOURCE SNAPSHOT OPERATIONS
    # =========================================================================
    
    def save_resource_snapshot(self, resources):
        """Save a resource snapshot for historical tracking"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO resource_snapshots 
                (cpu_total_cores, cpu_used_percent, memory_total_mb, 
                 memory_used_mb, storage_total_gb, storage_used_gb)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                resources['cpu']['total_cores'],
                resources['cpu']['used_percent'],
                resources['memory']['total_mb'],
                resources['memory']['used_mb'],
                resources['storage']['total_gb'],
                resources['storage']['used_gb']
            ))
    
    # =========================================================================
    # SUBSCRIPTION OPERATIONS
    # =========================================================================
    
    def create_subscription(self, subscription_id, subscription_type, callback_uri, filter_data=None):
        """Create a subscription (updated with type)"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO subscriptions (subscription_id, subscription_type, callback_uri, filter)
                VALUES (?, ?, ?, ?)
            ''', (subscription_id, subscription_type, callback_uri, 
                  json.dumps(filter_data) if filter_data else None))
    
    def get_subscription(self, subscription_id):
        """Get a specific subscription"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM subscriptions WHERE subscription_id = ?',
                (subscription_id,)
            )
            row = cursor.fetchone()
            if row:
                sub = dict(row)
                if sub['filter']:
                    sub['filter'] = json.loads(sub['filter'])
                return sub
            return None
    
    def get_all_subscriptions(self):
        """Get all subscriptions"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM subscriptions')
            subs = [dict(row) for row in cursor.fetchall()]
            for sub in subs:
                if sub['filter']:
                    sub['filter'] = json.loads(sub['filter'])
            return subs
    
    def get_subscriptions_by_type(self, subscription_type):
        """Get subscriptions by type"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM subscriptions WHERE subscription_type = ?',
                (subscription_type,)
            )
            subs = [dict(row) for row in cursor.fetchall()]
            for sub in subs:
                if sub['filter']:
                    sub['filter'] = json.loads(sub['filter'])
            return subs
    
    def delete_subscription(self, subscription_id):
        """Delete a subscription"""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM subscriptions WHERE subscription_id = ?', (subscription_id,))
    
    # =========================================================================
    # DMS ALARM OPERATIONS
    # =========================================================================
    
    def create_dms_alarm(self, alarm_id, deployment_id, severity, event_type, probable_cause):
        """Create a DMS alarm"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO dms_alarms 
                (alarm_id, deployment_id, alarm_raised_time, perceived_severity, 
                 event_type, probable_cause)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (alarm_id, deployment_id, datetime.now().isoformat(), 
                  severity, event_type, probable_cause))
    
    def get_dms_alarms(self, deployment_id=None):
        """Get all DMS alarms, optionally filtered by deployment"""
        with self.get_connection() as conn:
            if deployment_id:
                cursor = conn.execute(
                    'SELECT * FROM dms_alarms WHERE deployment_id = ? ORDER BY alarm_raised_time DESC',
                    (deployment_id,)
                )
            else:
                cursor = conn.execute('SELECT * FROM dms_alarms ORDER BY alarm_raised_time DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_dms_alarm(self, alarm_id):
        """Get specific DMS alarm"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM dms_alarms WHERE alarm_id = ?', (alarm_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def acknowledge_dms_alarm(self, alarm_id):
        """Acknowledge a DMS alarm"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE dms_alarms 
                SET alarm_acknowledged = 1, alarm_acknowledged_time = ?
                WHERE alarm_id = ?
            ''', (datetime.now().isoformat(), alarm_id))
    
    def clear_dms_alarm(self, alarm_id):
        """Clear a DMS alarm"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE dms_alarms 
                SET alarm_cleared_time = ?, perceived_severity = 'CLEARED'
                WHERE alarm_id = ?
            ''', (datetime.now().isoformat(), alarm_id))
    
    # =========================================================================
    # PERFORMANCE MONITORING OPERATIONS
    # =========================================================================
    
    def create_pm_job(self, job_id, job_type, object_type, object_instance_ids, 
                      callback_uri=None, collection_interval=60):
        """Create a performance monitoring job"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO pm_jobs 
                (job_id, job_type, object_type, object_instance_ids, 
                 callback_uri, collection_interval)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (job_id, job_type, object_type, 
                  json.dumps(object_instance_ids), callback_uri, collection_interval))
    
    def get_pm_jobs(self, job_type=None):
        """Get all PM jobs, optionally filtered by type"""
        with self.get_connection() as conn:
            if job_type:
                cursor = conn.execute(
                    'SELECT * FROM pm_jobs WHERE job_type = ? ORDER BY created_at DESC',
                    (job_type,)
                )
            else:
                cursor = conn.execute('SELECT * FROM pm_jobs ORDER BY created_at DESC')
            
            jobs = []
            for row in cursor.fetchall():
                job = dict(row)
                if job['object_instance_ids']:
                    job['object_instance_ids'] = json.loads(job['object_instance_ids'])
                jobs.append(job)
            return jobs
    
    def get_pm_job(self, job_id):
        """Get specific PM job"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM pm_jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()
            if row:
                job = dict(row)
                if job['object_instance_ids']:
                    job['object_instance_ids'] = json.loads(job['object_instance_ids'])
                return job
            return None
    
    def delete_pm_job(self, job_id):
        """Delete a PM job"""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM pm_jobs WHERE job_id = ?', (job_id,))
            conn.execute('DELETE FROM pm_reports WHERE job_id = ?', (job_id,))
    
    def create_pm_report(self, report_id, job_id, entries):
        """Create a performance report"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO pm_reports (report_id, job_id, entries)
                VALUES (?, ?, ?)
            ''', (report_id, job_id, json.dumps(entries)))
    
    def get_pm_reports(self, job_id):
        """Get all reports for a PM job"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM pm_reports WHERE job_id = ? ORDER BY created_at DESC',
                (job_id,)
            )
            reports = []
            for row in cursor.fetchall():
                report = dict(row)
                if report['entries']:
                    report['entries'] = json.loads(report['entries'])
                reports.append(report)
            return reports
    
    def get_pm_report(self, report_id):
        """Get specific PM report"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM pm_reports WHERE report_id = ?', (report_id,))
            row = cursor.fetchone()
            if row:
                report = dict(row)
                if report['entries']:
                    report['entries'] = json.loads(report['entries'])
                return report
            return None
    
    def create_pm_threshold(self, threshold_id, object_type, object_instance_id, 
                           criteria, callback_uri=None):
        """Create a performance threshold"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO pm_thresholds 
                (threshold_id, object_type, object_instance_id, criteria, callback_uri)
                VALUES (?, ?, ?, ?, ?)
            ''', (threshold_id, object_type, object_instance_id, 
                  json.dumps(criteria), callback_uri))
    
    def get_pm_thresholds(self):
        """Get all PM thresholds"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM pm_thresholds ORDER BY created_at DESC')
            thresholds = []
            for row in cursor.fetchall():
                threshold = dict(row)
                if threshold['criteria']:
                    threshold['criteria'] = json.loads(threshold['criteria'])
                thresholds.append(threshold)
            return thresholds
    
    def get_pm_threshold(self, threshold_id):
        """Get specific PM threshold"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM pm_thresholds WHERE threshold_id = ?',
                (threshold_id,)
            )
            row = cursor.fetchone()
            if row:
                threshold = dict(row)
                if threshold['criteria']:
                    threshold['criteria'] = json.loads(threshold['criteria'])
                return threshold
            return None
    
    def delete_pm_threshold(self, threshold_id):
        """Delete a PM threshold"""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM pm_thresholds WHERE threshold_id = ?', (threshold_id,))


# Singleton instance
db = DatabaseManager()
