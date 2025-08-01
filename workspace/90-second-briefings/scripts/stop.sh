#!/bin/bash
# Stop script for 90-Second Briefings system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "=========================================="
echo "  90-Second Briefings Stop Script"
echo "=========================================="
echo

# Check if running in Docker mode
if docker-compose ps briefings-app 2>/dev/null | grep -q "Up"; then
    DOCKER_MODE=true
    print_status "Detected Docker mode"
else
    DOCKER_MODE=false
    print_status "Detected local mode"
fi

# Function to stop Docker containers
stop_docker() {
    print_status "Stopping Docker containers..."
    
    # Graceful shutdown
    docker-compose stop
    
    # Remove containers
    if [ "$1" = "--remove" ]; then
        print_status "Removing containers..."
        docker-compose down
        
        if [ "$2" = "--volumes" ]; then
            print_status "Removing volumes..."
            docker-compose down -v
        fi
    fi
    
    print_success "Docker containers stopped"
}

# Function to stop local processes
stop_local() {
    print_status "Stopping local processes..."
    
    # Stop Project Manager
    if [ -f ".project_manager.pid" ]; then
        PID=$(cat .project_manager.pid)
        if kill -0 $PID 2>/dev/null; then
            print_status "Stopping Project Manager (PID: $PID)..."
            kill -TERM $PID
            sleep 2
            # Force kill if still running
            if kill -0 $PID 2>/dev/null; then
                kill -KILL $PID
            fi
        fi
        rm .project_manager.pid
    fi
    
    # Stop System Monitor
    if [ -f ".monitor.pid" ]; then
        PID=$(cat .monitor.pid)
        if kill -0 $PID 2>/dev/null; then
            print_status "Stopping System Monitor (PID: $PID)..."
            kill -TERM $PID
            sleep 2
            if kill -0 $PID 2>/dev/null; then
                kill -KILL $PID
            fi
        fi
        rm .monitor.pid
    fi
    
    # Stop Dashboard
    if [ -f ".dashboard.pid" ]; then
        PID=$(cat .dashboard.pid)
        if kill -0 $PID 2>/dev/null; then
            print_status "Stopping Dashboard (PID: $PID)..."
            kill -TERM $PID
            sleep 2
            if kill -0 $PID 2>/dev/null; then
                kill -KILL $PID
            fi
        fi
        rm .dashboard.pid
    fi
    
    # Stop any remaining Python processes related to the system
    print_status "Cleaning up remaining processes..."
    pkill -f "core.project_manager" 2>/dev/null || true
    pkill -f "core.system_monitor" 2>/dev/null || true
    pkill -f "streamlit run dashboard/app.py" 2>/dev/null || true
    
    # Optionally stop Redis if it was started by us
    if [ "$1" = "--redis" ]; then
        print_status "Stopping Redis server..."
        pkill redis-server 2>/dev/null || true
    fi
    
    print_success "Local processes stopped"
}

# Function to create shutdown report
create_shutdown_report() {
    print_status "Creating shutdown report..."
    
    # Get final system status
    if [ "$DOCKER_MODE" = true ]; then
        FINAL_STATUS=$(docker-compose exec -T briefings-app python -m core.system_monitor --status 2>/dev/null || echo "System unavailable")
    else
        FINAL_STATUS=$(python -m core.system_monitor --status 2>/dev/null || echo "System unavailable")
    fi
    
    # Create report
    cat > shutdown_report.txt << EOF
90-Second Briefings Shutdown Report
Generated: $(date)
Mode: $([ "$DOCKER_MODE" = true ] && echo "Docker" || echo "Local")

Final System Status:
$FINAL_STATUS

Shutdown initiated at: $(date)
Shutdown method: $1
EOF
    
    print_success "Shutdown report created: shutdown_report.txt"
}

# Function to backup data before shutdown
backup_data() {
    if [ "$1" = "--backup" ]; then
        print_status "Creating data backup..."
        
        BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # Copy important data
        cp -r data/ "$BACKUP_DIR/" 2>/dev/null || true
        cp -r logs/ "$BACKUP_DIR/" 2>/dev/null || true
        cp *.log "$BACKUP_DIR/" 2>/dev/null || true
        
        print_success "Data backed up to: $BACKUP_DIR"
    fi
}

# Main function
main() {
    # Parse arguments
    BACKUP=false
    REMOVE=false
    VOLUMES=false
    REDIS=false
    
    for arg in "$@"; do
        case $arg in
            --backup)
                BACKUP=true
                ;;
            --remove)
                REMOVE=true
                ;;
            --volumes)
                VOLUMES=true
                ;;
            --redis)
                REDIS=true
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
        esac
    done
    
    # Create backup if requested
    if [ "$BACKUP" = true ]; then
        backup_data --backup
    fi
    
    # Create shutdown report
    create_shutdown_report
    
    # Stop services
    if [ "$DOCKER_MODE" = true ]; then
        if [ "$REMOVE" = true ] && [ "$VOLUMES" = true ]; then
            stop_docker --remove --volumes
        elif [ "$REMOVE" = true ]; then
            stop_docker --remove
        else
            stop_docker
        fi
    else
        if [ "$REDIS" = true ]; then
            stop_local --redis
        else
            stop_local
        fi
    fi
    
    # Clean up any shutdown signal files
    rm -f EMERGENCY_SHUTDOWN PAUSE_NON_ESSENTIAL COST_WARNING SYSTEM_SHUTDOWN.json
    
    print_success "90-Second Briefings system stopped successfully"
    print_status "Check shutdown_report.txt for final system status"
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --backup     Create backup of data before shutdown"
    echo "  --remove     Remove Docker containers (Docker mode only)"
    echo "  --volumes    Remove Docker volumes (requires --remove)"
    echo "  --redis      Stop Redis server (local mode only)"
    echo "  --help       Show this help message"
    echo
    echo "Examples:"
    echo "  $0                        # Basic stop"
    echo "  $0 --backup              # Stop with data backup"
    echo "  $0 --remove --volumes     # Docker: remove containers and volumes"
    echo "  $0 --redis --backup       # Local: stop with Redis and backup"
}

# Run main function
main "$@"