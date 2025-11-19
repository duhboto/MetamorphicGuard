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

# Check if metamorphic-guard is installed
if ! command -v metamorphic-guard &> /dev/null; then
    echo "⚠️  metamorphic-guard command not found"
    
    # Check if we are in the repo structure and can run from source
    if [ -d "../metamorphic_guard" ]; then
        echo "🔄 Falling back to running from source (../metamorphic_guard found)"
        export PYTHONPATH=$PYTHONPATH:..
    else
        echo "❌ Error: metamorphic-guard is not installed and source not found."
        exit 1
    fi
fi

echo "Running distributed evaluation..."
echo "================================="
echo ""
echo "This will start a coordinator that dispatches work to workers."
echo "Start workers in separate terminals with:"
echo "  metamorphic-guard-worker --backend redis --queue-config '{\"url\":\"redis://localhost:6379/0\"}'"
echo ""
read -p "Press Enter to continue..."

# Use the custom runner
python scripts/runner.py evaluate \
  --config configs/distributed.toml \
  --html-report reports/distributed_report.html

echo ""
echo "✅ Evaluation complete!"
echo "📊 Report: reports/distributed_report.html"




