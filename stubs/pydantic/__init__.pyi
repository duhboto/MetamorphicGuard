"""Type stubs for pydantic library."""

from typing import Any, Callable, Dict, List, Literal, Optional, Set, TypeVar, Union
from typing_extensions import Self

T = TypeVar("T")

class ConfigDict(dict):
    """Pydantic configuration dictionary."""
    def __init__(self, **kwargs: Any) -> None:
        ...

class FieldInfo:
    """Field information for Pydantic models."""
    def __init__(
        self,
        default: Any = ...,
        *,
        alias: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        gt: Optional[float] = None,
        ge: Optional[float] = None,
        lt: Optional[float] = None,
        le: Optional[float] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        pattern: Optional[str] = None,
        default_factory: Optional[Callable[[], Any]] = None,
        **kwargs: Any,
    ) -> None:
        ...

def Field(
    default: Any = ...,
    *,
    alias: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    gt: Optional[float] = None,
    ge: Optional[float] = None,
    lt: Optional[float] = None,
    le: Optional[float] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    pattern: Optional[str] = None,
    default_factory: Optional[Callable[[], Any]] = None,
    **kwargs: Any,
) -> Any:
    """Create a field for a Pydantic model."""
    ...

class ValidationError(ValueError):
    """Raised when Pydantic validation fails."""
    errors: List[Dict[str, Any]]
    
    def __init__(self, errors: List[Dict[str, Any]], model: Any) -> None:
        ...

class BaseModel:
    """Base class for Pydantic models."""
    
    model_config: ConfigDict = ...
    
    def __init__(self, **data: Any) -> None:
        """Initialize model from keyword arguments."""
        ...
    
    @classmethod
    def model_validate(cls, obj: Any) -> Self:
        """Validate and create model instance from dict or object."""
        ...
    
    def model_dump(self, *, mode: Literal["json", "python"] = "python", **kwargs: Any) -> Dict[str, Any]:
        """Convert model to dictionary."""
        ...
    
    def model_dump_json(self, **kwargs: Any) -> str:
        """Convert model to JSON string."""
        ...

def field_validator(
    field: Union[str, List[str]],
    *,
    mode: Literal["before", "after", "wrap"] = "after",
    check_fields: Optional[bool] = None,
) -> Callable[[Callable[..., Any]], Any]:
    """Decorator for field validation."""
    ...


