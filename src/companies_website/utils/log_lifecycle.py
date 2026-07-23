import functools


def log_lifecycle():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            tag = type(self).__name__
            log = self.logger
            arg_str = ", ".join(
                [repr(a)[:100] for a in args] + [f"{k}={repr(v)[:100]}" for k, v in kwargs.items()]
            )
            log.info(f"[{tag}] -> {func.__name__}({arg_str})")
            try:
                result = func(self, *args, **kwargs)
            except Exception:
                log.info(f"[{tag}] X {func.__name__} raised exception")
                raise
            log.info(f"[{tag}] <- {func.__name__} -> {repr(result)[:200]}")
            return result

        return wrapper

    return decorator
