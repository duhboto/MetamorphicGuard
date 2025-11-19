# Plugin Contracts

Metamorphic Guard uses a plugin system based on Python entry points to allow extension of core components. This document defines the contracts for implementing custom plugins.

## Executor Plugin

Executors run candidate implementations in a sandbox.

**Entry Point Group:** `metamorphic_guard.executors`

**Interface:**

Plugins must expose a class or factory that returns an object with an `execute` method.

```python
class MyExecutor:
    def __init__(self, config: dict[str, any] | None = None) -> None:
        self.config = config or {}

    def execute(
        self,
        file_path: str,
        func_name: str,
        args: tuple,
        timeout_s: float,
        mem_mb: int
    ) -> dict[str, any]:
        """
        Execute the function.
        
        Args:
            file_path: Path to the file containing the function (or content string for virtual/LLM)
            func_name: Name of the function to call
            args: Tuple of arguments to pass to the function
            timeout_s: Execution timeout in seconds
            mem_mb: Memory limit in MB (advisory)
            
        Returns:
            dict with keys:
            - success: bool
            - result: Any (return value of function if success)
            - error: str (error message if failure)
            - duration_ms: float
            - stdout: str
            - stderr: str
            - error_type: str (optional category)
            - error_code: str (optional code)
        """
```

**Virtual Implementations:**
For LLM or API-based executors, `file_path` may be a raw string (e.g. system prompt) instead of a file path. Executors should handle this gracefully or check if the path exists.

## Monitor Plugin

Monitors observe the stream of test results to calculate aggregate metrics (latency, fairness, cost).

**Entry Point Group:** `metamorphic_guard.monitors`

**Interface:**

Plugins must expose a class inheriting from `metamorphic_guard.monitoring.Monitor` or implementing the protocol:

```python
from metamorphic_guard.monitoring import Monitor, MonitorContext, MonitorRecord

class MyMonitor(Monitor):
    def __init__(self, my_param: int = 10):
        super().__init__()
        self.my_param = my_param

    def start(self, context: MonitorContext) -> None:
        """Called before evaluation starts."""
        pass

    def record(self, record: MonitorRecord) -> None:
        """
        Called for each test case result.
        
        record.role: "baseline" or "candidate"
        record.duration_ms: float
        record.success: bool
        record.result: dict (execution result payload)
        """
        pass

    def finalize(self) -> dict[str, any]:
        """
        Called after evaluation. Return a summary dict.
        Should include "alerts": list[dict] if any issues found.
        """
        return {
            "id": self.identifier(),
            "summary": {...},
            "alerts": [] 
        }
```

## Metadata

Plugins can expose `PLUGIN_METADATA` on their class/module:

```python
PLUGIN_METADATA = {
    "name": "My Custom Plugin",
    "version": "1.0.0",
    "sandbox": True  # Request running in a separate process (for Monitors)
}
```

## Versioning

- **Stable API:** `metamorphic_guard.api`, `metamorphic_guard.monitoring`, `metamorphic_guard.executors` base classes.
- **Experimental:** Modules under `metamorphic_guard.experimental` (if any) or those marked internal (`_`).

Plugins should pin dependencies on `metamorphic-guard` major versions to ensure compatibility.

