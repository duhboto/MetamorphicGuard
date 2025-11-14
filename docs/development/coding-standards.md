# Coding Standards

## Type Safety
- Treat `mypy` strict errors as blockers.
- Prefer `JSONDict` / `JSONValue` from `metamorphic_guard.types` over `Dict[str, Any]`.
- Do not introduce untyped helper functions; annotate inputs and outputs explicitly.
- Avoid `Optional` defaults that are mutable; use `| None` with dataclasses or `Mapping`.

## Error Handling
- Replace bare `except Exception` with concrete exception classes (e.g. `OSError`, SDK-specific errors).
- Attach structured metadata (`error_code`, `error_type`) before bubbling up.
- Never swallow errors silently; log via `observability.log_event`.

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

