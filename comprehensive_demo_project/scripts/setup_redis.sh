#!/bin/bash
# Redis setup helper script

set -e

echo "Setting up Redis for distributed execution..."
echo "=============================================="

# Check if Redis is already running
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is already running"
    exit 0
fi

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "Starting Redis with Docker..."
    docker run -d -p 6379:6379 --name metamorphic-redis redis:7-alpine
    echo "✅ Redis started in Docker container 'metamorphic-redis'"
    echo ""
    echo "To stop Redis:"
    echo "  docker stop metamorphic-redis"
    echo "  docker rm metamorphic-redis"
elif command -v redis-server &> /dev/null; then
    echo "Starting Redis server..."
    redis-server --daemonize yes
    echo "✅ Redis server started"
else
    echo "❌ Neither Docker nor redis-server found"
    echo ""
    echo "Please install Redis:"
    echo "  - Docker: docker run -d -p 6379:6379 redis:7-alpine"
    echo "  - Homebrew: brew install redis && brew services start redis"
    echo "  - apt: sudo apt install redis-server && sudo systemctl start redis"
    exit 1
fi






