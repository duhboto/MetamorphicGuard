"""JUnit XML output for CI integration."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict


def write_junit_xml(result: Dict[str, Any], output_path: Path) -> None:
    """
    Write evaluation results as JUnit XML format.

    Args:
        result: Evaluation result dictionary
        output_path: Path to write JUnit XML file
    """
    baseline = result.get("baseline", {})
    candidate = result.get("candidate", {})
    decision = result.get("decision", {})
    
    # Calculate test statistics
    baseline_total = baseline.get("total", 0)
    baseline_passes = baseline.get("passes", 0)
    baseline_failures = baseline_total - baseline_passes
    
    candidate_total = candidate.get("total", 0)
    candidate_passes = candidate.get("passes", 0)
    candidate_failures = candidate_total - candidate_passes
    
    # Determine overall test suite status
    adopt = decision.get("adopt", False)
    total_tests = baseline_total + candidate_total
    total_failures = baseline_failures + candidate_failures
    total_errors = len(baseline.get("prop_violations", [])) + len(candidate.get("prop_violations", []))
    
    # Create root test suite
    testsuites = ET.Element("testsuites")
    testsuites.set("name", "Metamorphic Guard")
    testsuites.set("tests", str(total_tests))
    testsuites.set("failures", str(total_failures))
    testsuites.set("errors", str(total_errors))
    testsuites.set("time", str(result.get("job_metadata", {}).get("duration_seconds", 0)))
    
    # Baseline test suite
    baseline_suite = ET.SubElement(testsuites, "testsuite")
    baseline_suite.set("name", "baseline")
    baseline_suite.set("tests", str(baseline_total))
    baseline_suite.set("failures", str(baseline_failures))
    baseline_suite.set("time", "0")
    
    # Candidate test suite
    candidate_suite = ET.SubElement(testsuites, "testsuite")
    candidate_suite.set("name", "candidate")
    candidate_suite.set("tests", str(candidate_total))
    candidate_suite.set("failures", str(candidate_failures))
    candidate_suite.set("time", "0")
    
    # Add adoption decision as a test case
    decision_case = ET.SubElement(candidate_suite, "testcase")
    decision_case.set("name", "adoption_decision")
    decision_case.set("classname", "metamorphic_guard.gate")
    decision_case.set("time", "0")
    
    if not adopt:
        failure = ET.SubElement(decision_case, "failure")
        failure.set("message", decision.get("reason", "Adoption gate failed"))
        failure.text = f"Adopt: {adopt}, Reason: {decision.get('reason', 'unknown')}"
    
    # Add property violations as test failures
    for violation in baseline.get("prop_violations", [])[:10]:  # Limit to first 10
        testcase = ET.SubElement(baseline_suite, "testcase")
        testcase.set("name", f"property_{violation.get('test_case', 'unknown')}")
        testcase.set("classname", violation.get("property", "unknown"))
        testcase.set("time", "0")
        failure = ET.SubElement(testcase, "failure")
        failure.set("message", f"Property violation: {violation.get('property', 'unknown')}")
        failure.text = f"Input: {violation.get('input', '')}, Output: {violation.get('output', '')}"
    
    for violation in candidate.get("prop_violations", [])[:10]:  # Limit to first 10
        testcase = ET.SubElement(candidate_suite, "testcase")
        testcase.set("name", f"property_{violation.get('test_case', 'unknown')}")
        testcase.set("classname", violation.get("property", "unknown"))
        testcase.set("time", "0")
        failure = ET.SubElement(testcase, "failure")
        failure.set("message", f"Property violation: {violation.get('property', 'unknown')}")
        failure.text = f"Input: {violation.get('input', '')}, Output: {violation.get('output', '')}"
    
    # Write XML
    tree = ET.ElementTree(testsuites)
    ET.indent(tree, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

