"""The one place the app opens a database session.

Everything else hands a function to ``call`` (from an event handler) or
``in_session`` (from code already running in a worker thread). The function
gets the session as its first argument and is, with two exceptions, a use
case from the ``service`` package that takes the acting user's id and checks what
that user may do. The exceptions are the auth package's own tables
(``auth/service.py``, ``auth/directory.py``).

``tests/test_architecture.py`` keeps it that way.
"""

import asyncio
from collections.abc import Callable
from typing import Concatenate

import reflex as rx
from sqlmodel import Session


def in_session[**P, T](
    fn: Callable[Concatenate[Session, P], T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """``fn(db, ...)`` with a session of its own, in this thread. For code
    that already runs off the event loop; handlers use ``call``."""
    with rx.session() as db:
        return fn(db, *args, **kwargs)


async def call[**P, T](
    fn: Callable[Concatenate[Session, P], T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """Run a service function with a session of its own, off the event loop.

    ``rows = await call(service.group_list, me)`` — the function gets the
    session as its first argument. States reach the database only this way:
    a query never blocks the other sockets, and the session never outlives
    the call, so what comes back must be plain data or fully loaded rows.
    Refusals rise through it to ``toast_errors`` like from any other call.
    """
    return await asyncio.to_thread(lambda: in_session(fn, *args, **kwargs))
