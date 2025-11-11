"""OpenTelemetry integration for Metamorphic Guard."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.instrumentation import context
    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False
    trace = None  # type: ignore
    OTLPSpanExporter = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    Resource = None  # type: ignore


_telemetry_enabled = False
_tracer = None


def configure_telemetry(
    endpoint: Optional[str] = None,
    service_name: str = "metamorphic-guard",
    service_version: Optional[str] = None,
    enabled: bool = True,
) -> bool:
    """
    Configure OpenTelemetry tracing.
    
    Args:
        endpoint: OTLP endpoint URL (e.g., "http://localhost:4317")
        service_name: Service name for traces
        service_version: Service version
        enabled: Whether to enable telemetry
        
    Returns:
        True if telemetry was successfully configured, False otherwise
    """
    global _telemetry_enabled, _tracer
    
    if not OTLP_AVAILABLE:
        return False
    
    if not enabled or not endpoint:
        _telemetry_enabled = False
        _tracer = None
        return False
    
    try:
        # Create resource
        resource_attrs = {
            "service.name": service_name,
        }
        if service_version:
            resource_attrs["service.version"] = service_version
        
        resource = Resource.create(resource_attrs)
        
        # Create tracer provider
        provider = TracerProvider(resource=resource)
        
        # Create OTLP exporter
        exporter = OTLPSpanExporter(endpoint=endpoint)
        
        # Add span processor
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        
        # Set global tracer provider
        trace.set_tracer_provider(provider)
        
        # Get tracer
        _tracer = trace.get_tracer(__name__)
        _telemetry_enabled = True
        
        return True
    except Exception:
        _telemetry_enabled = False
        _tracer = None
        return False


def is_telemetry_enabled() -> bool:
    """Check if telemetry is enabled."""
    return _telemetry_enabled and _tracer is not None


def trace_evaluation(
    task_name: str,
    baseline_path: str,
    candidate_path: str,
    n: int,
    result: Dict[str, Any],
) -> None:
    """
    Export evaluation trace to OpenTelemetry.
    
    Args:
        task_name: Task name
        baseline_path: Baseline file path
        candidate_path: Candidate file path
        n: Number of test cases
        result: Evaluation result dictionary
    """
    if not is_telemetry_enabled():
        return
    
    try:
        with _tracer.start_as_current_span("metamorphic_guard.evaluation") as span:
            # Set attributes
            span.set_attribute("task.name", task_name)
            span.set_attribute("baseline.path", baseline_path)
            span.set_attribute("candidate.path", candidate_path)
            span.set_attribute("test_cases.n", n)
            
            # Decision attributes
            decision = result.get("decision", {})
            span.set_attribute("decision.adopt", decision.get("adopt", False))
            span.set_attribute("decision.reason", decision.get("reason", "unknown"))
            
            # Metrics
            baseline = result.get("baseline", {})
            candidate = result.get("candidate", {})
            span.set_attribute("baseline.pass_rate", baseline.get("pass_rate", 0.0))
            span.set_attribute("candidate.pass_rate", candidate.get("pass_rate", 0.0))
            span.set_attribute("delta_pass_rate", result.get("delta_pass_rate", 0.0))
            
            # LLM metrics if available
            llm_metrics = result.get("llm_metrics", {})
            if llm_metrics:
                baseline_metrics = llm_metrics.get("baseline", {})
                candidate_metrics = llm_metrics.get("candidate", {})
                span.set_attribute("llm.baseline.cost_usd", baseline_metrics.get("total_cost_usd", 0.0))
                span.set_attribute("llm.candidate.cost_usd", candidate_metrics.get("total_cost_usd", 0.0))
                span.set_attribute("llm.cost_delta_usd", llm_metrics.get("cost_delta_usd", 0.0))
                span.set_attribute("llm.cost_ratio", llm_metrics.get("cost_ratio", 1.0))
            
            # Trust scores if available
            trust_scores = result.get("trust_scores", {})
            if trust_scores:
                baseline_trust = trust_scores.get("baseline", {})
                candidate_trust = trust_scores.get("candidate", {})
                if baseline_trust:
                    span.set_attribute("trust.baseline.score", baseline_trust.get("score", 0.0))
                if candidate_trust:
                    span.set_attribute("trust.candidate.score", candidate_trust.get("score", 0.0))
            
            # Duration
            job_metadata = result.get("job_metadata", {})
            duration = job_metadata.get("duration_seconds")
            if duration:
                span.set_attribute("duration_seconds", duration)
            
            # Status
            if decision.get("adopt", False):
                span.set_status(trace.Status(trace.StatusCode.OK))
            else:
                span.set_status(trace.Status(trace.StatusCode.ERROR, decision.get("reason", "rejected")))
    except Exception:
        # Silently fail if telemetry export fails
        pass


def trace_test_case(
    case_index: int,
    role: str,
    duration_ms: float,
    success: bool,
    tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
) -> None:
    """
    Export individual test case trace.
    
    Args:
        case_index: Test case index
        role: Role (baseline or candidate)
        duration_ms: Duration in milliseconds
        success: Whether test passed
        tokens: Token count (for LLM evaluations)
        cost_usd: Cost in USD (for LLM evaluations)
    """
    if not is_telemetry_enabled():
        return
    
    try:
        with _tracer.start_as_current_span(f"metamorphic_guard.test_case") as span:
            span.set_attribute("test_case.index", case_index)
            span.set_attribute("test_case.role", role)
            span.set_attribute("test_case.duration_ms", duration_ms)
            span.set_attribute("test_case.success", success)
            
            if tokens is not None:
                span.set_attribute("llm.tokens", tokens)
            if cost_usd is not None:
                span.set_attribute("llm.cost_usd", cost_usd)
            
            if success:
                span.set_status(trace.Status(trace.StatusCode.OK))
            else:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
    except Exception:
        # Silently fail if telemetry export fails
        pass

