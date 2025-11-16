# Onboarding Checklist

Use this checklist to ensure you have everything set up correctly for using Metamorphic Guard in your project.

## Prerequisites

- [ ] Python 3.10 or higher installed
- [ ] pip (Python package manager) available
- [ ] Git installed (for version control)
- [ ] Basic understanding of Python programming
- [ ] Access to your baseline and candidate implementations

## Installation

- [ ] Metamorphic Guard installed: `pip install metamorphic-guard`
- [ ] Optional dependencies installed if needed:
  - [ ] LLM support: `pip install metamorphic-guard[llm]`
  - [ ] Queue backends: `pip install metamorphic-guard[queue]`
  - [ ] OpenTelemetry: `pip install metamorphic-guard[otel]`
- [ ] Installation verified: `metamorphic-guard --version`

## Project Setup

- [ ] Project directory created
- [ ] Baseline implementation created (`baseline.py` or equivalent)
- [ ] Candidate implementation created (`candidate.py` or equivalent)
- [ ] Configuration file created (using `metamorphic-guard init` or manually)
- [ ] Policy file selected or created (optional but recommended)

### Using Init Command

- [ ] Ran `metamorphic-guard init --project-dir <dir>` OR
- [ ] Ran `metamorphic-guard init --template <template>` OR
- [ ] Created configuration manually

## First Evaluation

- [ ] Ran a test evaluation locally
- [ ] Verified evaluation completes successfully
- [ ] Reviewed evaluation output and decision
- [ ] Generated HTML report: `--html-report report.html`
- [ ] Opened and reviewed HTML report in browser

## Understanding Results

- [ ] Understand what "Adopt? ✅ Yes" means
- [ ] Understand what "Adopt? ❌ No" means
- [ ] Know how to interpret Δ Pass Rate
- [ ] Know how to interpret confidence intervals (Δ 95% CI)
- [ ] Know where to find detailed JSON reports

## Configuration

- [ ] Selected appropriate preset (`--preset minimal|standard|sequential|adaptive|full`)
- [ ] Configured sample size (`--n`) appropriately
- [ ] Set up policy file (`--policy`) if using custom criteria
- [ ] Configured monitors if needed (`--monitor`)
- [ ] Set up reporting directory (`--report-dir`)

## Integration (Optional)

### CI/CD Integration

- [ ] Created GitHub Actions workflow (if using GitHub)
- [ ] Configured workflow to run on pull requests
- [ ] Set up report artifacts upload
- [ ] Added status badge to README
- [ ] Tested workflow in a test PR

### Distributed Execution (Optional)

- [ ] Queue backend installed and configured (Redis, SQS, etc.)
- [ ] Workers configured and running
- [ ] Dispatcher configured in evaluation
- [ ] Tested distributed execution

### Observability (Optional)

- [ ] Prometheus metrics enabled (if using)
- [ ] Structured logging configured (if using)
- [ ] OpenTelemetry tracing configured (if using)
- [ ] Webhook alerts configured (if using)

## Documentation

- [ ] Read [Quick Start Guide](quickstart.md)
- [ ] Reviewed [Task Specifications](concepts/task-specifications.md)
- [ ] Checked [Configuration Guide](user-guide/configuration.md)
- [ ] Reviewed [Policies Documentation](user-guide/policies.md)
- [ ] Explored [Examples](../examples/basic.md)

## Advanced Features (Optional)

- [ ] Explored adaptive sampling
- [ ] Tried sequential testing
- [ ] Set up custom monitors
- [ ] Created custom task specifications
- [ ] Explored LLM evaluation features (if applicable)

## Best Practices

- [ ] Using version control for implementations and configs
- [ ] Storing reports in a consistent location
- [ ] Documenting policy decisions
- [ ] Reviewing reports before making adoption decisions
- [ ] Setting up automated evaluations in CI/CD

## Troubleshooting

- [ ] Know where to find help:
  - [ ] API Reference: [api/reference.md](../api/reference.md)
  - [ ] Examples: [examples/](../examples/)
  - [ ] GitHub Issues: [GitHub Issues](https://github.com/duhboto/MetamorphicGuard/issues)
- [ ] Understand common error messages
- [ ] Know how to adjust sample size for faster evaluations
- [ ] Know how to interpret rejection reasons

## Next Steps

After completing this checklist, you should:

1. **Run regular evaluations** on your implementations
2. **Integrate into your workflow** (CI/CD, release process)
3. **Refine your policies** based on your risk tolerance
4. **Explore advanced features** as needed
5. **Share results** with your team

## Quick Reference

### Essential Commands

```bash
# Initialize project
metamorphic-guard init --project-dir my-project

# Run evaluation
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --n 100

# Generate HTML report
metamorphic-guard report report.json --output report.html

# List available presets
metamorphic-guard evaluate --help | grep preset
```

### Key Files

- `metamorphic.toml` - Main configuration file
- `baseline.py` - Baseline implementation
- `candidate.py` - Candidate implementation
- `policies/*.toml` - Policy files
- `reports/*.json` - JSON evaluation reports
- `*.html` - HTML reports

### Important Concepts

- **Baseline**: The reference implementation to compare against
- **Candidate**: The new implementation being evaluated
- **Property**: A requirement that outputs must satisfy
- **Metamorphic Relation**: A transformation that should preserve behavior
- **Policy**: Adoption criteria (min_delta, min_pass_rate, etc.)
- **Confidence Interval**: Statistical range for improvement estimate

## Getting Help

If you're stuck:

1. Check the [Quick Start Guide](quickstart.md) for step-by-step instructions
2. Review [Examples](../examples/) for common patterns
3. Consult the [API Reference](../api/reference.md) for detailed documentation
4. Search [GitHub Issues](https://github.com/duhboto/MetamorphicGuard/issues) for similar problems
5. Open a new issue with details about your problem

---

**Ready to start?** Begin with the [Quick Start Guide](quickstart.md) and work through this checklist as you go!

