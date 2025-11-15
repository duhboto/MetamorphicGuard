# Pytest Integration

Integrate Metamorphic Guard with pytest for seamless testing workflows.

## Installation

```bash
pip install metamorphic-guard pytest
```

## Basic Usage

### Using pytest-metamorphic Plugin

The `pytest_metamorphic` plugin provides pytest fixtures and markers:

```python
import pytest
from metamorphic_guard import TaskSpec, Property

@pytest.fixture
def my_task_spec():
    return TaskSpec(
        name="my_task",
        gen_inputs=lambda n, seed: [(i,) for i in range(n)],
        properties=[
            Property(
                check=lambda out, x: out > 0,
                description="Output is positive"
            )
        ],
        relations=[],
        equivalence=lambda a, b: a == b,
    )

def test_baseline_vs_candidate(my_task_spec):
    """Test baseline vs candidate using Metamorphic Guard."""
    from metamorphic_guard import run, Implementation
    
    result = run(
        task=my_task_spec,
        baseline=Implementation.from_path("baseline.py"),
        candidate=Implementation.from_path("candidate.py"),
        config={"n": 100},
    )
    
    assert result.adopt, f"Candidate rejected: {result.reason}"
```

### Pytest Markers

Use markers to configure evaluations:

```python
import pytest
from metamorphic_guard import run, TaskSpec, Implementation

@pytest.mark.metamorphic(
    task="my_task",
    baseline="baseline.py",
    candidate="candidate.py",
    n=400,
    min_delta=0.02,
)
def test_improvement():
    """Automatically run Metamorphic Guard evaluation."""
    # Test body is optional - evaluation runs automatically
    pass
```

### Fixtures

#### `metamorphic_config`

Access evaluation configuration:

```python
def test_with_config(metamorphic_config):
    """Use configuration from pytest.ini or conftest.py."""
    assert metamorphic_config["n"] == 400
    assert metamorphic_config["min_delta"] == 0.02
```

#### `metamorphic_result`

Access evaluation result:

```python
@pytest.mark.metamorphic(task="my_task", baseline="baseline.py", candidate="candidate.py")
def test_result(metamorphic_result):
    """Access evaluation result."""
    assert metamorphic_result.adopt
    assert metamorphic_result.report["delta_pass_rate"] > 0.02
```

## Configuration

### pytest.ini

```ini
[pytest]
metamorphic_task = my_task
metamorphic_baseline = baseline.py
metamorphic_candidate = candidate.py
metamorphic_n = 400
metamorphic_min_delta = 0.02
metamorphic_min_pass_rate = 0.80
```

### conftest.py

```python
import pytest

@pytest.fixture(scope="session")
def metamorphic_config():
    """Configure Metamorphic Guard for all tests."""
    return {
        "n": 400,
        "min_delta": 0.02,
        "min_pass_rate": 0.80,
        "alpha": 0.05,
    }
```

## Advanced Usage

### Parameterized Tests

```python
import pytest

@pytest.mark.parametrize("n,min_delta", [
    (100, 0.01),
    (400, 0.02),
    (1000, 0.03),
])
def test_multiple_configs(n, min_delta):
    """Test with different configurations."""
    from metamorphic_guard import run, TaskSpec, Implementation
    
    result = run(
        task=my_task_spec,
        baseline=Implementation.from_path("baseline.py"),
        candidate=Implementation.from_path("candidate.py"),
        config={"n": n, "min_delta": min_delta},
    )
    
    assert result.adopt
```

### Custom Test Functions

```python
def test_custom_evaluation():
    """Custom evaluation with full control."""
    from metamorphic_guard import run_eval
    
    result = run_eval(
        task_name="my_task",
        baseline_path="baseline.py",
        candidate_path="candidate.py",
        n=1000,
        parallel=4,
        dispatcher="local",
    )
    
    assert result["decision"]["adopt"]
    assert result["delta_pass_rate"] > 0.02
```

## Running Tests

### Run All Metamorphic Tests

```bash
pytest -m metamorphic
```

### Run Specific Test

```bash
pytest tests/test_my_feature.py::test_baseline_vs_candidate
```

### With Coverage

```bash
pytest --cov=metamorphic_guard --cov-report=html
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest
      - run: pytest --junitxml=reports/junit.xml
      - uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: reports/
```

## Best Practices

1. **Separate Test Files**: Keep Metamorphic Guard tests in separate files
2. **Use Fixtures**: Share task specs and configs via fixtures
3. **Mark Tests**: Use `@pytest.mark.metamorphic` for clarity
4. **Parallel Execution**: Use `pytest-xdist` for parallel test execution
5. **Report Generation**: Generate HTML reports for CI artifacts

## Examples

See `tests/` directory for complete examples:
- `tests/test_integration.py`: Full integration examples
- `tests/test_api.py`: API usage examples

## Troubleshooting

### Import Errors

```python
# Ensure pytest-metamorphic is installed
pip install pytest-metamorphic
```

### Configuration Not Found

```python
# Check pytest.ini or conftest.py
# Ensure markers are registered
```

### Test Failures

```python
# Check evaluation results
# Use --verbose for detailed output
pytest -v
```

