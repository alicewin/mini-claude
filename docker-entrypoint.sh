#!/bin/bash
set -e

# Initialize Mini-Claude if first run
if [ ! -f "/app/data/initialized" ]; then
    echo "Initializing Mini-Claude..."
    
    # Setup configuration if not exists
    if [ ! -f "/app/data/config.json" ]; then
        cp /app/config.json /app/data/config.json
    fi
    
    # Create symlinks for data persistence
    ln -sf /app/data/config.json /app/config.json
    ln -sf /app/data /app/backups
    ln -sf /app/data /app/logs
    
    # Mark as initialized
    touch /app/data/initialized
    echo "Mini-Claude initialized"
fi

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Warning: ANTHROPIC_API_KEY environment variable not set"
    echo "Mini-Claude will not be able to process tasks without an API key"
fi

# Execute the requested command
case "$1" in
    daemon)
        echo "Starting Mini-Claude daemon..."
        exec python mini_claude.py --daemon
        ;;
    task)
        shift
        echo "Running single task: $*"
        exec python mini_claude.py --task "$*"
        ;;
    queue)
        shift
        echo "Managing queue..."
        exec python task_queue.py "$@"
        ;;
    cli)
        shift
        echo "Running CLI command..."
        exec python cli.py "$@"
        ;;
    bash)
        echo "Starting bash shell..."
        exec /bin/bash
        ;;
    *)
        echo "Running custom command: $*"
        exec "$@"
        ;;
esac