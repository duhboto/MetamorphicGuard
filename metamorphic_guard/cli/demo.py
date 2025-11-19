"""
Demo launcher command.
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import click


@click.command("demo")
@click.option(
    "--interactive/--no-interactive",
    default=True,
    help="Run in interactive mode (prompt for demo selection).",
)
@click.option(
    "--name",
    type=click.Choice(["top_k", "ranking", "fairness", "llm"], case_sensitive=False),
    help="Specific demo to run (skips prompt).",
)
def demo_command(interactive: bool, name: Optional[str]) -> None:
    """Launch interactive demos and tutorials."""
    
    demos = {
        "top_k": {
            "title": "Top-K (Basic)",
            "description": "Simple numeric sorting task. Good for first-time users.",
            "path": "demo_project",
            "script": "src/run_demo.py",
            "readme": "demo_project/README.md",
        },
        "ranking": {
            "title": "Ranking Guard",
            "description": "Search ranking evaluation with monotonicity checks.",
            "path": "ranking_guard_project",
            "script": "run_demo_ranking.sh", # Note: this might need adjustment based on actual file
            "readme": "ranking_guard_project/README.md",
            "requires_pkg": True
        },
        "fairness": {
            "title": "Fairness Guard",
            "description": "Credit approval model with fairness parity checks.",
            "path": "fairness_guard_project",
            "script": "run_demo_fairness.sh", # Note: this might need adjustment
            "readme": "fairness_guard_project/README.md",
            "requires_pkg": True
        },
        "llm": {
            "title": "LLM Guard",
            "description": "AI model evaluation with mock (free) or real (paid) executors.",
            "path": "llm_demo_project",
            "script": "run_demo.py",
            "readme": "llm_demo_project/TUTORIAL.md",
        }
    }
    
    selected = name
    
    if not selected and interactive:
        click.echo("Metamorphic Guard Demos")
        click.echo("=======================")
        click.echo("Select a demo to run:")
        
        options = list(demos.keys())
        for i, key in enumerate(options):
            info = demos[key]
            click.echo(f"{i + 1}. {info['title']} - {info['description']}")
            
        value = click.prompt("Enter number", type=int, default=1)
        if 1 <= value <= len(options):
            selected = options[value - 1]
        else:
            click.echo("Invalid selection.")
            return

    if not selected:
        click.echo("No demo selected. Use --interactive or --name.")
        return
        
    info = demos[selected]
    click.echo(f"\n🚀 Launching {info['title']}...")
    
    # Locate the project root relative to this file (installed package or source)
    # This logic tries to find the repo root if running from source
    # If installed, we might need to clone or copy examples? 
    # For now, assume we are in the repo or have access to it.
    
    # Simple heuristic: check if CWD has the folder
    cwd = Path.cwd()
    demo_path = cwd / info["path"]
    
    if not demo_path.exists():
        # Try to find it relative to package location if installed in editable mode?
        # Or just fail and tell user to cd to repo root.
        # Since this is a CLI tool often used in the repo, we'll assume repo root for now.
        click.echo(f"❌ Could not find demo directory '{info['path']}' in current path.")
        click.echo("Please run this command from the Metamorphic Guard repository root.")
        return

    # Special handling for prereqs
    if selected == "llm":
        if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
            click.echo("ℹ️  No API keys detected. Running in MOCK mode (free/simulated).")
            click.echo("   (Set OPENAI_API_KEY or ANTHROPIC_API_KEY to use real models)")
    
    # Execute
    script_path = demo_path / info["script"]
    
    # If script is a .sh file, ensure executable
    if script_path.suffix == ".sh":
        if not os.access(script_path, os.X_OK):
            os.chmod(script_path, 0o755)
        cmd = [str(script_path)]
    else:
        cmd = [sys.executable, str(script_path)]
        
    click.echo(f"📂 Working directory: {demo_path}")
    click.echo(f"▶️  Running: {' '.join(cmd)}")
    click.echo("-" * 40)
    
    try:
        # We must run inside the demo dir for relative paths in the demo scripts to work usually
        subprocess.run(cmd, cwd=str(demo_path), check=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"\n❌ Demo failed with exit code {e.returncode}")
    except Exception as e:
        click.echo(f"\n❌ Error running demo: {e}")
    
    click.echo("-" * 40)
    click.echo(f"📖 Read more in: {info['readme']}")

