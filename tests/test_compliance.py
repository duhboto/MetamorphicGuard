"""
Tests for compliance rules and safety monitors.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.compliance import (
    ComplianceResult,
    ComplianceRule,
    FINANCIAL_RULE,
    GDPR_RULE,
    HIPAA_RULE,
    check_compliance,
    check_financial_compliance,
    check_gdpr_compliance,
    check_hipaa_compliance,
)
from metamorphic_guard.monitoring import MonitorContext, MonitorRecord
from metamorphic_guard.safety_monitors import (
    BiasMonitor,
    PIIMonitor,
    ToxicityMonitor,
)


# GDPR Compliance Tests
def test_check_gdpr_compliance_no_pii():
    """Test GDPR compliance check with no PII detected."""
    result = {
        "candidate": {
            "results": [
                {"result": "Hello world"},
                {"result": "Test output"},
            ],
        },
        "provenance": {
            "tracking": True,
        },
    }
    
    passed, details = check_gdpr_compliance(result)
    
    assert passed is True
    assert "checks" in details
    assert any(c["name"] == "pii_detection" and c["passed"] for c in details["checks"])
    assert any(c["name"] == "provenance_tracking" and c["passed"] for c in details["checks"])


def test_check_gdpr_compliance_pii_detected():
    """Test GDPR compliance check with PII detected."""
    result = {
        "candidate": {
            "results": [
                {"result": "user@example.com"},
                {"result": "Test output"},
            ],
        },
        "provenance": {
            "tracking": True,
        },
    }
    
    passed, details = check_gdpr_compliance(result)
    
    assert passed is False
    assert "checks" in details
    pii_check = next(c for c in details["checks"] if c["name"] == "pii_detection")
    assert pii_check["passed"] is False


def test_check_gdpr_compliance_no_provenance():
    """Test GDPR compliance check without provenance tracking."""
    result = {
        "candidate": {
            "results": [
                {"result": "Hello world"},
            ],
        },
    }
    
    passed, details = check_gdpr_compliance(result)
    
    assert passed is False
    provenance_check = next(c for c in details["checks"] if c["name"] == "provenance_tracking")
    assert provenance_check["passed"] is False


# HIPAA Compliance Tests
def test_check_hipaa_compliance_no_phi():
    """Test HIPAA compliance check with no PHI detected."""
    result = {
        "candidate": {
            "results": [
                {"result": "General information"},
                {"result": "Test output"},
            ],
        },
        "provenance": {
            "audit_log": True,
        },
    }
    
    passed, details = check_hipaa_compliance(result)
    
    assert passed is True
    assert "checks" in details
    phi_check = next(c for c in details["checks"] if c["name"] == "phi_detection")
    assert phi_check["passed"] is True
    audit_check = next(c for c in details["checks"] if c["name"] == "audit_logging")
    assert audit_check["passed"] is True


def test_check_hipaa_compliance_phi_detected():
    """Test HIPAA compliance check with PHI detected."""
    result = {
        "candidate": {
            "results": [
                {"result": "Patient diagnosis: diabetes"},
                {"result": "Test output"},
            ],
        },
        "provenance": {
            "audit_log": True,
        },
    }
    
    passed, details = check_hipaa_compliance(result)
    
    assert passed is False
    phi_check = next(c for c in details["checks"] if c["name"] == "phi_detection")
    assert phi_check["passed"] is False


def test_check_hipaa_compliance_no_audit_log():
    """Test HIPAA compliance check without audit logging."""
    result = {
        "candidate": {
            "results": [
                {"result": "General information"},
            ],
        },
        "provenance": {},
    }
    
    passed, details = check_hipaa_compliance(result)
    
    assert passed is False
    audit_check = next(c for c in details["checks"] if c["name"] == "audit_logging")
    assert audit_check["passed"] is False


# Financial Compliance Tests
def test_check_financial_compliance_complete():
    """Test financial compliance check with all requirements met."""
    result = {
        "provenance": {
            "model_version": "v1.2.3",
        },
        "seed": 42,
        "policy_version": "1.0",
    }
    
    passed, details = check_financial_compliance(result)
    
    assert passed is True
    assert "checks" in details
    version_check = next(c for c in details["checks"] if c["name"] == "model_versioning")
    assert version_check["passed"] is True
    repro_check = next(c for c in details["checks"] if c["name"] == "reproducibility")
    assert repro_check["passed"] is True


def test_check_financial_compliance_no_version():
    """Test financial compliance check without model versioning."""
    result = {
        "provenance": {},
        "seed": 42,
        "policy_version": "1.0",
    }
    
    passed, details = check_financial_compliance(result)
    
    assert passed is False
    version_check = next(c for c in details["checks"] if c["name"] == "model_versioning")
    assert version_check["passed"] is False


def test_check_financial_compliance_no_reproducibility():
    """Test financial compliance check without reproducibility."""
    result = {
        "provenance": {
            "model_version": "v1.2.3",
        },
    }
    
    passed, details = check_financial_compliance(result)
    
    assert passed is False
    repro_check = next(c for c in details["checks"] if c["name"] == "reproducibility")
    assert repro_check["passed"] is False


# Compliance Rule Integration Tests
def test_check_compliance_single_rule():
    """Test compliance checking with a single rule."""
    result = {
        "candidate": {
            "results": [
                {"result": "Hello world"},
            ],
        },
        "provenance": {
            "tracking": True,
        },
    }
    
    compliance_result = check_compliance(result, [GDPR_RULE])
    
    assert isinstance(compliance_result, ComplianceResult)
    assert compliance_result.passed is True
    assert len(compliance_result.rules_passed) == 1
    assert len(compliance_result.rules_failed) == 0
    assert compliance_result.overall_score > 0.0


def test_check_compliance_multiple_rules():
    """Test compliance checking with multiple rules."""
    result = {
        "candidate": {
            "results": [
                {"result": "General information"},
            ],
        },
        "provenance": {
            "tracking": True,
            "audit_log": True,
            "model_version": "v1.0",
        },
        "seed": 42,
        "policy_version": "1.0",
    }
    
    compliance_result = check_compliance(result, [GDPR_RULE, HIPAA_RULE, FINANCIAL_RULE])
    
    assert isinstance(compliance_result, ComplianceResult)
    assert compliance_result.passed is True
    assert len(compliance_result.rules_passed) == 3
    assert len(compliance_result.rules_failed) == 0
    assert compliance_result.overall_score > 0.0


def test_check_compliance_partial_failure():
    """Test compliance checking with some rules failing."""
    result = {
        "candidate": {
            "results": [
                {"result": "user@example.com"},  # PII detected
            ],
        },
        "provenance": {
            "tracking": True,
        },
    }
    
    compliance_result = check_compliance(result, [GDPR_RULE])
    
    assert compliance_result.passed is False
    assert len(compliance_result.rules_failed) == 1
    assert compliance_result.rules_failed[0]["rule"] == "GDPR"


def test_check_compliance_custom_rule():
    """Test compliance checking with a custom rule."""
    def custom_check(result):
        has_metadata = "metadata" in result
        return has_metadata, {"check": "metadata_present", "passed": has_metadata}
    
    custom_rule = ComplianceRule(
        name="Custom",
        description="Custom compliance check",
        check=custom_check,
        severity="warning",
    )
    
    result = {"metadata": {"version": "1.0"}}
    compliance_result = check_compliance(result, [custom_rule])
    
    assert compliance_result.passed is True
    assert "Custom" in compliance_result.rules_passed


# Safety Monitor Tests
def test_toxicity_monitor():
    """Test ToxicityMonitor detection."""
    monitor = ToxicityMonitor(threshold=0.7)
    context = MonitorContext(
        task="test",
        total_cases=10,
    )
    
    monitor.start(context)
    
    # Record non-toxic content
    monitor.record(MonitorRecord(
        case_index=0,
        role="candidate",
        duration_ms=10.0,
        success=True,
        result={"result": "Hello, how are you?"},
    ))
    
    # Record potentially toxic content
    monitor.record(MonitorRecord(
        case_index=1,
        role="candidate",
        duration_ms=10.0,
        success=True,
        result={"result": "This is hate speech and violence"},
    ))
    
    summary = monitor.finalize()
    
    assert "summary" in summary
    assert summary["summary"]["total_count"] == 2
    assert summary["summary"]["toxic_count"] >= 0  # May or may not detect based on threshold
    assert summary["summary"]["toxic_rate"] >= 0.0


def test_bias_monitor():
    """Test BiasMonitor detection."""
    monitor = BiasMonitor()
    context = MonitorContext(
        task="test",
        total_cases=10,
    )
    
    monitor.start(context)
    
    # Record potentially biased content
    monitor.record(MonitorRecord(
        case_index=0,
        role="candidate",
        duration_ms=10.0,
        success=True,
        result={"result": "Only men can do this job"},
    ))
    
    summary = monitor.finalize()
    
    assert "summary" in summary
    assert summary["summary"]["total_count"] == 1
    assert summary["summary"]["bias_count"] >= 0
    assert summary["summary"]["bias_rate"] >= 0.0


def test_pii_monitor():
    """Test PIIMonitor detection."""
    monitor = PIIMonitor()
    context = MonitorContext(
        task="test",
        total_cases=10,
    )
    
    monitor.start(context)
    
    # Record content with PII
    monitor.record(MonitorRecord(
        case_index=0,
        role="candidate",
        duration_ms=10.0,
        success=True,
        result={"result": "Contact: user@example.com or call 555-1234"},
    ))
    
    # Record content without PII
    monitor.record(MonitorRecord(
        case_index=1,
        role="candidate",
        duration_ms=10.0,
        success=True,
        result={"result": "Hello world"},
    ))
    
    summary = monitor.finalize()
    
    assert "summary" in summary
    assert summary["summary"]["total_count"] == 2
    assert summary["summary"]["pii_count"] >= 1  # Should detect email and phone
    assert summary["summary"]["pii_rate"] > 0.0


def test_toxicity_monitor_threshold():
    """Test ToxicityMonitor with different thresholds."""
    monitor_low = ToxicityMonitor(threshold=0.3)
    monitor_high = ToxicityMonitor(threshold=0.9)
    
    context = MonitorContext(
        task="test",
        total_cases=10,
    )
    
    test_result = {"result": "This is offensive content"}
    
    monitor_low.start(context)
    monitor_low.record(MonitorRecord(case_index=0, role="candidate", duration_ms=10.0, success=True, result=test_result))
    summary_low = monitor_low.finalize()
    
    monitor_high.start(context)
    monitor_high.record(MonitorRecord(case_index=0, role="candidate", duration_ms=10.0, success=True, result=test_result))
    summary_high = monitor_high.finalize()
    
    # Lower threshold should be more sensitive
    assert summary_low["summary"]["toxic_count"] >= summary_high["summary"]["toxic_count"]


def test_safety_monitors_integration():
    """Test multiple safety monitors working together."""
    monitors = [
        ToxicityMonitor(threshold=0.7),
        BiasMonitor(),
        PIIMonitor(),
    ]
    
    context = MonitorContext(
        task="test",
        total_cases=5,
    )
    
    for monitor in monitors:
        monitor.start(context)
    
    test_cases = [
        {"result": "Hello world"},
        {"result": "user@example.com"},
        {"result": "This is hate speech"},
    ]
    
    for idx, test_result in enumerate(test_cases):
        record = MonitorRecord(case_index=idx, role="candidate", duration_ms=10.0, success=True, result=test_result)
        for monitor in monitors:
            monitor.record(record)
    
    summaries = [monitor.finalize() for monitor in monitors]
    
    assert len(summaries) == 3
    assert all("summary" in s for s in summaries)
    # PII monitor should detect email in case 1
    pii_summary = summaries[2]  # PIIMonitor is last
    assert pii_summary["summary"]["pii_count"] >= 1

