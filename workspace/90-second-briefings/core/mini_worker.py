#!/usr/bin/env python3
"""
Base Mini-Worker class for the 90-Second Briefings system
Provides common functionality and cost tracking integration
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod

from core.cost_tracker import get_cost_tracker
from core.task_queue import TaskQueue

class WorkerType(Enum):
    SCRAPER = "scraper"
    SUMMARIZER = "summarizer"
    AUDIO = "audio"
    DASHBOARD = "dashboard"
    PROJECT_MANAGER = "project_manager"

@dataclass
class WorkerStatus:
    worker_id: str
    worker_type: WorkerType
    status: str  # active, paused, stopped, error
    last_activity: datetime
    tasks_completed: int
    current_task: Optional[str]
    cost_today: float
    uptime_seconds: float
    error_count: int

class MiniWorker(ABC):
    """
    Abstract base class for all Mini-Workers in the system
    Provides common functionality, cost tracking, and error handling
    """
    
    def __init__(self, worker_id: str, worker_type: WorkerType):
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.logger = logging.getLogger(f"{worker_type.value}.{worker_id}")
        
        # Cost tracking
        self.cost_tracker = get_cost_tracker()
        
        # Task management
        self.task_queue = None  # Will be set by Project Manager
        self.current_task = None
        
        # Status tracking
        self.status = "initializing"
        self.start_time = datetime.now()
        self.last_activity = datetime.now()
        self.tasks_completed = 0
        self.error_count = 0
        
        # Configuration
        self.max_daily_cost = 5.0  # £5 per worker
        self.max_concurrent_tasks = 3
        self.health_check_interval = 300  # 5 minutes
        
        # Setup logging
        self._setup_logging()
        
        self.logger.info(f"Mini-Worker {worker_id} ({worker_type.value}) initialized")
    
    def _setup_logging(self):
        """Setup worker-specific logging"""
        
        # Create worker-specific log file
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = f"{log_dir}/{self.worker_type.value}_{self.worker_id}.log"
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def set_task_queue(self, task_queue: TaskQueue):
        """Set the task queue for this worker"""
        self.task_queue = task_queue
        self.logger.info("Task queue connected")
    
    async def start(self):
        """Start the worker"""
        self.status = "active"
        self.logger.info(f"Worker {self.worker_id} started")
        
        # Start main work loop
        await self._work_loop()
    
    async def stop(self):
        """Stop the worker gracefully"""
        self.status = "stopped"
        self.logger.info(f"Worker {self.worker_id} stopped")
    
    async def pause(self):
        """Pause the worker"""
        self.status = "paused"
        self.logger.info(f"Worker {self.worker_id} paused")
    
    async def resume(self):
        """Resume the worker"""
        if self.status == "paused":
            self.status = "active"
            self.logger.info(f"Worker {self.worker_id} resumed")
    
    async def _work_loop(self):
        """Main work loop for processing tasks"""
        
        while self.status in ["active", "paused"]:
            try:
                if self.status == "paused":
                    await asyncio.sleep(5)
                    continue
                
                # Check if we have budget for more work
                if not await self._check_budget():
                    self.logger.warning("Daily budget exceeded, pausing worker")
                    await self.pause()
                    continue
                
                # Get next task
                if self.task_queue:
                    task = await self.task_queue.get_next_task(self.worker_type.value)
                    
                    if task:
                        await self._process_task(task)
                    else:
                        # No tasks available, wait
                        await asyncio.sleep(10)
                else:
                    # No task queue, wait
                    await asyncio.sleep(30)
                    
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"Error in work loop: {e}")
                await asyncio.sleep(30)  # Back off on errors
    
    async def _process_task(self, task):
        """Process a single task"""
        
        self.current_task = task.id
        self.last_activity = datetime.now()
        
        try:
            self.logger.info(f"Processing task {task.id}: {task.description}")
            
            # Update task status
            if self.task_queue:
                await self.task_queue.update_task_status(task.id, {
                    "status": "processing",
                    "started_at": datetime.now().isoformat(),
                    "assigned_worker": self.worker_id
                })
            
            # Execute the task (implemented by subclasses)
            await self.execute_task(task.id)
            
            # Task completed successfully
            self.tasks_completed += 1
            self.current_task = None
            
            self.logger.info(f"Task {task.id} completed successfully")
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Task {task.id} failed: {e}")
            
            # Update task with error
            if self.task_queue:
                await self.task_queue.update_task_status(task.id, {
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.now().isoformat()
                })
    
    @abstractmethod
    async def execute_task(self, task_id: str):
        """
        Execute a specific task - must be implemented by subclasses
        """
        pass
    
    async def _check_budget(self) -> bool:
        """Check if worker has budget remaining for today"""
        
        summary = self.cost_tracker.get_daily_summary()
        worker_cost = summary["costs_by_worker"].get(self.worker_id, 0)
        
        return worker_cost < self.max_daily_cost
    
    async def track_cost(self, service: str, units: int, operation: str = "api_call", **metadata) -> float:
        """Track cost for this worker"""
        
        if operation == "api_call":
            return await self.cost_tracker.track_api_call(
                service, units, self.worker_id, **metadata
            )
        elif operation == "storage":
            return await self.cost_tracker.track_storage_cost(
                service, units, self.worker_id, operation, **metadata
            )
        else:
            return await self.cost_tracker.track_custom_cost(
                service, operation, metadata.get("cost_gbp", 0.001), 
                self.worker_id, units, **metadata
            )
    
    def get_status(self) -> WorkerStatus:
        """Get current worker status"""
        
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        # Get worker cost from cost tracker
        summary = self.cost_tracker.get_daily_summary()
        worker_cost = summary["costs_by_worker"].get(self.worker_id, 0)
        
        return WorkerStatus(
            worker_id=self.worker_id,
            worker_type=self.worker_type,
            status=self.status,
            last_activity=self.last_activity,
            tasks_completed=self.tasks_completed,
            current_task=self.current_task,
            cost_today=worker_cost,
            uptime_seconds=uptime,
            error_count=self.error_count
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        
        status = self.get_status()
        
        # Check if worker is responsive
        time_since_activity = (datetime.now() - self.last_activity).total_seconds()
        is_healthy = time_since_activity < self.health_check_interval
        
        # Check error rate
        error_rate = self.error_count / max(self.tasks_completed + self.error_count, 1)
        high_error_rate = error_rate > 0.1  # More than 10% errors
        
        # Check budget status
        has_budget = await self._check_budget()
        
        health_status = "healthy"
        if not is_healthy:
            health_status = "unresponsive"
        elif high_error_rate:
            health_status = "degraded"
        elif not has_budget:
            health_status = "budget_limited"
        
        return {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type.value,
            "health_status": health_status,
            "is_responsive": is_healthy,
            "error_rate": error_rate,
            "has_budget": has_budget,
            "status": asdict(status),
            "last_check": datetime.now().isoformat()
        }
    
    def __str__(self):
        return f"MiniWorker({self.worker_id}, {self.worker_type.value}, {self.status})"
    
    def __repr__(self):
        return self.__str__()

# Utility function to create workers
def create_worker(worker_type: str, worker_id: str = None) -> MiniWorker:
    """Factory function to create workers"""
    
    if worker_id is None:
        worker_id = f"{worker_type.title()}-01"
    
    if worker_type == "scraper":
        from scraper.scraper_worker import ScraperWorker
        return ScraperWorker(worker_id)
    
    elif worker_type == "summarizer":
        from core.summarizer_worker import SummarizationWorker
        return SummarizationWorker(worker_id)
    
    elif worker_type == "audio":
        from audio.audio_worker import AudioWorker
        return AudioWorker(worker_id)
    
    elif worker_type == "dashboard":
        from dashboard.dashboard_worker import DashboardWorker
        return DashboardWorker(worker_id)
    
    else:
        raise ValueError(f"Unknown worker type: {worker_type}")