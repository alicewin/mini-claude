#!/usr/bin/env python3
"""
Project Manager Clone - Orchestrates Mini-Workers for 90-Second Briefings
Autonomous task coordination with cost and quality controls
"""

import os
import json
import logging
import asyncio
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from core.task_queue import TaskQueue, Task, TaskStatus
from core.cost_tracker import CostTracker
from core.mini_worker import MiniWorker, WorkerType
from core.claude_interface import ClaudeInterface

class ProjectStatus(Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class BriefingProject:
    id: str
    name: str
    niche: str
    frequency: str  # daily, weekly
    sources: List[str]
    delivery_methods: List[str]  # email, notion, rss, audio
    status: ProjectStatus
    created_at: datetime
    deadline: datetime
    tasks: List[str] = None
    cost_budget: float = 20.0  # £20 daily budget
    quality_threshold: float = 0.85

@dataclass
class WorkerAllocation:
    worker_id: str
    worker_type: WorkerType
    status: str
    current_task: Optional[str]
    cost_used: float
    performance_score: float

class ProjectManagerClone:
    """
    Autonomous Project Manager that coordinates Mini-Workers
    Reports to Claude Senior Engineer
    """
    
    def __init__(self, config_path: str = "config/pm_config.json"):
        self.config = self._load_config(config_path)
        self.task_queue = TaskQueue()
        self.cost_tracker = CostTracker()
        self.claude = ClaudeInterface()
        
        # Worker fleet management
        self.workers: Dict[str, MiniWorker] = {}
        self.worker_allocations: Dict[str, WorkerAllocation] = {}
        self.active_projects: Dict[str, BriefingProject] = {}
        
        # Scheduling and monitoring
        self.running = False
        self.max_concurrent_workers = 4
        self.daily_cost_limit = 80.0  # £80 total (£20 per worker)
        
        self._setup_logging()
        self._initialize_workers()
        self._setup_scheduler()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load project manager configuration"""
        default_config = {
            "niches": ["tech", "startup", "finance", "healthcare"],
            "sources": {
                "tech": [
                    "https://techcrunch.com",
                    "https://arstechnica.com", 
                    "https://theverge.com",
                    "https://news.ycombinator.com"
                ],
                "startup": [
                    "https://techcrunch.com/startups",
                    "https://angel.co/blog",
                    "https://firstround.com/review"
                ]
            },
            "delivery_schedule": {
                "daily": "06:00",
                "weekly": "monday_06:00"
            },
            "quality_controls": {
                "min_sources": 5,
                "max_age_hours": 24,
                "sentiment_balance": 0.3,
                "readability_score": 70
            }
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return {**default_config, **json.load(f)}
        return default_config
    
    def _setup_logging(self):
        """Setup comprehensive logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - PM-CLONE - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/project_manager.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _initialize_workers(self):
        """Initialize the Mini-Worker fleet"""
        worker_configs = [
            (WorkerType.SCRAPER, "Scraper-01", "Web scraping and API integration"),
            (WorkerType.SUMMARIZER, "Summarizer-01", "AI summarization and sentiment analysis"),
            (WorkerType.AUDIO, "Audio-01", "TTS and audio processing"),
            (WorkerType.DASHBOARD, "Dashboard-01", "UI and delivery systems")
        ]
        
        for worker_type, worker_id, description in worker_configs:
            worker = MiniWorker(
                worker_id=worker_id,
                worker_type=worker_type,
                cost_tracker=self.cost_tracker
            )
            
            self.workers[worker_id] = worker
            self.worker_allocations[worker_id] = WorkerAllocation(
                worker_id=worker_id,
                worker_type=worker_type,
                status="idle",
                current_task=None,
                cost_used=0.0,
                performance_score=1.0
            )
            
            self.logger.info(f"Initialized {worker_type.value} worker: {worker_id}")
    
    def _setup_scheduler(self):
        """Setup automated briefing schedules"""
        # Daily briefings at 6 AM
        schedule.every().day.at("06:00").do(self._trigger_daily_briefing)
        
        # Weekly briefings on Monday at 6 AM
        schedule.every().monday.at("06:00").do(self._trigger_weekly_briefing)
        
        # Hourly status check
        schedule.every().hour.do(self._health_check)
        
        # Daily cost reset
        schedule.every().day.at("00:00").do(self._reset_daily_costs)
    
    async def create_briefing_project(self, niche: str, frequency: str = "daily", 
                                    custom_sources: List[str] = None) -> str:
        """Create a new briefing project"""
        project_id = str(uuid.uuid4())[:8]
        
        # Get sources for niche
        sources = custom_sources or self.config["sources"].get(niche, [])
        
        # Determine deadline
        if frequency == "daily":
            deadline = datetime.now() + timedelta(hours=2)  # 2 hours to complete
        else:
            deadline = datetime.now() + timedelta(hours=6)  # 6 hours for weekly
        
        project = BriefingProject(
            id=project_id,
            name=f"{niche.title()} {frequency.title()} Briefing",
            niche=niche,
            frequency=frequency,
            sources=sources,
            delivery_methods=["email", "notion"],
            status=ProjectStatus.PLANNING,
            created_at=datetime.now(),
            deadline=deadline
        )
        
        self.active_projects[project_id] = project
        
        self.logger.info(f"Created briefing project: {project.name} (ID: {project_id})")
        
        # Start project execution
        await self._execute_project(project_id)
        
        return project_id
    
    async def _execute_project(self, project_id: str):
        """Execute a briefing project using Mini-Workers"""
        project = self.active_projects[project_id]
        project.status = ProjectStatus.EXECUTING
        
        self.logger.info(f"Executing project: {project.name}")
        
        # Phase 1: Data Collection (Scraper Worker)
        scraper_tasks = []
        for source in project.sources:
            task_id = await self.task_queue.submit_task(
                description=f"Scrape {source} for {project.niche} news",
                task_type="scrape_source",
                priority=8,
                source_url=source,
                niche=project.niche,
                max_age_hours=24
            )
            scraper_tasks.append(task_id)
        
        # Assign to scraper worker
        await self._assign_tasks_to_worker("Scraper-01", scraper_tasks)
        
        # Wait for scraping completion
        await self._wait_for_tasks(scraper_tasks, timeout=1800)  # 30 minutes
        
        # Phase 2: Content Processing (Summarizer Worker)
        summarizer_task_id = await self.task_queue.submit_task(
            description=f"Generate {project.frequency} briefing for {project.niche}",
            task_type="generate_briefing",
            priority=9,
            project_id=project_id,
            niche=project.niche,
            frequency=project.frequency,
            source_tasks=scraper_tasks
        )
        
        await self._assign_tasks_to_worker("Summarizer-01", [summarizer_task_id])
        await self._wait_for_tasks([summarizer_task_id], timeout=900)  # 15 minutes
        
        # Phase 3: Delivery (Dashboard Worker)
        delivery_task_id = await self.task_queue.submit_task(
            description=f"Deliver {project.niche} briefing via {project.delivery_methods}",
            task_type="deliver_briefing",
            priority=9,
            project_id=project_id,
            briefing_task=summarizer_task_id,
            delivery_methods=project.delivery_methods
        )
        
        await self._assign_tasks_to_worker("Dashboard-01", [delivery_task_id])
        await self._wait_for_tasks([delivery_task_id], timeout=600)  # 10 minutes
        
        # Phase 4: Audio Generation (Optional - Premium)
        if "audio" in project.delivery_methods:
            audio_task_id = await self.task_queue.submit_task(
                description=f"Generate audio briefing for {project.niche}",
                task_type="generate_audio",
                priority=7,
                project_id=project_id,
                briefing_task=summarizer_task_id
            )
            
            await self._assign_tasks_to_worker("Audio-01", [audio_task_id])
            await self._wait_for_tasks([audio_task_id], timeout=1200)  # 20 minutes
        
        # Mark project complete
        project.status = ProjectStatus.COMPLETED
        
        # Report to Claude Senior
        await self._report_to_senior(project_id)
        
        self.logger.info(f"Project completed: {project.name}")
    
    async def _assign_tasks_to_worker(self, worker_id: str, task_ids: List[str]):
        """Assign tasks to a specific worker"""
        worker = self.workers[worker_id]
        allocation = self.worker_allocations[worker_id]
        
        allocation.status = "busy"
        allocation.current_task = task_ids[0] if task_ids else None
        
        for task_id in task_ids:
            await worker.execute_task(task_id)
        
        self.logger.info(f"Assigned {len(task_ids)} tasks to {worker_id}")
    
    async def _wait_for_tasks(self, task_ids: List[str], timeout: int = 3600):
        """Wait for tasks to complete with timeout"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            completed = 0
            for task_id in task_ids:
                task_status = await self.task_queue.get_task_status(task_id)
                if task_status and task_status.get("status") in ["completed", "failed"]:
                    completed += 1
            
            if completed == len(task_ids):
                self.logger.info(f"All {len(task_ids)} tasks completed")
                return True
            
            await asyncio.sleep(10)  # Check every 10 seconds
        
        self.logger.warning(f"Timeout waiting for tasks: {task_ids}")
        return False
    
    async def _report_to_senior(self, project_id: str):
        """Report project completion to Claude Senior Engineer"""
        project = self.active_projects[project_id]
        
        # Collect performance metrics
        total_cost = sum(alloc.cost_used for alloc in self.worker_allocations.values())
        avg_performance = sum(alloc.performance_score for alloc in self.worker_allocations.values()) / len(self.worker_allocations)
        
        report = {
            "project_id": project_id,
            "project_name": project.name,
            "status": project.status.value,
            "completion_time": datetime.now().isoformat(),
            "total_cost": total_cost,
            "average_performance": avg_performance,
            "worker_summary": {
                worker_id: {
                    "cost_used": alloc.cost_used,
                    "performance": alloc.performance_score,
                    "status": alloc.status
                }
                for worker_id, alloc in self.worker_allocations.items()
            }
        }
        
        # Save report
        with open(f"logs/project_report_{project_id}.json", "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        self.logger.info(f"Project report generated for {project_id}")
        
        # Send to Claude Senior (placeholder for real integration)
        await self._notify_senior_engineer(report)
    
    async def _notify_senior_engineer(self, report: Dict[str, Any]):
        """Notify Claude Senior Engineer of completion"""
        # This would integrate with the main Mini-Claude system
        notification = {
            "type": "project_completion",
            "timestamp": datetime.now().isoformat(),
            "report": report,
            "requires_review": report["total_cost"] > 50.0 or report["average_performance"] < 0.8
        }
        
        # Save notification for Claude Senior to pick up
        with open("logs/senior_notifications.jsonl", "a") as f:
            f.write(json.dumps(notification) + "\n")
    
    def _trigger_daily_briefing(self):
        """Trigger daily briefing generation"""
        self.logger.info("Triggering daily briefing generation")
        asyncio.create_task(self.create_briefing_project("tech", "daily"))
    
    def _trigger_weekly_briefing(self):
        """Trigger weekly briefing generation"""
        self.logger.info("Triggering weekly briefing generation")
        asyncio.create_task(self.create_briefing_project("startup", "weekly"))
    
    def _health_check(self):
        """Perform system health check"""
        total_cost = sum(alloc.cost_used for alloc in self.worker_allocations.values())
        
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "total_daily_cost": total_cost,
            "cost_limit": self.daily_cost_limit,
            "workers_active": sum(1 for alloc in self.worker_allocations.values() if alloc.status == "busy"),
            "projects_active": len([p for p in self.active_projects.values() if p.status == ProjectStatus.EXECUTING])
        }
        
        # Emergency shutdown if cost exceeded
        if total_cost > self.daily_cost_limit:
            self.logger.critical(f"Daily cost limit exceeded: £{total_cost}")
            self._emergency_shutdown()
        
        with open("logs/health_check.jsonl", "a") as f:
            f.write(json.dumps(health_status) + "\n")
    
    def _reset_daily_costs(self):
        """Reset daily cost tracking"""
        for allocation in self.worker_allocations.values():
            allocation.cost_used = 0.0
        
        self.cost_tracker.reset_daily_costs()
        self.logger.info("Daily costs reset")
    
    def _emergency_shutdown(self):
        """Emergency shutdown all operations"""
        self.logger.critical("EMERGENCY SHUTDOWN - Cost limit exceeded")
        
        # Stop all workers
        for worker in self.workers.values():
            worker.stop()
        
        # Mark all projects as failed
        for project in self.active_projects.values():
            if project.status == ProjectStatus.EXECUTING:
                project.status = ProjectStatus.FAILED
        
        self.running = False
        
        # Create stop_all.sh script
        with open("stop_all.sh", "w") as f:
            f.write("#!/bin/bash\n")
            f.write("echo 'Emergency shutdown initiated by Project Manager'\n")
            f.write("pkill -f 'project_manager.py'\n")
            f.write("pkill -f 'mini_worker.py'\n")
            f.write("echo 'All Mini-Claude processes stopped'\n")
        
        os.chmod("stop_all.sh", 0o755)
    
    async def start(self):
        """Start the Project Manager Clone"""
        self.running = True
        self.logger.info("Project Manager Clone started")
        
        # Create demo briefing
        await self.create_briefing_project("tech", "daily")
        
        # Main scheduling loop
        while self.running:
            schedule.run_pending()
            await asyncio.sleep(60)  # Check every minute
    
    def stop(self):
        """Stop the Project Manager Clone"""
        self.running = False
        for worker in self.workers.values():
            worker.stop()
        self.logger.info("Project Manager Clone stopped")

# CLI Interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="90-Second Briefings Project Manager")
    parser.add_argument("--action", choices=["start", "demo", "status"], default="start")
    parser.add_argument("--niche", default="tech", help="Briefing niche")
    parser.add_argument("--frequency", choices=["daily", "weekly"], default="daily")
    
    args = parser.parse_args()
    
    pm = ProjectManagerClone()
    
    if args.action == "demo":
        project_id = await pm.create_briefing_project(args.niche, args.frequency)
        print(f"Demo briefing project created: {project_id}")
    elif args.action == "status":
        print(f"Active projects: {len(pm.active_projects)}")
        for project_id, project in pm.active_projects.items():
            print(f"  {project_id}: {project.name} - {project.status.value}")
    else:
        await pm.start()

if __name__ == "__main__":
    asyncio.run(main())