#!/bin/bash
# Launch script for 90-Second Briefings system

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

# Banner
echo "=========================================="
echo "  90-Second Briefings Launch Script"
echo "  AI-Curated News for Busy Professionals"
echo "=========================================="
echo

# Check if running in Docker or local mode
if [ "$1" = "--docker" ]; then
    DOCKER_MODE=true
    print_status "Running in Docker mode"
else
    DOCKER_MODE=false
    print_status "Running in local mode"
fi

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if [ "$DOCKER_MODE" = true ]; then
        # Check Docker and Docker Compose
        if ! command -v docker &> /dev/null; then
            print_error "Docker is not installed. Please install Docker first."
            exit 1
        fi
        
        if ! command -v docker-compose &> /dev/null; then
            print_error "Docker Compose is not installed. Please install Docker Compose first."
            exit 1
        fi
        
        print_success "Docker prerequisites satisfied"
    else
        # Check Python
        if ! command -v python3 &> /dev/null; then
            print_error "Python 3 is not installed. Please install Python 3.8+ first."
            exit 1
        fi
        
        # Check Python version
        python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if [ $(echo "$python_version >= 3.8" | bc -l) -eq 0 ]; then
            print_error "Python 3.8+ is required. Current version: $python_version"
            exit 1
        fi
        
        print_success "Python prerequisites satisfied (Python $python_version)"
    fi
}

# Function to setup environment
setup_environment() {
    print_status "Setting up environment..."
    
    # Check for .env file
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            print_warning ".env file not found. Creating from .env.example"
            cp .env.example .env
            print_warning "Please edit .env file with your API keys and configuration"
            print_warning "The system will use default/demo values for missing configurations"
        else
            print_error ".env.example file not found. Cannot create environment configuration."
            exit 1
        fi
    else
        print_success "Environment file found"
    fi
    
    # Create necessary directories
    mkdir -p data/{costs,monitoring}
    mkdir -p logs
    mkdir -p audio_output
    mkdir -p dashboard
    mkdir -p config
    
    print_success "Directories created"
}

# Function to install dependencies
install_dependencies() {
    if [ "$DOCKER_MODE" = false ]; then
        print_status "Installing Python dependencies..."
        
        # Check if virtual environment exists
        if [ ! -d "venv" ]; then
            print_status "Creating virtual environment..."
            python3 -m venv venv
        fi
        
        # Activate virtual environment
        source venv/bin/activate
        
        # Install requirements
        pip install --upgrade pip
        pip install -r requirements.txt
        
        # Download NLTK data
        python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('vader_lexicon')"
        
        print_success "Dependencies installed"
    fi
}

