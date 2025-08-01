#!/usr/bin/env python3
"""
Task Queue System for 90-Second Briefings
Orchestrates work across Mini-Workers with priority and cost controls
"""

import os
import asyncio
import logging
import sqlite3
import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import redis

class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 5
    HIGH = 8
    URGENT = 10

@dataclass
class Task:
    id: str
    description: str
    task_type: str
    priority: int
    parameters: Dict[str, Any]
    worker_type: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = None
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_worker: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 3600
    cost_estimate: float = 0.0
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.dependencies is None:
            self.dependencies = []

class QueueBackend:
    """Abstract base for queue storage backends"""
    
    async def add_task(self, task: Task) -> str:
        raise NotImplementedError
    
    async def get_next_task(self, worker_type: str = None) -> Optional[Task]:
        raise NotImplementedError
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        raise NotImplementedError
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        raise NotImplementedError
    
    async def list_tasks(self, status: TaskStatus = None, worker_type: str = None) -> List[Task]:
        raise NotImplementedError

class SQLiteQueueBackend(QueueBackend):
    """SQLite backend for task queue"""
    
    def __init__(self, db_path: str = "data/task_queue.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    parameters TEXT NOT NULL,
                    worker_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    assigned_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    assigned_worker TEXT,
                    result TEXT,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    timeout_seconds INTEGER DEFAULT 3600,
                    cost_estimate REAL DEFAULT 0.0,
                    dependencies TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status_priority 
                ON tasks(status, priority DESC, created_at ASC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_worker_type 
                ON tasks(worker_type, status)
            """)
            
            conn.commit()
    
    async def add_task(self, task: Task) -> str:
        """Add task to queue"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO tasks 
                    (id, description, task_type, priority, parameters, worker_type, 
                     status, created_at, max_retries, timeout_seconds, cost_estimate, dependencies)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.id,
                    task.description,
                    task.task_type,
                    task.priority,
                    json.dumps(task.parameters),
                    task.worker_type,
                    task.status.value,
                    task.created_at.isoformat(),
                    task.max_retries,
                    task.timeout_seconds,
                    task.cost_estimate,
                    json.dumps(task.dependencies)
                ))
                conn.commit()
        
        return task.id
    
    async def get_next_task(self, worker_type: str = None) -> Optional[Task]:
        """Get next available task"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Build query
                query = """
                    SELECT * FROM tasks 
                    WHERE status = 'pending'
                """
                params = []
                
                if worker_type:
                    query += " AND worker_type = ?"
                    params.append(worker_type)
                
                query += " ORDER BY priority DESC, created_at ASC LIMIT 1"
                
                cursor = conn.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    # Check dependencies
                    dependencies = json.loads(row['dependencies'] or '[]')
                    if dependencies:
                        # Check if all dependencies are completed
                        for dep_id in dependencies:
                            dep_cursor = conn.execute(
                                "SELECT status FROM tasks WHERE id = ?",
                                (dep_id,)
                            )
                            dep_row = dep_cursor.fetchone()
                            if not dep_row or dep_row['status'] != 'completed':
                                return None  # Dependencies not met
                    
                    # Mark as assigned
                    conn.execute("""
                        UPDATE tasks 
                        SET status = 'assigned', assigned_at = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), row['id']))
                    conn.commit()
                    
                    # Convert to Task object
                    task = Task(
                        id=row['id'],
                        description=row['description'],
                        task_type=row['task_type'],
                        priority=row['priority'],
                        parameters=json.loads(row['parameters']),
                        worker_type=row['worker_type'],
                        status=TaskStatus(row['status']),
                        created_at=datetime.fromisoformat(row['created_at']),
                        assigned_at=datetime.fromisoformat(row['assigned_at']) if row['assigned_at'] else None,
                        started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
                        completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                        assigned_worker=row['assigned_worker'],
                        result=row['result'],
                        error=row['error'],
                        retry_count=row['retry_count'],
                        max_retries=row['max_retries'],
                        timeout_seconds=row['timeout_seconds'],
                        cost_estimate=row['cost_estimate'],
                        dependencies=json.loads(row['dependencies'] or '[]')
                    )
                    
                    return task
        
        return None
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Update task with new data"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                # Build dynamic update query
                set_clauses = []
                params = []
                
                for key, value in updates.items():
                    if key in ['status', 'assigned_worker', 'result', 'error', 'retry_count']:
                        set_clauses.append(f"{key} = ?")
                        params.append(value)
                    elif key.endswith('_at'):
                        set_clauses.append(f"{key} = ?")
                        params.append(value)
                
                if set_clauses:
                    query = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
                    params.append(task_id)
                    
                    cursor = conn.execute(query, params)
                    conn.commit()
                    
                    return cursor.rowcount > 0
        
        return False
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get specific task by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            
            if row:
                return Task(
                    id=row['id'],
                    description=row['description'],
                    task_type=row['task_type'],
                    priority=row['priority'],
                    parameters=json.loads(row['parameters']),
                    worker_type=row['worker_type'],
                    status=TaskStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    assigned_at=datetime.fromisoformat(row['assigned_at']) if row['assigned_at'] else None,
                    started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                    assigned_worker=row['assigned_worker'],
                    result=row['result'],
                    error=row['error'],
                    retry_count=row['retry_count'],
                    max_retries=row['max_retries'],
                    timeout_seconds=row['timeout_seconds'],
                    cost_estimate=row['cost_estimate'],
                    dependencies=json.loads(row['dependencies'] or '[]')
                )
        
        return None
    
    async def list_tasks(self, status: TaskStatus = None, worker_type: str = None) -> List[Task]:
        """List tasks with optional filtering"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT * FROM tasks WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status.value)
            
            if worker_type:
                query += " AND worker_type = ?"
                params.append(worker_type)
            
            query += " ORDER BY created_at DESC"
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            tasks = []
            for row in rows:
                task = Task(
                    id=row['id'],
                    description=row['description'],
                    task_type=row['task_type'],
                    priority=row['priority'],
                    parameters=json.loads(row['parameters']),
                    worker_type=row['worker_type'],
                    status=TaskStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    assigned_at=datetime.fromisoformat(row['assigned_at']) if row['assigned_at'] else None,
                    started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                    assigned_worker=row['assigned_worker'],
                    result=row['result'],
                    error=row['error'],
                    retry_count=row['retry_count'],
                    max_retries=row['max_retries'],
                    timeout_seconds=row['timeout_seconds'],
                    cost_estimate=row['cost_estimate'],
                    dependencies=json.loads(row['dependencies'] or '[]')
                )
                tasks.append(task)
            
            return tasks

class RedisQueueBackend(QueueBackend):
    """Redis backend for distributed task queue"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        try:
            self.redis = redis.from_url(redis_url)
            self.redis.ping()
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Redis: {e}")
    
    async def add_task(self, task: Task) -> str:
        """Add task to Redis queue"""
        # Store task data
        task_data = asdict(task)
        task_data['created_at'] = task.created_at.isoformat()
        task_data['status'] = task.status.value
        
        # Convert datetime fields
        for field in ['assigned_at', 'started_at', 'completed_at']:
            if task_data[field]:
                task_data[field] = task_data[field].isoformat()
        
        self.redis.hset(f"task:{task.id}", mapping={
            k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            for k, v in task_data.items()
        })
        
        # Add to priority queue
        queue_key = f"queue:{task.worker_type}:pending"
        self.redis.zadd(queue_key, {task.id: task.priority})
        
        return task.id
    
    async def get_next_task(self, worker_type: str = None) -> Optional[Task]:
        """Get next task from Redis queue"""
        if not worker_type:
            return None
        
        queue_key = f"queue:{worker_type}:pending"
        
        # Get highest priority task
        task_ids = self.redis.zrevrange(queue_key, 0, 0)
        
        if task_ids:
            task_id = task_ids[0].decode('utf-8')
            
            # Move to processing queue
            self.redis.zrem(queue_key, task_id)
            processing_key = f"queue:{worker_type}:processing"
            self.redis.zadd(processing_key, {task_id: time.time()})
            
            # Get task data
            task_data = self.redis.hgetall(f"task:{task_id}")
            
            if task_data:
                # Convert back to Task object
                data = {}
                for k, v in task_data.items():
                    key = k.decode('utf-8')
                    value = v.decode('utf-8')
                    
                    if key in ['parameters', 'dependencies']:
                        data[key] = json.loads(value)
                    elif key.endswith('_at') and value != 'None':
                        data[key] = datetime.fromisoformat(value)
                    elif key in ['priority', 'retry_count', 'max_retries', 'timeout_seconds']:
                        data[key] = int(value)
                    elif key == 'cost_estimate':
                        data[key] = float(value)
                    elif key == 'status':
                        data[key] = TaskStatus(value)
                    else:
                        data[key] = value
                
                return Task(**data)
        
        return None
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Update task in Redis"""
        updates_formatted = {}
        for k, v in updates.items():
            if isinstance(v, datetime):
                updates_formatted[k] = v.isoformat()
            elif isinstance(v, Enum):
                updates_formatted[k] = v.value
            elif isinstance(v, (dict, list)):
                updates_formatted[k] = json.dumps(v)
            else:
                updates_formatted[k] = str(v)
        
        return self.redis.hset(f"task:{task_id}", mapping=updates_formatted) > 0
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task from Redis"""
        task_data = self.redis.hgetall(f"task:{task_id}")
        
        if task_data:
            data = {}
            for k, v in task_data.items():
                key = k.decode('utf-8')
                value = v.decode('utf-8')
                
                if key in ['parameters', 'dependencies']:
                    data[key] = json.loads(value)
                elif key.endswith('_at') and value != 'None':
                    data[key] = datetime.fromisoformat(value)
                elif key in ['priority', 'retry_count', 'max_retries', 'timeout_seconds']:
                    data[key] = int(value)
                elif key == 'cost_estimate':
                    data[key] = float(value)
                elif key == 'status':
                    data[key] = TaskStatus(value)
                else:
                    data[key] = value
            
            return Task(**data)
        
        return None

