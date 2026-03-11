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

The returned getter also exposes two helper methods:
    get_my_class.reset()              # set instance to None (useful in tests)
    get_my_class.init(*args, **kwargs) # force-create with specific args
"""

from typing import TypeVar, Callable, Optional

T = TypeVar("T")


def singleton_factory(cls: type[T], *default_args, **default_kwargs) -> Callable[[], T]:
    """
    Create a singleton factory function for a class.

    Returns a callable that always returns the same instance.
    First call creates the instance, subsequent calls return it.

    The returned callable has two extra attributes:
        .reset()               — sets the internal instance to None so the next
                                 call to the getter recreates it (useful in tests).
        .init(*args, **kwargs) — creates (or recreates) the instance with the
                                 given arguments and stores it as the singleton.

    Usage:
        get_session_manager = singleton_factory(SessionManager)

        # With default args baked in:
        get_cache = singleton_factory(CacheManager, max_size=1000)

        # Reset in tests:
        get_session_manager.reset()

        # Force-create with custom args:
        get_cache.init(max_size=500)
    """
    instance: Optional[T] = None

    def get_instance() -> T:
        nonlocal instance
        if instance is None:
            instance = cls(*default_args, **default_kwargs)
        return instance

    def reset() -> None:
        """Set the singleton instance to None so the next call recreates it."""
        nonlocal instance
        instance = None

    def init(*args, **kwargs) -> T:
        """Create (or replace) the singleton instance with the given arguments."""
        nonlocal instance
        instance = cls(*args, **kwargs)
        return instance

    get_instance.__name__ = f"get_{cls.__name__.lower()}"
    get_instance.__doc__ = f"Get or create {cls.__name__} singleton."
    get_instance.reset = reset  # type: ignore[attr-defined]
    get_instance.init = init    # type: ignore[attr-defined]
    return get_instance
