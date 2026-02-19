#!/bin/bash
# setup_environment.sh
# Sets up virtual environments and installs dependencies for all services.

set -e  # Exit on error

BASE_DIR=$(pwd)
echo "Setting up environment in: $BASE_DIR"

# Function to setup python venv
setup_venv() {
    SERVICE_DIR=$1
    echo "------------------------------------------------"
    echo "Setting up $SERVICE_DIR..."
    cd "$BASE_DIR/$SERVICE_DIR"
    
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    echo "Installing requirements..."
    source venv/bin/activate
    pip install --upgrade pip
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        echo "No requirements.txt found."
    fi
    deactivate
    echo "Done with $SERVICE_DIR"
}

# 0. Root Tools (ROS2 System Manager)
setup_venv "."

# 1. Malle AI Service
setup_venv "malle_ai_service"

# 2. Malle Service
setup_venv "malle_service"

# 3. Malle Web Sevice (Backend)
setup_venv "malle_web_service/service"

# 4. Malle Web Service (Frontend - Admin)
echo "------------------------------------------------"
echo "Setting up Malle Web Service (Frontend - Admin)..."
cd "$BASE_DIR/malle_web_service/ui/admin"
if [ -f "package.json" ]; then
    echo "Installing npm packages..."
    npm install
else
    echo "No package.json found in admin UI."
fi

echo "------------------------------------------------"
echo "Setup Complete! You can now run ros2_system_manager.py"
