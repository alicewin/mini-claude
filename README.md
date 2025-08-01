# Mini-Claude 🤖

**A lightweight AI agent for repetitive coding, testing, and documentation tasks**

Built by Claude Senior Engineer to handle routine development work autonomously while maintaining strict security guardrails.

## 🚀 Quick Start

### Installation

```bash
# Clone or download Mini-Claude
cd mini-claude

# Install dependencies
pip install -r requirements.txt

# Set up environment
export ANTHROPIC_API_KEY="your-api-key-here"

# Initialize Mini-Claude
python cli.py setup
```

### Your First Task

```bash
# Run a single task
python cli.py task "write unit tests for this function" --file utils.py

# Or use the direct interface
python mini_claude.py --task "debug this error" --code "def broken(): return x + 1"
```

## 📋 Features

- **🔒 Security First**: Comprehensive guardrails prevent malicious operations
- **🔄 Self-Updating**: Safely updates helper scripts with approval workflow
- **⚡ Queue System**: SQLite or Redis-backed task queue for scalability
- **📝 Smart Templates**: Reusable prompts for common development tasks
- **🛡️ Sandboxed Execution**: Safe code execution environment
- **📊 Activity Logging**: Complete audit trail of all operations
- **🐳 Docker Ready**: Easy deployment with Docker/Docker Compose

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User/CLI      │    │   Mini-Claude    │    │   Claude API    │
│                 │───▶│   Core Agent     │───▶│   (Haiku)       │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Task Queue     │
                       │   (SQLite/Redis) │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Security        │
                       │  Guardrails      │
                       └──────────────────┘
```

## 🛠️ Core Components

### 1. Mini-Claude Agent (`mini_claude.py`)
- **LLM Interface**: Connects to Claude Haiku for cost-effective processing
- **Task Executor**: Runs tasks with security validation and sandboxing
- **Activity Logger**: Comprehensive logging of all operations

### 2. Task Queue (`task_queue.py`)
- **SQLite Backend**: Local task storage (default)
- **Redis Backend**: Distributed task queue for scaling
- **Priority System**: Handle urgent tasks first

### 3. Security Guardrails (`guardrails.py`)
- **Code Analysis**: AST and pattern-based security scanning
- **File System Protection**: Prevents access to sensitive directories
- **Command Validation**: Restricts dangerous system operations
- **Content Filtering**: Blocks suspicious patterns and credentials

### 4. Self-Update System (`self_update.py`)
- **Controlled Updates**: Only helper scripts, never core files
- **Approval Workflow**: Human review required for protected files
- **Rollback Support**: Automatic backup and restore capabilities
- **Change Tracking**: Complete audit trail of modifications

## 📖 Usage Guide

### Command Line Interface

```bash
# Setup and status
python cli.py setup                    # Initialize environment
python cli.py status                   # Check system status
python cli.py install                  # Install dependencies

# Single tasks
python cli.py task "write tests for utils.py" --file utils.py
python cli.py task "translate this to TypeScript" --code "def hello(): pass"
python cli.py task "debug this error" --type debug_error

# Daemon mode (background processing)
python cli.py daemon                   # Run daemon (foreground)
python cli.py daemon --background      # Run daemon (background)

# Queue management
python cli.py queue --submit "refactor function" --type refactor_function
python cli.py queue --list             # List all tasks
python cli.py queue --list --status pending  # Filter by status
python cli.py queue --get task-id-123  # Get task details

# Update management
python cli.py updates --list           # List pending updates
python cli.py updates --approve update-123  # Approve update
python cli.py updates --reject update-456   # Reject update
python cli.py updates --rollback update-789 # Rollback update
```

### Task Types

| Task Type | Description | Example |
|-----------|-------------|---------|
| `write_tests` | Generate unit tests | Write tests for authentication module |
| `translate_code` | Convert between languages | Translate Python to JavaScript |
| `debug_error` | Fix code errors | Debug IndexError in data processing |
| `format_code` | Clean up code style | Format according to PEP 8 |
| `generate_docs` | Create documentation | Document API endpoints |
| `refactor_function` | Improve code structure | Refactor for better performance |
| `general` | Custom tasks | Any development task |

### Configuration

Edit `config.json` to customize behavior:

```json
{
  "anthropic_api_key": "your-key-here",
  "model": "claude-3-haiku-20240307",
  "max_concurrent_tasks": 3,
  "queue_backend": "sqlite",
  "security": {
    "max_file_size": 10485760,
    "sandbox_enabled": true,
    "max_execution_time": 300
  }
}
```

## 🐳 Docker Deployment

### Quick Start with Docker

```bash
# Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# Run with Docker Compose (includes Redis)
docker-compose up -d

# Check status
docker-compose logs mini-claude

# Submit tasks
docker-compose exec mini-claude python cli.py task "write tests"
```

### Manual Docker Build

```bash
# Build image
docker build -t mini-claude .

# Run daemon
docker run -d \
  -e ANTHROPIC_API_KEY="your-key" \
  -v $(pwd)/workspace:/app/workspace \
  --name mini-claude \
  mini-claude daemon

# Run single task
docker run --rm \
  -e ANTHROPIC_API_KEY="your-key" \
  mini-claude task "debug this code"
