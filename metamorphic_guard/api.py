"""
Public entry points for defining tasks and running evaluations.

This module provides a minimal, typed surface for downstream users.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import tempfile
import uuid
import warnings
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Hashable,
    Iterator,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypeVar,
    TypedDict,
    Union,
)

from .config import EvaluatorConfig, load_config
from .policy import PolicyLoadError, PolicyParseError, resolve_policy_option
from .notifications import collect_alerts, send_webhook_alerts
from .observability import configure_logging, configure_metrics, close_logging
from .types import JSONDict, JSONValue

from .harness import run_eval
from .dispatch import Dispatcher
from .monitoring import Monitor, resolve_monitors
from .specs import MetamorphicRelation, Metric, Property, Spec, register_spec, unregister_spec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TypedDict definitions for structured configurations
# ---------------------------------------------------------------------------


class PolicyConfig(TypedDict, total=False):
    """Type for policy configuration dictionaries."""

    gating: Dict[str, JSONValue]
    descriptor: Dict[str, JSONValue]
    name: str


class ExtraOptions(TypedDict, total=False):
    """Type for extra options in EvaluationConfig."""

    parallel: Optional[int]
    dispatcher: Optional[Union[str, JSONValue]]  # Dispatcher serialized as string or dict
    executor: Optional[str]
    executor_config: Optional[JSONDict]
    queue_config: Optional[JSONDict]
    monitors: Optional[JSONValue]  # Monitors serialized for TypedDict
    relation_correction: Optional[str]
    policy_version: Optional[str]
    policy_config: Optional[PolicyConfig]


class ObservabilityConfig(TypedDict, total=False):
    """Type for observability configuration."""

    logging_enabled: Optional[bool]
    log_path: Optional[Union[str, Path]]
    log_context: Optional[Mapping[str, JSONValue]]
    metrics_enabled: Optional[bool]
    metrics_port: Optional[int]
    metrics_host: Optional[str]


class QueueConfig(TypedDict, total=False):
    """Type for queue configuration."""

    backend: str
    url: Optional[str]
    heartbeat_timeout: Optional[float]
    enable_requeue: Optional[bool]

# ---------------------------------------------------------------------------
# Type variables for generic task specifications
T = TypeVar("T")  # Input/output type variable
OutputT = TypeVar("OutputT")  # Output type variable


class CallableImplementation(Protocol):
    """Protocol for callable implementations that can be validated."""

    __module__: str
    __qualname__: str

    def __call__(self, *args: object) -> object: ...


# ---------------------------------------------------------------------------
# User-facing dataclasses


@dataclass(frozen=True)
class TaskSpec:
    """
    User-facing task specification.

    Wraps the internal Spec with a stable name so callers can define
    metamorphic evaluation suites without consulting the registry API.
    """

    name: str
    gen_inputs: Callable[[int, int], List[Tuple[object, ...]]]
    properties: Sequence[Property]
    relations: Sequence[MetamorphicRelation]
    equivalence: Callable[[object, object], bool]
    fmt_in: Callable[[Tuple[object, ...]], str] = lambda args: str(args)
    fmt_out: Callable[[object], str] = lambda result: str(result)
    cluster_key: Optional[Callable[[Tuple[object, ...]], Hashable]] = None
    metrics: Sequence[Metric] = field(default_factory=tuple)

    def to_spec(self) -> Spec:
        """Convert to the internal Spec representation."""
        return Spec(
            gen_inputs=self.gen_inputs,
            properties=list(self.properties),
            relations=list(self.relations),
            equivalence=self.equivalence,
            fmt_in=self.fmt_in,
            fmt_out=self.fmt_out,
            cluster_key=self.cluster_key,
            metrics=list(self.metrics),
        )


@dataclass(frozen=True)
class Implementation:
    """
    Reference to a Python file that exposes a `solve` function.
    """

    path: Optional[str] = None
    func: Optional[CallableImplementation] = None

    def __post_init__(self) -> None:
        if (self.path is None) == (self.func is None):
            raise ValueError("Provide exactly one of 'path' or 'func' for Implementation.")
        if self.path is not None:
            # Normalize to string path
            object.__setattr__(self, "path", str(self.path))
        if self.func is not None:
            self._validate_callable(self.func)

    @classmethod
    def from_callable(cls, func: CallableImplementation) -> "Implementation":
        """Create an Implementation backed by a Python callable."""
        return cls(path=None, func=func)

    @classmethod
    def from_dotted(cls, dotted: str) -> "Implementation":
        """
        Construct an Implementation from a dotted path of the form 'module:callable'.

        The callable portion can include attribute access (e.g. 'pkg.mod:factory.create').
        """

        if ":" not in dotted:
            raise ValueError("Dotted path must be in the form 'module:callable'.")

        module_name, attr_path = dotted.split(":", 1)
        module_name = module_name.strip()
        attr_path = attr_path.strip()
        if not module_name or not attr_path:
            raise ValueError("Both module and callable must be provided in dotted path.")

        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise ValueError(f"Cannot import module '{module_name}'.") from exc

        target: object = module
        for part in attr_path.split("."):
            if not hasattr(target, part):
                raise ValueError(f"Attribute '{part}' not found while resolving '{dotted}'.")
            target = getattr(target, part)

        if not callable(target):
            raise ValueError(f"Resolved object '{dotted}' is not callable.")

        return cls.from_callable(target)

    @classmethod
    def from_specifier(cls, specifier: str) -> "Implementation":
        """
        Construct an Implementation from either a filesystem path or a dotted callable reference.
        """

        specifier = specifier.strip()
        if not specifier:
            raise ValueError("Implementation specifier cannot be empty.")

        path_candidate = Path(specifier)
        # On Windows drive letters include ':'. Treat absolute drives as file paths.
        is_windows_drive = bool(path_candidate.drive)
        if ":" in specifier and not is_windows_drive:
            try:
                return cls.from_dotted(specifier)
            except ValueError as exc:
                raise ValueError(f"Unable to resolve implementation specifier '{specifier}': {exc}") from exc

        return cls(path=str(path_candidate))

    @staticmethod
    def _validate_callable(func: CallableImplementation) -> None:
        module = getattr(func, "__module__", None)
        qualname = getattr(func, "__qualname__", None)
        if not module or not qualname:
            raise ValueError("Callable must have importable __module__ and __qualname__ attributes.")
        if "<locals>" in qualname:
            raise ValueError(
                "Callable implementations must be defined at module scope (no nested functions or lambdas)."
            )
        try:
            importlib.import_module(module)
        except ImportError as exc:
            raise ValueError(f"Cannot import module '{module}' for callable implementation.") from exc

    @contextmanager
    def materialize(self):
        """Yield a file path that exposes a `solve` function."""
        if self.path is not None:
            yield self.path
            return
        yield from self._materialize_callable()

    def _materialize_callable(self):
        assert self.func is not None  # for type-checkers

        module = self.func.__module__  # validated in __post_init__
        qualname = self.func.__qualname__
        parts = qualname.split(".")
        if any(part == "<locals>" for part in parts):
            raise ValueError("Callable implementations must be defined at module scope.")

        try:
            source_file = inspect.getfile(self.func)
        except (OSError, TypeError) as exc:
            raise ValueError("Callable implementations must originate from Python source files.") from exc

        root_dir = Path(source_file).resolve()
        for _ in range(len(module.split("."))):
            root_dir = root_dir.parent

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "callable_impl.py"
            attr_lines = ["    attr = module"]
            for part in parts:
                attr_lines.append(f"    attr = getattr(attr, {part!r})")
            attr_lines.append("    return attr")
            loader_body = "\n".join(attr_lines)
            source = (
                "from importlib import import_module\n"
                "import sys\n\n"
                f"def _load():\n"
                f"    search_path = {str(root_dir)!r}\n"
                "    if search_path not in sys.path:\n"
                "        sys.path.insert(0, search_path)\n"
                f"    module = import_module({module!r})\n"
                f"{loader_body}\n\n"
                "_FUNC = _load()\n\n"
                "def solve(*args, **kwargs):\n"
                "    return _FUNC(*args, **kwargs)\n"
            )
            path.write_text(source, encoding="utf-8")
            yield str(path)


@dataclass(init=False)
class EvaluationConfig:
    """
    Configuration knobs forwarded to the evaluation harness.

    The defaults match the CLI behavior.
    """

    n: int = 400
    seed: int = 42
    timeout_s: float = 2.0
    mem_mb: int = 512
    alpha: float = 0.05
    violation_cap: int = 25
    min_delta: float = 0.02
    bootstrap_samples: int = 1000
    ci_method: str = "bootstrap"
    rr_ci_method: str = "log"
    min_pass_rate: float = 0.80
    power_target: float = 0.8
    failed_artifact_limit: Optional[int] = None
    failed_artifact_ttl_days: Optional[int] = None
    sequential_method: str = "none"
    max_looks: int = 1
    look_number: int = 1
    relation_correction: Optional[str] = None
    policy_version: Optional[str] = None
    policy_config: Optional[PolicyConfig] = None

    # Flexible extension point for advanced options not yet surfaced above.
    # Note: Using Dict[str, JSONValue] instead of ExtraOptions because TypedDict
    # doesn't work well with dataclass fields that are mutated at runtime.
    extra_options: Dict[str, JSONValue] = field(default_factory=dict)

    def __init__(
        self,
        n: int = 400,
        seed: int = 42,
        timeout_s: float = 2.0,
        mem_mb: int = 512,
        alpha: float = 0.05,
        violation_cap: int = 25,
        min_delta: Optional[float] = None,
        *,
        improve_delta: Optional[float] = None,
        bootstrap_samples: int = 1000,
        ci_method: str = "bootstrap",
        rr_ci_method: str = "log",
        min_pass_rate: float = 0.80,
        power_target: float = 0.8,
        failed_artifact_limit: Optional[int] = None,
        failed_artifact_ttl_days: Optional[int] = None,
        sequential_method: str = "none",
        max_looks: int = 1,
        look_number: int = 1,
        relation_correction: Optional[str] = None,
        policy_version: Optional[str] = None,
        policy_config: Optional[PolicyConfig] = None,
        extra_options: Optional[Dict[str, JSONValue]] = None,
    ) -> None:
        if improve_delta is not None:
            warnings.warn(
                "EvaluationConfig(improve_delta=...) is deprecated; use min_delta instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        if min_delta is None and improve_delta is not None:
            resolved_min_delta = float(improve_delta)
        elif min_delta is not None:
            resolved_min_delta = float(min_delta)
            if improve_delta is not None and float(improve_delta) != resolved_min_delta:
                warnings.warn(
                    "Both min_delta and improve_delta were provided; ignoring improve_delta.",
                    DeprecationWarning,
                    stacklevel=2,
                )
        else:
            resolved_min_delta = 0.02

        self.n = int(n)
        self.seed = int(seed)
        self.timeout_s = float(timeout_s)
        self.mem_mb = int(mem_mb)
        self.alpha = float(alpha)
        self.violation_cap = int(violation_cap)
        self.min_delta = float(resolved_min_delta)
        self.bootstrap_samples = int(bootstrap_samples)
        self.ci_method = str(ci_method)
        self.rr_ci_method = str(rr_ci_method)
        self.min_pass_rate = float(min_pass_rate)
        self.power_target = float(power_target)
        self.failed_artifact_limit = failed_artifact_limit
        self.failed_artifact_ttl_days = failed_artifact_ttl_days
        self.sequential_method = sequential_method
        self.max_looks = int(max_looks)
        self.look_number = int(look_number)
        self.relation_correction = relation_correction
        self.policy_version = policy_version
        self.policy_config = dict(policy_config) if policy_config is not None else None
        self.extra_options = dict(extra_options) if extra_options else {}

    def to_kwargs(self) -> Dict[str, JSONValue]:
        """Render keyword arguments for the harness without deep-copying extras."""

        payload: Dict[str, JSONValue] = {
            "n": self.n,
            "seed": self.seed,
            "timeout_s": self.timeout_s,
            "mem_mb": self.mem_mb,
            "alpha": self.alpha,
            "violation_cap": self.violation_cap,
            "parallel": None,
            "min_delta": self.min_delta,
            "bootstrap_samples": self.bootstrap_samples,
            "ci_method": self.ci_method,
            "rr_ci_method": self.rr_ci_method,
            "executor": None,
            "executor_config": None,
            "dispatcher": None,
            "queue_config": None,
            "monitors": None,
            "failed_artifact_limit": self.failed_artifact_limit,
            "failed_artifact_ttl_days": self.failed_artifact_ttl_days,
            "policy_version": self.policy_version,
            "min_pass_rate": self.min_pass_rate,
            "power_target": self.power_target,
            "sequential_method": self.sequential_method,
            "max_looks": self.max_looks,
            "look_number": self.look_number,
            "relation_correction": self.relation_correction,
            "policy_config": self.policy_config,
        }

        extras = self.extra_options or {}
        payload.update(extras)

        # Remove any keys that remain None so run_eval uses its defaults.
        return {k: v for k, v in payload.items() if v is not None}


@dataclass
class EvaluationResult:
    """Wrapper over the harness response."""

    report: JSONDict

    @property
    def adopt(self) -> bool:
        decision = self.report.get("decision") or {}
        return bool(decision.get("adopt"))

    @property
    def reason(self) -> str:
        decision = self.report.get("decision") or {}
        return decision.get("reason", "")

    def to_json(self, path: str, *, indent: int = 2) -> None:
        """Serialize the full report to disk."""
        import json

        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.report, handle, indent=indent, sort_keys=True)


# ---------------------------------------------------------------------------
# Execution helpers


@contextmanager
def _registered_spec(spec: TaskSpec):
    """
    Temporarily register a TaskSpec under its name.

    If the name already exists we create a unique temporary namespace instead.
    """

    target_name = spec.name
    temp_name: Optional[str] = None

    if target_name in _existing_specs():
        temp_name = f"{target_name}__{uuid.uuid4().hex}"
        target_name = temp_name

    internal_spec = spec.to_spec()
    register_spec(target_name, internal_spec, overwrite=True)

    try:
        yield target_name
    finally:
        unregister_spec(target_name)


def _existing_specs() -> Sequence[str]:
    from .specs import list_tasks

    return list_tasks()


def resolve_monitor_specs(
    monitor_specs: Sequence[str],
    *,
    sandbox_plugins: Optional[bool] = None,
) -> List[Monitor]:
    """
    Instantiate monitors using CLI-style specifications.

    Args:
        monitor_specs: Sequence such as ["latency:percentile=0.99"].
        sandbox_plugins: When True (default), plugin monitors run in a sandbox.
    """

    if not monitor_specs:
        return []

    should_sandbox = True if sandbox_plugins is None else bool(sandbox_plugins)
    return resolve_monitors(monitor_specs, sandbox_plugins=should_sandbox)


@contextmanager
def _observability_context(
    *,
    logging_enabled: Optional[bool] = None,
    log_path: Optional[str | Path] = None,
    log_context: Optional[Mapping[str, JSONValue]] = None,
    metrics_enabled: Optional[bool] = None,
    metrics_port: Optional[int] = None,
    metrics_host: Optional[str] = None,
) -> Iterator[None]:
    """Configure logging/metrics similarly to the CLI, then restore state."""

    configure_logging(
        enabled=logging_enabled,
        path=log_path,
        context=dict(log_context) if log_context else None,
    )

    metrics_host = metrics_host or "0.0.0.0"
    if metrics_enabled or metrics_port is not None:
        configure_metrics(
            enabled=metrics_enabled if metrics_enabled is not None else True,
            port=metrics_port,
            host=metrics_host,
        )
    elif metrics_enabled is not None:
        configure_metrics(enabled=metrics_enabled)

    try:
        yield
    finally:
        try:
            close_logging()
        except Exception:  # pragma: no cover - defensive logging cleanup
            logger.exception("Failed to close logging")


def _dispatch_alerts(
    result: JSONDict,
    alert_webhooks: Optional[Sequence[str]],
    alert_metadata: Optional[Mapping[str, JSONValue]] = None,
) -> None:
    if not alert_webhooks:
        return

    try:
        alerts = collect_alerts(result.get("monitors", {}))
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to collect monitor alerts")
        return

    if not alerts:
        return

    metadata: Dict[str, JSONValue] = {
        "task": result.get("task"),
        "decision": result.get("decision"),
        "run_id": (result.get("job_metadata") or {}).get("run_id"),
        "policy_version": (result.get("config") or {}).get("policy_version"),
    }
    if alert_metadata:
        metadata.update(alert_metadata)

    try:
        send_webhook_alerts(alerts, alert_webhooks, metadata=metadata)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to dispatch alert webhooks")


def _compose_monitors(
    *,
    monitors: Optional[Sequence[Monitor]],
    monitor_specs: Optional[Sequence[str]],
    config_monitor_specs: Optional[Sequence[str]],
    sandbox_plugins: Optional[bool],
    config_sandbox_plugins: Optional[bool],
) -> Optional[List[Monitor]]:
    resolved: List[Monitor] = []

    if monitors:
        resolved.extend(monitors)

    specs: List[str] = []
    if config_monitor_specs:
        specs.extend(config_monitor_specs)
    if monitor_specs:
        specs.extend(monitor_specs)

    if specs:
        effective_sandbox = (
            sandbox_plugins
            if sandbox_plugins is not None
            else (config_sandbox_plugins if config_sandbox_plugins is not None else True)
        )
        resolved.extend(resolve_monitor_specs(specs, sandbox_plugins=effective_sandbox))

    return resolved or None


def _evaluation_config_from_evaluator(
    cfg: EvaluatorConfig,
) -> Tuple[EvaluationConfig, ObservabilityConfig, List[str], Optional[bool]]:
    extra_options: Dict[str, JSONValue] = {}
    min_delta = cfg.min_delta
    alpha = cfg.alpha
    min_pass_rate = cfg.min_pass_rate
    violation_cap = cfg.violation_cap
    power_target = cfg.power_target
    policy_version_value = cfg.policy_version

    if cfg.parallel:
        extra_options["parallel"] = cfg.parallel
    if cfg.relation_correction:
        extra_options["relation_correction"] = cfg.relation_correction
    if cfg.dispatcher:
        extra_options["dispatcher"] = cfg.dispatcher
    if cfg.queue is not None:
        extra_options["queue_config"] = cfg.queue.model_dump(exclude_none=True)
    if cfg.executor:
        extra_options["executor"] = cfg.executor
    if cfg.executor_config is not None:
        extra_options["executor_config"] = cfg.executor_config

    observability: ObservabilityConfig = {
        "logging_enabled": cfg.log_json,
        "log_path": cfg.log_file,
        "log_context": None,
        "metrics_enabled": cfg.metrics_enabled,
        "metrics_port": cfg.metrics_port,
        "metrics_host": cfg.metrics_host,
    }

    monitor_specs = list(cfg.monitors) if cfg.monitors else []

    if cfg.policy:
        try:
            policy_payload = resolve_policy_option(str(cfg.policy))
        except (PolicyLoadError, PolicyParseError) as exc:
            raise ValueError(f"Invalid policy configuration: {exc}") from exc

        extra_options["policy_config"] = policy_payload

        gating = policy_payload.get("gating", {})
        if "min_delta" in gating:
            min_delta = float(gating["min_delta"])
        if "min_pass_rate" in gating:
            min_pass_rate = float(gating["min_pass_rate"])
        if "alpha" in gating:
            alpha = float(gating["alpha"])
        if "power_target" in gating:
            power_target = float(gating["power_target"])
        if "violation_cap" in gating:
            violation_cap = int(gating["violation_cap"])

        if policy_version_value is None:
            descriptor = policy_payload.get("descriptor", {})
            if isinstance(descriptor, dict):
                candidate_version = (
                    descriptor.get("name")
                    or descriptor.get("label")
                    or policy_payload.get("name")
                )
                if isinstance(candidate_version, str) and candidate_version:
                    policy_version_value = candidate_version

    if policy_version_value:
        extra_options["policy_version"] = policy_version_value

    # Drop empty entries from extras
    extra_options = {k: v for k, v in extra_options.items() if v not in (None, [], {})}

    evaluation_cfg = EvaluationConfig(
        n=cfg.n,
        seed=cfg.seed,
        timeout_s=cfg.timeout_s,
        mem_mb=cfg.mem_mb,
        alpha=alpha,
        violation_cap=violation_cap,
        min_delta=min_delta,
        bootstrap_samples=cfg.bootstrap_samples,
        ci_method=cfg.ci_method,
        rr_ci_method=cfg.rr_ci_method,
        min_pass_rate=min_pass_rate,
        power_target=power_target,
        failed_artifact_limit=cfg.failed_artifact_limit,
        failed_artifact_ttl_days=cfg.failed_artifact_ttl_days,
        extra_options=extra_options,
    )

    return evaluation_cfg, observability, monitor_specs, cfg.sandbox_plugins


def run(
    task: TaskSpec,
    baseline: Implementation,
    candidate: Implementation,
    config: Optional[EvaluationConfig] = None,
    *,
    alert_webhooks: Optional[Sequence[str]] = None,
    alert_metadata: Optional[Mapping[str, JSONValue]] = None,
    dispatcher: Optional[Union[str, Dispatcher]] = None,
    queue_config: Optional[QueueConfig] = None,
    monitors: Optional[Sequence[Monitor]] = None,
    monitor_specs: Optional[Sequence[str]] = None,
    sandbox_plugins: Optional[bool] = None,
    logging_enabled: Optional[bool] = None,
    log_path: Optional[str | Path] = None,
    log_context: Optional[Mapping[str, JSONValue]] = None,
    metrics_enabled: Optional[bool] = None,
    metrics_port: Optional[int] = None,
    metrics_host: Optional[str] = None,
) -> EvaluationResult:
    """
    Execute baseline vs candidate under the provided task.
    """

    cfg = config or EvaluationConfig()
    extra_options = dict(cfg.extra_options)
    if dispatcher is not None:
        extra_options["dispatcher"] = dispatcher
    if queue_config is not None:
        extra_options["queue_config"] = dict(queue_config)

    final_monitors = _compose_monitors(
        monitors=monitors,
        monitor_specs=monitor_specs,
        config_monitor_specs=None,
        sandbox_plugins=sandbox_plugins,
        config_sandbox_plugins=None,
    )
    if final_monitors is not None:
        extra_options["monitors"] = final_monitors
    else:
        extra_options.pop("monitors", None)

    cfg = replace(cfg, extra_options=extra_options)

    # Security warning for local executor when evaluating potentially untrusted code.
    try:
        import os as _os  # local import to avoid polluting module namespace
        suppress = _os.environ.get("METAMORPHIC_GUARD_SUPPRESS_SECURITY_WARNING") == "1"
    except Exception:
        suppress = False
    try:
        executor_value = extra_options.get("executor") if extra_options is not None else None
    except Exception:
        executor_value = None
    if not suppress and (executor_value is None or str(executor_value).strip().lower() == "local"):
        logger.warning(
            "Running with executor=local. This isolation is not sufficient for untrusted code. "
            "Use the Docker executor for stronger isolation: --executor docker "
            "--executor-config '{\"image\":\"python:3.11-slim\",\"read_only\":true,\"cap_drop\":[\"ALL\"],"
            "\"tmpfs\":[\"/tmp\"],\"security_opt\":[\"no-new-privileges:true\"]}'. "
            "To silence this warning, set METAMORPHIC_GUARD_SUPPRESS_SECURITY_WARNING=1."
        )

    with _observability_context(
        logging_enabled=logging_enabled,
        log_path=log_path,
        log_context=log_context,
        metrics_enabled=metrics_enabled,
        metrics_port=metrics_port,
        metrics_host=metrics_host,
    ):
        with _registered_spec(task) as task_name, ExitStack() as stack:
            baseline_path = stack.enter_context(baseline.materialize())
            candidate_path = stack.enter_context(candidate.materialize())
            kwargs = cfg.to_kwargs()
            report = run_eval(
                task_name=task_name,
                baseline_path=baseline_path,
                candidate_path=candidate_path,
                **kwargs,
            )

    # Attach a lightweight replay hint to the report for UX.
    try:
        replay_args = [
            "metamorphic-guard",
            "evaluate",
            "--task",
            task.name,
            "--baseline",
            str(baseline_path),
            "--candidate",
            str(candidate_path),
            "--n",
            str(cfg.n),
            "--seed",
            str(cfg.seed),
            "--ci-method",
            cfg.ci_method,
        ]
        # Only include min_delta if non-default to reduce noise
        if cfg.min_delta != 0.02:
            replay_args += ["--min-delta", str(cfg.min_delta)]
        if cfg.policy_version:
            replay_args += ["--policy-version", str(cfg.policy_version)]
        report.setdefault("replay", {})["cli"] = " ".join(replay_args)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to attach replay command to report")

    _dispatch_alerts(report, alert_webhooks, alert_metadata)

    return EvaluationResult(report=report)


def run_with_config(
    config: Union[EvaluatorConfig, str, Path, Mapping[str, JSONValue]],
    *,
    task: TaskSpec,
    alert_webhooks: Optional[Sequence[str]] = None,
    alert_metadata: Optional[Mapping[str, JSONValue]] = None,
    dispatcher: Optional[Union[str, Dispatcher]] = None,
    queue_config: Optional[QueueConfig] = None,
    monitors: Optional[Sequence[Monitor]] = None,
    monitor_specs: Optional[Sequence[str]] = None,
    sandbox_plugins: Optional[bool] = None,
    logging_enabled: Optional[bool] = None,
    log_path: Optional[str | Path] = None,
    log_context: Optional[Mapping[str, JSONValue]] = None,
    metrics_enabled: Optional[bool] = None,
    metrics_port: Optional[int] = None,
    metrics_host: Optional[str] = None,
) -> EvaluationResult:
    """
    Execute an evaluation described by a TOML configuration file.

    Args:
        config: EvaluatorConfig object or path to a TOML file.
        task: Task specification corresponding to the config's task entry.
    """

    if not isinstance(config, EvaluatorConfig):
        if isinstance(config, Mapping):
            data = dict(config)
            block = data.get("metamorphic_guard", data)
            config = EvaluatorConfig.model_validate(block)
        else:
            config = load_config(Path(config))

    if config.task != task.name:
        raise ValueError(
            f"Configuration task '{config.task}' does not match provided TaskSpec name '{task.name}'."
        )

    baseline_impl = Implementation.from_specifier(config.baseline)
    candidate_impl = Implementation.from_specifier(config.candidate)
    eval_cfg, observability, config_monitor_specs, config_sandbox_plugins = _evaluation_config_from_evaluator(config)

    if logging_enabled is not None:
        observability["logging_enabled"] = logging_enabled
    if log_path is not None:
        observability["log_path"] = log_path
    if log_context is not None:
        observability["log_context"] = log_context
    if metrics_enabled is not None:
        observability["metrics_enabled"] = metrics_enabled
    if metrics_port is not None:
        observability["metrics_port"] = metrics_port
    if metrics_host is not None:
        observability["metrics_host"] = metrics_host

    extra_options = dict(eval_cfg.extra_options)
    if dispatcher is not None:
        extra_options["dispatcher"] = dispatcher
    if queue_config is not None:
        extra_options["queue_config"] = dict(queue_config)

    final_monitors = _compose_monitors(
        monitors=monitors,
        monitor_specs=monitor_specs,
        config_monitor_specs=config_monitor_specs,
        sandbox_plugins=sandbox_plugins,
        config_sandbox_plugins=config_sandbox_plugins,
    )
    if final_monitors is not None:
        extra_options["monitors"] = final_monitors
    else:
        extra_options.pop("monitors", None)

    eval_cfg = replace(eval_cfg, extra_options=extra_options)

    return run(
        task=task,
        baseline=baseline_impl,
        candidate=candidate_impl,
        config=eval_cfg,
        alert_webhooks=alert_webhooks,
        alert_metadata=alert_metadata,
        dispatcher=dispatcher,
        queue_config=queue_config,
        monitors=final_monitors,
        monitor_specs=None,
        sandbox_plugins=sandbox_plugins
        if sandbox_plugins is not None
        else config_sandbox_plugins,
        **observability,
    )


__all__ = [
    "TaskSpec",
    "Implementation",
    "EvaluationConfig",
    "EvaluationResult",
    "run",
    "run_with_config",
    "resolve_monitor_specs",
    "Property",
    "MetamorphicRelation",
    "Metric",
]

