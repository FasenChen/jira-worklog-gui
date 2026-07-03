"""
Shared decorators for connection management.
"""
from functools import wraps


def require_connection(error_class, message="未连接到服务器"):
    """Factory: returns a decorator that checks self.is_connected."""

    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            if not self.is_connected:
                raise error_class(message)
            return method(self, *args, **kwargs)

        return wrapper

    return decorator