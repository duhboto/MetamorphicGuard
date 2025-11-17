#!/bin/bash
# Distributed evaluation script

set -e

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis is not running"
    echo "Starting Redis with Docker..."
    docker run -d -p 6379:6379 --name metamorphic-redis redis:7-alpine || true
    sleep 2
fi

echo "Running distributed evaluation..."
echo "================================="
echo ""
echo "This will start a coordinator that dispatches work to workers."
echo "Start workers in separate terminals with:"
echo "  metamorphic-guard-worker --backend redis --queue-config '{\"url\":\"redis://localhost:6379/0\"}'"
echo ""
read -p "Press Enter to continue..."

metamorphic-guard evaluate \
  --config configs/distributed.toml \
  --html-report reports/distributed_report.html

echo ""
echo "✅ Evaluation complete!"
echo "📊 Report: reports/distributed_report.html"

