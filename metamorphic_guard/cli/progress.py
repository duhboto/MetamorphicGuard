"""
Progress indicators and enhanced error messages for CLI.
"""

from __future__ import annotations

import sys
import time
from typing import Any, Callable, Optional

import click


class ProgressBar:
    """Simple progress bar for long-running operations."""

    def __init__(
        self,
        total: int,
        label: str = "Progress",
        width: int = 40,
        show_percent: bool = True,
        show_eta: bool = True,
    ) -> None:
        self.total = total
        self.current = 0
        self.label = label
        self.width = width
        self.show_percent = show_percent
        self.show_eta = show_eta
        self.start_time = time.monotonic()
        self.last_update = 0.0

    def update(self, n: int = 1) -> None:
        """Update progress by n steps."""
        self.current = min(self.current + n, self.total)
        self._render()

    def _render(self) -> None:
        """Render progress bar."""
        now = time.monotonic()
        # Throttle updates to max 10 Hz
        if now - self.last_update < 0.1:
            return
        self.last_update = now

        if self.total == 0:
            percent = 0.0
            filled = 0
        else:
            percent = self.current / self.total
            filled = int(self.width * percent)

        bar = "█" * filled + "░" * (self.width - filled)

        parts = [f"{self.label}: [{bar}]"]
        if self.show_percent:
            parts.append(f"{percent:.1%}")
        if self.show_eta and self.current > 0 and self.current < self.total:
            elapsed = now - self.start_time
            rate = self.current / elapsed if elapsed > 0 else 0
            remaining = (self.total - self.current) / rate if rate > 0 else 0
            parts.append(f"ETA: {remaining:.1f}s")

        click.echo("\r" + " ".join(parts), nl=False)
        sys.stdout.flush()

    def finish(self) -> None:
        """Finish and print newline."""
        self.current = self.total
        self._render()
        click.echo()  # Newline


class Spinner:
    """Simple spinner for indeterminate progress."""

    def __init__(self, message: str = "Processing", frames: list[str] | None = None) -> None:
        self.message = message
        self.frames = frames or ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.frame_index = 0
        self.running = False

    def start(self) -> None:
        """Start spinner."""
        self.running = True
        self._spin()

    def stop(self) -> None:
        """Stop spinner."""
        self.running = False
        click.echo("\r" + " " * (len(self.message) + 10) + "\r", nl=False)
        sys.stdout.flush()

    def _spin(self) -> None:
        """Update spinner frame."""
        if not self.running:
            return

        frame = self.frames[self.frame_index % len(self.frames)]
        click.echo(f"\r{frame} {self.message}", nl=False)
        sys.stdout.flush()

        self.frame_index += 1
        time.sleep(0.1)
        if self.running:
            self._spin()


def format_error_message(error: Exception, context: Optional[dict[str, Any]] = None) -> str:
    """
    Format error message with helpful context and suggestions.
    
    Args:
        error: The exception that occurred
        context: Optional context dictionary
    
    Returns:
        Formatted error message with suggestions
    """
    error_type = type(error).__name__
    error_msg = str(error)

    lines = [
        f"❌ Error: {error_type}",
        f"   {error_msg}",
    ]

    # Add context if provided
    if context:
        lines.append("\nContext:")
        for key, value in context.items():
            lines.append(f"   {key}: {value}")

    # Add suggestions based on error type
    suggestions = _get_error_suggestions(error_type, error_msg)
    if suggestions:
        lines.append("\n💡 Suggestions:")
        for suggestion in suggestions:
            lines.append(f"   • {suggestion}")

    return "\n".join(lines)


def _get_error_suggestions(error_type: str, error_msg: str) -> list[str]:
    """Get suggestions based on error type and message."""
    suggestions = []

    if "ImportError" in error_type or "ModuleNotFoundError" in error_type:
        if "boto3" in error_msg:
            suggestions.append("Install boto3: pip install boto3")
        elif "pika" in error_msg:
            suggestions.append("Install pika: pip install pika")
        elif "kafka" in error_msg:
            suggestions.append("Install kafka-python: pip install kafka-python")
        elif "redis" in error_msg:
            suggestions.append("Install redis: pip install redis")
        else:
            suggestions.append("Check that all required dependencies are installed")
            suggestions.append("Run: pip install -r requirements.txt")

    elif "FileNotFoundError" in error_type:
        suggestions.append("Check that the file path is correct")
        suggestions.append("Use absolute paths if relative paths fail")

    elif "ValueError" in error_type:
        if "queue backend" in error_msg.lower():
            suggestions.append("Available backends: memory, redis, sqs, rabbitmq, kafka")
            suggestions.append("Check queue-config JSON syntax")
        elif "task" in error_msg.lower() and "not found" in error_msg.lower():
            suggestions.append("List available tasks: metamorphic-guard plugin list")
            suggestions.append("Register your task with @task decorator")

    elif "BudgetExceededError" in error_type:
        suggestions.append("Increase --budget-limit or reduce --n")
        suggestions.append("Use --budget-action warn to continue with warning")
        suggestions.append("Check model pricing: metamorphic-guard model pricing")

    elif "TimeoutError" in error_type:
        suggestions.append("Increase --timeout-s for slower implementations")
        suggestions.append("Check for infinite loops or blocking operations")

    elif "ConnectionError" in error_type or "ConnectionRefusedError" in error_type:
        if "redis" in error_msg.lower():
            suggestions.append("Start Redis: docker run -p 6379:6379 redis")
            suggestions.append("Check Redis URL in queue-config")
        elif "rabbitmq" in error_msg.lower():
            suggestions.append("Start RabbitMQ: docker run -p 5672:5672 rabbitmq")
            suggestions.append("Check RabbitMQ connection settings")

    return suggestions


def echo_success(message: str) -> None:
    """Print success message."""
    click.echo(f"✅ {message}")


def echo_warning(message: str) -> None:
    """Print warning message."""
    click.echo(f"⚠️  {message}", err=True)


def echo_error(message: str, error: Optional[Exception] = None) -> None:
    """Print error message with optional exception details."""
    click.echo(f"❌ {message}", err=True)
    if error:
        formatted = format_error_message(error)
        click.echo(formatted, err=True)


def echo_info(message: str) -> None:
    """Print info message."""
    click.echo(f"ℹ️  {message}")

