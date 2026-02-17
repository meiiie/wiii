"""
Singleton utilities for reducing boilerplate across services and engine components.

Replaces the repetitive pattern:
    _instance: Optional[MyClass] = None
    def get_my_class() -> MyClass:
        global _instance
        if _instance is None:
            _instance = MyClass()
        return _instance

With:
    get_my_class = singleton_factory(MyClass)
"""

from typing import TypeVar, Callable, Optional

T = TypeVar("T")


def singleton_factory(cls: type[T], *args, **kwargs) -> Callable[..., T]:
    """
    Create a singleton factory function for a class.

    Returns a callable that always returns the same instance.
    First call creates the instance, subsequent calls return it.

    Usage:
        get_session_manager = singleton_factory(SessionManager)

        # With default args:
        get_cache = singleton_factory(CacheManager, max_size=1000)
    """
    instance: Optional[T] = None

    def get_instance() -> T:
        nonlocal instance
        if instance is None:
            instance = cls(*args, **kwargs)
        return instance

    get_instance.__name__ = f"get_{cls.__name__.lower()}"
    get_instance.__doc__ = f"Get or create {cls.__name__} singleton."
    return get_instance
