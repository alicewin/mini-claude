#!/usr/bin/env python3
"""
System Monitor for 90-Second Briefings
Comprehensive monitoring, alerting, and emergency shutdown capabilities
"""

import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import signal
import sys

from core.cost_tracker import get_cost_tracker, AlertSeverity
from core.task_queue import TaskQueue
from core.mini_worker import MiniWorker, WorkerStatus

@dataclass
class SystemAlert:
    timestamp: datetime
    severity: str  # info, warning, critical, emergency
    component: str  # system, worker, cost, task_queue
    message: str
    details: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[datetime] = None

@dataclass
class SystemHealth:
    timestamp: datetime
    overall_status: str  # healthy, degraded, critical, emergency
    active_workers: int
    total_tasks_today: int
    cost_utilization: float
    error_rate: float
    uptime_hours: float
    alerts_count: int
    emergency_shutdown: bool

class SystemMonitor:
    """
    Comprehensive system monitoring with emergency shutdown capabilities
    Monitors costs, worker health, task queues, and system resources
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Core components
        self.cost_tracker = get_cost_tracker()
        self.task_queue = None
        self.workers: Dict[str, MiniWorker] = {}
        
        # Monitoring state
        self.start_time = datetime.now()
        self.monitoring_active = False
        self.alerts: List[SystemAlert] = []
        self.health_history: List[SystemHealth] = []
        
        # Emergency controls
        self.emergency_shutdown_active = False
        self.shutdown_reason = None
        
        # Configuration
        self.monitor_interval = 60  # seconds
        self.health_check_interval = 300  # 5 minutes
        self.alert_retention_days = 7
        
        # Shutdown signals
        self.shutdown_files = [
            "EMERGENCY_SHUTDOWN",
            "PAUSE_NON_ESSENTIAL", 
            "COST_WARNING"
        ]
        
        # Setup directories
        self.data_dir = Path("data/monitoring")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self._setup_monitoring_logs()
        
        # Register signal handlers
        self._register_signal_handlers()
        
        self.logger.info("SystemMonitor initialized")
    
    def _setup_monitoring_logs(self):
        """Setup monitoring-specific logging"""
        
        monitor_handler = logging.FileHandler("system_monitor.log")
        monitor_handler.setFormatter(logging.Formatter(
            '%(asctime)s - MONITOR - %(levelname)s - %(message)s'
        ))
        
        self.logger.addHandler(monitor_handler)
        self.logger.setLevel(logging.INFO)
    
    def _register_signal_handlers(self):
        """Register system signal handlers for graceful shutdown"""
        
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            asyncio.create_task(self.shutdown_system("signal_received"))
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def register_task_queue(self, task_queue: TaskQueue):
        """Register task queue for monitoring"""
        self.task_queue = task_queue
        self.logger.info("Task queue registered for monitoring")
    
    def register_worker(self, worker: MiniWorker):
        """Register worker for monitoring"""
        self.workers[worker.worker_id] = worker
        self.logger.info(f"Worker {worker.worker_id} registered for monitoring")
    
    async def start_monitoring(self):
        """Start system monitoring"""
        
        self.monitoring_active = True
        self.logger.info("System monitoring started")
        
        # Start monitoring tasks
        tasks = [
            asyncio.create_task(self._cost_monitoring_loop()),
            asyncio.create_task(self._worker_health_loop()),
            asyncio.create_task(self._system_health_loop()),
            asyncio.create_task(self._shutdown_signal_monitor()),
            asyncio.create_task(self._alert_processor())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.logger.info("Monitoring tasks cancelled")
    
    async def stop_monitoring(self):
        """Stop system monitoring"""
        
        self.monitoring_active = False
        self.logger.info("System monitoring stopped")
    
    async def _cost_monitoring_loop(self):
        """Monitor costs and budget utilization"""
        
        while self.monitoring_active:
            try:
                summary = self.cost_tracker.get_daily_summary()
                
                # Check for cost alerts
                if summary["utilization_percent"] > 70:
                    severity = "warning"
                    if summary["utilization_percent"] > 90:
                        severity = "critical"
                    if summary["utilization_percent"] > 100:
                        severity = "emergency"
                    
                    await self._create_alert(
                        severity=severity,
                        component="cost",
                        message=f"Daily cost utilization at {summary['utilization_percent']:.1f}%",
                        details=summary
                    )
                
                # Check emergency shutdown flag
                if summary["emergency_shutdown"]:
                    await self._trigger_emergency_shutdown("cost_limit_exceeded")
                
                await asyncio.sleep(self.monitor_interval)
                
            except Exception as e:
                self.logger.error(f"Error in cost monitoring: {e}")
                await asyncio.sleep(self.monitor_interval)
    
    async def _worker_health_loop(self):
        """Monitor worker health and performance"""
        
        while self.monitoring_active:
            try:
                unhealthy_workers = []
                
                for worker_id, worker in self.workers.items():
                    health = await worker.health_check()
                    
                    if health["health_status"] != "healthy":
                        unhealthy_workers.append({
                            "worker_id": worker_id,
                            "status": health["health_status"],
                            "error_rate": health["error_rate"]
                        })
                        
                        # Create alert for unhealthy worker
                        severity = "warning"
                        if health["health_status"] == "unresponsive":
                            severity = "critical"
                        
                        await self._create_alert(
                            severity=severity,
                            component="worker",
                            message=f"Worker {worker_id} health: {health['health_status']}",
                            details=health
                        )
                
                # System-wide worker health
                if len(unhealthy_workers) > len(self.workers) / 2:
                    await self._create_alert(
                        severity="critical",
                        component="system",
                        message=f"More than half of workers unhealthy ({len(unhealthy_workers)}/{len(self.workers)})",
                        details={"unhealthy_workers": unhealthy_workers}
                    )
                
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in worker health monitoring: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    async def _system_health_loop(self):
        """Monitor overall system health"""
        
        while self.monitoring_active:
            try:
                health = await self._calculate_system_health()
                self.health_history.append(health)
                
                # Keep only recent history
                cutoff = datetime.now() - timedelta(days=1)
                self.health_history = [h for h in self.health_history if h.timestamp > cutoff]
                
                # System health alerts
                if health.overall_status in ["critical", "emergency"]:
                    await self._create_alert(
                        severity=health.overall_status,
                        component="system",
                        message=f"System health: {health.overall_status}",
                        details=asdict(health)
                    )
                
                # Save health data
                await self._save_health_data(health)
                
                await asyncio.sleep(self.monitor_interval)
                
            except Exception as e:
                self.logger.error(f"Error in system health monitoring: {e}")
                await asyncio.sleep(self.monitor_interval)
    
    async def _shutdown_signal_monitor(self):
        """Monitor for shutdown signal files"""
        
        while self.monitoring_active:
            try:
                for shutdown_file in self.shutdown_files:
                    if Path(shutdown_file).exists():
                        self.logger.warning(f"Shutdown signal detected: {shutdown_file}")
                        
                        # Read shutdown reason if available
                        try:
                            with open(shutdown_file, 'r') as f:
                                reason = f.read().strip()
                        except:
                            reason = f"Signal file: {shutdown_file}"
                        
                        if shutdown_file == "EMERGENCY_SHUTDOWN":
                            await self._trigger_emergency_shutdown(reason)
                        elif shutdown_file == "PAUSE_NON_ESSENTIAL":
                            await self._pause_non_essential_workers()
                        
                        # Remove the signal file
                        try:
                            Path(shutdown_file).unlink()
                        except:
                            pass
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error monitoring shutdown signals: {e}")
                await asyncio.sleep(10)
    
    async def _alert_processor(self):
        """Process and manage alerts"""
        
        while self.monitoring_active:
            try:
                # Clean up old alerts
                cutoff = datetime.now() - timedelta(days=self.alert_retention_days)
                self.alerts = [a for a in self.alerts if a.timestamp > cutoff]
                
                # Process active alerts
                critical_alerts = [a for a in self.alerts if a.severity == "critical" and not a.resolved]
                emergency_alerts = [a for a in self.alerts if a.severity == "emergency" and not a.resolved]
                
                if emergency_alerts and not self.emergency_shutdown_active:
                    await self._trigger_emergency_shutdown("emergency_alerts")
                
                await asyncio.sleep(self.monitor_interval)
                
            except Exception as e:
                self.logger.error(f"Error processing alerts: {e}")
                await asyncio.sleep(self.monitor_interval)
    
    async def _calculate_system_health(self) -> SystemHealth:
        """Calculate overall system health"""
        
        uptime = (datetime.now() - self.start_time).total_seconds() / 3600
        
        # Cost information
        cost_summary = self.cost_tracker.get_daily_summary()
        cost_utilization = cost_summary["utilization_percent"] / 100
        
        # Worker information
        active_workers = len([w for w in self.workers.values() if w.status == "active"])
        
        # Task information
        total_tasks = 0
        error_count = 0
        
        for worker in self.workers.values():
            status = worker.get_status()
            total_tasks += status.tasks_completed
            error_count += status.error_count
        
        error_rate = error_count / max(total_tasks + error_count, 1)
        
        # Alert information
        active_alerts = len([a for a in self.alerts if not a.resolved])
        
        # Determine overall status
        overall_status = "healthy"
        
        if self.emergency_shutdown_active:
            overall_status = "emergency"
        elif cost_utilization > 1.0 or error_rate > 0.2:
            overall_status = "critical"
        elif cost_utilization > 0.8 or error_rate > 0.1 or active_workers < len(self.workers) * 0.5:
            overall_status = "degraded"
        
        return SystemHealth(
            timestamp=datetime.now(),
            overall_status=overall_status,
            active_workers=active_workers,
            total_tasks_today=total_tasks,
            cost_utilization=cost_utilization,
            error_rate=error_rate,
            uptime_hours=uptime,
            alerts_count=active_alerts,
            emergency_shutdown=self.emergency_shutdown_active
        )
    
    async def _create_alert(self, severity: str, component: str, message: str, details: Dict[str, Any]):
        """Create and log system alert"""
        
        alert = SystemAlert(
            timestamp=datetime.now(),
            severity=severity,
            component=component,
            message=message,
            details=details
        )
        
        self.alerts.append(alert)
        
        # Log the alert
        log_level = logging.INFO
        if severity == "warning":
            log_level = logging.WARNING
        elif severity == "critical":
            log_level = logging.ERROR
        elif severity == "emergency":
            log_level = logging.CRITICAL
        
        self.logger.log(log_level, f"ALERT [{severity.upper()}] {component}: {message}")
        
        # Save alert
        await self._save_alert(alert)
    
    async def _trigger_emergency_shutdown(self, reason: str):
        """Trigger emergency shutdown of the entire system"""
        
        if self.emergency_shutdown_active:
            return  # Already in shutdown
        
        self.emergency_shutdown_active = True
        self.shutdown_reason = reason
        
        self.logger.critical(f"EMERGENCY SHUTDOWN TRIGGERED: {reason}")
        
        # Create emergency alert
        await self._create_alert(
            severity="emergency",
            component="system",
            message=f"Emergency shutdown triggered: {reason}",
            details={"reason": reason, "timestamp": datetime.now().isoformat()}
        )
        
        # Stop all workers
        for worker in self.workers.values():
            try:
                await worker.stop()
            except Exception as e:
                self.logger.error(f"Error stopping worker {worker.worker_id}: {e}")
        
        # Stop task queue monitoring
        if self.task_queue:
            try:
                await self.task_queue.stop_monitoring()
            except Exception as e:
                self.logger.error(f"Error stopping task queue: {e}")
        
        # Stop cost tracking
        try:
            await self.cost_tracker.stop_monitoring()
        except Exception as e:
            self.logger.error(f"Error stopping cost tracker: {e}")
        
        # Create shutdown status file
        with open("SYSTEM_SHUTDOWN.json", 'w') as f:
            json.dump({
                "shutdown_time": datetime.now().isoformat(),
                "reason": reason,
                "active_workers": len(self.workers),
                "system_health": asdict(await self._calculate_system_health())
            }, f, indent=2)
        
        self.logger.critical("Emergency shutdown completed")
    
    async def _pause_non_essential_workers(self):
        """Pause non-essential workers to conserve budget"""
        
        self.logger.warning("Pausing non-essential workers")
        
        # Define essential workers (keep scraper and project manager active)
        essential_types = ["scraper", "project_manager"]
        
        for worker in self.workers.values():
            if worker.worker_type.value not in essential_types:
                try:
                    await worker.pause()
                    self.logger.info(f"Paused non-essential worker: {worker.worker_id}")
                except Exception as e:
                    self.logger.error(f"Error pausing worker {worker.worker_id}: {e}")
    
    async def _save_health_data(self, health: SystemHealth):
        """Save system health data"""
        
        health_file = self.data_dir / f"health_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        try:
            with open(health_file, 'a') as f:
                f.write(json.dumps(asdict(health), default=str) + '\n')
        except Exception as e:
            self.logger.error(f"Error saving health data: {e}")
    
    async def _save_alert(self, alert: SystemAlert):
        """Save alert data"""
        
        alerts_file = self.data_dir / "alerts.jsonl"
        
        try:
            with open(alerts_file, 'a') as f:
                f.write(json.dumps(asdict(alert), default=str) + '\n')
        except Exception as e:
            self.logger.error(f"Error saving alert: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        
        if not self.health_history:
            return {"status": "initializing"}
        
        latest_health = self.health_history[-1]
        
        active_alerts = [a for a in self.alerts if not a.resolved]
        recent_alerts = [a for a in self.alerts if a.timestamp > datetime.now() - timedelta(hours=1)]
        
        return {
            "system_health": asdict(latest_health),
            "emergency_shutdown": self.emergency_shutdown_active,
            "shutdown_reason": self.shutdown_reason,
            "active_workers": len([w for w in self.workers.values() if w.status == "active"]),
            "total_workers": len(self.workers),
            "active_alerts": len(active_alerts),
            "recent_alerts": len(recent_alerts),
            "uptime_hours": (datetime.now() - self.start_time).total_seconds() / 3600,
            "monitoring_active": self.monitoring_active
        }
    
    async def shutdown_system(self, reason: str = "manual_shutdown"):
        """Gracefully shutdown the system"""
        
        self.logger.info(f"Initiating system shutdown: {reason}")
        
        # Stop monitoring
        await self.stop_monitoring()
        
        # Stop workers
        for worker in self.workers.values():
            await worker.stop()
        
        # Final health report
        final_health = await self._calculate_system_health()
        await self._save_health_data(final_health)
        
        self.logger.info("System shutdown completed")

# Global system monitor
_system_monitor = None

def get_system_monitor() -> SystemMonitor:
    """Get global system monitor instance"""
    global _system_monitor
    if _system_monitor is None:
        _system_monitor = SystemMonitor()
    return _system_monitor

# CLI interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="System Monitor")
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument("--alerts", action="store_true", help="Show active alerts")
    parser.add_argument("--health", action="store_true", help="Show health history")
    parser.add_argument("--shutdown", action="store_true", help="Shutdown system")
    
    args = parser.parse_args()
    
    monitor = get_system_monitor()
    
    if args.status:
        status = monitor.get_system_status()
        print("System Status:")
        print(json.dumps(status, indent=2, default=str))
    
    elif args.alerts:
        active_alerts = [a for a in monitor.alerts if not a.resolved]
        print(f"Active Alerts ({len(active_alerts)}):")
        for alert in active_alerts[-10:]:  # Show last 10
            print(f"  [{alert.severity.upper()}] {alert.component}: {alert.message}")
    
    elif args.health:
        if monitor.health_history:
            latest = monitor.health_history[-1]
            print("Latest Health Check:")
            print(json.dumps(asdict(latest), indent=2, default=str))
        else:
            print("No health data available")
    
    elif args.shutdown:
        await monitor.shutdown_system("manual_cli_shutdown")
        print("System shutdown initiated")

if __name__ == "__main__":
    asyncio.run(main())