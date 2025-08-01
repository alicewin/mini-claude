#!/usr/bin/env python3
"""
Task Queue System for Mini-Claude
Supports both SQLite and Redis backends for task management
"""

import json
import sqlite3
import threading
import time
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import hashlib

# Import mini_claude Task class
from mini_claude import Task

class QueueBackend(ABC):
    """Abstract base class for queue backends"""
    
    @abstractmethod
    def add_task(self, task: Task) -> str:
        pass
    
    @abstractmethod
    def get_next_task(self) -> Optional[Task]:
        pass
    
    @abstractmethod
    def update_task_status(self, task: Task) -> bool:
        pass
    
    @abstractmethod
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        pass

class SQLiteBackend(QueueBackend):
    """SQLite backend for task storage"""
    
    def __init__(self, db_path: str = "mini_claude_tasks.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    result TEXT,
                    error TEXT,
                    priority INTEGER DEFAULT 5
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status_priority 
                ON tasks(status, priority, created_at)
            """)
            conn.commit()
    
    def add_task(self, task: Task) -> str:
        """Add a task to the queue"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO tasks 
                    (id, description, task_type, parameters, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    task.id,
                    task.description,
                    task.task_type,
                    json.dumps(task.parameters),
                    task.status,
                    task.created_at
                ))
                conn.commit()
        return task.id
    
    def get_next_task(self) -> Optional[Task]:
        """Get the next pending task"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM tasks 
                    WHERE status = 'pending' 
                    ORDER BY priority ASC, created_at ASC 
                    LIMIT 1
                """)
                row = cursor.fetchone()
                
                if row:
                    # Mark as processing
                    conn.execute(
                        "UPDATE tasks SET status = 'processing' WHERE id = ?",
                        (row['id'],)
                    )
                    conn.commit()
                    
                    return Task(
                        id=row['id'],
                        description=row['description'],
                        task_type=row['task_type'],
                        parameters=json.loads(row['parameters']),
                        status='processing',
                        created_at=row['created_at'],
                        completed_at=row['completed_at'],
                        result=row['result'],
                        error=row['error']
                    )
        return None
    
    def update_task_status(self, task: Task) -> bool:
        """Update task status and results"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE tasks 
                    SET status = ?, completed_at = ?, result = ?, error = ?
                    WHERE id = ?
                """, (
                    task.status,
                    task.completed_at,
                    task.result,
                    task.error,
                    task.id
                ))
                conn.commit()
                return conn.total_changes > 0
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row['id'],
                    'description': row['description'],
                    'status': row['status'],
                    'created_at': row['created_at'],
                    'completed_at': row['completed_at'],
                    'error': row['error']
                }
        return None
    
    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """List all tasks, optionally filtered by status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if status:
                cursor = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                )
            else:
                cursor = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            
            tasks = []
            for row in cursor.fetchall():
                tasks.append(Task(
                    id=row['id'],
                    description=row['description'],
                    task_type=row['task_type'],
                    parameters=json.loads(row['parameters']),
                    status=row['status'],
                    created_at=row['created_at'],
                    completed_at=row['completed_at'],
                    result=row['result'],
                    error=row['error']
                ))
            return tasks

class RedisBackend(QueueBackend):
    """Redis backend for distributed task queue"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        try:
            import redis
            self.redis = redis.from_url(redis_url)
            self.redis.ping()  # Test connection
        except ImportError:
            raise ImportError("Redis backend requires: pip install redis")
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Redis: {e}")
    
    def add_task(self, task: Task) -> str:
        """Add task to Redis queue"""
        task_data = {
            'id': task.id,
            'description': task.description,
            'task_type': task.task_type,
            'parameters': task.parameters,
            'status': task.status,
            'created_at': task.created_at
        }
        
        # Store task data
        self.redis.hset(f"task:{task.id}", mapping=task_data)
        
        # Add to pending queue
        self.redis.lpush("pending_tasks", task.id)
        
        return task.id
    
    def get_next_task(self) -> Optional[Task]:
        """Get next task from Redis queue"""
        # Move task from pending to processing
        task_id = self.redis.brpoplpush("pending_tasks", "processing_tasks", timeout=1)
        
        if task_id:
            task_id = task_id.decode('utf-8')
            task_data = self.redis.hgetall(f"task:{task_id}")
            
            if task_data:
                # Mark as processing
                self.redis.hset(f"task:{task_id}", "status", "processing")
                
                return Task(
                    id=task_data[b'id'].decode('utf-8'),
                    description=task_data[b'description'].decode('utf-8'),
                    task_type=task_data[b'task_type'].decode('utf-8'),
                    parameters=json.loads(task_data[b'parameters'].decode('utf-8')),
                    status='processing',
                    created_at=task_data[b'created_at'].decode('utf-8')
                )
        return None
    
    def update_task_status(self, task: Task) -> bool:
        """Update task status in Redis"""
        updates = {
            'status': task.status,
            'completed_at': task.completed_at or '',
            'result': task.result or '',
            'error': task.error or ''
        }
        
        # Update task data
        self.redis.hset(f"task:{task.id}", mapping=updates)
        
        # Remove from processing queue if completed/failed
        if task.status in ['completed', 'failed']:
            self.redis.lrem("processing_tasks", 0, task.id)
        
        return True
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status from Redis"""
        task_data = self.redis.hgetall(f"task:{task_id}")
        
        if task_data:
            return {
                'id': task_data[b'id'].decode('utf-8'),
                'description': task_data[b'description'].decode('utf-8'),
                'status': task_data[b'status'].decode('utf-8'),
                'created_at': task_data[b'created_at'].decode('utf-8'),
                'completed_at': task_data.get(b'completed_at', b'').decode('utf-8'),
                'error': task_data.get(b'error', b'').decode('utf-8')
            }
        return None
    
    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """List tasks from Redis - basic implementation"""
        # This is a simplified implementation
        # In production, you'd want better indexing
        task_keys = self.redis.keys("task:*")
        tasks = []
        
        for key in task_keys:
            task_data = self.redis.hgetall(key)
            if task_data:
                task_status = task_data[b'status'].decode('utf-8')
                if status and task_status != status:
                    continue
                
                tasks.append(Task(
                    id=task_data[b'id'].decode('utf-8'),
                    description=task_data[b'description'].decode('utf-8'),
                    task_type=task_data[b'task_type'].decode('utf-8'),
                    parameters=json.loads(task_data[b'parameters'].decode('utf-8')),
                    status=task_status,
                    created_at=task_data[b'created_at'].decode('utf-8'),
                    completed_at=task_data.get(b'completed_at', b'').decode('utf-8'),
                    result=task_data.get(b'result', b'').decode('utf-8'),
                    error=task_data.get(b'error', b'').decode('utf-8')
                ))
        
        return sorted(tasks, key=lambda x: x.created_at, reverse=True)

class TaskQueue:
    """High-level task queue interface"""
    
    def __init__(self, backend_type: str = "sqlite", **backend_kwargs):
        if backend_type == "sqlite":
            self.backend = SQLiteBackend(**backend_kwargs)
        elif backend_type == "redis":
            self.backend = RedisBackend(**backend_kwargs)
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")
    
    def submit_task(self, description: str, task_type: str = "general", 
                   priority: int = 5, **parameters) -> str:
        """Submit a new task to the queue"""
        task = Task(
            id=self._generate_task_id(description),
            description=description,
            task_type=task_type,
            parameters=parameters,
            created_at=datetime.now().isoformat()
        )
        
        return self.backend.add_task(task)
    
    def get_next_task(self) -> Optional[Task]:
        """Get the next task to process"""
        return self.backend.get_next_task()
    
    def update_task_status(self, task: Task) -> bool:
        """Update task status and results"""
        return self.backend.update_task_status(task)
    
    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        return self.backend.get_task_status(task_id)
    
    def list_all_tasks(self, status: Optional[str] = None) -> List[Task]:
        """List all tasks"""
        return self.backend.list_tasks(status)
    
    def _generate_task_id(self, description: str) -> str:
        """Generate unique task ID"""
        timestamp = str(time.time())
        return hashlib.md5(f"{description}{timestamp}".encode()).hexdigest()[:8]

# CLI for task queue management
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Mini-Claude Task Queue Manager")
    parser.add_argument("--backend", choices=["sqlite", "redis"], default="sqlite")
    parser.add_argument("--submit", help="Submit a new task")
    parser.add_argument("--type", default="general", help="Task type")
    parser.add_argument("--list", action="store_true", help="List all tasks")
    parser.add_argument("--status", help="Filter by status")
    parser.add_argument("--get", help="Get task status by ID")
    
    args = parser.parse_args()
    
    queue = TaskQueue(backend_type=args.backend)
    
    if args.submit:
        task_id = queue.submit_task(args.submit, args.type)
        print(f"Task submitted: {task_id}")
    
    elif args.list:
        tasks = queue.list_all_tasks(args.status)
        print(f"Found {len(tasks)} tasks:")
        for task in tasks:
            print(f"  {task.id}: {task.status} - {task.description}")
    
    elif args.get:
        status = queue.get_status(args.get)
        if status:
            print(json.dumps(status, indent=2))
        else:
            print(f"Task {args.get} not found")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()