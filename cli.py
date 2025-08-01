#!/usr/bin/env python3
"""
Command Line Interface for Mini-Claude
Provides easy access to all Mini-Claude functionality
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List

def setup_environment():
    """Setup Mini-Claude environment"""
    print("Setting up Mini-Claude environment...")
    
    # Check if config exists
    config_path = Path("config.json")
    if not config_path.exists():
        print("Creating default configuration...")
        default_config = {
            "anthropic_api_key": "",
            "model": "claude-3-haiku-20240307",
            "max_concurrent_tasks": 3,
            "check_interval": 5
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"Created {config_path}")
    
    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\nANTHROPIC_API_KEY environment variable not set!")
        print("Please set it with: export ANTHROPIC_API_KEY='your-api-key'")
        print("Or add it to config.json")
    
    # Create directories
    dirs_to_create = ["backups", "logs"]
    for dir_name in dirs_to_create:
        Path(dir_name).mkdir(exist_ok=True)
        print(f"Created directory: {dir_name}")
    
    print("Setup complete!")

def run_single_task(args):
    """Run a single task"""
    cmd = [
        "python", "mini_claude.py",
        "--task", args.task,
        "--type", args.type
    ]
    
    if args.file:
        cmd.extend(["--file", args.file])
    if args.code:
        cmd.extend(["--code", args.code])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Task failed: {e}", file=sys.stderr)
        if e.stdout:
            print("Output:", e.stdout)
        if e.stderr:
            print("Errors:", e.stderr, file=sys.stderr)

def start_daemon(args):
    """Start Mini-Claude daemon"""
    print("Starting Mini-Claude daemon...")
    cmd = ["python", "mini_claude.py", "--daemon"]
    
    if args.config:
        cmd.extend(["--config", args.config])
    
    try:
        # Run in background if requested
        if args.background:
            subprocess.Popen(cmd)
            print("Daemon started in background")
        else:
            subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nDaemon stopped")

def manage_queue(args):
    """Manage task queue"""
    cmd = ["python", "task_queue.py"]
    
    if args.backend:
        cmd.extend(["--backend", args.backend])
    
    if args.submit:
        cmd.extend(["--submit", args.submit])
        if args.type:
            cmd.extend(["--type", args.type])
    elif args.list:
        cmd.append("--list")
        if args.status:
            cmd.extend(["--status", args.status])
    elif args.get:
        cmd.extend(["--get", args.get])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Queue operation failed: {e}", file=sys.stderr)

def manage_updates(args):
    """Manage self-updates"""
    cmd = ["python", "self_update.py"]
    
    if args.list_updates:
        cmd.append("--list")
    elif args.approve:
        cmd.extend(["--approve", args.approve])
    elif args.reject:
        cmd.extend(["--reject", args.reject])
    elif args.rollback:
        cmd.extend(["--rollback", args.rollback])
    elif args.cleanup:
        cmd.extend(["--cleanup", str(args.cleanup)])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Update operation failed: {e}", file=sys.stderr)

def show_status():
    """Show Mini-Claude system status"""
    print("Mini-Claude System Status")
    print("=" * 40)
    
    # Check configuration
    config_path = Path("config.json")
    if config_path.exists():
        print("✓ Configuration file exists")
        with open(config_path) as f:
            config = json.load(f)
        
        if config.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY"):
            print("✓ API key configured")
        else:
            print("✗ API key not configured")
    else:
        print("✗ Configuration file missing")
    
    # Check dependencies
    try:
        import anthropic
        print("✓ Anthropic library installed")
    except ImportError:
        print("✗ Anthropic library not installed")
    
    # Check database
    db_path = Path("mini_claude_tasks.db")
    if db_path.exists():
        print("✓ Task database exists")
    else:
        print("- Task database will be created on first use")
    
    # Check for pending updates
    updates_path = Path("pending_updates.json")
    if updates_path.exists():
        with open(updates_path) as f:
            updates = json.load(f)
        pending_count = sum(1 for u in updates.values() if u.get("status") == "pending")
        if pending_count > 0:
            print(f"⚠ {pending_count} pending updates require approval")
        else:
            print("✓ No pending updates")
    else:
        print("✓ No pending updates")
    
    # Check logs
    log_path = Path("activity.log")
    if log_path.exists():
        size_mb = log_path.stat().st_size / (1024 * 1024)
        print(f"✓ Activity log exists ({size_mb:.1f} MB)")
    else:
        print("- Activity log will be created on first use")

def install_dependencies():
    """Install required dependencies"""
    print("Installing Mini-Claude dependencies...")
    
    requirements = [
        "anthropic>=0.25.0",
        "redis",  # Optional for Redis backend
    ]
    
    for req in requirements:
        try:
            print(f"Installing {req}...")
            subprocess.run([sys.executable, "-m", "pip", "install", req], 
                         check=True, capture_output=True)
            print(f"✓ {req} installed")
        except subprocess.CalledProcessError as e:
            if "redis" in req:
                print(f"⚠ {req} installation failed (optional)")
            else:
                print(f"✗ {req} installation failed: {e}")
                return False
    
    print("Dependencies installed successfully!")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Mini-Claude CLI - Lightweight AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s setup                           # Setup Mini-Claude environment
  %(prog)s task "write tests for utils.py" # Run a single task
  %(prog)s daemon --background             # Start daemon in background
  %(prog)s queue --submit "debug error"    # Submit task to queue
  %(prog)s queue --list --status pending   # List pending tasks
  %(prog)s updates --list                  # List pending updates
  %(prog)s status                          # Show system status
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Setup Mini-Claude environment")
    
    # Task command
    task_parser = subparsers.add_parser("task", help="Run a single task")
    task_parser.add_argument("task", help="Task description")
    task_parser.add_argument("--type", default="general", help="Task type")
    task_parser.add_argument("--file", help="File to process")
    task_parser.add_argument("--code", help="Code to process")
    
    # Daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Start Mini-Claude daemon")
    daemon_parser.add_argument("--background", action="store_true", help="Run in background")
    daemon_parser.add_argument("--config", help="Config file path")
    
    # Queue command
    queue_parser = subparsers.add_parser("queue", help="Manage task queue")
    queue_parser.add_argument("--backend", choices=["sqlite", "redis"], default="sqlite")
    queue_parser.add_argument("--submit", help="Submit a new task")
    queue_parser.add_argument("--type", default="general", help="Task type")
    queue_parser.add_argument("--list", action="store_true", help="List tasks")
    queue_parser.add_argument("--status", help="Filter by status")
    queue_parser.add_argument("--get", help="Get task status by ID")
    
    # Updates command
    updates_parser = subparsers.add_parser("updates", help="Manage self-updates")
    updates_parser.add_argument("--list", dest="list_updates", action="store_true", help="List pending updates")
    updates_parser.add_argument("--approve", help="Approve update by ID")
    updates_parser.add_argument("--reject", help="Reject update by ID")
    updates_parser.add_argument("--rollback", help="Rollback update by ID")
    updates_parser.add_argument("--cleanup", type=int, help="Cleanup backups older than N days")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show system status")
    
    # Install command
    install_parser = subparsers.add_parser("install", help="Install dependencies")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Change to Mini-Claude directory if needed
    script_dir = Path(__file__).parent
    if script_dir != Path.cwd():
        os.chdir(script_dir)
    
    # Execute commands
    if args.command == "setup":
        setup_environment()
    elif args.command == "task":
        run_single_task(args)
    elif args.command == "daemon":
        start_daemon(args)
    elif args.command == "queue":
        manage_queue(args)
    elif args.command == "updates":
        manage_updates(args)
    elif args.command == "status":
        show_status()
    elif args.command == "install":
        install_dependencies()

if __name__ == "__main__":
    main()