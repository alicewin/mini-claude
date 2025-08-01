#!/usr/bin/env python3
"""
Mini-Claude: A lightweight AI agent for repetitive coding tasks
Built by Claude Senior Engineer to handle routine development work
"""

import os
import sys
import json
import logging
import argparse
import subprocess
import tempfile
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import sqlite3
import threading
import signal

try:
    import anthropic
    from anthropic import Anthropic
except ImportError:
    print("Error: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

@dataclass
class Task:
    id: str
    description: str
    task_type: str
    parameters: Dict[str, Any]
    status: str = "pending"
    created_at: str = ""
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None

class SecurityGuardrails:
    """Security guardrails to prevent unsafe operations"""
    
    FORBIDDEN_PATTERNS = [
        "rm -rf",
        "sudo",
        "eval(",
        "exec(",
        "__import__",
        "open(",
        "subprocess.run",
        "os.system",
        "shell=True"
    ]
    
    ALLOWED_OPERATIONS = [
        "write_tests",
        "translate_code", 
        "debug_error",
        "format_code",
        "generate_docs",
        "refactor_function"
    ]
    
    @classmethod
    def validate_task(cls, task: Task) -> bool:
        """Validate that a task is safe to execute"""
        if task.task_type not in cls.ALLOWED_OPERATIONS:
            return False
            
        task_content = str(task.parameters)
        for pattern in cls.FORBIDDEN_PATTERNS:
            if pattern in task_content.lower():
                return False
                
        return True
    
    @classmethod
    def validate_code(cls, code: str) -> bool:
        """Validate generated code for safety"""
        for pattern in cls.FORBIDDEN_PATTERNS:
            if pattern in code.lower():
                return False
        return True

class ActivityLogger:
    """Comprehensive activity logging"""
    
    def __init__(self, log_file: str = "activity.log"):
        self.log_file = log_file
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log_task_start(self, task: Task):
        self.logger.info(f"TASK_START: {task.id} - {task.task_type} - {task.description}")
    
    def log_task_complete(self, task: Task):
        self.logger.info(f"TASK_COMPLETE: {task.id} - Status: {task.status}")
    
    def log_security_violation(self, task: Task, reason: str):
        self.logger.warning(f"SECURITY_VIOLATION: {task.id} - {reason}")
    
    def log_error(self, task_id: str, error: str):
        self.logger.error(f"ERROR: {task_id} - {error}")

class LLMInterface:
    """Interface to interact with Anthropic's Claude API"""
    
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        self.client = Anthropic(api_key=api_key)
        self.model = model
    
    def generate_response(self, prompt: str, max_tokens: int = 4000) -> str:
        """Generate response from Claude"""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            raise Exception(f"LLM API Error: {str(e)}")

class PromptManager:
    """Manages reusable prompt templates"""
    
    def __init__(self, templates_dir: str = "prompt_templates"):
        self.templates_dir = Path(templates_dir)
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """Load all prompt templates from files"""
        templates = {}
        if self.templates_dir.exists():
            for template_file in self.templates_dir.glob("*.txt"):
                with open(template_file, 'r') as f:
                    templates[template_file.stem] = f.read()
        return templates
    
    def get_prompt(self, task_type: str, **kwargs) -> str:
        """Get formatted prompt for task type"""
        if task_type not in self.templates:
            return f"Please {task_type} based on the following: {kwargs}"
        
        template = self.templates[task_type]
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing parameter {e} for template {task_type}")

class TaskExecutor:
    """Executes individual tasks with sandboxing"""
    
    def __init__(self, llm: LLMInterface, prompt_manager: PromptManager, logger: ActivityLogger):
        self.llm = llm
        self.prompt_manager = prompt_manager
        self.logger = logger
    
    def execute_task(self, task: Task) -> Task:
        """Execute a single task"""
        self.logger.log_task_start(task)
        
        # Security validation
        if not SecurityGuardrails.validate_task(task):
            task.status = "failed"
            task.error = "Security violation detected"
            self.logger.log_security_violation(task, task.error)
            return task
        
        try:
            # Generate prompt
            prompt = self.prompt_manager.get_prompt(task.task_type, **task.parameters)
            
            # Call LLM
            response = self.llm.generate_response(prompt)
            
            # Validate response
            if not SecurityGuardrails.validate_code(response):
                task.status = "failed"
                task.error = "Generated code failed security validation"
                self.logger.log_security_violation(task, task.error)
                return task
            
            # Execute in sandbox if needed
            result = self._execute_in_sandbox(task, response)
            
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.now().isoformat()
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self.logger.log_error(task.id, str(e))
        
        self.logger.log_task_complete(task)
        return task
    
    def _execute_in_sandbox(self, task: Task, code: str) -> str:
        """Execute code in a safe sandbox environment"""
        if task.task_type in ["write_tests", "format_code"]:
            # For code generation tasks, return the generated code
            return code
        elif task.task_type == "debug_error":
            # For debugging, return analysis
            return code
        else:
            # For other tasks, return the LLM response
            return code

class MiniClaude:
    """Main Mini-Claude agent class"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config = self._load_config(config_file)
        self.logger = ActivityLogger()
        self.llm = LLMInterface(
            self.config.get("anthropic_api_key", os.getenv("ANTHROPIC_API_KEY")),
            self.config.get("model", "claude-3-haiku-20240307")
        )
        self.prompt_manager = PromptManager()
        self.executor = TaskExecutor(self.llm, self.prompt_manager, self.logger)
        self.running = False
    
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """Load configuration from file"""
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        return {
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
            "model": "claude-3-haiku-20240307",
            "max_concurrent_tasks": 3,
            "check_interval": 5
        }
    
    def execute_single_task(self, task_description: str, task_type: str = "general", **parameters) -> Dict[str, Any]:
        """Execute a single task and return result"""
        task = Task(
            id=hashlib.md5(f"{task_description}{time.time()}".encode()).hexdigest()[:8],
            description=task_description,
            task_type=task_type,
            parameters=parameters,
            created_at=datetime.now().isoformat()
        )
        
        completed_task = self.executor.execute_task(task)
        
        return {
            "task_id": completed_task.id,
            "status": completed_task.status,
            "result": completed_task.result,
            "error": completed_task.error
        }
    
    def start_daemon_mode(self):
        """Start Mini-Claude in daemon mode to process queue"""
        from task_queue import TaskQueue
        
        self.logger.logger.info("Starting Mini-Claude daemon mode")
        self.running = True
        queue = TaskQueue()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        while self.running:
            try:
                task = queue.get_next_task()
                if task:
                    completed_task = self.executor.execute_task(task)
                    queue.update_task_status(completed_task)
                else:
                    time.sleep(self.config.get("check_interval", 5))
            except Exception as e:
                self.logger.log_error("daemon", str(e))
                time.sleep(10)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

def main():
    parser = argparse.ArgumentParser(description="Mini-Claude: Lightweight AI Agent")
    parser.add_argument("--task", help="Task description to execute")
    parser.add_argument("--type", default="general", help="Task type")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--file", help="File to process")
    parser.add_argument("--code", help="Code to process")
    
    args = parser.parse_args()
    
    if not os.getenv("ANTHROPIC_API_KEY") and not os.path.exists(args.config):
        print("Error: ANTHROPIC_API_KEY environment variable not set and no config file found")
        sys.exit(1)
    
    mini_claude = MiniClaude(args.config)
    
    if args.daemon:
        mini_claude.start_daemon_mode()
    elif args.task:
        parameters = {}
        if args.file:
            parameters["file_path"] = args.file
        if args.code:
            parameters["code"] = args.code
            
        result = mini_claude.execute_single_task(args.task, args.type, **parameters)
        print(json.dumps(result, indent=2))
    else:
        print("Use --task 'description' to run a single task or --daemon for queue mode")
        parser.print_help()

if __name__ == "__main__":
    main()