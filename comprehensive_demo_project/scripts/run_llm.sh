#!/bin/bash
# LLM evaluation script

set -e

# Check for API keys
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  Warning: No LLM API keys found"
    echo "Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable"
    echo ""
    echo "Example:"
    echo "  export OPENAI_API_KEY='your-key-here'"
    echo "  ./scripts/run_llm.sh"
    exit 1
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

echo "Running LLM evaluation..."
echo "========================="

# Use the custom runner
python scripts/runner.py evaluate \
  --config configs/llm.toml \
  --html-report reports/llm_report.html

echo ""
echo "✅ Evaluation complete!"
echo "📊 Report: reports/llm_report.html"
echo "💰 Check the report for cost information"