class TaskQueue:
    """Main task queue orchestrator"""
    
    def __init__(self, backend_type: str = "sqlite", **backend_kwargs):
        self.logger = logging.getLogger(__name__)
        
        # Initialize backend
        if backend_type == "sqlite":
            self.backend = SQLiteQueueBackend(**backend_kwargs)
        elif backend_type == "redis":
            self.backend = RedisQueueBackend(**backend_kwargs)
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")
        
        # Task monitoring
        self.running = False
        self.monitor_task = None
        
        self.logger.info(f"TaskQueue initialized with {backend_type} backend")
    
    async def submit_task(self, description: str, task_type: str, worker_type: str = None,
                         priority: int = TaskPriority.MEDIUM.value, timeout: int = 3600,
                         dependencies: List[str] = None, **parameters) -> str:
        """Submit new task to queue"""
        
        # Auto-determine worker type if not specified
        if not worker_type:
            worker_type = self._determine_worker_type(task_type)
        
        # Generate task ID
        task_id = str(uuid.uuid4())[:8]
        
        # Estimate cost
        cost_estimate = self._estimate_task_cost(task_type, parameters)
        
        # Create task
        task = Task(
            id=task_id,
            description=description,
            task_type=task_type,
            priority=priority,
            parameters=parameters,
            worker_type=worker_type,
            timeout_seconds=timeout,
            cost_estimate=cost_estimate,
            dependencies=dependencies or []
        )
        
        # Add to queue
        await self.backend.add_task(task)
        
        self.logger.info(f"Task submitted: {task_id} - {description}")
        return task_id
    
    def _determine_worker_type(self, task_type: str) -> str:
        """Auto-determine worker type from task type"""
        worker_mapping = {
            'scrape_source': 'scraper',
            'scrape_social': 'scraper',
            'scrape_rss': 'scraper',
            'generate_briefing': 'summarizer',
            'analyze_sentiment': 'summarizer',
            'extract_topics': 'summarizer',
            'generate_audio': 'audio',
            'create_podcast_episode': 'audio',
            'generate_rss_feed': 'audio',
            'deliver_briefing': 'dashboard',
            'send_email_digest': 'dashboard',
            'export_to_notion': 'dashboard',
            'start_dashboard': 'dashboard'
        }
        
        return worker_mapping.get(task_type, 'general')
    
    def _estimate_task_cost(self, task_type: str, parameters: Dict[str, Any]) -> float:
        """Estimate task cost in pounds"""
        base_costs = {
            'scrape_source': 0.01,  # Web scraping
            'generate_briefing': 0.05,  # Claude Haiku summarization
            'generate_audio': 0.10,  # OpenAI TTS
            'deliver_briefing': 0.02,  # Email/Notion delivery
        }
        
        base_cost = base_costs.get(task_type, 0.01)
        
        # Adjust for complexity
        if 'source_url' in parameters:
            base_cost *= 1.2  # Web scraping complexity
        if 'max_posts' in parameters:
            base_cost *= parameters.get('max_posts', 10) / 10
        
        return round(base_cost, 3)
    
    async def get_next_task(self, worker_type: str = None) -> Optional[Task]:
        """Get next task for worker"""
        return await self.backend.get_next_task(worker_type)
    
    async def update_task_status(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Update task status and metadata"""
        return await self.backend.update_task(task_id, updates)
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get specific task"""
        return await self.backend.get_task(task_id)
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status info"""
        task = await self.get_task(task_id)
        if task:
            return {
                'id': task.id,
                'status': task.status.value,
                'progress': self._calculate_progress(task),
                'created_at': task.created_at.isoformat(),
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'result': task.result,
                'error': task.error
            }
        return None
    
    def _calculate_progress(self, task: Task) -> float:
        """Calculate task progress percentage"""
        if task.status == TaskStatus.PENDING:
            return 0.0
        elif task.status == TaskStatus.ASSIGNED:
            return 0.1
        elif task.status == TaskStatus.PROCESSING:
            return 0.5
        elif task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            return 1.0
        else:
            return 0.0
    
    async def list_tasks(self, status: TaskStatus = None, worker_type: str = None) -> List[Task]:
        """List tasks with filtering"""
        return await self.backend.list_tasks(status, worker_type)
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        all_tasks = await self.list_tasks()
        
        stats = {
            'total_tasks': len(all_tasks),
            'by_status': {},
            'by_worker_type': {},
            'by_priority': {},
            'average_completion_time': 0,
            'total_cost': 0
        }
        
        completion_times = []
        
        for task in all_tasks:
            # Status counts
            status = task.status.value
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
            
            # Worker type counts
            worker_type = task.worker_type
            stats['by_worker_type'][worker_type] = stats['by_worker_type'].get(worker_type, 0) + 1
            
            # Priority counts
            priority = task.priority
            stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1
            
            # Completion times
            if task.completed_at and task.created_at:
                completion_time = (task.completed_at - task.created_at).total_seconds()
                completion_times.append(completion_time)
            
            # Total cost
            stats['total_cost'] += task.cost_estimate
        
        if completion_times:
            stats['average_completion_time'] = sum(completion_times) / len(completion_times)
        
        return stats
    
    async def start_monitoring(self):
        """Start background task monitoring"""
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_tasks())
        self.logger.info("Task monitoring started")
    
    async def stop_monitoring(self):
        """Stop background monitoring"""
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
        self.logger.info("Task monitoring stopped")
    
    async def _monitor_tasks(self):
        """Monitor tasks for timeouts and failures"""
        while self.running:
            try:
                # Check for timed out tasks
                processing_tasks = await self.list_tasks(TaskStatus.PROCESSING)
                
                for task in processing_tasks:
                    if task.started_at:
                        elapsed = (datetime.now() - task.started_at).total_seconds()
                        if elapsed > task.timeout_seconds:
                            # Mark as failed due to timeout
                            await self.update_task_status(task.id, {
                                'status': TaskStatus.FAILED.value,
                                'error': f'Task timed out after {elapsed:.0f} seconds',
                                'completed_at': datetime.now().isoformat()
                            })
                            
                            self.logger.warning(f"Task {task.id} timed out")
                
                # Check for failed tasks that can be retried
                failed_tasks = await self.list_tasks(TaskStatus.FAILED)
                
                for task in failed_tasks:
                    if task.retry_count < task.max_retries:
                        # Reset for retry
                        await self.update_task_status(task.id, {
                            'status': TaskStatus.PENDING.value,
                            'retry_count': task.retry_count + 1,
                            'assigned_at': None,
                            'started_at': None,
                            'assigned_worker': None,
                            'error': None
                        })
                        
                        self.logger.info(f"Task {task.id} queued for retry {task.retry_count + 1}")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in task monitoring: {e}")
                await asyncio.sleep(30)

# CLI Interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Task Queue Manager")
    parser.add_argument("--backend", choices=["sqlite", "redis"], default="sqlite")
    parser.add_argument("--submit", help="Submit a new task")
    parser.add_argument("--type", default="general", help="Task type")
    parser.add_argument("--worker", help="Worker type")
    parser.add_argument("--priority", type=int, default=5, help="Task priority")
    parser.add_argument("--list", action="store_true", help="List all tasks")
    parser.add_argument("--status", help="Filter by status")
    parser.add_argument("--stats", action="store_true", help="Show queue statistics")
    parser.add_argument("--monitor", action="store_true", help="Start monitoring")
    
    args = parser.parse_args()
    
    queue = TaskQueue(backend_type=args.backend)
    
    if args.submit:
        task_id = await queue.submit_task(
            description=args.submit,
            task_type=args.type,
            worker_type=args.worker,
            priority=args.priority
        )
        print(f"Task submitted: {task_id}")
    
    elif args.list:
        status_filter = TaskStatus(args.status) if args.status else None
        tasks = await queue.list_tasks(status=status_filter)
        
        print(f"Found {len(tasks)} tasks:")
        for task in tasks:
            print(f"  {task.id}: {task.status.value} - {task.description[:50]}...")
    
    elif args.stats:
        stats = await queue.get_queue_stats()
        print("Queue Statistics:")
        print(f"  Total tasks: {stats['total_tasks']}")
        print(f"  By status: {stats['by_status']}")
        print(f"  By worker: {stats['by_worker_type']}")
        print(f"  Total cost: £{stats['total_cost']:.2f}")
        print(f"  Avg completion: {stats['average_completion_time']:.1f}s")
    
    elif args.monitor:
        await queue.start_monitoring()
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await queue.stop_monitoring()
    
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())