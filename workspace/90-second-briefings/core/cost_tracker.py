#!/usr/bin/env python3
"""
Cost Tracking and Guardrails System for 90-Second Briefings
Comprehensive monitoring with £20/day limits and emergency shutdown
"""

import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from pathlib import Path

@dataclass
class CostEvent:
    timestamp: datetime
    service: str  # anthropic, openai-tts, aws-s3, email, etc.
    operation: str  # api_call, storage, transfer, etc.
    units: int  # tokens, bytes, requests, etc.
    cost_gbp: float
    worker_id: str
    project_id: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class CostAlert:
    severity: AlertSeverity
    message: str
    current_cost: float
    threshold: float
    service: str
    worker_id: str
    timestamp: datetime
    action_taken: Optional[str] = None

class ServiceConfig:
    """Service-specific cost configurations"""
    
    ANTHROPIC_PRICING = {
        "claude-3-haiku-20240307": {
            "input_tokens": 0.25 / 1_000_000,  # $0.25 per 1M tokens
            "output_tokens": 1.25 / 1_000_000   # $1.25 per 1M tokens
        }
    }
    
    OPENAI_PRICING = {
        "tts-1-hd": 0.030 / 1000,  # $0.030 per 1K characters
        "whisper-1": 0.006 / 60    # $0.006 per minute
    }
    
    AWS_PRICING = {
        "s3_storage": 0.023 / (1024**3),  # $0.023 per GB per month
        "s3_requests": 0.0004 / 1000      # $0.0004 per 1K requests
    }
    
    # Convert USD to GBP (approximate rate)
    USD_TO_GBP = 0.79

