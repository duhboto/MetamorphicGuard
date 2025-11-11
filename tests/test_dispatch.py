import tempfile
import textwrap
import threading
import time

from metamorphic_guard.dispatch_queue import (
    InMemoryQueueAdapter,
    QueueDispatcher,
    _Result,
    _decode_args,
    _prepare_payload,
)


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


def test_prepare_payload_adaptive_compression_small_payload():
    payload, compressed, raw_len, encoded_len = _prepare_payload(
        [(1,)],
        compress_default=True,
        adaptive=True,
        threshold_bytes=1024,
    )

    assert not compressed
    assert raw_len < encoded_len or raw_len == encoded_len
    assert payload


def test_prepare_payload_large_payload_prefers_compression():
    large_args = [(list(range(200)),)]
    payload, compressed, raw_len, encoded_len = _prepare_payload(
        large_args,
        compress_default=True,
        adaptive=True,
        threshold_bytes=64,
    )

    assert compressed is True
    assert encoded_len > 0


def test_queue_requeues_stalled_worker(monkeypatch):
    adapter = InMemoryQueueAdapter()

    requeue_counts: list[int] = []

    def _record_requeue(count: int = 1) -> None:
        requeue_counts.append(count)

    monkeypatch.setattr(
        "metamorphic_guard.dispatch_queue.increment_queue_requeued",
        _record_requeue,
    )

    dispatcher = QueueDispatcher(
        workers=1,
        config={
            "backend": "memory",
            "spawn_local_workers": False,
            "lease_seconds": 0.1,
            "heartbeat_timeout": 0.05,
            "batch_size": 1,
            "adaptive_batching": False,
            "result_poll_timeout": 0.01,
            "metrics_interval": 0.02,
        },
    )
    dispatcher.adapter = adapter

    inputs = [(value,) for value in range(2)]

    def run_case(case_index, args):
        return {"success": True, "result": args[0], "duration_ms": 5.0}

    stall_claimed = threading.Event()

    def stalled_worker() -> None:
        adapter.register_worker("stall")
        task = adapter.consume_task("stall", timeout=1.0)
        if not task or task.job_id == "__shutdown__":
            return
        stall_claimed.set()
        time.sleep(0.25)

    stop_event = threading.Event()

    def finisher_worker() -> None:
        stall_claimed.wait()
        adapter.register_worker("finisher")
        while not stop_event.is_set():
            task = adapter.consume_task("finisher", timeout=0.05)
            if task is None:
                continue
            if task.job_id == "__shutdown__":
                break
            args_list = _decode_args(task.payload, compress=task.compressed)
            for case_index, args in zip(task.case_indices, args_list):
                result = {"success": True, "result": args[0], "duration_ms": 8.0}
                adapter.publish_result(
                    _Result(
                        job_id=task.job_id,
                        task_id=task.task_id,
                        case_index=case_index,
                        role=task.role,
                        result=result,
                    )
                )

    stall_thread = threading.Thread(target=stalled_worker)
    finisher_thread = threading.Thread(target=finisher_worker, daemon=True)

    stall_thread.start()
    finisher_thread.start()

    results = dispatcher.execute(
        test_inputs=inputs,
        run_case=run_case,
        role="baseline",
        monitors=[],
        call_spec=None,
    )

    stop_event.set()
    adapter.signal_shutdown()
    stall_thread.join(timeout=1.0)
    finisher_thread.join(timeout=1.0)

    assert stall_claimed.is_set(), "stall worker failed to claim a task"
    assert [result["result"] for result in results] == [0, 1]
    assert sum(requeue_counts) >= 1

