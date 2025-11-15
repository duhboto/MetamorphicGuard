# Plugin Marketplace

The Metamorphic Guard plugin marketplace is a curated collection of community-contributed plugins.

## Table of Contents

1. [Available Plugins](#available-plugins)
2. [Submitting Plugins](#submitting-plugins)
3. [Plugin Guidelines](#plugin-guidelines)
4. [Plugin Categories](#plugin-categories)

## Available Plugins

### Executors

Executors provide custom execution backends.

#### Official Executors

- `openai`: OpenAI API executor
- `anthropic`: Anthropic API executor
- `vllm`: vLLM local executor
- `docker`: Docker container executor

### Judges

Judges evaluate LLM outputs for quality.

#### Official Judges

- `LengthJudge`: Checks output length
- `CoherenceJudge`: Evaluates coherence
- `RelevanceJudge`: Checks relevance

### Mutants

Mutants transform inputs for metamorphic testing.

#### Official Mutants

- `ParaphraseMutant`: Paraphrases prompts
- `NegationMutant`: Negates prompts
- `SynonymMutant`: Replaces with synonyms

### Monitors

Monitors track metrics and observability.

#### Official Monitors

- `LatencyMonitor`: Tracks execution latency
- `LLMCostMonitor`: Tracks LLM API costs
- `FairnessGapMonitor`: Tracks fairness metrics
- `ResourceMonitor`: Tracks resource usage
- `PerformanceProfiler`: Comprehensive profiling

## Submitting Plugins

### Submission Process

1. **Develop your plugin** following the [plugin development guide](../contributing.md#plugin-development)

2. **Create a repository** for your plugin:
   - Use naming convention: `metamorphic-guard-<plugin-name>`
   - Include README with usage examples
   - Add tests and CI/CD

3. **Submit for inclusion**:
   - Open an issue with tag `plugin-submission`
   - Include:
     - Plugin name and description
     - Repository URL
     - Usage examples
     - Test results

4. **Review process**:
   - Maintainers review code quality
   - Check for security issues
   - Verify documentation
   - Test compatibility

5. **Approval**:
   - Plugin added to marketplace
   - Listed in documentation
   - Featured in release notes

### Submission Template

```markdown
## Plugin Information

- **Name**: my-plugin
- **Type**: Monitor
- **Repository**: https://github.com/user/metamorphic-guard-my-plugin
- **Version**: 1.0.0
- **Author**: Your Name

## Description

Brief description of what the plugin does.

## Usage

```python
from my_plugin import MyPlugin

monitor = MyPlugin(config={"key": "value"})
```

## Examples

Link to examples or include code snippets.

## Testing

- Test coverage: 85%
- Compatible with: Metamorphic Guard >= 2.0.0
```

## Plugin Guidelines

### Code Quality

- Follow Metamorphic Guard coding standards
- Include comprehensive tests (>80% coverage)
- Use type hints throughout
- Document all public APIs

### Security

- No hardcoded secrets
- Validate all inputs
- Use sandboxing when appropriate
- Follow security best practices

### Documentation

- Clear README with examples
- API documentation
- Usage examples
- Migration guides (if applicable)

### Compatibility

- Support latest Metamorphic Guard version
- Backward compatible when possible
- Clear version requirements

### Maintenance

- Respond to issues promptly
- Keep dependencies updated
- Maintain test coverage
- Update documentation

## Plugin Categories

### By Type

- **Executors**: Execution backends
- **Judges**: Output evaluation
- **Mutants**: Input transformation
- **Monitors**: Observability

### By Domain

- **LLM**: Large language model plugins
- **ML**: Machine learning plugins
- **Security**: Security-focused plugins
- **Performance**: Performance optimization plugins

### By Status

- **Official**: Maintained by core team
- **Community**: Community-maintained
- **Experimental**: Early stage, may have issues

## Featured Plugins

### Community Favorites

*Coming soon - submit your plugin to be featured!*

## Plugin Development Resources

- [Plugin Development Guide](../contributing.md#plugin-development)
- [Scaffolding Tool](../cookbook.md#interactive-init--plugin-scaffolds)
- [API Reference](../api/reference.md)
- [Examples](../examples/)

## Support

- **Plugin Issues**: Open issue in plugin repository
- **Marketplace Questions**: Use GitHub Discussions
- **Plugin Development Help**: See [Contributing Guide](../contributing.md)

