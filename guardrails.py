#!/usr/bin/env python3
"""
Enhanced Security Guardrails for Mini-Claude
Comprehensive security measures to prevent malicious operations
"""

import os
import re
import ast
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
import subprocess
import tempfile

@dataclass
class SecurityViolation:
    """Represents a security violation"""
    severity: str  # "critical", "high", "medium", "low"
    category: str
    description: str
    details: Dict[str, Any]

class CodeAnalyzer:
    """Analyzes code for security vulnerabilities"""
    
    CRITICAL_PATTERNS = [
        # System commands
        r'os\.system\s*\(',
        r'subprocess\.(run|call|Popen|check_output)\s*\(',
        r'eval\s*\(',
        r'exec\s*\(',
        r'__import__\s*\(',
        
        # File operations
        r'open\s*\(\s*["\'][/\\]',  # Absolute paths
        r'shutil\.(rmtree|move|copy)',
        r'os\.(remove|unlink|rmdir)',
        
        # Network operations
        r'urllib\.request',
        r'requests\.(get|post|put|delete)',
        r'socket\.',
        r'ftplib\.',
        r'smtplib\.',
        
        # Dangerous modules
        r'import\s+(os|subprocess|shutil|socket|urllib|requests|ftplib|smtplib)',
        r'from\s+(os|subprocess|shutil|socket|urllib|requests|ftplib|smtplib)',
    ]
    
    HIGH_RISK_PATTERNS = [
        # Code injection
        r'compile\s*\(',
        r'globals\s*\(\s*\)',
        r'locals\s*\(\s*\)',
        r'vars\s*\(',
        r'dir\s*\(',
        
        # File system access
        r'os\.path\.',
        r'pathlib\.',
        r'glob\.',
        
        # Process control
        r'os\.fork\s*\(\s*\)',
        r'threading\.',
        r'multiprocessing\.',
    ]
    
    MEDIUM_RISK_PATTERNS = [
        # Dynamic attribute access
        r'getattr\s*\(',
        r'setattr\s*\(',
        r'hasattr\s*\(',
        r'delattr\s*\(',
        
        # Reflection
        r'type\s*\(',
        r'isinstance\s*\(',
        r'__class__',
        r'__dict__',
        r'__getattribute__',
    ]
    
    def analyze_code(self, code: str, language: str = "python") -> List[SecurityViolation]:
        """Analyze code for security issues"""
        violations = []
        
        if language.lower() == "python":
            violations.extend(self._analyze_python_code(code))
        elif language.lower() in ["javascript", "js", "typescript", "ts"]:
            violations.extend(self._analyze_javascript_code(code))
        else:
            violations.extend(self._analyze_generic_code(code))
        
        return violations
    
    def _analyze_python_code(self, code: str) -> List[SecurityViolation]:
        """Analyze Python code specifically"""
        violations = []
        
        # Pattern-based analysis
        for pattern in self.CRITICAL_PATTERNS:
            matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                violations.append(SecurityViolation(
                    severity="critical",
                    category="dangerous_operation",
                    description=f"Critical security pattern detected: {match.group()}",
                    details={"pattern": pattern, "match": match.group(), "position": match.start()}
                ))
        
        for pattern in self.HIGH_RISK_PATTERNS:
            matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                violations.append(SecurityViolation(
                    severity="high",
                    category="risky_operation",
                    description=f"High-risk pattern detected: {match.group()}",
                    details={"pattern": pattern, "match": match.group(), "position": match.start()}
                ))
        
        # AST-based analysis for Python
        try:
            tree = ast.parse(code)
            violations.extend(self._analyze_ast(tree))
        except SyntaxError:
            # If code doesn't parse, that's suspicious
            violations.append(SecurityViolation(
                severity="medium",
                category="syntax_error",
                description="Code contains syntax errors",
                details={"error": "Failed to parse Python code"}
            ))
        
        return violations
    
    def _analyze_ast(self, tree: ast.AST) -> List[SecurityViolation]:
        """Analyze Python AST for dangerous operations"""
        violations = []
        
        for node in ast.walk(tree):
            # Check for dangerous function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec', 'compile']:
                        violations.append(SecurityViolation(
                            severity="critical",
                            category="code_injection",
                            description=f"Dangerous function call: {node.func.id}",
                            details={"function": node.func.id, "line": node.lineno}
                        ))
                
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['system'] and isinstance(node.func.value, ast.Name):
                        if node.func.value.id == 'os':
                            violations.append(SecurityViolation(
                                severity="critical",
                                category="system_command",
                                description="Direct system command execution",
                                details={"method": "os.system", "line": node.lineno}
                            ))
            
            # Check for dangerous imports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ['os', 'subprocess', 'shutil']:
                        violations.append(SecurityViolation(
                            severity="high",
                            category="dangerous_import",
                            description=f"Import of potentially dangerous module: {alias.name}",
                            details={"module": alias.name, "line": node.lineno}
                        ))
        
        return violations
    
    def _analyze_javascript_code(self, code: str) -> List[SecurityViolation]:
        """Analyze JavaScript/TypeScript code"""
        violations = []
        
        js_dangerous_patterns = [
            r'eval\s*\(',
            r'Function\s*\(',
            r'setTimeout\s*\(\s*["\'][^"\']*["\']',
            r'setInterval\s*\(\s*["\'][^"\']*["\']',
            r'document\.write\s*\(',
            r'innerHTML\s*=',
            r'outerHTML\s*=',
            r'require\s*\(\s*["\']child_process["\']',
            r'require\s*\(\s*["\']fs["\']',
            r'require\s*\(\s*["\']path["\']',
        ]
        
        for pattern in js_dangerous_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                violations.append(SecurityViolation(
                    severity="high",
                    category="dangerous_operation",
                    description=f"Dangerous JavaScript pattern: {match.group()}",
                    details={"pattern": pattern, "match": match.group(), "position": match.start()}
                ))
        
        return violations
    
    def _analyze_generic_code(self, code: str) -> List[SecurityViolation]:
        """Generic code analysis for other languages"""
        violations = []
        
        # Look for shell commands
        shell_patterns = [
            r'rm\s+-rf',
            r'sudo\s+',
            r'chmod\s+777',
            r'> /dev/null',
            r'2>&1',
            r'\| sh',
            r'\| bash',
        ]
        
        for pattern in shell_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                violations.append(SecurityViolation(
                    severity="high",
                    category="shell_command",
                    description=f"Potentially dangerous shell command: {match.group()}",
                    details={"pattern": pattern, "match": match.group(), "position": match.start()}
                ))
        
        return violations

