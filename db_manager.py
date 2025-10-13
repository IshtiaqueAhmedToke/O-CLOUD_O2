#!/usr/bin/env python3
"""
Database Manager for O-CLOUD O2 Interface
Handles all database operations with SQLite
"""

import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

DATABASE_PATH = '/home/toke/o-cloud/ocloud.db'

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
    
    def create_subscription(self, subscription_id, callback_uri, filter_data=None):
        """Create a subscription"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO subscriptions (subscription_id, callback_uri, filter)
                VALUES (?, ?, ?)
            ''', (subscription_id, callback_uri, json.dumps(filter_data) if filter_data else None))
    
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
    
    def delete_subscription(self, subscription_id):
        """Delete a subscription"""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM subscriptions WHERE subscription_id = ?', (subscription_id,))


# Singleton instance
db = DatabaseManager()