```

## 🔐 Security Features

### Guardrails

- **Code Analysis**: Scans for dangerous patterns (eval, exec, system calls)
- **File Access Control**: Restricts access to system directories
- **Command Filtering**: Blocks dangerous shell commands
- **Size Limits**: Prevents processing of oversized files
- **Extension Filtering**: Only allows approved file types

### Allowed Operations

Mini-Claude can only perform these task types:
- ✅ Writing unit tests
- ✅ Translating code between languages  
- ✅ Debugging errors and fixing code
- ✅ Formatting and cleaning code
- ✅ Generating documentation
- ✅ Refactoring functions
- ❌ System administration
- ❌ Network operations
- ❌ File system modifications outside workspace

### Self-Update Safety

- **Protected Files**: Core files (`mini_claude.py`, `self_update.py`) require human approval
- **Automatic Backups**: All changes backed up with rollback capability
- **Change Auditing**: Complete log of all modifications
- **Update Approval**: Pending changes must be explicitly approved

## 📊 Monitoring and Logging

### Activity Logs

All operations are logged to `activity.log`:

```
2024-01-15 10:30:00 - INFO - TASK_START: abc123 - write_tests - Generate tests for user authentication
2024-01-15 10:30:15 - INFO - TASK_COMPLETE: abc123 - Status: completed
2024-01-15 10:31:00 - WARNING - SECURITY_VIOLATION: def456 - Dangerous pattern detected
```

### System Status

```bash
python cli.py status
```

Shows:
- ✓ Configuration status
- ✓ API key configuration
- ✓ Database status  
- ✓ Pending updates
- ✓ Log file size

## 🔧 Development

### Project Structure

```
mini-claude/
├── mini_claude.py          # Core agent
├── task_queue.py           # Queue management
├── self_update.py          # Update system
├── guardrails.py           # Security system
├── cli.py                  # Command line interface
├── config.json             # Configuration
├── requirements.txt        # Dependencies
├── setup.py               # Package setup
├── Dockerfile             # Container definition
├── docker-compose.yml     # Multi-service setup
├── prompt_templates/      # Reusable prompts
│   ├── write_tests.txt
│   ├── translate_code.txt
│   ├── debug_error.txt
│   └── ...
├── backups/              # Update backups
├── logs/                 # Activity logs
└── README.md            # This file
```

### Adding Custom Templates

Create new prompt templates in `prompt_templates/`:

```txt
# prompt_templates/my_task.txt
You are an expert software engineer.

TASK: {description}

CODE TO PROCESS:
{code}

Please complete this task following best practices.
```

Use with:
```bash
python cli.py task "my custom task" --type my_task --code "..."
```

### Testing

```bash
# Install dev dependencies
pip install -e .[dev]

# Run tests
pytest tests/

# Security scan
bandit -r . -x tests/

# Code formatting
black .
flake8 .
```

## ⚠️ Important Limitations

### What Mini-Claude CANNOT Do

- **Replicate itself** without explicit approval
- **Modify core files** without human review
- **Access system directories** outside workspace
- **Execute arbitrary shell commands**
- **Connect to external networks** (except Claude API)
- **Install software** or modify system
- **Access sensitive files** or credentials

### What Requires Human Approval

- Updates to `mini_claude.py` or `self_update.py`
- Changes to security configuration
- Installation of new dependencies
- Modification of Docker configuration

## 🚨 Emergency Procedures

### Stop All Operations

```bash
# Stop daemon
pkill -f "mini_claude.py --daemon"

# Or with Docker
docker-compose down
```

### Rollback Bad Update

```bash
# List recent updates
python cli.py updates --list

# Rollback specific update
python cli.py updates --rollback update-id-123
```

### Reset to Clean State

```bash
# Backup current state
cp -r . ../mini-claude-backup

# Clean databases and logs
rm -f mini_claude_tasks.db activity.log pending_updates.json

# Reinitialize
python cli.py setup
```

## 🤝 Contributing

Mini-Claude is designed to be self-contained and secure. If you need to make changes:

1. **Test thoroughly** in isolated environment
2. **Review security implications** of any modifications  
3. **Update documentation** to reflect changes
4. **Ensure backward compatibility** with existing tasks

## 📝 License

MIT License - See LICENSE file for details.

## 🆘 Support

### Common Issues

**Q: "ANTHROPIC_API_KEY not set" error**
A: Set environment variable: `export ANTHROPIC_API_KEY="your-key"`

**Q: Task fails with "Security violation"**
A: Check `activity.log` for details. Mini-Claude blocks potentially dangerous operations.

**Q: Daemon won't start**
A: Check `python cli.py status` and ensure all dependencies are installed.

**Q: Queue tasks not processing**
A: Ensure daemon is running: `python cli.py daemon`

### Getting Help

1. Check `activity.log` for error details
2. Run `python cli.py status` to diagnose issues
3. Ensure API key is configured correctly
4. Verify file permissions in workspace

---

**Built by Claude Senior Engineer** 🤖  
*A two-tier AI system for automated development tasks*

---

## 🎯 Quick Launch Command

Ready to start? Run this command to launch Mini-Claude and send your first task:

```bash
export ANTHROPIC_API_KEY="your-key-here" && \
python cli.py setup && \
python cli.py task "write unit tests for the calculate_total function in this code: def calculate_total(items): return sum(item.price for item in items)"
```

🚀 **Mini-Claude is now ready to assist with your development tasks!**