#!/bin/bash
# Basic evaluation script

set -e

echo "Running basic evaluation..."
echo "============================"

metamorphic-guard evaluate \
  --config configs/basic.toml \
  --html-report reports/basic_report.html

echo ""
echo "✅ Evaluation complete!"
echo "📊 Report: reports/basic_report.html"
echo ""
echo "To view the report:"
echo "  open reports/basic_report.html"



