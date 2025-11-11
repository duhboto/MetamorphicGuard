#!/usr/bin/env python3
"""Export Pydantic models to JSON Schema files."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from metamorphic_guard.config import EvaluatorConfig
    from metamorphic_guard.report_schema import Report
except ImportError as e:
    print(f"Error importing models: {e}")
    print("Make sure you're running from the project root with dependencies installed")
    exit(1)


def export_report_schema(output_path: Path) -> None:
    """Export report schema to JSON."""
    schema = Report.model_json_schema(mode="serialization")
    
    # Add schema metadata
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "Metamorphic Guard Report"
    schema["description"] = "JSON schema for Metamorphic Guard evaluation reports"
    
    output_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"✓ Exported report schema to {output_path}")


def export_config_schema(output_path: Path) -> None:
    """Export config schema to JSON."""
    schema = EvaluatorConfig.model_json_schema(mode="serialization")
    
    # Add schema metadata
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "Metamorphic Guard Configuration"
    schema["description"] = "JSON schema for Metamorphic Guard configuration files (TOML)"
    
    output_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"✓ Exported config schema to {output_path}")


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    schemas_dir = project_root / "schemas"
    schemas_dir.mkdir(exist_ok=True)
    
    export_report_schema(schemas_dir / "report.schema.json")
    export_config_schema(schemas_dir / "config.schema.json")
    
    print("\n✓ All schemas exported successfully")

