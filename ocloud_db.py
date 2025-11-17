#!/usr/bin/env python3
"""
O-CLOUD Database Manager
Handles infrastructure inventory and monitoring data for O2 IMS and DMS interfaces
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
import threading

class OCloudDB:
    def __init__(self, db_path: str = "ocloud.db"):
        self.db_path = db_path
        self.local = threading.local()
        self._init_db()
    
    def _get_connection(self):
        """Get thread-local database connection"""
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn
    
    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def _init_db(self):
        """Initialize database with schema"""
        with open('ocloud_schema.sql', 'r') as f:
            schema = f.read()
        
        with self.get_cursor() as cursor:
            cursor.executescript(schema)
    
    # =========================================================================
    # O-Cloud Operations
    # =========================================================================
    
    def init_ocloud(self, ocloud_id: str, global_cloud_id: str, name: str, 
                    description: str = None, service_uri: str = None):
        """Initialize O-Cloud instance"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO ocloud 
                (ocloud_id, global_cloud_id, name, description, service_uri, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ocloud_id, global_cloud_id, name, description, service_uri, 
                  datetime.now(timezone.utc).isoformat()))
    
    def get_ocloud(self, ocloud_id: str) -> Optional[Dict]:
        """Get O-Cloud information"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM ocloud WHERE ocloud_id = ?", (ocloud_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # =========================================================================
    # Resource Pool Operations
    # =========================================================================
    
    def create_resource_pool(self, pool_id: str, ocloud_id: str, name: str,
                            description: str = None, location: str = None,
                            global_location_id: str = None) -> str:
        """Create a resource pool"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO resource_pools 
                (resource_pool_id, ocloud_id, global_location_id, name, description, location, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pool_id, ocloud_id, global_location_id, name, description, location,
                  datetime.now(timezone.utc).isoformat()))
        return pool_id
    
    def get_resource_pool(self, pool_id: str) -> Optional[Dict]:
        """Get resource pool by ID"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM resource_pools WHERE resource_pool_id = ?", (pool_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_resource_pools(self, ocloud_id: str = None) -> List[Dict]:
        """Get all resource pools, optionally filtered by ocloud_id"""
        with self.get_cursor() as cursor:
            if ocloud_id:
                cursor.execute("SELECT * FROM resource_pools WHERE ocloud_id = ?", (ocloud_id,))
            else:
                cursor.execute("SELECT * FROM resource_pools")
            return [dict(row) for row in cursor.fetchall()]
    
    # =========================================================================
    # Resource Type Operations
    # =========================================================================
    
    def create_resource_type(self, type_id: str, name: str, vendor: str = None,
                            model: str = None, version: str = None, 
                            description: str = None) -> str:
        """Create a resource type"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO resource_types 
                (resource_type_id, name, vendor, model, version, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (type_id, name, vendor, model, version, description))
        return type_id
    
    def get_resource_type(self, type_id: str) -> Optional[Dict]:
        """Get resource type by ID"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM resource_types WHERE resource_type_id = ?", (type_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_resource_types(self) -> List[Dict]:
        """Get all resource types"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM resource_types")
            return [dict(row) for row in cursor.fetchall()]
    
    # =========================================================================
    # Resource Operations (Physical/Virtual Infrastructure)
    # =========================================================================
    
    def create_resource(self, resource_id: str, resource_type_id: str,
                       resource_pool_id: str, name: str, description: str = None,
                       global_asset_id: str = None, parent_id: str = None,
                       extensions: Dict = None) -> str:
        """Create an infrastructure resource"""
        extensions_json = json.dumps(extensions) if extensions else None
        
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO resources 
                (resource_id, resource_type_id, resource_pool_id, global_asset_id,
                 name, description, parent_id, extensions, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (resource_id, resource_type_id, resource_pool_id, global_asset_id,
                  name, description, parent_id, extensions_json,
                  datetime.now(timezone.utc).isoformat()))
        return resource_id
    
    def get_resource(self, resource_id: str) -> Optional[Dict]:
        """Get resource by ID"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM resources WHERE resource_id = ?", (resource_id,))
            row = cursor.fetchone()
            if row:
                resource = dict(row)
                if resource.get('extensions'):
                    resource['extensions'] = json.loads(resource['extensions'])
                return resource
            return None
    
    def get_resources(self, resource_pool_id: str = None, 
                     resource_type_id: str = None) -> List[Dict]:
        """Get resources with optional filters"""
        with self.get_cursor() as cursor:
            query = "SELECT * FROM resources WHERE 1=1"
            params = []
            
            if resource_pool_id:
                query += " AND resource_pool_id = ?"
                params.append(resource_pool_id)
            
            if resource_type_id:
                query += " AND resource_type_id = ?"
                params.append(resource_type_id)
            
            cursor.execute(query, params)
            resources = []
            for row in cursor.fetchall():
                resource = dict(row)
                if resource.get('extensions'):
                    resource['extensions'] = json.loads(resource['extensions'])
                resources.append(resource)
            return resources
    
    def update_resource_state(self, resource_id: str, 
                             administrative_state: str = None,
                             operational_state: str = None,
                             availability_status: str = None):
        """Update resource operational states"""
        updates = []
        params = []
        
        if administrative_state:
            updates.append("administrative_state = ?")
            params.append(administrative_state)
        
        if operational_state:
            updates.append("operational_state = ?")
            params.append(operational_state)
        
        if availability_status:
            updates.append("availability_status = ?")
            params.append(availability_status)
        
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(resource_id)
            
            with self.get_cursor() as cursor:
                cursor.execute(f"""
                    UPDATE resources SET {', '.join(updates)} WHERE resource_id = ?
                """, params)
    
    # =========================================================================
    # Deployment Manager Operations
    # =========================================================================
    
    def create_deployment_manager(self, dm_id: str, ocloud_id: str, name: str,
                                  dm_type: str, service_uri: str = None,
                                  description: str = None, support_profiles: List = None,
                                  capacity: Dict = None) -> str:
        """Create a deployment manager"""
        profiles_json = json.dumps(support_profiles) if support_profiles else None
        capacity_json = json.dumps(capacity) if capacity else None
        
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO deployment_managers 
                (deployment_manager_id, ocloud_id, name, description,
                 deployment_manager_type, service_uri, support_profiles, capacity, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (dm_id, ocloud_id, name, description, dm_type, service_uri,
                  profiles_json, capacity_json, datetime.now(timezone.utc).isoformat()))
        return dm_id
    
    def get_deployment_manager(self, dm_id: str) -> Optional[Dict]:
        """Get deployment manager by ID"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM deployment_managers WHERE deployment_manager_id = ?", (dm_id,))
            row = cursor.fetchone()
            if row:
                dm = dict(row)
                if dm.get('support_profiles'):
                    dm['support_profiles'] = json.loads(dm['support_profiles'])
                if dm.get('capacity'):
                    dm['capacity'] = json.loads(dm['capacity'])
                return dm
            return None
    
    def get_deployment_managers(self, ocloud_id: str = None) -> List[Dict]:
        """Get all deployment managers"""
        with self.get_cursor() as cursor:
            if ocloud_id:
                cursor.execute("SELECT * FROM deployment_managers WHERE ocloud_id = ?", (ocloud_id,))
            else:
                cursor.execute("SELECT * FROM deployment_managers")
            
            managers = []
            for row in cursor.fetchall():
                dm = dict(row)
                if dm.get('support_profiles'):
                    dm['support_profiles'] = json.loads(dm['support_profiles'])
                if dm.get('capacity'):
                    dm['capacity'] = json.loads(dm['capacity'])
                managers.append(dm)
            return managers
    
    # =========================================================================
    # Performance Monitoring Operations
    # =========================================================================
    
    def create_performance_job(self, job_id: str, object_type: str,
                              object_instance_ids: List[str], criteria: Dict,
                              callback_uri: str, collection_interval: int = 60,
                              reporting_period: int = 300) -> str:
        """Create a performance monitoring job"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO performance_jobs 
                (job_id, object_type, object_instance_ids, criteria, callback_uri,
                 collection_interval, reporting_period, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, object_type, json.dumps(object_instance_ids), 
                  json.dumps(criteria), callback_uri, collection_interval,
                  reporting_period, datetime.now(timezone.utc).isoformat()))
        return job_id
    
    def get_performance_job(self, job_id: str) -> Optional[Dict]:
        """Get performance job by ID"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM performance_jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                job = dict(row)
                job['object_instance_ids'] = json.loads(job['object_instance_ids'])
                job['criteria'] = json.loads(job['criteria'])
                return job
            return None
    
    def get_performance_jobs(self) -> List[Dict]:
        """Get all performance jobs"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM performance_jobs")
            jobs = []
            for row in cursor.fetchall():
                job = dict(row)
                # Parse JSON fields
                try:
                    job['object_instance_ids'] = json.loads(job['object_instance_ids'])
                except:
                    pass
                try:
                    job['criteria'] = json.loads(job['criteria'])
                except:
                    pass
                jobs.append(job)
            return jobs
    
    def record_performance_data(self, resource_id: str, metric_id: str, 
                               value: float, timestamp: datetime = None):
        """Record performance metric data"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO performance_data (resource_id, metric_id, value, timestamp)
                VALUES (?, ?, ?, ?)
            """, (resource_id, metric_id, value, timestamp.isoformat()))
    
    def get_performance_data(self, resource_id: str, metric_id: str = None,
                            start_time: datetime = None, end_time: datetime = None,
                            limit: int = 1000) -> List[Dict]:
        """Query performance data"""
        with self.get_cursor() as cursor:
            query = "SELECT * FROM performance_data WHERE resource_id = ?"
            params = [resource_id]
            
            if metric_id:
                query += " AND metric_id = ?"
                params.append(metric_id)
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # =========================================================================
    # Alarm Operations
    # =========================================================================
    
    def create_alarm(self, alarm_id: str, resource_id: str, perceived_severity: str,
                    probable_cause: str, alarm_type: str = None,
                    is_root_cause: bool = False) -> str:
        """Create an infrastructure alarm"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO alarms 
                (alarm_id, resource_id, alarm_raised_time, perceived_severity,
                 probable_cause, alarm_type, is_root_cause)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (alarm_id, resource_id, datetime.now(timezone.utc).isoformat(),
                  perceived_severity, probable_cause, alarm_type, is_root_cause))
        return alarm_id
    
    def get_alarm(self, alarm_id: str) -> Optional[Dict]:
        """Get alarm by ID"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM alarms WHERE alarm_id = ?", (alarm_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_alarms(self, resource_id: str = None, severity: str = None,
                  active_only: bool = False) -> List[Dict]:
        """Get alarms with optional filters"""
        with self.get_cursor() as cursor:
            query = "SELECT * FROM alarms WHERE 1=1"
            params = []
            
            if resource_id:
                query += " AND resource_id = ?"
                params.append(resource_id)
            
            if severity:
                query += " AND perceived_severity = ?"
                params.append(severity)
            
            if active_only:
                query += " AND alarm_cleared_time IS NULL"
            
            query += " ORDER BY alarm_raised_time DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def clear_alarm(self, alarm_id: str):
        """Clear an alarm"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE alarms 
                SET alarm_cleared_time = ?, alarm_changed_time = ?
                WHERE alarm_id = ?
            """, (datetime.now(timezone.utc).isoformat(),
                  datetime.now(timezone.utc).isoformat(), alarm_id))
    
    def acknowledge_alarm(self, alarm_id: str):
        """Acknowledge an alarm"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE alarms 
                SET alarm_acknowledged = 1, alarm_acknowledged_time = ?,
                    alarm_changed_time = ?
                WHERE alarm_id = ?
            """, (datetime.now(timezone.utc).isoformat(),
                  datetime.now(timezone.utc).isoformat(), alarm_id))
    
    def update_alarm(self, alarm_id: str, **kwargs):
        """Update alarm fields dynamically"""
        with self.get_cursor() as cursor:
            # Build dynamic UPDATE query
            fields = []
            values = []
            
            for key, value in kwargs.items():
                fields.append(f"{key} = ?")
                values.append(value)
            
            if fields:
                # Always update changed time
                fields.append("alarm_changed_time = ?")
                values.append(datetime.now(timezone.utc).isoformat())
                values.append(alarm_id)
                
                query = f"UPDATE alarms SET {', '.join(fields)} WHERE alarm_id = ?"
                cursor.execute(query, values)
    
    # =========================================================================
    # Subscription Operations
    # =========================================================================
    
    def create_subscription(self, subscription_id: str, subscription_type: str,
                           callback_uri: str, filter_criteria: Dict = None,
                           consumer_subscription_id: str = None,
                           expires_at: datetime = None) -> str:
        """Create a notification subscription"""
        filter_json = json.dumps(filter_criteria) if filter_criteria else None
        expires = expires_at.isoformat() if expires_at else None
        
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO subscriptions 
                (subscription_id, subscription_type, callback_uri, filter,
                 consumer_subscription_id, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subscription_id, subscription_type, callback_uri, filter_json,
                  consumer_subscription_id, expires))
        return subscription_id
    
    def get_subscription(self, subscription_id: str) -> Optional[Dict]:
        """Get subscription by ID"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM subscriptions WHERE subscription_id = ?", 
                         (subscription_id,))
            row = cursor.fetchone()
            if row:
                sub = dict(row)
                if sub.get('filter'):
                    sub['filter'] = json.loads(sub['filter'])
                return sub
            return None
    
    def get_subscriptions(self, subscription_type: str = None) -> List[Dict]:
        """Get all subscriptions"""
        with self.get_cursor() as cursor:
            if subscription_type:
                cursor.execute("SELECT * FROM subscriptions WHERE subscription_type = ?",
                             (subscription_type,))
            else:
                cursor.execute("SELECT * FROM subscriptions")
            
            subscriptions = []
            for row in cursor.fetchall():
                sub = dict(row)
                if sub.get('filter'):
                    sub['filter'] = json.loads(sub['filter'])
                subscriptions.append(sub)
            return subscriptions
    
    def delete_subscription(self, subscription_id: str):
        """Delete a subscription"""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM subscriptions WHERE subscription_id = ?",
                         (subscription_id,))
    
    # Performance Data Methods
    def get_performance_data_since(self, resource_id: str, metric_id: str, since_timestamp: str) -> List[Dict]:
        """Get performance data points since a timestamp"""
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT metric_id, value, timestamp
                FROM performance_data
                WHERE resource_id = ? AND metric_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            ''', (resource_id, metric_id, since_timestamp))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def update_performance_job_last_report(self, job_id: str, timestamp: str):
        """Update the last report time for a performance job"""
        with self.get_cursor() as cursor:
            cursor.execute('''
                UPDATE performance_jobs
                SET last_report_time = ?
                WHERE job_id = ?
            ''', (timestamp, job_id))

# Global database instance
db = OCloudDB()
