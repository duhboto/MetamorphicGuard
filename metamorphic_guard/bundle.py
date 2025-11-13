"""Create reproducible evaluation bundles from reports."""

from __future__ import annotations

import json
import tarfile
import tempfile
from pathlib import Path

import click


def create_repro_bundle(
    report_path: Path,
    output_path: Path,
    baseline_path: Path | None = None,
    candidate_path: Path | None = None,
) -> Path:
    """
    Create a reproducible bundle from a report.
    
    Args:
        report_path: Path to the JSON report
        output_path: Path for the output .tgz file
        baseline_path: Optional path to baseline file (if not in report)
        candidate_path: Optional path to candidate file (if not in report)
        
    Returns:
        Path to the created bundle
    """
    # Load report
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    
    # Extract metadata
    spec_fingerprint = report.get("spec_fingerprint", "")
    hashes = report.get("hashes", {})
    baseline_hash = hashes.get("baseline", "")
    candidate_hash = hashes.get("candidate", "")
    config = report.get("config", {})
    job_metadata = report.get("job_metadata", {})
    
    # Create temporary directory for bundle contents
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_dir = Path(tmpdir) / "repro_bundle"
        bundle_dir.mkdir()
        
        # Copy report
        (bundle_dir / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        
        # Create metadata file
        metadata = {
            "spec_fingerprint": spec_fingerprint,
            "baseline_hash": baseline_hash,
            "candidate_hash": candidate_hash,
            "config": config,
            "job_metadata": job_metadata,
            "metamorphic_guard_version": report.get("metamorphic_guard_version", "unknown"),
        }
        (bundle_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        
        # Copy baseline and candidate if provided
        if baseline_path and baseline_path.exists():
            (bundle_dir / "baseline.py").write_text(
                baseline_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        elif baseline_hash:
            (bundle_dir / "baseline.hash").write_text(baseline_hash, encoding="utf-8")
        
        if candidate_path and candidate_path.exists():
            (bundle_dir / "candidate.py").write_text(
                candidate_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        elif candidate_hash:
            (bundle_dir / "candidate.hash").write_text(candidate_hash, encoding="utf-8")
        
        # Create README
        readme_content = f"""# Metamorphic Guard Repro Bundle

This bundle contains all information needed to reproduce the evaluation.

## Contents

- `report.json`: Full evaluation report
- `metadata.json`: Evaluation metadata including fingerprints and hashes
- `baseline.py` or `baseline.hash`: Baseline implementation (or hash if file not available)
- `candidate.py` or `candidate.hash`: Candidate implementation (or hash if file not available)

## Reproducing

1. Install Metamorphic Guard:
   ```bash
   pip install metamorphic-guard
   ```

2. If you have the baseline and candidate files, run:
   ```bash
   metamorphic-guard evaluate \\
     --task {report.get('task', 'unknown')} \\
     --baseline baseline.py \\
     --candidate candidate.py \\
     --n {job_metadata.get('n', 400)} \\
     --seed {job_metadata.get('seed', 42)}
   ```

3. Compare the results with `report.json`.

## Metadata

- **Spec Fingerprint**: {spec_fingerprint}
- **Baseline Hash**: {baseline_hash}
- **Candidate Hash**: {candidate_hash}
- **Metamorphic Guard Version**: {metadata.get('metamorphic_guard_version', 'unknown')}
"""
        (bundle_dir / "README.md").write_text(readme_content, encoding="utf-8")
        
        # Create tar.gz
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(bundle_dir, arcname="repro_bundle")
    
    return output_path


@click.command()
@click.argument("report", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output bundle file path (defaults to <report>.tgz)",
)
@click.option(
    "--baseline",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to baseline implementation file",
)
@click.option(
    "--candidate",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to candidate implementation file",
)
def bundle_command(
    report: Path,
    output: Path | None,
    baseline: Path | None,
    candidate: Path | None,
) -> None:
    """Create a reproducible bundle from an evaluation report."""
    output_path = output or report.with_suffix(".tgz")
    
    try:
        bundle_path = create_repro_bundle(
            report_path=report,
            output_path=output_path,
            baseline_path=baseline,
            candidate_path=candidate,
        )
        click.echo(f"Repro bundle created: {bundle_path}")
    except Exception as e:
        click.echo(f"Error creating bundle: {e}", err=True)
        raise click.Abort() from e

