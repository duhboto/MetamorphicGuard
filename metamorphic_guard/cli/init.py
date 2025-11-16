"""
Init command for creating starter configuration files and project scaffolding.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional, Sequence

import click


# Available templates
TEMPLATES = {
    "minimal": "Minimal configuration - only core options",
    "standard": "Standard evaluation with common defaults",
    "sequential": "Sequential testing for iterative PR workflows",
    "adaptive": "Adaptive testing with automatic sample size determination",
    "llm": "LLM evaluation configuration",
    "distributed": "Distributed evaluation with queue-based execution",
}


def _get_template_path(template_name: str) -> Path:
    """Get the path to a template file."""
    # Templates are in the project root templates/ directory
    # When installed, they should be in the package data
    import metamorphic_guard
    
    # Try to find templates relative to package
    package_dir = Path(metamorphic_guard.__file__).parent.parent
    template_path = package_dir / "templates" / f"{template_name}.toml"
    
    if not template_path.exists():
        # Fallback: try current directory
        template_path = Path("templates") / f"{template_name}.toml"
    
    return template_path


@click.command("init")
@click.option(
    "--path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=Path("metamorphic.toml"),
    show_default=True,
    help="Configuration file to create.",
)
@click.option(
    "--template",
    type=click.Choice(list(TEMPLATES.keys()), case_sensitive=False),
    default=None,
    help="Use a template configuration. Available: " + ", ".join(TEMPLATES.keys()),
)
@click.option("--task", default="top_k", show_default=True, help="Task name (only used if --template not specified)")
@click.option("--baseline", default="baseline.py", show_default=True, help="Baseline path (only used if --template not specified)")
@click.option("--candidate", default="candidate.py", show_default=True, help="Candidate path (only used if --template not specified)")
@click.option("--distributed/--no-distributed", default=False, show_default=True, help="Enable distributed execution (only used if --template not specified)")
@click.option("--monitor", "monitor_names", multiple=True, help="Monitors to enable by default (only used if --template not specified)")
@click.option("--interactive/--no-interactive", default=False, show_default=False, help="Launch an interactive wizard.")
@click.option(
    "--project-dir",
    type=click.Path(file_okay=False, writable=True, path_type=Path),
    default=None,
    help="Create a full project structure in this directory (includes baseline.py, candidate.py, README.md, .github/workflows/)",
)
def init_command(
    path: Path,
    template: Optional[str],
    task: str,
    baseline: str,
    candidate: str,
    distributed: bool,
    monitor_names: Sequence[str],
    interactive: bool,
    project_dir: Optional[Path],
) -> None:
    """Create a starter TOML configuration file or scaffold a full project."""
    
    # If project_dir is specified, scaffold a full project
    if project_dir:
        _scaffold_project(project_dir, template, task, baseline, candidate, interactive)
        return
    
    # Otherwise, just create a config file
    monitors = list(monitor_names)

    if interactive:
        if not template:
            template_choice = click.prompt(
                "Template (minimal, standard, sequential, adaptive, llm, distributed, or 'none' for custom)",
                default="standard",
            )
            if template_choice.lower() != "none":
                template = template_choice.lower()
        
        if not template:
            task = click.prompt("Task name", default=task)
            baseline = click.prompt("Baseline path", default=baseline)
            candidate = click.prompt("Candidate path", default=candidate)
            distributed = click.confirm("Enable distributed execution?", default=distributed)
            monitor_default = ",".join(monitors)
            monitor_input = click.prompt(
                "Monitors (comma separated, blank for none)",
                default=monitor_default,
                show_default=bool(monitor_default),
            )
            monitors = [m.strip() for m in monitor_input.split(",") if m.strip()] if monitor_input else []

    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use template if specified
    if template:
        template_path = _get_template_path(template)
        if template_path.exists():
            # Copy template and customize task/baseline/candidate if provided
            content = template_path.read_text(encoding="utf-8")
            
            # Replace placeholders if user provided values
            if task != "top_k":
                content = content.replace("your_task_name", task)
                content = content.replace('name = "your_task_name"', f'name = "{task}"')
            if baseline != "baseline.py":
                content = content.replace("path/to/baseline.py", baseline)
                content = content.replace('baseline = "path/to/baseline.py"', f'baseline = "{baseline}"')
            if candidate != "candidate.py":
                content = content.replace("path/to/candidate.py", candidate)
                content = content.replace('candidate = "path/to/candidate.py"', f'candidate = "{candidate}"')
            
            path.write_text(content, encoding="utf-8")
            click.echo(f"Created configuration from '{template}' template: {path}")
            if template in TEMPLATES:
                click.echo(f"  Description: {TEMPLATES[template]}")
        else:
            click.echo(f"Warning: Template '{template}' not found at {template_path}", err=True)
            click.echo("Falling back to basic configuration", err=True)
            _write_basic_config(path, task, baseline, candidate, distributed, monitors)
    else:
        _write_basic_config(path, task, baseline, candidate, distributed, monitors)


def _write_basic_config(
    path: Path,
    task: str,
    baseline: str,
    candidate: str,
    distributed: bool,
    monitors: list[str],
) -> None:
    """Write a basic configuration file."""
    lines = ["[task]"]
    lines.append(f'name = "{task}"')
    lines.append(f'baseline = "{baseline}"')
    lines.append(f'candidate = "{candidate}"')
    
    lines.append("")
    lines.append("[execution]")
    lines.append("n = 400")
    lines.append("seed = 42")
    lines.append("timeout_s = 2.0")
    lines.append("mem_mb = 512")
    
    lines.append("")
    lines.append("[statistics]")
    lines.append("alpha = 0.05")
    lines.append("min_delta = 0.02")
    lines.append("ci_method = \"bootstrap\"")
    lines.append("bootstrap_samples = 1000")
    
    if monitors:
        lines.append("")
        lines.append("[monitoring]")
        monitor_str = ", ".join(f'"{name}"' for name in monitors)
        lines.append(f"monitors = [{monitor_str}]")
    
    if distributed:
        lines.append("")
        lines.append("[dispatcher]")
        lines.append('type = "queue"')
        lines.append("")
        lines.append("[queue]")
        lines.append('backend = "redis"')
        lines.append('connection = { host = "localhost", port = 6379, db = 0 }')
    
    lines.append("")
    lines.append("[reporting]")
    lines.append('report_dir = "reports"')
    
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    click.echo(f"Created configuration file: {path}")


def _scaffold_project(
    project_dir: Path,
    template: Optional[str],
    task: str,
    baseline: str,
    candidate: str,
    interactive: bool,
) -> None:
    """Scaffold a full project structure."""
    project_dir.mkdir(parents=True, exist_ok=True)
    
    if interactive:
        task = click.prompt("Task name", default=task)
        baseline_name = click.prompt("Baseline filename", default=baseline)
        candidate_name = click.prompt("Candidate filename", default=candidate)
        template_choice = click.prompt(
            "Template (minimal, standard, sequential, adaptive, llm, distributed, or 'none' for custom)",
            default=template or "standard",
        )
        if template_choice.lower() != "none":
            template = template_choice.lower()
    else:
        baseline_name = baseline
        candidate_name = candidate
    
    # Create config file
    config_path = project_dir / "metamorphic.toml"
    if template:
        template_path = _get_template_path(template)
        if template_path.exists():
            content = template_path.read_text(encoding="utf-8")
            content = content.replace("your_task_name", task)
            content = content.replace("path/to/baseline.py", baseline_name)
            content = content.replace("path/to/candidate.py", candidate_name)
            config_path.write_text(content, encoding="utf-8")
        else:
            _write_basic_config(config_path, task, baseline_name, candidate_name, False, [])
    else:
        _write_basic_config(config_path, task, baseline_name, candidate_name, False, [])
    
    # Create baseline.py stub
    baseline_path = project_dir / baseline_name
    if not baseline_path.exists():
        baseline_path.write_text(f'''"""