class FileSystemGuard:
    """Guards against dangerous file system operations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.max_file_size = config.get("max_file_size", 10 * 1024 * 1024)  # 10MB
        self.allowed_extensions = set(config.get("allowed_file_extensions", []))
        self.forbidden_dirs = set(config.get("forbidden_directories", []))
    
    def validate_file_path(self, file_path: str) -> List[SecurityViolation]:
        """Validate file path for security"""
        violations = []
        path = Path(file_path).resolve()
        
        # Check for path traversal
        if ".." in str(path):
            violations.append(SecurityViolation(
                severity="critical",
                category="path_traversal",
                description="Path traversal attempt detected",
                details={"path": str(path)}
            ))
        
        # Check forbidden directories
        for forbidden_dir in self.forbidden_dirs:
            if str(path).startswith(forbidden_dir):
                violations.append(SecurityViolation(
                    severity="critical",
                    category="forbidden_directory",
                    description=f"Access to forbidden directory: {forbidden_dir}",
                    details={"path": str(path), "forbidden_dir": forbidden_dir}
                ))
        
        # Check file extension
        if self.allowed_extensions and path.suffix not in self.allowed_extensions:
            violations.append(SecurityViolation(
                severity="medium",
                category="forbidden_extension",
                description=f"File extension not allowed: {path.suffix}",
                details={"path": str(path), "extension": path.suffix}
            ))
        
        # Check file size if file exists
        if path.exists() and path.is_file():
            if path.stat().st_size > self.max_file_size:
                violations.append(SecurityViolation(
                    severity="medium",
                    category="file_too_large",
                    description=f"File exceeds maximum size: {path.stat().st_size} bytes",
                    details={"path": str(path), "size": path.stat().st_size, "max_size": self.max_file_size}
                ))
        
        return violations
    
    def validate_file_content(self, content: str) -> List[SecurityViolation]:
        """Validate file content for security"""
        violations = []
        
        # Check for binary content
        try:
            content.encode('utf-8')
        except UnicodeEncodeError:
            violations.append(SecurityViolation(
                severity="medium",
                category="binary_content",
                description="Binary content detected",
                details={"content_length": len(content)}
            ))
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'-----BEGIN [A-Z]+ KEY-----',  # Potential private keys
            r'password\s*=\s*["\'][^"\']+["\']',  # Hardcoded passwords
            r'secret\s*=\s*["\'][^"\']+["\']',  # Hardcoded secrets
            r'token\s*=\s*["\'][^"\']+["\']',  # Hardcoded tokens
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(SecurityViolation(
                    severity="high",
                    category="sensitive_data",
                    description=f"Potential sensitive data detected: {pattern}",
                    details={"pattern": pattern}
                ))
        
        return violations

class ExecutionSandbox:
    """Provides sandboxed execution environment"""
    
    def __init__(self, config: Dict[str, Any]):
        self.max_execution_time = config.get("max_execution_time", 300)  # 5 minutes
        self.sandbox_enabled = config.get("sandbox_enabled", True)
        self.allowed_commands = set([
            "python", "python3", "node", "npm", "yarn", "pip", "pip3",
            "git", "ls", "cat", "echo", "grep", "find", "wc", "sort"
        ])
    
    def validate_command(self, command: str) -> List[SecurityViolation]:
        """Validate command for execution"""
        violations = []
        
        if not self.sandbox_enabled:
            return violations
        
        # Parse command
        cmd_parts = command.split()
        if not cmd_parts:
            return violations
        
        base_command = cmd_parts[0]
        
        # Check if command is allowed
        if base_command not in self.allowed_commands:
            violations.append(SecurityViolation(
                severity="critical",
                category="forbidden_command",
                description=f"Command not allowed: {base_command}",
                details={"command": command, "base_command": base_command}
            ))
        
        # Check for dangerous flags
        dangerous_flags = [
            "-rf", "--recursive --force", "--delete", "--remove",
            "--privileged", "--cap-add", "--security-opt"
        ]
        
        for flag in dangerous_flags:
            if flag in command:
                violations.append(SecurityViolation(
                    severity="high",
                    category="dangerous_flag",
                    description=f"Dangerous command flag detected: {flag}",
                    details={"command": command, "flag": flag}
                ))
        
        return violations

class ComprehensiveGuardrails:
    """Main security guardrails system"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.code_analyzer = CodeAnalyzer()
        self.fs_guard = FileSystemGuard(self.config.get("security", {}))
        self.sandbox = ExecutionSandbox(self.config.get("security", {}))
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load security configuration"""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def validate_task(self, task_description: str, task_type: str, 
                     parameters: Dict[str, Any]) -> List[SecurityViolation]:
        """Comprehensive task validation"""
        violations = []
        
        # Validate task type
        allowed_task_types = [
            "write_tests", "translate_code", "debug_error", 
            "format_code", "generate_docs", "refactor_function", "general"
        ]
        
        if task_type not in allowed_task_types:
            violations.append(SecurityViolation(
                severity="medium",
                category="unknown_task_type",
                description=f"Unknown task type: {task_type}",
                details={"task_type": task_type}
            ))
        
        # Validate file paths in parameters
        for key, value in parameters.items():
            if key.endswith("_path") or key.endswith("_file"):
                if isinstance(value, str):
                    violations.extend(self.fs_guard.validate_file_path(value))
        
        # Validate code content
        if "code" in parameters:
            language = parameters.get("language", "python")
            violations.extend(self.code_analyzer.analyze_code(parameters["code"], language))
        
        return violations
    
    def validate_generated_content(self, content: str, content_type: str = "code") -> List[SecurityViolation]:
        """Validate generated content"""
        violations = []
        
        if content_type == "code":
            violations.extend(self.code_analyzer.analyze_code(content))
        
        violations.extend(self.fs_guard.validate_file_content(content))
        
        return violations
    
    def validate_command_execution(self, command: str) -> List[SecurityViolation]:
        """Validate command before execution"""
        return self.sandbox.validate_command(command)
    
    def get_security_summary(self, violations: List[SecurityViolation]) -> Dict[str, Any]:
        """Get summary of security violations"""
        if not violations:
            return {"status": "safe", "violations": 0}
        
        severity_counts = {}
        categories = set()
        
        for violation in violations:
            severity_counts[violation.severity] = severity_counts.get(violation.severity, 0) + 1
            categories.add(violation.category)
        
        # Determine overall status
        if any(v.severity == "critical" for v in violations):
            status = "critical"
        elif any(v.severity == "high" for v in violations):
            status = "high_risk"
        elif any(v.severity == "medium" for v in violations):
            status = "medium_risk"
        else:
            status = "low_risk"
        
        return {
            "status": status,
            "violations": len(violations),
            "severity_counts": severity_counts,
            "categories": list(categories),
            "details": [
                {
                    "severity": v.severity,
                    "category": v.category,
                    "description": v.description
                }
                for v in violations
            ]
        }

# Integration with existing SecurityGuardrails class
class SecurityGuardrails:
    """Enhanced security guardrails for Mini-Claude (maintains backward compatibility)"""
    
    def __init__(self):
        self.comprehensive = ComprehensiveGuardrails()
    
    @classmethod
    def validate_task(cls, task) -> bool:
        """Backward compatible task validation"""
        guardrails = cls()
        violations = guardrails.comprehensive.validate_task(
            task.description, 
            task.task_type, 
            task.parameters
        )
        
        # Return False if any critical or high severity violations
        return not any(v.severity in ["critical", "high"] for v in violations)
    
    @classmethod
    def validate_code(cls, code: str) -> bool:
        """Backward compatible code validation"""
        guardrails = cls()
        violations = guardrails.comprehensive.validate_generated_content(code, "code")
        
        # Return False if any critical violations
        return not any(v.severity == "critical" for v in violations)

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "Design Mini-Claude architecture and core components", "status": "completed", "priority": "high"}, {"id": "2", "content": "Create core agent framework (mini_claude.py)", "status": "completed", "priority": "high"}, {"id": "3", "content": "Build task queue system (task_queue.py)", "status": "completed", "priority": "high"}, {"id": "4", "content": "Create prompt templates directory with reusable prompts", "status": "completed", "priority": "medium"}, {"id": "5", "content": "Implement self-update mechanism (self_update.py)", "status": "completed", "priority": "medium"}, {"id": "6", "content": "Add guardrails and security measures", "status": "completed", "priority": "high"}, {"id": "7", "content": "Create CLI interface and configuration", "status": "in_progress", "priority": "medium"}, {"id": "8", "content": "Generate requirements.txt and setup files", "status": "pending", "priority": "low"}, {"id": "9", "content": "Create comprehensive README.md documentation", "status": "pending", "priority": "medium"}, {"id": "10", "content": "Generate architecture diagram", "status": "pending", "priority": "low"}]