# Function to check API keys
check_api_keys() {
    print_status "Checking API configuration..."
    
    # Source environment variables
    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
    
    missing_keys=()
    
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        missing_keys+=("ANTHROPIC_API_KEY")
    fi
    
    if [ -z "$OPENAI_API_KEY" ]; then
        missing_keys+=("OPENAI_API_KEY")
    fi
    
    if [ ${#missing_keys[@]} -gt 0 ]; then
        print_warning "Missing API keys: ${missing_keys[*]}"
        print_warning "The system will run in demo mode for missing services"
    else
        print_success "Required API keys configured"
    fi
}

# Function to start services
start_services() {
    print_status "Starting 90-Second Briefings system..."
    
    if [ "$DOCKER_MODE" = true ]; then
        # Docker mode
        print_status "Building and starting Docker containers..."
        docker-compose up --build -d
        
        # Wait for services to be ready
        print_status "Waiting for services to start..."
        sleep 10
        
        # Check if containers are running
        if docker-compose ps | grep -q "Up"; then
            print_success "Docker containers started successfully"
        else
            print_error "Failed to start Docker containers"
            docker-compose logs
            exit 1
        fi
        
    else
        # Local mode
        source venv/bin/activate
        
        # Start Redis in background if not running
        if ! pgrep redis-server > /dev/null; then
            print_status "Starting Redis server..."
            redis-server --daemonize yes --port 6379
        fi
        
        # Start the system
        print_status "Starting Project Manager and Workers..."
        export PYTHONPATH=$PWD
        python -m core.project_manager --start &
        PROJECT_MANAGER_PID=$!
        
        # Start system monitor
        print_status "Starting System Monitor..."
        python -m core.system_monitor &
        MONITOR_PID=$!
        
        # Start web dashboard in background
        print_status "Starting Web Dashboard..."
        cd dashboard && streamlit run app.py --server.port=8000 --server.host=0.0.0.0 &
        DASHBOARD_PID=$!
        cd ..
        
        print_success "Services started in local mode"
        
        # Save PIDs for cleanup
        echo $PROJECT_MANAGER_PID > .project_manager.pid
        echo $MONITOR_PID > .monitor.pid
        echo $DASHBOARD_PID > .dashboard.pid
    fi
}

# Function to show system status
show_status() {
    echo
    print_status "System Status:"
    echo "🔗 Web Dashboard: http://localhost:8000"
    echo "📊 System Monitor: Check logs/ directory"
    echo "💰 Cost Tracking: Check data/costs/ directory"
    echo "📝 Activity Logs: activity.log and costs.log"
    echo
    
    if [ "$DOCKER_MODE" = true ]; then
        echo "Docker Commands:"
        echo "  View logs:     docker-compose logs -f"
        echo "  Stop system:   docker-compose down"
        echo "  Restart:       docker-compose restart"
    else
        echo "Local Commands:"
        echo "  Stop system:   ./scripts/stop.sh"
        echo "  View status:   python -m core.system_monitor --status"
        echo "  Check costs:   python -m core.cost_tracker --summary"
    fi
    echo
}

# Function to run health check
run_health_check() {
    print_status "Running health check..."
    
    # Wait a bit for services to fully start
    sleep 5
    
    # Check web dashboard
    if curl -s http://localhost:8000 > /dev/null; then
        print_success "Web dashboard is accessible"
    else
        print_warning "Web dashboard not accessible yet (may take a few more seconds)"
    fi
    
    # Check if system is processing
    if [ -f "data/costs/costs_$(date +%Y%m%d).json" ]; then
        print_success "Cost tracking is active"
    else
        print_warning "Cost tracking not yet active (will activate after first task)"
    fi
}

# Function to create demo briefing
create_demo_briefing() {
    if [ "$2" = "--demo" ]; then
        print_status "Creating demo briefing..."
        
        if [ "$DOCKER_MODE" = true ]; then
            docker-compose exec briefings-app python -m core.project_manager --demo
        else
            source venv/bin/activate
            python -m core.project_manager --demo
        fi
        
        print_success "Demo briefing created (check data/ directory)"
    fi
}

# Main execution
main() {
    check_prerequisites
    setup_environment
    install_dependencies
    check_api_keys
    start_services
    run_health_check
    create_demo_briefing "$@"
    show_status
    
    print_success "90-Second Briefings system launched successfully!"
    print_status "The system is now running and will begin generating briefings."
    print_status "Monitor the logs and dashboard for real-time updates."
}

# Cleanup function for graceful shutdown
cleanup() {
    print_status "Shutting down system..."
    
    if [ "$DOCKER_MODE" = true ]; then
        docker-compose down
    else
        # Kill background processes
        if [ -f ".project_manager.pid" ]; then
            kill $(cat .project_manager.pid) 2>/dev/null || true
            rm .project_manager.pid
        fi
        
        if [ -f ".monitor.pid" ]; then
            kill $(cat .monitor.pid) 2>/dev/null || true
            rm .monitor.pid
        fi
        
        if [ -f ".dashboard.pid" ]; then
            kill $(cat .dashboard.pid) 2>/dev/null || true
            rm .dashboard.pid
        fi
    fi
    
    print_success "System shutdown complete"
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --docker     Run in Docker mode (default: local mode)"
    echo "  --demo       Create a demo briefing after startup"
    echo "  --help       Show this help message"
    echo
    echo "Examples:"
    echo "  $0                    # Start in local mode"
    echo "  $0 --docker          # Start in Docker mode"
    echo "  $0 --docker --demo   # Start in Docker mode with demo briefing"
}

# Check for help flag
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_help
    exit 0
fi

# Run main function
main "$@"

# Keep script running in local mode
if [ "$DOCKER_MODE" = false ]; then
    print_status "System is running. Press Ctrl+C to stop."
    wait
fi