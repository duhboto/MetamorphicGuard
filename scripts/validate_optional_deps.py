#!/usr/bin/env python3
"""
Validation script for optional dependencies.

This script validates that optional dependency groups can be imported correctly.
It checks that all expected modules for a given install profile are importable.

Usage:
    python scripts/validate_optional_deps.py [profile]

    Where profile is one of: llm, otel, queue, docs, all, or 'base' for core only.

Examples:
    # Validate LLM dependencies
    python scripts/validate_optional_deps.py llm

    # Validate all profiles
    python scripts/validate_optional_deps.py all

    # Validate base (core) dependencies
    python scripts/validate_optional_deps.py base
"""

from __future__ import annotations

import sys
from typing import Dict, List, Tuple

# Define expected imports for each profile
PROFILE_IMPORTS: Dict[str, List[Tuple[str, str, str]]] = {
    "base": [
        ("click", "click", "Core CLI framework"),
        ("pydantic", "pydantic", "Core data validation"),
    ],
    "llm": [
        ("openai", "openai", "OpenAI API support"),
        ("anthropic", "anthropic", "Anthropic API support"),
        ("vllm", "vllm", "Local vLLM inference"),
    ],
    "otel": [
        ("opentelemetry-api", "opentelemetry", "OpenTelemetry API"),
        ("opentelemetry-sdk", "opentelemetry.sdk", "OpenTelemetry SDK"),
        (
            "opentelemetry-exporter-otlp-proto-grpc",
            "opentelemetry.exporter.otlp.proto.grpc",
            "OpenTelemetry OTLP gRPC exporter",
        ),
    ],
    "queue": [
        ("redis", "redis", "Redis queue backend"),
        ("boto3", "boto3", "AWS SQS queue backend"),
        ("pika", "pika", "RabbitMQ queue backend"),
        ("kafka", "kafka", "Kafka queue backend (kafka-python)"),
    ],
    "docs": [
        ("mkdocs", "mkdocs", "MkDocs documentation tool"),
        ("mkdocs-material", "mkdocs", "MkDocs Material theme"),
        ("mkdocstrings", "mkdocstrings", "MkDocstrings plugin"),
        ("pymdown-extensions", "pymdownx", "PyMdown extensions"),
    ],
    "all": [
        # LLM
        ("openai", "openai", "OpenAI API support"),
        ("anthropic", "anthropic", "Anthropic API support"),
        ("vllm", "vllm", "Local vLLM inference"),
        # OpenTelemetry
        ("opentelemetry-api", "opentelemetry", "OpenTelemetry API"),
        ("opentelemetry-sdk", "opentelemetry.sdk", "OpenTelemetry SDK"),
        # Queue
        ("redis", "redis", "Redis queue backend"),
        ("boto3", "boto3", "AWS SQS queue backend"),
        ("pika", "pika", "RabbitMQ queue backend"),
        ("kafka", "kafka", "Kafka queue backend"),
        # Docs (skip in all profile to avoid heavy dependencies in CI)
    ],
}


def validate_import(package_name: str, import_path: str, description: str) -> Tuple[bool, str]:
    """
    Validate that a module can be imported.

    Args:
        package_name: Name of the package (for error messages)
        import_path: Python import path (e.g., "openai" or "opentelemetry.sdk")
        description: Human-readable description

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        __import__(import_path)
        return True, f"✅ {package_name} ({description})"
    except ImportError as e:
        return False, f"❌ {package_name} ({description}): {e}"
    except Exception as e:
        return False, f"⚠️  {package_name} ({description}): Unexpected error: {e}"


def validate_profile(profile: str) -> Tuple[bool, List[str]]:
    """
    Validate all imports for a given profile.

    Args:
        profile: Profile name (llm, otel, queue, docs, all, or base)

    Returns:
        Tuple of (all_passed: bool, messages: List[str])
    """
    if profile not in PROFILE_IMPORTS:
        return False, [f"❌ Unknown profile: {profile}. Available: {', '.join(PROFILE_IMPORTS.keys())}"]

    imports = PROFILE_IMPORTS[profile]
    results: List[Tuple[bool, str]] = []
    messages: List[str] = []

    messages.append(f"Validating profile: {profile}")
    messages.append(f"Checking {len(imports)} dependencies...")
    messages.append("")

    for package_name, import_path, description in imports:
        success, message = validate_import(package_name, import_path, description)
        results.append((success, message))
        messages.append(message)

    all_passed = all(success for success, _ in results)
    passed_count = sum(1 for success, _ in results if success)
    failed_count = len(results) - passed_count

    messages.append("")
    messages.append(f"Summary: {passed_count}/{len(results)} passed, {failed_count} failed")

    return all_passed, messages


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_optional_deps.py [profile]")
        print(f"Available profiles: {', '.join(PROFILE_IMPORTS.keys())}")
        return 1

    profile = sys.argv[1].lower()

    # Special case: validate all profiles
    if profile == "all-profiles":
        all_passed = True
        for prof in ["base", "llm", "otel", "queue", "docs"]:
            passed, messages = validate_profile(prof)
            print("\n".join(messages))
            print("")
            if not passed:
                all_passed = False
        return 0 if all_passed else 1

    success, messages = validate_profile(profile)
    print("\n".join(messages))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())