class CostTracker:
    """
    Comprehensive cost tracking system with real-time monitoring
    and automatic guardrails to prevent budget overruns
    """
    
    def __init__(self, daily_limit_gbp: float = 20.0):
        self.daily_limit_gbp = daily_limit_gbp
        self.logger = logging.getLogger(__name__)
        
        # Storage
        self.data_dir = Path("data/costs")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory tracking
        self.daily_costs: Dict[str, float] = {}  # service -> cost
        self.worker_costs: Dict[str, float] = {}  # worker_id -> cost
        self.cost_events: List[CostEvent] = []
        self.alerts: List[CostAlert] = []
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Monitoring
        self.monitoring_active = False
        self.emergency_shutdown = False
        
        # Load existing data
        self._load_daily_costs()
        
        # Initialize logs
        self.activity_log = logging.getLogger("activity")
        self.costs_log = logging.getLogger("costs")
        self._setup_logging()
        
        self.logger.info(f"CostTracker initialized with £{daily_limit_gbp}/day limit")
    
    def _setup_logging(self):
        """Setup specialized logging for activity and costs"""
        
        # Activity log
        activity_handler = logging.FileHandler("activity.log")
        activity_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.activity_log.addHandler(activity_handler)
        self.activity_log.setLevel(logging.INFO)
        
        # Costs log
        costs_handler = logging.FileHandler("costs.log")
        costs_handler.setFormatter(logging.Formatter(
            '%(asctime)s - COST - %(message)s'
        ))
        self.costs_log.addHandler(costs_handler)
        self.costs_log.setLevel(logging.INFO)
    
    def _load_daily_costs(self):
        """Load today's costs from storage"""
        today_file = self.data_dir / f"costs_{datetime.now().strftime('%Y%m%d')}.json"
        
        try:
            if today_file.exists():
                with open(today_file, 'r') as f:
                    data = json.load(f)
                
                self.daily_costs = data.get("daily_costs", {})
                self.worker_costs = data.get("worker_costs", {})
                
                # Load events
                for event_data in data.get("events", []):
                    event = CostEvent(
                        timestamp=datetime.fromisoformat(event_data["timestamp"]),
                        service=event_data["service"],
                        operation=event_data["operation"],
                        units=event_data["units"],
                        cost_gbp=event_data["cost_gbp"],
                        worker_id=event_data["worker_id"],
                        project_id=event_data.get("project_id"),
                        metadata=event_data.get("metadata", {})
                    )
                    self.cost_events.append(event)
                
                total_cost = sum(self.daily_costs.values())
                self.logger.info(f"Loaded daily costs: £{total_cost:.3f}")
        
        except Exception as e:
            self.logger.error(f"Failed to load daily costs: {e}")
    
    async def track_api_call(self, service: str, units: int, worker_id: str = "unknown", 
                           project_id: Optional[str] = None, **metadata) -> float:
        """Track API call costs"""
        
        cost_gbp = self._calculate_api_cost(service, units, **metadata)
        
        event = CostEvent(
            timestamp=datetime.now(),
            service=service,
            operation="api_call",
            units=units,
            cost_gbp=cost_gbp,
            worker_id=worker_id,
            project_id=project_id,
            metadata=metadata
        )
        
        await self._record_cost_event(event)
        return cost_gbp
    
    async def track_storage_cost(self, service: str, bytes_used: int, worker_id: str,
                               operation: str = "storage", **metadata) -> float:
        """Track storage costs"""
        
        cost_gbp = self._calculate_storage_cost(service, bytes_used, **metadata)
        
        event = CostEvent(
            timestamp=datetime.now(),
            service=service,
            operation=operation,
            units=bytes_used,
            cost_gbp=cost_gbp,
            worker_id=worker_id,
            metadata=metadata
        )
        
        await self._record_cost_event(event)
        return cost_gbp
    
    async def track_custom_cost(self, service: str, operation: str, cost_gbp: float,
                              worker_id: str, units: int = 1, **metadata) -> float:
        """Track custom cost events"""
        
        event = CostEvent(
            timestamp=datetime.now(),
            service=service,
            operation=operation,
            units=units,
            cost_gbp=cost_gbp,
            worker_id=worker_id,
            metadata=metadata
        )
        
        await self._record_cost_event(event)
        return cost_gbp
    
    def _calculate_api_cost(self, service: str, units: int, **metadata) -> float:
        """Calculate cost for API calls"""
        
        if service.startswith("claude"):
            model = metadata.get("model", "claude-3-haiku-20240307")
            input_tokens = metadata.get("input_tokens", units)
            output_tokens = metadata.get("output_tokens", 0)
            
            pricing = ServiceConfig.ANTHROPIC_PRICING.get(model, 
                ServiceConfig.ANTHROPIC_PRICING["claude-3-haiku-20240307"])
            
            cost_usd = (input_tokens * pricing["input_tokens"] + 
                       output_tokens * pricing["output_tokens"])
            
            return cost_usd * ServiceConfig.USD_TO_GBP
        
        elif service.startswith("openai"):
            if "tts" in service:
                cost_usd = units * ServiceConfig.OPENAI_PRICING["tts-1-hd"]
            else:
                cost_usd = units * 0.001  # Default rate
            
            return cost_usd * ServiceConfig.USD_TO_GBP
        
        else:
            # Default estimation: 1 unit = £0.001
            return units * 0.001
    
    def _calculate_storage_cost(self, service: str, bytes_used: int, **metadata) -> float:
        """Calculate storage costs"""
        
        if service == "aws-s3":
            gb_used = bytes_used / (1024**3)
            cost_usd = gb_used * ServiceConfig.AWS_PRICING["s3_storage"]
            return cost_usd * ServiceConfig.USD_TO_GBP
        
        else:
            # Default: £0.001 per MB
            mb_used = bytes_used / (1024**2)
            return mb_used * 0.001
    
    async def _record_cost_event(self, event: CostEvent):
        """Record cost event with guardrail checks"""
        
        with self.lock:
            # Add to tracking
            self.cost_events.append(event)
            
            # Update daily totals
            if event.service not in self.daily_costs:
                self.daily_costs[event.service] = 0
            self.daily_costs[event.service] += event.cost_gbp
            
            # Update worker totals
            if event.worker_id not in self.worker_costs:
                self.worker_costs[event.worker_id] = 0
            self.worker_costs[event.worker_id] += event.cost_gbp
            
            # Log the event
            self.costs_log.info(
                f"COST_EVENT: {event.service} | {event.worker_id} | "
                f"£{event.cost_gbp:.4f} | {event.units} {event.operation}"
            )
            
            self.activity_log.info(
                f"Cost tracked: {event.service} £{event.cost_gbp:.4f} "
                f"(Worker: {event.worker_id})"
            )
        
        # Check guardrails
        await self._check_cost_guardrails(event)
        
        # Save to disk
        await self._save_daily_costs()
    
    async def _check_cost_guardrails(self, event: CostEvent):
        """Check cost guardrails and trigger alerts"""
        
        total_daily_cost = sum(self.daily_costs.values())
        worker_cost = self.worker_costs.get(event.worker_id, 0)
        
        # Worker-specific limits (£5 per worker max)
        worker_limit = 5.0
        if worker_cost > worker_limit * 0.8:  # 80% warning
            severity = AlertSeverity.WARNING if worker_cost < worker_limit else AlertSeverity.CRITICAL
            
            alert = CostAlert(
                severity=severity,
                message=f"Worker {event.worker_id} approaching/exceeding £{worker_limit} limit",
                current_cost=worker_cost,
                threshold=worker_limit,
                service=event.service,
                worker_id=event.worker_id,
                timestamp=datetime.now()
            )
            
            await self._handle_cost_alert(alert)
        
        # Daily limit checks
        if total_daily_cost > self.daily_limit_gbp * 0.7:  # 70% warning
            severity = AlertSeverity.WARNING
            if total_daily_cost > self.daily_limit_gbp * 0.9:  # 90% critical
                severity = AlertSeverity.CRITICAL
            if total_daily_cost > self.daily_limit_gbp:  # 100% emergency
                severity = AlertSeverity.EMERGENCY
            
            alert = CostAlert(
                severity=severity,
                message=f"Daily cost limit approaching/exceeded: £{total_daily_cost:.2f}/£{self.daily_limit_gbp}",
                current_cost=total_daily_cost,
                threshold=self.daily_limit_gbp,
                service="system",
                worker_id="all",
                timestamp=datetime.now()
            )
            
            await self._handle_cost_alert(alert)
    
    async def _handle_cost_alert(self, alert: CostAlert):
        """Handle cost alerts with appropriate actions"""
        
        self.alerts.append(alert)
        
        # Log alert
        self.costs_log.warning(
            f"COST_ALERT: {alert.severity.value.upper()} | {alert.message} | "
            f"£{alert.current_cost:.2f}/£{alert.threshold:.2f}"
        )
        
        self.activity_log.warning(f"Cost alert: {alert.message}")
        
        # Take action based on severity
        if alert.severity == AlertSeverity.EMERGENCY:
            await self._emergency_shutdown()
            alert.action_taken = "emergency_shutdown"
        
        elif alert.severity == AlertSeverity.CRITICAL:
            await self._pause_non_essential_workers()
            alert.action_taken = "pause_non_essential"
        
        elif alert.severity == AlertSeverity.WARNING:
            await self._notify_project_manager()
            alert.action_taken = "notification_sent"
        
        # Save alert
        await self._save_alert(alert)
    
    async def _emergency_shutdown(self):
        """Emergency shutdown to prevent further costs"""
        
        if self.emergency_shutdown:
            return  # Already in shutdown
        
        self.emergency_shutdown = True
        
        self.logger.critical("EMERGENCY SHUTDOWN: Daily cost limit exceeded!")
        self.costs_log.critical("EMERGENCY_SHUTDOWN: Daily limit exceeded - stopping all operations")
        self.activity_log.critical("Emergency shutdown activated due to cost limits")
        
        # Create shutdown signal file
        shutdown_file = Path("EMERGENCY_SHUTDOWN")
        with open(shutdown_file, 'w') as f:
            f.write(f"Emergency shutdown at {datetime.now().isoformat()}\n")
            f.write(f"Total daily cost: £{sum(self.daily_costs.values()):.2f}\n")
            f.write(f"Limit: £{self.daily_limit_gbp}\n")
        
        # TODO: Implement actual worker shutdown mechanism
        # This would send stop signals to all workers
    
    async def _pause_non_essential_workers(self):
        """Pause non-essential workers to reduce costs"""
        
        self.logger.warning("Pausing non-essential workers due to cost limits")
        self.activity_log.warning("Non-essential workers paused - cost limit approaching")
        
        # Create pause signal
        pause_file = Path("PAUSE_NON_ESSENTIAL")
        with open(pause_file, 'w') as f:
            f.write(f"Non-essential pause at {datetime.now().isoformat()}\n")
    
    async def _notify_project_manager(self):
        """Notify project manager of cost warnings"""
        
        self.logger.info("Notifying project manager of cost warning")
        self.activity_log.info("Project manager notified of cost status")
        
        # Create notification file
        notification_file = Path("COST_WARNING")
        with open(notification_file, 'w') as f:
            f.write(f"Cost warning at {datetime.now().isoformat()}\n")
            f.write(f"Current daily cost: £{sum(self.daily_costs.values()):.2f}\n")
    
    async def _save_daily_costs(self):
        """Save daily costs to storage"""
        
        today_file = self.data_dir / f"costs_{datetime.now().strftime('%Y%m%d')}.json"
        
        data = {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "daily_costs": self.daily_costs,
            "worker_costs": self.worker_costs,
            "total_cost": sum(self.daily_costs.values()),
            "events": [asdict(event) for event in self.cost_events[-100:]]  # Last 100 events
        }
        
        try:
            with open(today_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        
        except Exception as e:
            self.logger.error(f"Failed to save daily costs: {e}")
    
    async def _save_alert(self, alert: CostAlert):
        """Save alert to storage"""
        
        alerts_file = self.data_dir / "alerts.jsonl"
        
        try:
            with open(alerts_file, 'a') as f:
                f.write(json.dumps(asdict(alert), default=str) + '\n')
        
        except Exception as e:
            self.logger.error(f"Failed to save alert: {e}")
    
    def get_daily_summary(self) -> Dict[str, Any]:
        """Get daily cost summary"""
        
        with self.lock:
            total_cost = sum(self.daily_costs.values())
            
            return {
                "date": datetime.now().strftime('%Y-%m-%d'),
                "total_cost_gbp": total_cost,
                "daily_limit_gbp": self.daily_limit_gbp,
                "utilization_percent": (total_cost / self.daily_limit_gbp) * 100,
                "costs_by_service": dict(self.daily_costs),
                "costs_by_worker": dict(self.worker_costs),
                "emergency_shutdown": self.emergency_shutdown,
                "alerts_count": len(self.alerts)
            }
    
    def get_cost_breakdown(self, hours: int = 24) -> Dict[str, Any]:
        """Get detailed cost breakdown for specified hours"""
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_events = [e for e in self.cost_events if e.timestamp >= cutoff_time]
        
        # Group by service
        service_costs = {}
        for event in recent_events:
            if event.service not in service_costs:
                service_costs[event.service] = {
                    "total_cost": 0,
                    "event_count": 0,
                    "total_units": 0
                }
            
            service_costs[event.service]["total_cost"] += event.cost_gbp
            service_costs[event.service]["event_count"] += 1
            service_costs[event.service]["total_units"] += event.units
        
        return {
            "period_hours": hours,
            "total_events": len(recent_events),
            "total_cost": sum(e.cost_gbp for e in recent_events),
            "service_breakdown": service_costs
        }
    
    def is_budget_available(self, estimated_cost: float) -> bool:
        """Check if budget is available for estimated operation"""
        
        current_total = sum(self.daily_costs.values())
        return (current_total + estimated_cost) <= self.daily_limit_gbp
    
    def get_remaining_budget(self) -> float:
        """Get remaining daily budget"""
        
        current_total = sum(self.daily_costs.values())
        return max(0, self.daily_limit_gbp - current_total)
    
    async def start_monitoring(self):
        """Start background cost monitoring"""
        
        self.monitoring_active = True
        self.logger.info("Cost monitoring started")
        
        # Background monitoring loop would go here
        # For now, just set the flag
    
    async def stop_monitoring(self):
        """Stop background cost monitoring"""
        
        self.monitoring_active = False
        await self._save_daily_costs()
        self.logger.info("Cost monitoring stopped")

# Global cost tracker instance
_cost_tracker = None

def get_cost_tracker() -> CostTracker:
    """Get global cost tracker instance"""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker

# CLI Interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Cost Tracker")
    parser.add_argument("--summary", action="store_true", help="Show daily summary")
    parser.add_argument("--breakdown", type=int, default=24, help="Show cost breakdown for N hours")
    parser.add_argument("--limit", type=float, help="Set daily limit in GBP")
    parser.add_argument("--test", action="store_true", help="Run test cost tracking")
    
    args = parser.parse_args()
    
    tracker = get_cost_tracker()
    
    if args.limit:
        tracker.daily_limit_gbp = args.limit
        print(f"Daily limit set to £{args.limit}")
    
    if args.summary:
        summary = tracker.get_daily_summary()
        print("Daily Cost Summary:")
        print(f"  Total: £{summary['total_cost_gbp']:.3f} / £{summary['daily_limit_gbp']}")
        print(f"  Utilization: {summary['utilization_percent']:.1f}%")
        print(f"  Emergency shutdown: {summary['emergency_shutdown']}")
        
        if summary['costs_by_service']:
            print("  By service:")
            for service, cost in summary['costs_by_service'].items():
                print(f"    {service}: £{cost:.3f}")
    
    if args.breakdown:
        breakdown = tracker.get_cost_breakdown(args.breakdown)
        print(f"\nCost Breakdown ({args.breakdown}h):")
        print(f"  Total events: {breakdown['total_events']}")
        print(f"  Total cost: £{breakdown['total_cost']:.3f}")
        
        for service, data in breakdown['service_breakdown'].items():
            print(f"  {service}: £{data['total_cost']:.3f} ({data['event_count']} events)")
    
    if args.test:
        print("Running cost tracking test...")
        
        # Test API call tracking
        await tracker.track_api_call("claude-haiku", 1000, "test-worker", 
                                   input_tokens=1000, output_tokens=200)
        
        await tracker.track_api_call("openai-tts", 500, "audio-worker")
        
        await tracker.track_storage_cost("aws-s3", 1024*1024*10, "storage-worker")  # 10MB
        
        print("Test costs tracked successfully")
        
        summary = tracker.get_daily_summary()
        print(f"New total: £{summary['total_cost_gbp']:.3f}")

if __name__ == "__main__":
    asyncio.run(main())