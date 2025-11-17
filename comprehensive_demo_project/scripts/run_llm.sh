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

echo "Running LLM evaluation..."
echo "========================="

metamorphic-guard evaluate \
  --config configs/llm.toml \
  --html-report reports/llm_report.html

echo ""
echo "✅ Evaluation complete!"
echo "📊 Report: reports/llm_report.html"
echo "💰 Check the report for cost information"

