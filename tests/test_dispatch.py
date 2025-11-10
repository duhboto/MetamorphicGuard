import tempfile
import textwrap

from metamorphic_guard.dispatch_queue import QueueDispatcher


def dummy_run_case(index, args):
    data = {"success": True, "duration_ms": 1.0, "result": args[0]}
    return data


def test_queue_dispatcher_memory_backend():
    dispatcher = QueueDispatcher(
        workers=2,
        config={"backend": "memory", "spawn_local_workers": True, "lease_seconds": 0.5},
    )
    inputs = [(i,) for i in range(10)]

    results = dispatcher.execute(
        test_inputs=inputs,
        run_case=dummy_run_case,
        role="baseline",
        monitors=[],
        call_spec={"file_path": "dummy", "func_name": "solve"},
    )

    assert len(results) == len(inputs)
    assert all(result["success"] for result in results)
    assert [result["result"] for result in results] == list(range(10))

