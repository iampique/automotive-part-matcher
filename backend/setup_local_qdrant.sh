#!/bin/bash
# Script to set up Qdrant locally using Docker

set -e

echo "=========================================="
echo "Setting up Qdrant locally"
echo "=========================================="

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    echo ""
    echo "Please install Docker Desktop:"
    echo "1. Visit: https://www.docker.com/products/docker-desktop/"
    echo "2. Download and install Docker Desktop for Mac"
    echo "3. Start Docker Desktop"
    echo "4. Run this script again"
    exit 1
fi

# Check if Docker daemon is running
if ! docker ps &> /dev/null; then
    echo "❌ Docker daemon is not running"
    echo ""
    echo "Please start Docker Desktop and try again"
    exit 1
fi

echo "✓ Docker is available and running"

# Check if Qdrant container is already running
if docker ps --format '{{.Names}}' | grep -q "^qdrant$"; then
    echo "✓ Qdrant container is already running"
    QDRANT_URL="http://localhost:6333"
else
    echo "Starting Qdrant container..."
    
    # Stop and remove existing container if it exists
    docker stop qdrant 2>/dev/null || true
    docker rm qdrant 2>/dev/null || true
    
    # Start Qdrant container
    docker run -d \
        --name qdrant \
        -p 6333:6333 \
        -p 6334:6334 \
        -v $(pwd)/qdrant_storage:/qdrant/storage:z \
        qdrant/qdrant:latest
    
    echo "✓ Qdrant container started"
    echo "  Waiting for Qdrant to be ready..."
    
    # Wait for Qdrant to be ready
    for i in {1..30}; do
        if curl -s http://localhost:6333/health > /dev/null 2>&1; then
            echo "✓ Qdrant is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Qdrant failed to start after 30 seconds"
            exit 1
        fi
        sleep 1
    done
    
    QDRANT_URL="http://localhost:6333"
fi

echo ""
echo "=========================================="
echo "Qdrant is running at: $QDRANT_URL"
echo "=========================================="
echo ""
echo "Updating .env file..."

# Update .env file
cd "$(dirname "$0")"

# Backup existing .env
if [ -f .env ]; then
    cp .env .env.backup
    echo "✓ Backed up existing .env to .env.backup"
fi

# Update QDRANT_URL in .env (or create if it doesn't exist)
if grep -q "^QDRANT_URL=" .env 2>/dev/null; then
    # Update existing QDRANT_URL
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|^QDRANT_URL=.*|QDRANT_URL=$QDRANT_URL|" .env
    else
        # Linux
        sed -i "s|^QDRANT_URL=.*|QDRANT_URL=$QDRANT_URL|" .env
    fi
else
    # Add QDRANT_URL if it doesn't exist
    echo "QDRANT_URL=$QDRANT_URL" >> .env
fi

# Remove QDRANT_API_KEY for local instance (not needed)
if grep -q "^QDRANT_API_KEY=" .env 2>/dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' '/^QDRANT_API_KEY=/d' .env
    else
        sed -i '/^QDRANT_API_KEY=/d' .env
    fi
fi

echo "✓ Updated .env file"
echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "You can now run:"
echo "  python3 ingest_data.py"
echo ""
echo "To stop Qdrant, run:"
echo "  docker stop qdrant"
echo ""