Baseline implementation for {task} task.
"""

def solve(*args):
    """
    Baseline implementation.
    
    Args:
        *args: Task-specific arguments
    
    Returns:
        Task-specific result
    """
    # TODO: Implement baseline
    raise NotImplementedError("Implement baseline solution")
''', encoding="utf-8")
    
    # Create candidate.py stub
    candidate_path = project_dir / candidate_name
    if not candidate_path.exists():
        candidate_path.write_text(f'''"""
Candidate implementation for {task} task.
"""

def solve(*args):
    """
    Candidate implementation.
    
    Args:
        *args: Task-specific arguments
    
    Returns:
        Task-specific result
    """
    # TODO: Implement candidate
    raise NotImplementedError("Implement candidate solution")
''', encoding="utf-8")
    
    # Create README.md
    readme_path = project_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(f'''# {task} Evaluation Project

This project uses Metamorphic Guard to evaluate the candidate implementation against the baseline.

## Files

- `metamorphic.toml`: Evaluation configuration
- `{baseline_name}`: Baseline implementation
- `{candidate_name}`: Candidate implementation

## Running Evaluations

```bash
metamorphic-guard evaluate \\
    --task {task} \\
    --baseline {baseline_name} \\
    --candidate {candidate_name} \\
    --n 400
```

Or use the config file:

```bash
metamorphic-guard evaluate --config metamorphic.toml
```

## Results

Evaluation reports are saved to the `reports/` directory.
''', encoding="utf-8")
    
    # Create .github/workflows/ directory and CI template
    workflows_dir = project_dir / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    
    workflow_path = workflows_dir / "evaluate.yml"
    if not workflow_path.exists():
        workflow_path.write_text(f'''name: Evaluate Candidate

on:
  pull_request:
    paths:
      - '{candidate_name}'
      - 'metamorphic.toml'
  workflow_dispatch:

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Metamorphic Guard
        run: pip install metamorphic-guard
      
      - name: Run Evaluation
        run: |
          metamorphic-guard evaluate \\
            --task {task} \\
            --baseline {baseline_name} \\
            --candidate {candidate_name} \\
            --n 400 \\
            --report-dir reports
      
      - name: Upload Reports
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: evaluation-reports
          path: reports/
''', encoding="utf-8")
    
    click.echo(f"Scaffolded project in {project_dir}")
    click.echo(f"  Configuration: {config_path}")
    click.echo(f"  Baseline: {baseline_path}")
    click.echo(f"  Candidate: {candidate_path}")
    click.echo(f"  README: {readme_path}")
    click.echo(f"  CI workflow: {workflow_path}")

