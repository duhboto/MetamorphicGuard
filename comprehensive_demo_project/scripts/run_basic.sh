#!/bin/bash
# Basic evaluation script

set -e

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

echo "Running basic evaluation..."
echo "============================"

# Use the custom runner which registers the task
python scripts/runner.py evaluate \
  --config configs/basic.toml \
  --html-report reports/basic_report.html

echo ""
echo "✅ Evaluation complete!"
echo "📊 Report: reports/basic_report.html"
echo ""
echo "To view the report:"
echo "  open reports/basic_report.html"




