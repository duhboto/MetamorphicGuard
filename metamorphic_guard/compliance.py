"""
Compliance checks for regulatory requirement validation.

This module provides utilities for validating evaluations against
regulatory requirements (GDPR, HIPAA, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .types import JSONDict


@dataclass
class ComplianceRule:
    """A compliance rule to check."""
    
    name: str
    description: str
    check: callable  # Function that takes result and returns (passed: bool, details: Dict)
    severity: str = "error"  # "error", "warning", "info"


@dataclass
class ComplianceResult:
    """Result of compliance checking."""
    
    passed: bool
    rules_passed: List[str]
    rules_failed: List[Dict[str, Any]]
    overall_score: float
    details: Dict[str, Any]


def check_gdpr_compliance(result: JSONDict) -> tuple[bool, Dict[str, Any]]:
    """
    Check GDPR compliance requirements.
    
    Args:
        result: Evaluation result
    
    Returns:
        Tuple of (passed, details)
    """
    details: Dict[str, Any] = {
        "checks": [],
    }
    passed = True
    
    # Check for PII in results
    pii_detected = False
    if "candidate" in result:
        candidate_results = result["candidate"].get("results", [])
        for res in candidate_results:
            output = str(res.get("result", ""))
            # Simple PII check
            if "@" in output or any(char.isdigit() for char in output[-4:]):
                pii_detected = True
                break
    
    if pii_detected:
        passed = False
        details["checks"].append({
            "name": "pii_detection",
            "passed": False,
            "message": "Potential PII detected in results",
        })
    else:
        details["checks"].append({
            "name": "pii_detection",
            "passed": True,
            "message": "No PII detected",
        })
    
    # Check for data retention policy
    if "provenance" in result:
        details["checks"].append({
            "name": "provenance_tracking",
            "passed": True,
            "message": "Provenance tracking enabled",
        })
    else:
        details["checks"].append({
            "name": "provenance_tracking",
            "passed": False,
            "message": "Provenance tracking not enabled",
        })
        passed = False
    
    return passed, details


def check_hipaa_compliance(result: JSONDict) -> tuple[bool, Dict[str, Any]]:
    """
    Check HIPAA compliance requirements.
    
    Args:
        result: Evaluation result
    
    Returns:
        Tuple of (passed, details)
    """
    details: Dict[str, Any] = {
        "checks": [],
    }
    passed = True
    
    # Check for PHI (Protected Health Information)
    phi_keywords = ["patient", "diagnosis", "medical record", "ssn", "date of birth"]
    phi_detected = False
    
    if "candidate" in result:
        candidate_results = result["candidate"].get("results", [])
        for res in candidate_results:
            output = str(res.get("result", "")).lower()
            if any(keyword in output for keyword in phi_keywords):
                phi_detected = True
                break
    
    if phi_detected:
        passed = False
        details["checks"].append({
            "name": "phi_detection",
            "passed": False,
            "message": "Potential PHI detected in results",
        })
    else:
        details["checks"].append({
            "name": "phi_detection",
            "passed": True,
            "message": "No PHI detected",
        })
    
    # Check for audit logging
    if "provenance" in result and result["provenance"].get("audit_log"):
        details["checks"].append({
            "name": "audit_logging",
            "passed": True,
            "message": "Audit logging enabled",
        })
    else:
        details["checks"].append({
            "name": "audit_logging",
            "passed": False,
            "message": "Audit logging not enabled",
        })
        passed = False
    
    return passed, details


def check_financial_compliance(result: JSONDict) -> tuple[bool, Dict[str, Any]]:
    """
    Check financial services compliance (SOX, etc.).
    
    Args:
        result: Evaluation result
    
    Returns:
        Tuple of (passed, details)
    """
    details: Dict[str, Any] = {
        "checks": [],
    }
    passed = True
    
    # Check for model versioning
    if "provenance" in result:
        model_version = result["provenance"].get("model_version")
        if model_version:
            details["checks"].append({
                "name": "model_versioning",
                "passed": True,
                "message": f"Model version tracked: {model_version}",
            })
        else:
            details["checks"].append({
                "name": "model_versioning",
                "passed": False,
                "message": "Model version not tracked",
            })
            passed = False
    
    # Check for reproducibility
    if "seed" in result and "policy_version" in result:
        details["checks"].append({
            "name": "reproducibility",
            "passed": True,
            "message": "Evaluation is reproducible",
        })
    else:
        details["checks"].append({
            "name": "reproducibility",
            "passed": False,
            "message": "Evaluation not fully reproducible",
        })
        passed = False
    
    return passed, details


# Built-in compliance rules
GDPR_RULE = ComplianceRule(
    name="GDPR",
    description="General Data Protection Regulation compliance",
    check=check_gdpr_compliance,
    severity="error",
)

HIPAA_RULE = ComplianceRule(
    name="HIPAA",
    description="Health Insurance Portability and Accountability Act compliance",
    check=check_hipaa_compliance,
    severity="error",
)

FINANCIAL_RULE = ComplianceRule(
    name="Financial",
    description="Financial services compliance (SOX, etc.)",
    check=check_financial_compliance,
    severity="error",
)


def check_compliance(
    result: JSONDict,
    rules: Sequence[ComplianceRule],
) -> ComplianceResult:
    """
    Check evaluation result against compliance rules.
    
    Args:
        result: Evaluation result
        rules: Compliance rules to check
    
    Returns:
        ComplianceResult with pass/fail status
    """
    rules_passed = []
    rules_failed = []
    total_checks = 0
    passed_checks = 0
    
    for rule in rules:
        try:
            passed, details = rule.check(result)
            total_checks += len(details.get("checks", []))
            passed_checks += sum(1 for c in details.get("checks", []) if c.get("passed", False))
            
            if passed:
                rules_passed.append(rule.name)
            else:
                rules_failed.append({
                    "rule": rule.name,
                    "severity": rule.severity,
                    "description": rule.description,
                    "details": details,
                })
        except Exception as e:
            rules_failed.append({
                "rule": rule.name,
                "severity": rule.severity,
                "error": str(e),
            })
    
    overall_passed = len(rules_failed) == 0
    overall_score = passed_checks / total_checks if total_checks > 0 else 0.0
    
    return ComplianceResult(
        passed=overall_passed,
        rules_passed=rules_passed,
        rules_failed=rules_failed,
        overall_score=overall_score,
        details={
            "total_rules": len(rules),
            "passed_rules": len(rules_passed),
            "failed_rules": len(rules_failed),
        },
    )

