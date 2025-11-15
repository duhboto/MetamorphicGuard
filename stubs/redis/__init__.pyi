"""Type stubs for redis library (optional dependency)."""

from typing import Any, BinaryIO, Callable, Dict, Iterator, List, Optional, Protocol, Tuple, Union
from typing_extensions import Self

class WatchError(Exception):
    """Raised when a watched key changes during a transaction."""
    pass

class Pipeline:
    """Redis pipeline for batching commands."""
    
    def __enter__(self) -> Self:
        """Enter pipeline context."""
        ...
    
    def __exit__(self, exc_type: Optional[type[BaseException]], exc_val: Optional[BaseException], exc_tb: Any) -> None:
        """Exit pipeline context."""
        ...
    
    def watch(self, *keys: str) -> None:
        """Watch keys for changes."""
        ...
    
    def multi(self) -> None:
        """Start a transaction."""
        ...
    
    def hget(self, name: str, key: str) -> Optional[bytes]:
        """Get a hash field value."""
        ...
    
    def hdel(self, name: str, *keys: str) -> int:
        """Delete one or more hash fields."""
        ...
    
    def execute(self) -> List[Any]:
        """Execute all commands in the pipeline."""
        ...

class Redis:
    """Redis client for interacting with Redis server."""
    
    WatchError: type[WatchError] = WatchError
    
    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> "Redis":
        """Create a Redis client from a URL."""
        ...
    
    def rpush(self, name: str, *values: Union[str, bytes]) -> int:
        """Append one or more values to the end of a list."""
        ...
    
    def blpop(self, keys: Union[str, Tuple[str, ...]], timeout: int = 0) -> Optional[Tuple[bytes, bytes]]:
        """Blocking left pop from a list."""
        ...
    
    def hset(self, name: str, key: Optional[str] = None, value: Optional[Union[str, bytes, int, float]] = None, mapping: Optional[Dict[str, Union[str, bytes, int, float]]] = None) -> int:
        """Set hash field(s)."""
        ...
    
    def hget(self, name: str, key: str) -> Optional[bytes]:
        """Get a hash field value."""
        ...
    
    def hgetall(self, name: str) -> Dict[bytes, bytes]:
        """Get all hash fields and values."""
        ...
    
    def hdel(self, name: str, *keys: str) -> int:
        """Delete one or more hash fields."""
        ...
    
    def pipeline(self, transaction: bool = True, shard_hint: Optional[str] = None) -> Pipeline:
        """Return a new pipeline object."""
        ...
    
    def set(self, name: str, value: Union[str, bytes], ex: Optional[int] = None, px: Optional[int] = None, nx: bool = False, xx: bool = False) -> bool:
        """Set a key's value."""
        ...
    
    def llen(self, name: str) -> int:
        """Get the length of a list."""
        ...


