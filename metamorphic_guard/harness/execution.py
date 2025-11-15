"""
Execution logic for running test cases and managing execution plans.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from ..dispatch import Dispatcher, ensure_dispatcher
from ..monitoring import Monitor, MonitorContext
from ..observability import add_log_context, log_event
from ..sandbox import run_in_sandbox
from ..specs import Spec
from ..types import JSONDict


@dataclass
class ExecutionPlan:
    """Plan for executing an evaluation."""
    spec: Spec
    test_inputs: List[Tuple[object, ...]]
    dispatcher: Dispatcher
    monitors: List[Monitor]
    worker_count: int
    run_id: str

    @property
    def total_cases(self) -> int:
        return len(self.test_inputs)


def prepare_execution_plan(
    *,
    task_name: str,
    spec: Spec,
    n: int,
    seed: int,
    parallel: Optional[int],
    dispatcher: Dispatcher | str | None,
    queue_config: JSONDict | None,
    monitors: Sequence[Monitor] | None,
    explicit_inputs: Optional[List[Tuple[object, ...]]],
    executor: Optional[str],
) -> ExecutionPlan:
    """Prepare an execution plan for running evaluations."""
    if explicit_inputs is not None:
        test_inputs = [tuple(case) for case in explicit_inputs]
    else:
        test_inputs = spec.gen_inputs(n, seed)

    # Auto-detect optimal worker count if parallel is None
    if parallel is None:
        import os
        # Default to CPU count for I/O-bound tasks (sandbox execution is I/O-bound)
        cpu_count = os.cpu_count() or 4
        worker_count = max(1, cpu_count)
    else:
        worker_count = max(1, parallel)
    
    dispatcher_obj = ensure_dispatcher(dispatcher, worker_count, queue_config)

    monitor_objs = list(monitors or [])
    if monitor_objs:
        context = MonitorContext(task=task_name, total_cases=len(test_inputs))
        for monitor in monitor_objs:
            monitor.start(context)

    run_id = f"eval-{uuid.uuid4().hex}"
    add_log_context(run_id=run_id)
    log_event(
        "run_eval_start",
        task=task_name,
        total_cases=len(test_inputs),
        dispatcher=getattr(dispatcher_obj, "kind", "local"),
        executor=executor,
    )

    return ExecutionPlan(
        spec=spec,
        test_inputs=list(test_inputs),
        dispatcher=dispatcher_obj,
        monitors=monitor_objs,
        worker_count=worker_count,
        run_id=run_id,
    )


def execute_implementations(
    plan: ExecutionPlan,
    *,
    baseline_path: str,
    candidate_path: str,
    timeout_s: float,
    mem_mb: int,
    executor: Optional[str],
    executor_config: JSONDict | None,
    baseline_executor: Optional[str],
    baseline_executor_config: JSONDict | None,
    candidate_executor: Optional[str],
    candidate_executor_config: JSONDict | None,
) -> Tuple[List[JSONDict], List[JSONDict]]:
    """Execute baseline and candidate implementations."""
    def make_runner(
        file_path: str,
        role_executor: Optional[str],
        role_executor_config: JSONDict | None,
    ) -> Callable[[int, Tuple[object, ...]], JSONDict]:
        def _run_case(index: int, call_args: Tuple[object, ...]) -> JSONDict:
            return run_in_sandbox(
                file_path,
                "solve",
                call_args,
                timeout_s,
                mem_mb,
                executor=role_executor,
                executor_config=role_executor_config,
            )

        return _run_case

    dispatcher_obj = plan.dispatcher
    monitors = plan.monitors
    test_inputs = plan.test_inputs

    baseline_effective_executor = baseline_executor if baseline_executor is not None else executor
    baseline_effective_config = (
        baseline_executor_config if baseline_executor_config is not None else executor_config
    )
    candidate_effective_executor = (
        candidate_executor if candidate_executor is not None else executor
    )
    candidate_effective_config = (
        candidate_executor_config if candidate_executor_config is not None else executor_config
    )

    baseline_results = dispatcher_obj.execute(
        test_inputs=test_inputs,
        run_case=make_runner(
            baseline_path,
            baseline_effective_executor,
            baseline_effective_config,
        ),
        role="baseline",
        monitors=monitors,
        call_spec=build_call_spec(
            baseline_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=baseline_effective_executor,
            executor_config=baseline_effective_config,
        ),
    )
    candidate_results = dispatcher_obj.execute(
        test_inputs=test_inputs,
        run_case=make_runner(
            candidate_path,
            candidate_effective_executor,
            candidate_effective_config,
        ),
        role="candidate",
        monitors=monitors,
        call_spec=build_call_spec(
            candidate_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=candidate_effective_executor,
            executor_config=candidate_effective_config,
        ),
    )
    return baseline_results, candidate_results


def relation_rng(
    seed: int,
    case_index: int,
    relation_index: int,
    relation_name: str,
) -> random.Random:
    """
    Build a deterministic RNG for a relation invocation.

    The construction uses a stable hash so results are reproducible across Python
    invocations regardless of PYTHONHASHSEED.
    """
    payload = f"{seed}:{case_index}:{relation_index}:{relation_name}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    seed_int = int.from_bytes(digest[:8], "big")
    return random.Random(seed_int)


def relation_cache_key(relation_index: int, args: Tuple[object, ...]) -> str:
    """Build a stable cache key for relation reruns."""
    return f"{relation_index}:{repr(args)}"


def build_call_spec(
    file_path: str,
    *,
    timeout_s: float,
    mem_mb: int,
    executor: str | None,
    executor_config: JSONDict | None,
) -> JSONDict:
    """Build a call specification for sandbox execution."""
    spec: JSONDict = {
        "file_path": file_path,
        "func_name": "solve",
        "timeout_s": timeout_s,
        "mem_mb": mem_mb,
    }
    if executor is not None:
        spec["executor"] = executor
    if executor_config is not None:
        spec["executor_config"] = executor_config
    return spec

