# Contributing to Metamorphic Guard

Thank you for your interest in contributing to Metamorphic Guard! This guide will help you get started.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Code Standards](#code-standards)
4. [Testing](#testing)
5. [Submitting Changes](#submitting-changes)
6. [Plugin Development](#plugin-development)
7. [Documentation](#documentation)

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- Basic understanding of metamorphic testing concepts

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/metamorphic-guard.git
   cd metamorphic-guard
   ```
3. Add upstream remote:
   ```bash
   git remote add upstream https://github.com/metamorphic-guard/metamorphic-guard.git
   ```

## Development Setup

### Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
```

### Pre-commit Hooks

Install pre-commit hooks for code quality:

```bash
pip install pre-commit
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=metamorphic_guard --cov-report=html

# Run specific test file
pytest tests/test_api.py

# Run with verbose output
pytest -v
```

## Code Standards

### Type Safety

- Use `mypy` for type checking (strict mode)
- Prefer `JSONDict`, `JSONValue` over `Dict[str, Any]`
- Use `TypedDict` for structured dictionaries
- Avoid `Any` types in public APIs

### Code Style

- Follow PEP 8
- Use `black` for formatting (line length: 100)
- Use `ruff` for linting
- Maximum line length: 100 characters

### Formatting

```bash
# Format code
black metamorphic_guard tests

# Lint code
ruff check metamorphic_guard tests

# Type check
mypy metamorphic_guard
```

### Error Handling

- Use specific exception types
- Provide helpful error messages
- Include context in error messages
- Use `from .errors import CustomError` for custom exceptions

### Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Include type hints in docstrings
- Document complex algorithms

Example:

```python
def compute_delta_ci(
    baseline_metrics: PassRateMetrics,
    candidate_metrics: PassRateMetrics,
    method: str = "bootstrap",
    alpha: float = 0.05,
    samples: int = 1000,
) -> Tuple[float, float]:
    """
    Compute confidence interval for pass rate difference.
    
    Args:
        baseline_metrics: Baseline pass rate metrics
        candidate_metrics: Candidate pass rate metrics
        method: CI method ("bootstrap", "newcombe", "bayesian")
        alpha: Significance level (default: 0.05)
        samples: Number of bootstrap samples
    
    Returns:
        Tuple of (lower_bound, upper_bound)
    
    Raises:
        ValueError: If method is invalid
    """
    ...
```

## Testing

### Test Structure

- Tests go in `tests/` directory
- Mirror the package structure
- Use descriptive test names: `test_function_name_scenario`

### Test Types

1. **Unit Tests**: Test individual functions/classes
2. **Integration Tests**: Test component interactions
3. **End-to-End Tests**: Test full evaluation workflows

### Writing Tests

```python
import pytest
from metamorphic_guard import run, TaskSpec, Implementation

def test_evaluation_accepts_candidate():
    """Test that evaluation accepts improved candidate."""
    task = TaskSpec(
        name="test_task",
        gen_inputs=lambda n, seed: [(i,) for i in range(n)],
        properties=[],
        relations=[],
        equivalence=lambda a, b: a == b,
    )
    
    result = run(
        task=task,
        baseline=Implementation.from_path("baseline.py"),
        candidate=Implementation.from_path("candidate.py"),
    )
    
    assert result.adopt is True
    assert result.reason == "meets_gate"
```

### Test Coverage

- Aim for >80% coverage
- Cover edge cases and error paths
- Test both success and failure scenarios

## Submitting Changes

### Workflow

1. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes**:
   - Write code following standards
   - Add tests
   - Update documentation
   - Run tests and linting

3. **Commit changes**:
   ```bash
   git add .
   git commit -m "feat: Add new feature"
   ```
   
   Commit message format:
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation
   - `test:` Tests
   - `refactor:` Code refactoring
   - `perf:` Performance improvement

4. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create Pull Request**:
   - Fill out PR template
   - Link related issues
   - Request review

### Pull Request Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Type checking passes (`mypy`)
- [ ] Documentation updated
- [ ] Changelog updated (if applicable)
- [ ] No merge conflicts

## Plugin Development

### Creating a Plugin

1. **Choose plugin type**:
   - Executor: Custom execution backend
   - Judge: Output evaluation logic
   - Mutant: Input transformation
   - Monitor: Observability/metrics

2. **Use scaffolding**:
   ```bash
   metamorphic-guard scaffold-plugin --kind monitor --name MyMonitor
   ```

3. **Implement interface**:
   ```python
   from metamorphic_guard.monitoring import Monitor, MonitorContext, MonitorRecord

   class MyMonitor(Monitor):
       def start(self, context: MonitorContext) -> None:
           ...
       
       def record(self, record: MonitorRecord) -> None:
           ...
       
       def finalize(self) -> Dict[str, Any]:
           ...
       
       @property
       def identifier(self) -> str:
           return "my_monitor"
   ```

4. **Register entry point** in `pyproject.toml`:
   ```toml
   [project.entry-points."metamorphic_guard.monitors"]
   my_monitor = "my_package:MyMonitor"
   ```

5. **Add tests**:
   ```python
   def test_my_monitor():
       monitor = MyMonitor()
       # Test implementation
   ```

### Plugin Best Practices

- Follow the interface contract
- Handle errors gracefully
- Document configuration options
- Include example usage
- Add tests

## Documentation

### Documentation Structure

- `docs/`: Main documentation
- `docs/api/`: API reference
- `docs/cookbook/`: Recipes and examples
- `docs/development/`: Developer guides

### Writing Documentation

1. Use Markdown
2. Include code examples
3. Add diagrams for complex concepts
4. Keep it up-to-date with code

### Building Documentation

```bash
# Install mkdocs
pip install mkdocs mkdocs-material

# Serve locally
mkdocs serve

# Build
mkdocs build
```

## Code Review Process

1. **Automated Checks**: CI runs tests, linting, type checking
2. **Review**: Maintainers review code
3. **Feedback**: Address review comments
4. **Approval**: After approval, maintainers merge

## Getting Help

- **Issues**: Open an issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Discord**: Join our Discord server (if available)

## Recognition

Contributors are recognized in:
- `CONTRIBUTORS.md`
- Release notes
- Project documentation

Thank you for contributing to Metamorphic Guard! 🎉

