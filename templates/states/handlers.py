"""What every event handler that calls the service has in common.

``toast_errors`` goes *under* the event decorator::

    @share_owner_event
    async def publish(self): ...

The service refuses with an exception whose message is written for the user
(``PermissionDeniedError``, ``DomainError``, ...). A handler lets it rise;
this decorator turns it into the error toast. A handler writes its own
``try/except`` for these only when it has something to restore first, and
says what in a comment.

``call`` is how a state reaches the service: with a session of its own, in a
worker thread.
"""

import functools
import inspect
from collections.abc import Callable
from typing import Any, cast

from .. import service
from ..auth.service import AdminActionError
from ..components.toast import notify_error
from ..utils.casting import InvalidInput
from ..utils.db import call, in_session
from ..utils.logging import get_logger

log = get_logger(__name__)

# Refusals whose message is safe to show as it is.
REFUSALS: tuple[type[Exception], ...] = (
    service.PermissionDeniedError,
    service.DomainError,
    AdminActionError,
    InvalidInput,
)


# Set on a wrapped handler, so a test can tell which ones are covered.
TOAST_ATTR = "_toasts_refusals"


def _refused(handler: str, error: Exception) -> Any:
    # Logged: a toast is quiet, and a refusal nobody expected is a bug report.
    log.info("handler.refused", handler=handler, error=type(error).__name__)
    return notify_error(str(error))


def toast_errors[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Show a refused action as an error toast instead of raising.

    For plain and ``async`` handlers, background tasks included. Anything
    that is not a refusal propagates. The wrapper keeps the signature, which
    Reflex reads to bind the event's arguments.
    """
    name = fn.__qualname__
    if inspect.isasyncgenfunction(fn) or inspect.isgeneratorfunction(fn):
        raise TypeError(f"{name}: toast_errors does not wrap generator handlers")

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def run_async(*args: P.args, **kwargs: P.kwargs) -> Any:
            try:
                return await fn(*args, **kwargs)
            except REFUSALS as error:
                return _refused(name, error)

        setattr(run_async, TOAST_ATTR, True)
        return cast(Callable[P, R], run_async)

    @functools.wraps(fn)
    def run(*args: P.args, **kwargs: P.kwargs) -> Any:
        try:
            return fn(*args, **kwargs)
        except REFUSALS as error:
            return _refused(name, error)

    setattr(run, TOAST_ATTR, True)
    return cast(Callable[P, R], run)


__all__ = ["REFUSALS", "TOAST_ATTR", "call", "in_session", "toast_errors"]
