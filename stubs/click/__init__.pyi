"""Type stubs for click library."""

from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple, TypeVar, Union
from typing_extensions import ParamSpec

P = ParamSpec("P")
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

class Context:
    """Click context object."""
    pass

class BaseCommand:
    """Base command class."""
    name: Optional[str] = None
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the command."""
        ...

class Command(BaseCommand):
    """Click command decorator."""
    def __init__(self, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        ...
    def add_command(self, cmd: BaseCommand, name: Optional[str] = None) -> None:
        """Add a subcommand."""
        ...

class Group(BaseCommand):
    """Click group for organizing commands."""
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        ...
    def command(self, *args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Command]:
        """Decorator to register a command."""
        ...
    def add_command(self, cmd: BaseCommand, name: Optional[str] = None) -> None:
        """Add a subcommand."""
        ...
    def parse_args(self, ctx: Context, args: List[str]) -> List[str]:
        """Parse command line arguments."""
        ...

class Choice:
    """Type for click.Choice parameter type."""
    def __init__(self, choices: Sequence[str], case_sensitive: bool = True) -> None:
        ...

class Path:
    """Type for click.Path parameter type."""
    def __init__(
        self,
        exists: bool = False,
        file_okay: bool = True,
        dir_okay: bool = True,
        writable: bool = False,
        readable: bool = True,
        resolve_path: bool = False,
        allow_dash: bool = False,
        path_type: Optional[type] = None,
    ) -> None:
        ...

class ClickException(Exception):
    """Base exception for Click."""
    def __init__(self, message: str) -> None:
        ...

def command(name: Optional[str] = None, cls: Optional[type[Command]] = None, **attrs: Any) -> Callable[[Callable[..., Any]], Command]:
    """Decorator to create a command."""
    ...

def group(name: Optional[str] = None, cls: Optional[type[Group]] = None, **attrs: Any) -> Callable[[Callable[..., Any]], Group]:
    """Decorator to create a command group."""
    ...

def option(*param_decls: str, cls: Optional[type] = None, **attrs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to add an option to a command."""
    ...

def argument(*param_decls: str, cls: Optional[type] = None, **attrs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to add an argument to a command."""
    ...

def echo(message: Any = None, file: Any = None, nl: bool = True, err: bool = False, color: Optional[bool] = None) -> None:
    """Print a message."""
    ...

def confirm(text: str, default: bool = False, abort: bool = False, prompt_suffix: str = ": ", show_default: bool = True, err: bool = False) -> bool:
    """Prompt for confirmation."""
    ...

def prompt(text: str, default: Any = None, hide_input: bool = False, confirmation_prompt: bool = False, type: Any = None, value_proc: Optional[Callable[[str], Any]] = None, prompt_suffix: str = ": ", show_default: bool = True, err: bool = False, show_choices: bool = True) -> str:
    """Prompt for input."""
    ...


