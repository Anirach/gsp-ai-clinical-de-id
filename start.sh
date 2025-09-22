#!/bin/bash

# Clinical Text De-Identification System - Startup Script
# This script sets up and starts the de-identification system

set -e

echo "=========================================="
echo "Clinical Text De-Identification System"
echo "Thai/English De-ID with PDPA/HIPAA Compliance"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Python version
check_python() {
    print_status "Checking Python version..."
    if command -v python3 &> /dev/null; then
        python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
        if [[ $(echo "$python_version >= 3.8" | bc -l) -eq 1 ]]; then
            print_status "Python $python_version found ✓"
        else
            print_error "Python 3.8+ required, found $python_version"
            exit 1
        fi
    else
        print_error "Python 3 not found"
        exit 1
    fi
}

# Check Node.js version
check_nodejs() {
    print_status "Checking Node.js version..."
    if command -v node &> /dev/null; then
        node_version=$(node --version | cut -d. -f1 | sed 's/v//')
        if [[ $node_version -ge 16 ]]; then
            print_status "Node.js $(node --version) found ✓"
        else
            print_warning "Node.js 16+ recommended, found $(node --version)"
        fi
    else
        print_warning "Node.js not found - frontend won't be available"
    fi
}

# Install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install dependencies
    pip install -r requirements.txt
    
    # Download spaCy model if not exists
    print_status "Checking spaCy English model..."
    python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null || {
        print_status "Downloading spaCy English model..."
        python -m spacy download en_core_web_sm
    }
    
    print_status "Python dependencies installed ✓"
}

# Install Node.js dependencies
install_node_deps() {
    if command -v npm &> /dev/null; then
        print_status "Installing Node.js dependencies..."
        cd frontend
        npm install
        cd ..
        print_status "Node.js dependencies installed ✓"
    else
        print_warning "npm not found - skipping frontend setup"
    fi
}

# Create necessary directories
create_directories() {
    print_status "Creating directories..."
    mkdir -p logs
    mkdir -p logs/audit
    mkdir -p data/exports
    print_status "Directories created ✓"
}

# Run basic tests
run_tests() {
    print_status "Running basic functionality tests..."
    source venv/bin/activate
    
    cd tests
    python test_basic_functionality.py
    test_result=$?
    cd ..
    
    if [ $test_result -eq 0 ]; then
        print_status "Basic tests passed ✓"
    else
        print_warning "Some tests failed - system may have limited functionality"
    fi
}

# Start backend service
start_backend() {
    print_status "Starting backend service..."
    source venv/bin/activate
    
    # Set environment
    export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend/src"
    
    # Start with PM2 if available, otherwise direct
    if command -v pm2 &> /dev/null; then
        print_status "Starting backend with PM2..."
        pm2 start --name "clinical-deid-api" --interpreter python3 backend/src/main.py
        pm2 logs clinical-deid-api --nostream --lines 5
    else
        print_status "Starting backend directly..."
        cd backend/src
        python main.py &
        BACKEND_PID=$!
        cd ../..
        echo $BACKEND_PID > backend.pid
        print_status "Backend started (PID: $BACKEND_PID)"
    fi
}

# Start frontend service
start_frontend() {
    if command -v npm &> /dev/null && [ -d "frontend/node_modules" ]; then
        print_status "Starting frontend service..."
        
        cd frontend
        if command -v pm2 &> /dev/null; then
            print_status "Starting frontend with PM2..."
            pm2 start --name "clinical-deid-ui" npm -- start
        else
            print_status "Starting frontend directly..."
            npm start &
            FRONTEND_PID=$!
            echo $FRONTEND_PID > ../frontend.pid
            print_status "Frontend started (PID: $FRONTEND_PID)"
        fi
        cd ..
    else
        print_warning "Frontend not available - npm or dependencies missing"
    fi
}

# Display service information
show_service_info() {
    print_status "Service Information:"
    echo ""
    echo "🔧 Backend API:"
    echo "   URL: http://localhost:8000"
    echo "   Docs: http://localhost:8000/docs"
    echo "   Health: http://localhost:8000/health"
    echo ""
    
    if command -v npm &> /dev/null && [ -d "frontend/node_modules" ]; then
        echo "🖥️  Frontend UI:"
        echo "   URL: http://localhost:3000"
        echo ""
    fi
    
    echo "👤 Demo Accounts:"
    echo "   Admin: admin / admin123"
    echo "   Reviewer: reviewer / reviewer123"
    echo "   Operator: operator / operator123"
    echo ""
    
    echo "📋 Features:"
    echo "   ✓ Bilingual Detection (Thai/English)"
    echo "   ✓ Policy-driven Transformations"
    echo "   ✓ Deterministic Pseudonymization"
    echo "   ✓ Complete Audit Trails"
    echo "   ✓ PDPA/HIPAA/GDPR Compliance"
    echo ""
    
    echo "📁 Important Files:"
    echo "   Configuration: .env"
    echo "   Logs: logs/"
    echo "   Sample Data: data/samples/"
    echo ""
}

# Main execution
main() {
    print_status "Starting Clinical DeID System setup..."
    
    # Pre-flight checks
    check_python
    check_nodejs
    
    # Setup
    create_directories
    install_python_deps
    install_node_deps
    
    # Tests
    run_tests
    
    # Start services
    start_backend
    sleep 3  # Wait for backend to start
    start_frontend
    
    # Information
    echo ""
    print_status "System startup complete!"
    show_service_info
    
    print_status "System is ready for use 🚀"
    
    # Keep script running if started services directly
    if [ ! -z "$BACKEND_PID" ] || [ ! -z "$FRONTEND_PID" ]; then
        print_status "Press Ctrl+C to stop services..."
        trap 'print_status "Stopping services..."; kill $BACKEND_PID 2>/dev/null; kill $FRONTEND_PID 2>/dev/null; exit' INT
        wait
    fi
}

# Run main function
main "$@"