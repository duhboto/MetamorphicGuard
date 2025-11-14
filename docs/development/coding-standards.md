# Coding Standards

## Type Safety
- Treat `mypy` strict errors as blockers.
- Prefer `JSONDict`, `JSONList`, `JSONValue`, and queue-specific aliases over `Dict[str, Any]`.
- Centralize aliases in `metamorphic_guard.types` so downstream packages can reuse them.
- Do not introduce untyped helper functions; annotate inputs and outputs explicitly.
- Avoid `Optional` defaults that are mutable; use `| None` with dataclasses or `Mapping`.

## Error Handling
- Replace bare `except Exception` blocks with concrete exception classes (e.g. `OSError`, SDK-specific errors).
- For queue/workflow code, raise `QueueSerializationError` or convert third-party exceptions into an `ErrorContext`.
- Attach structured metadata (`error_code`, `error_type`, `details`) before bubbling up or emitting monitor events.
- Never swallow errors silently; log via `observability.log_event` or publish failed case records.

## Observability
- Every long-running task should emit:
  - `log_event("phase.start", ...)` / `log_event("phase.end", ...)`
  - Prometheus counters or gauges when metrics exist.
- Avoid printing directly; use structured logging.

## File Organization
- Keep modules below ~400 lines. If larger, split into `execution`, `manager`, `utils` style submodules.
- Use packages (`sandbox_workspace.py`, `queue_serialization.py`) for shared helpers.

## Contributions
- Run `pytest` and `mypy --strict`.
- Update documentation when touching user-facing CLI flags or APIs.
- Prefer dependency-free solutions; gate optional deps with informative errors.

